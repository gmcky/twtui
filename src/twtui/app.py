"""Application: stream launch + main input loop."""
import threading
import time

from rich.live import Live

from twtui.api import (
    OFFLINE, get_status, twitch_search, top_games, search_games, game_streams,
)
from twtui.keys import read_key, term_setup, term_restore, _hotkey, SPECIAL
from twtui.config import (
    SETTINGS, SETTINGS_SCHEMA,
    load_config, save_config, load_channels, save_channels,
)
from twtui.ui import (
    console, loading_panel, render, render_search, render_cats, render_cat,
    render_settings, _filter_streams,
)
from twtui.streams import launch, sync_state, install_exit_handlers, cleanup_on_start


def sort_channels(channels, status):
    channels.sort(key=lambda c: (not (status.get(c) or OFFLINE)["live"], -(status.get(c) or OFFLINE)["viewers"]))


def main():
    load_config()
    install_exit_handlers()
    cleanup_on_start()
    channels = load_channels()   # may be empty on a fresh install — that's fine,
                                 # follow channels from the search view (tab / →)

    status = {ch: False for ch in channels}
    opened = set()
    followed = {c.lower() for c in channels}   # lowercased logins, kept in sync
    selected = 0

    # Shared state for the search modes + worker thread.
    st = {
        "mode": "list",      # "list" | "search" | "cats" | "cat" | "settings"
        "query": "",         # channel search
        "set_section": 0,
        "set_sel": 0,
        "set_editing": False,
        "set_buf": "",
        "results": [],
        "sel": 0,
        "gen": 0,            # bumped on every keystroke; stale replies are dropped
        "searching": False,
        # category search ("cats")
        "cat_query": "",
        "cat_results": [],
        "cat_sel": 0,
        "cat_searching": False,
        # inside a category ("cat"): streams loaded once, filtered client-side
        "game_name": "",
        "game_display": "",
        "cat_streams": [],
        "cat_ch_query": "",
        "cat_ch_sel": 0,
        "stop": False,
    }
    lock = threading.Lock()
    typed = threading.Event()

    with Live(loading_panel(), console=console, screen=True, auto_refresh=True, refresh_per_second=12) as live:

        def paint_list():
            live.update(render(channels, status, selected, False, opened), refresh=True)

        def paint_settings():
            live.update(render_settings(st), refresh=True)

        def paint_search():
            live.update(render_search(st, opened, followed), refresh=True)

        def paint_cats():
            live.update(render_cats(st), refresh=True)

        def paint_cat():
            live.update(render_cat(st, opened, followed), refresh=True)

        def search_worker():
            # Debounce keystrokes, query Twitch off-thread, repaint. Serves the two
            # network-backed views: channel search and categories.
            while not st["stop"]:
                typed.wait(timeout=0.5)
                if st["stop"]:
                    return
                if not typed.is_set():
                    continue
                typed.clear()
                time.sleep(0.22)          # coalesce fast typing
                if typed.is_set():
                    continue              # more keys arrived; reprocess
                with lock:
                    gen, mode = st["gen"], st["mode"]
                    q = st["cat_query"] if mode == "cats" else st["query"]

                if mode == "cats":
                    with lock:
                        st["cat_searching"] = True
                    if st["mode"] == "cats":
                        paint_cats()
                    res = search_games(q) if q.strip() else top_games()
                    with lock:
                        if gen != st["gen"]:
                            continue
                        st["cat_results"], st["cat_sel"], st["cat_searching"] = res, 0, False
                    if st["mode"] == "cats":
                        paint_cats()
                    continue

                # channel search
                if not q.strip():
                    with lock:
                        st["results"], st["searching"] = [], False
                    if st["mode"] == "search":
                        paint_search()
                    continue
                with lock:
                    st["searching"] = True
                if st["mode"] == "search":
                    paint_search()
                res = twitch_search(q)
                with lock:
                    if gen != st["gen"]:   # a newer query is pending; drop this
                        continue
                    st["results"], st["sel"], st["searching"] = res, 0, False
                if st["mode"] == "search":
                    paint_search()

        worker = threading.Thread(target=search_worker, daemon=True)
        worker.start()

        def sync_worker():
            while not st["stop"]:
                for _ in range(50):
                    if st["stop"]:
                        break
                    time.sleep(0.1)
                if not st["stop"]:
                    sync_state()

        sync_th = threading.Thread(target=sync_worker, daemon=True)
        sync_th.start()

        status = get_status(channels)
        sort_channels(channels, status)
        live.auto_refresh = False
        paint_list()

        def open_categories():
            # Enter category search; kick the worker to load top games.
            st["mode"] = "cats"
            with lock:
                st["cat_query"], st["cat_results"], st["cat_sel"] = "", [], 0
                st["cat_searching"] = True
                st["gen"] += 1
            typed.set()
            paint_cats()

        def follow_toggle(res):
            # Follow/unfollow, then re-sort so a new live channel joins the live group.
            nonlocal selected
            login = res["login"]
            if login.lower() in followed:
                for c in [c for c in channels if c.lower() == login.lower()]:
                    channels.remove(c)
                    status.pop(c, None)
                followed.discard(login.lower())
            else:
                channels.append(login)
                followed.add(login.lower())
                status[login] = {
                    "live": res["live"], "viewers": res["viewers"],
                    "game": res["game"], "display": res["display"],
                }
            sort_channels(channels, status)
            selected = min(selected, max(len(channels) - 1, 0))
            save_channels(channels)

        term_state = term_setup()
        try:
            while True:
                tok = read_key()
                if tok is None:
                    continue
                mode = st["mode"]
                char = tok if tok not in SPECIAL else None

                if tok == "CTRL_Q":
                    st["stop"] = True
                    typed.set()
                    break

                if mode == "settings":
                    if st["set_editing"]:
                        if tok == "ENTER":
                            fields = SETTINGS_SCHEMA[st["set_section"]][1]
                            key = fields[st["set_sel"]]["key"]
                            SETTINGS[key] = st["set_buf"]
                            save_config()
                            st["set_editing"] = False
                            paint_settings()
                        elif tok == "ESC":
                            st["set_editing"] = False
                            paint_settings()
                        elif tok == "BACKSPACE":
                            st["set_buf"] = st["set_buf"][:-1]
                            paint_settings()
                        elif char is not None:
                            st["set_buf"] += char
                            paint_settings()
                        continue
                    
                    fields = SETTINGS_SCHEMA[st["set_section"]][1]
                    if tok in ("UP", "DOWN"):
                        delta = -1 if tok == "UP" else 1
                        st["set_sel"] = (st["set_sel"] + delta) % len(fields)
                        paint_settings()
                    elif tok in ("LEFT", "RIGHT"):
                        delta = -1 if tok == "LEFT" else 1
                        st["set_section"] = (st["set_section"] + delta) % len(SETTINGS_SCHEMA)
                        st["set_sel"] = 0
                        paint_settings()
                    elif tok == "ENTER" or char == " ":
                        f = fields[st["set_sel"]]
                        key = f["key"]
                        if f["type"] == "bool":
                            SETTINGS[key] = not SETTINGS[key]
                            save_config()
                            paint_settings()
                        elif f["type"] == "choice":
                            opts = f["choices"]
                            idx = opts.index(SETTINGS[key]) if SETTINGS[key] in opts else 0
                            SETTINGS[key] = opts[(idx + 1) % len(opts)]
                            save_config()
                            paint_settings()
                        elif f["type"] == "text":
                            st["set_editing"] = True
                            st["set_buf"] = SETTINGS[key]
                            paint_settings()
                    elif tok == "ESC":
                        st["mode"] = "list"
                        paint_list()
                    continue

                if tok in ("UP", "DOWN"):
                    delta = -1 if tok == "UP" else 1
                    if mode == "list":
                        if channels:
                            selected = (selected + delta) % len(channels)
                        paint_list()
                    elif mode == "search":
                        with lock:
                            if st["results"]:
                                st["sel"] = (st["sel"] + delta) % len(st["results"])
                        paint_search()
                    elif mode == "cats":
                        with lock:
                            if st["cat_results"]:
                                st["cat_sel"] = (st["cat_sel"] + delta) % len(st["cat_results"])
                        paint_cats()
                    else:  # cat
                        n = len(_filter_streams(st["cat_streams"], st["cat_ch_query"]))
                        if n:
                            st["cat_ch_sel"] = (st["cat_ch_sel"] + delta) % n
                        paint_cat()
                    continue

                if tok in ("LEFT", "RIGHT"):     # switch streamers/categories
                    if mode == "search":
                        open_categories()
                    elif mode == "cats":
                        st["mode"] = "search"
                        paint_search()
                    continue

                if tok == "TAB":                 # toggle list <-> search
                    if mode == "list":
                        st["mode"] = "search"
                        paint_search()
                    elif mode == "search":
                        st["mode"] = "list"
                        paint_list()
                    continue


                if mode == "cats":
                    if tok == "ENTER":
                        with lock:
                            g = st["cat_results"][st["cat_sel"]] if st["cat_results"] else None
                        if g:
                            st["game_name"], st["game_display"] = g["name"], g["display"]
                            st["cat_ch_query"], st["cat_ch_sel"] = "", 0
                            st["cat_streams"], st["cat_searching"] = [], True
                            st["mode"] = "cat"
                            paint_cat()                   # loading spinner
                            streams = game_streams(g["name"])
                            with lock:
                                st["cat_streams"], st["cat_searching"], st["cat_ch_sel"] = streams, False, 0
                            paint_cat()
                    elif tok == "ESC":
                        st["mode"] = "search"
                        paint_search()
                    elif tok == "BACKSPACE":
                        with lock:
                            st["cat_query"] = st["cat_query"][:-1]
                            st["gen"] += 1
                        typed.set()
                        paint_cats()
                    elif char is not None:
                        with lock:
                            st["cat_query"] += char
                            st["gen"] += 1
                        typed.set()
                        paint_cats()
                    continue

                if mode == "cat":
                    filtered = _filter_streams(st["cat_streams"], st["cat_ch_query"])
                    if tok == "ENTER":
                        res = filtered[st["cat_ch_sel"]] if filtered else None
                        if res:
                            launch(res["login"])
                            opened.add(res["login"])
                            paint_cat()
                    elif tok == "CTRL_F":
                        res = filtered[st["cat_ch_sel"]] if filtered else None
                        if res:
                            follow_toggle(res)
                            paint_cat()
                    elif tok == "ESC":
                        st["mode"] = "cats"
                        paint_cats()
                    elif tok == "BACKSPACE":
                        st["cat_ch_query"] = st["cat_ch_query"][:-1]
                        st["cat_ch_sel"] = 0
                        paint_cat()
                    elif char is not None:
                        st["cat_ch_query"] += char
                        st["cat_ch_sel"] = 0
                        paint_cat()
                    continue

                if mode == "search":
                    if tok == "ENTER":
                        with lock:
                            res = st["results"][st["sel"]] if st["results"] else None
                        if res:
                            launch(res["login"])
                            opened.add(res["login"])
                            paint_search()
                    elif tok == "CTRL_F":
                        with lock:
                            res = st["results"][st["sel"]] if st["results"] else None
                        if res:
                            follow_toggle(res)
                            paint_search()
                    elif tok == "CTRL_G":
                        open_categories()
                    elif tok == "ESC":
                        st["mode"] = "list"
                        paint_list()
                    elif tok == "BACKSPACE":
                        with lock:
                            st["query"] = st["query"][:-1]
                            st["gen"] += 1
                        typed.set()
                        paint_search()
                    elif char is not None:
                        # Any language: Twitch search matches display names too.
                        with lock:
                            st["query"] += char
                            st["gen"] += 1
                        typed.set()
                        paint_search()
                    continue

                # --- list mode (hotkeys matched by physical key, any layout) ---
                if tok == "ENTER":
                    if channels:
                        launch(channels[selected])
                        opened.add(channels[selected])
                        paint_list()
                elif tok == "CTRL_G":
                    open_categories()
                elif tok == "ESC":
                    st["stop"] = True
                    typed.set()
                    break
                else:
                    hot = _hotkey(char) if char else None
                    if hot == "f":               # unfollow selected channel
                        if channels:
                            removed = channels.pop(selected)
                            followed.discard(removed.lower())
                            status.pop(removed, None)
                            save_channels(channels)
                            if selected >= len(channels):
                                selected = max(len(channels) - 1, 0)
                            paint_list()
                    elif hot == "/":             # jump straight into search
                        st["mode"] = "search"
                        paint_search()
                    elif hot == "s":             # settings
                        st["mode"] = "settings"
                        st["set_section"] = 0
                        st["set_sel"] = 0
                        st["set_editing"] = False
                        paint_settings()
                    elif hot == "r":
                        live.auto_refresh = True
                        live.update(loading_panel(), refresh=True)
                        status = get_status(channels)
                        sort_channels(channels, status)
                        selected = 0
                        live.auto_refresh = False
                        paint_list()
                    elif hot == "q":
                        st["stop"] = True
                        typed.set()
                        break
        finally:
            term_restore(term_state)

