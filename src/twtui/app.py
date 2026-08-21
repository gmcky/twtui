"""Application: stream launch + main input loop."""

import threading
import time

from rich.live import Live

from twtui.api import (
    OFFLINE,
    channel_videos,
    game_streams,
    get_status,
    search_games,
    top_games,
    twitch_search,
)
from twtui.config import (
    BUNDLE_KEYS,
    FEATURES_LOCKED,
    SETTINGS,
    SETTINGS_SCHEMA,
    apply_preset,
    clip_target,
    load_channels,
    load_config,
    rebuild_keybinds,
    rebuild_theme,
    save_channels,
    save_config,
    set_run_on_startup,
    sync_preset_from_settings,
    vod_target,
)
from twtui.keymap import SPECIAL, action_of, fold
from twtui.keys import read_key, term_restore, term_setup
from twtui.streams import (
    LAUNCH_GRACE,
    cleanup_on_start,
    install_exit_handlers,
    launch,
    live_channels,
    open_recording,
    stream_alive,
    sync_state,
)
from twtui.ui import (
    _filter_streams,
    console,
    loading_panel,
    render,
    render_cat,
    render_cats,
    render_channel,
    render_confirm,
    render_search,
    render_settings,
)


def sort_channels(channels, status):
    channels.sort(
        key=lambda c: (
            not (status.get(c) or OFFLINE)["live"],
            -(status.get(c) or OFFLINE)["viewers"],
        )
    )


def main():
    load_config()
    install_exit_handlers()
    still_open = cleanup_on_start()
    channels = load_channels()  # may be empty on a fresh install — that's fine,
    # follow channels from the search view (tab / →)

    status = {ch: False for ch in channels}
    opened = set(still_open)  # streams from a previous session, still running
    followed = {c.lower() for c in channels}  # lowercased logins, kept in sync
    selected = 0

    # Shared state for the search modes + worker thread.
    st = {
        "mode": "list",  # "list" | "search" | "cats" | "cat" | "settings"
        "query": "",  # channel search
        "set_section": 0,
        "set_sel": 0,
        "set_editing": False,
        "set_buf": "",
        "set_capturing": False,
        "set_picking": False,
        "pick_sel": 0,
        "results": [],
        "sel": 0,
        "gen": 0,  # bumped on every keystroke; stale replies are dropped
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
        "ch_login": "",
        "ch_display": "",
        "ch_videos": [],
        "ch_query": "",
        "ch_sel": 0,
        "ch_searching": False,
        "ch_back": "list",
        "stop": False,
        "confirm_quit": False,
        "failed": {},
    }
    lock = threading.Lock()
    typed = threading.Event()

    with Live(
        loading_panel(), console=console, screen=True, auto_refresh=True, refresh_per_second=12
    ) as live:
        # The quit-confirm modal must stay on top: background workers keep
        # painting the underlying view, so every painter yields to it here.
        def paint_list():
            if st.get("confirm_quit"):
                return
            live.update(
                render(channels, status, selected, False, opened, st["failed"]), refresh=True
            )

        def paint_settings():
            if st.get("confirm_quit"):
                return
            live.update(render_settings(st), refresh=True)

        def paint_search():
            if st.get("confirm_quit"):
                return
            live.update(render_search(st, opened, followed), refresh=True)

        def paint_cats():
            if st.get("confirm_quit"):
                return
            live.update(render_cats(st), refresh=True)

        def paint_cat():
            if st.get("confirm_quit"):
                return
            live.update(render_cat(st, opened, followed), refresh=True)

        def paint_channel():
            if st.get("confirm_quit"):
                return
            live.update(render_channel(st), refresh=True)

        def open_channel(login, display, back_mode):
            st["mode"] = "channel"
            st["ch_login"] = login
            st["ch_display"] = display
            st["ch_back"] = back_mode
            with lock:
                st["ch_query"], st["ch_videos"], st["ch_sel"] = "", [], 0
                st["ch_searching"] = True
            paint_channel()

            def _load():
                vids = channel_videos(login)
                with lock:
                    if st["ch_login"] == login:
                        st["ch_videos"] = vids
                        st["ch_searching"] = False
                if st["mode"] == "channel" and st["ch_login"] == login:
                    paint_channel()

            threading.Thread(target=_load, daemon=True).start()

        def watch_launch(ch, entry):
            time.sleep(LAUNCH_GRACE)
            if st["stop"]:
                return
            if not stream_alive(entry):
                with lock:
                    opened.discard(ch)
                    st["failed"][ch] = time.time()
                m = st["mode"]
                if m == "list":
                    paint_list()
                elif m == "search":
                    paint_search()
                elif m == "cat":
                    paint_cat()

        def do_launch(ch, repaint):
            entry = launch(ch)
            opened.add(ch)
            st["failed"].pop(ch, None)
            repaint()
            threading.Thread(target=watch_launch, args=(ch, entry), daemon=True).start()

        def request_quit():
            if SETTINGS.get("confirm_before_quit") and opened:
                st["confirm_quit"] = True
                live.update(render_confirm(len(opened)), refresh=True)
            else:
                st["stop"] = True
                typed.set()

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
                time.sleep(0.22)  # coalesce fast typing
                if typed.is_set():
                    continue  # more keys arrived; reprocess
                with lock:
                    gen, mode = st["gen"], st["mode"]
                    q = st["cat_query"] if mode == "cats" else st["query"]

                if mode == "cats":
                    with lock:
                        st["cat_searching"] = True
                    if st["mode"] == "cats":
                        paint_cats()
                    res = (
                        search_games(q, SETTINGS["category_rows"])
                        if q.strip()
                        else top_games(SETTINGS["category_rows"])
                    )
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
                res = twitch_search(q, SETTINGS["search_results"])
                with lock:
                    if gen != st["gen"]:  # a newer query is pending; drop this
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
                    now = time.time()
                    alive = live_channels()
                    with lock:
                        # Drop the "open" tag for streams whose process died
                        # (e.g. player closed by hand), not just grace failures.
                        stale = opened - alive
                        opened.difference_update(stale)
                        for c in [c for c, ts in st["failed"].items() if now - ts > 6]:
                            del st["failed"][c]
                    if stale:
                        m = st["mode"]
                        if m == "list":
                            paint_list()
                        elif m == "search":
                            paint_search()
                        elif m == "cat":
                            paint_cat()

        sync_th = threading.Thread(target=sync_worker, daemon=True)
        sync_th.start()

        def autorefresh_worker():
            nonlocal selected
            while not st["stop"]:
                secs = SETTINGS["list_autorefresh_secs"]
                if secs <= 0:
                    time.sleep(1)
                    continue
                for _ in range(int(secs * 10)):
                    if st["stop"] or SETTINGS["list_autorefresh_secs"] != secs:
                        break
                    time.sleep(0.1)
                if st["stop"]:
                    break
                if st["mode"] != "list":
                    continue
                new_status = get_status(channels)
                with lock:
                    cur = channels[selected] if 0 <= selected < len(channels) else None
                    status.clear()
                    status.update(new_status)
                    sort_channels(channels, status)
                    if cur is not None and cur in channels:
                        selected = channels.index(cur)
                    else:
                        selected = min(selected, max(len(channels) - 1, 0))
                if st["mode"] == "list":
                    paint_list()

        ar_th = threading.Thread(target=autorefresh_worker, daemon=True)
        ar_th.start()

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
                    "live": res["live"],
                    "viewers": res["viewers"],
                    "game": res["game"],
                    "display": res["display"],
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

                if st.get("confirm_quit"):
                    k = fold(tok)  # layout-agnostic y/n
                    if tok == "ENTER" or k == "y":
                        st["stop"] = True
                        typed.set()
                        break
                    elif tok == "ESC" or k == "n":
                        st["confirm_quit"] = False
                        mode = st["mode"]
                        if mode == "list":
                            paint_list()
                        elif mode == "search":
                            paint_search()
                        elif mode == "cats":
                            paint_cats()
                        elif mode == "cat":
                            paint_cat()
                        elif mode == "channel":
                            paint_channel()
                        elif mode == "settings":
                            paint_settings()
                    continue

                mode = st["mode"]
                char = tok if tok not in SPECIAL else None

                if tok == "CTRL_Q":
                    request_quit()
                    if st["stop"]:
                        break
                    continue

                if mode == "settings":
                    if st.get("set_picking"):
                        fields = SETTINGS_SCHEMA[st["set_section"]][1]
                        f = fields[st["set_sel"]]
                        opts = f["choices"]
                        if tok == "UP":
                            st["pick_sel"] = (st["pick_sel"] - 1) % len(opts)
                            paint_settings()
                        elif tok == "DOWN":
                            st["pick_sel"] = (st["pick_sel"] + 1) % len(opts)
                            paint_settings()
                        elif tok == "ENTER":
                            if f["type"] == "preset":
                                apply_preset(opts[st["pick_sel"]])
                            else:
                                SETTINGS[f["key"]] = opts[st["pick_sel"]]
                                if f["key"] in BUNDLE_KEYS:
                                    sync_preset_from_settings()
                            save_config()
                            rebuild_theme()
                            rebuild_keybinds()
                            st["set_picking"] = False
                            paint_settings()
                        elif tok == "ESC":
                            st["set_picking"] = False
                            paint_settings()
                        continue

                    if st.get("set_capturing"):
                        if tok == "ESC":
                            st["set_capturing"] = False
                            paint_settings()
                            continue
                        if tok in SPECIAL or char is None or len(char) != 1:
                            continue
                        norm_char = fold(char)
                        used = {SETTINGS[k] for k in SETTINGS if k.startswith("key_")}
                        if norm_char in used:
                            continue

                        fields = SETTINGS_SCHEMA[st["set_section"]][1]
                        key = fields[st["set_sel"]]["key"]
                        SETTINGS[key] = norm_char
                        save_config()
                        rebuild_theme()
                        rebuild_keybinds()
                        st["set_capturing"] = False
                        paint_settings()
                        continue

                    if st["set_editing"]:
                        if tok == "ENTER":
                            fields = SETTINGS_SCHEMA[st["set_section"]][1]
                            f = fields[st["set_sel"]]
                            key = f["key"]
                            if f["type"] == "int":
                                try:
                                    val = int(st["set_buf"])
                                except ValueError:
                                    val = SETTINGS[key]
                                SETTINGS[key] = max(f["min"], min(f["max"], val))
                            else:
                                SETTINGS[key] = st["set_buf"]
                            if key in BUNDLE_KEYS:
                                sync_preset_from_settings()
                            save_config()
                            rebuild_theme()
                            rebuild_keybinds()
                            st["set_editing"] = False
                            paint_settings()
                        elif tok == "ESC":
                            st["set_editing"] = False
                            paint_settings()
                        elif tok == "BACKSPACE":
                            st["set_buf"] = st["set_buf"][:-1]
                            paint_settings()
                        elif char is not None:
                            fields = SETTINGS_SCHEMA[st["set_section"]][1]
                            if fields[st["set_sel"]]["type"] == "int":
                                if char.isdigit():
                                    st["set_buf"] += char
                                    paint_settings()
                            else:
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
                            if key in BUNDLE_KEYS:
                                sync_preset_from_settings()
                            save_config()
                            if key == "run_on_startup":
                                set_run_on_startup(SETTINGS[key])
                            rebuild_theme()
                            rebuild_keybinds()
                            paint_settings()
                        elif f["type"] in ("choice", "color", "preset"):
                            opts = f["choices"]
                            st["pick_sel"] = (
                                opts.index(SETTINGS[key]) if SETTINGS[key] in opts else 0
                            )
                            st["set_picking"] = True
                            paint_settings()
                        elif f["type"] == "text":
                            st["set_editing"] = True
                            st["set_buf"] = SETTINGS[key]
                            paint_settings()
                        elif f["type"] == "int" and tok == "ENTER":
                            st["set_editing"] = True
                            st["set_buf"] = str(SETTINGS[key])
                            paint_settings()
                        elif f["type"] == "key" and tok == "ENTER":
                            st["set_capturing"] = True
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
                    elif mode == "cat":
                        n = len(_filter_streams(st["cat_streams"], st["cat_ch_query"]))
                        if n:
                            st["cat_ch_sel"] = (st["cat_ch_sel"] + delta) % n
                        paint_cat()
                    elif mode == "channel":
                        vids = st["ch_videos"]
                        filtered = [
                            v for v in vids if st["ch_query"].strip().lower() in v["title"].lower()
                        ]
                        if filtered:
                            st["ch_sel"] = (st["ch_sel"] + delta) % len(filtered)
                        paint_channel()
                    continue

                if tok in ("LEFT", "RIGHT"):  # switch streamers/categories
                    if mode == "search":
                        open_categories()
                    elif mode == "cats":
                        st["mode"] = "search"
                        paint_search()
                    continue

                if tok == "TAB":  # toggle list <-> search
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
                            paint_cat()  # loading spinner
                            streams = game_streams(g["name"], SETTINGS["streams_per_category"])
                            with lock:
                                st["cat_streams"], st["cat_searching"], st["cat_ch_sel"] = (
                                    streams,
                                    False,
                                    0,
                                )
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
                            do_launch(res["login"], paint_cat)
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

                if mode == "channel":
                    vids = st["ch_videos"]
                    filtered = [
                        v for v in vids if st["ch_query"].strip().lower() in v["title"].lower()
                    ]
                    if tok == "ENTER":
                        res = filtered[st["ch_sel"]] if filtered else None
                        if res:
                            do_launch(f"videos/{res['id']}", paint_channel)
                    elif tok == "ESC":
                        st["mode"] = st["ch_back"]
                        if st["mode"] == "list":
                            paint_list()
                        elif st["mode"] == "search":
                            paint_search()
                    elif tok == "BACKSPACE":
                        st["ch_query"] = st["ch_query"][:-1]
                        st["ch_sel"] = 0
                        paint_channel()
                    elif char is not None:
                        st["ch_query"] += char
                        st["ch_sel"] = 0
                        paint_channel()
                    continue

                if tok == "CTRL_V" and not FEATURES_LOCKED:
                    if mode == "list" and channels:
                        ch = channels[selected]
                        meta = status.get(ch) or OFFLINE
                        disp = meta.get("display", ch)
                        open_channel(ch, disp, "list")
                    elif mode == "search":
                        with lock:
                            res = st["results"][st["sel"]] if st["results"] else None
                        if res:
                            open_channel(res["login"], res["display"], "search")
                    continue

                if mode == "search":
                    if tok == "ENTER":
                        vt = None if FEATURES_LOCKED else vod_target(st["query"])
                        ct = clip_target(st["query"]) if not vt else None
                        if vt:
                            do_launch(vt, paint_search)
                        elif ct:
                            do_launch(ct, paint_search)
                        else:
                            with lock:
                                res = st["results"][st["sel"]] if st["results"] else None
                            if res:
                                do_launch(res["login"], paint_search)
                    elif tok == "CTRL_F":
                        with lock:
                            res = st["results"][st["sel"]] if st["results"] else None
                        if res:
                            follow_toggle(res)
                            paint_search()
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
                        do_launch(channels[selected], paint_list)
                elif tok == "ESC":
                    request_quit()
                    if st["stop"]:
                        break
                else:
                    hot = action_of(char)
                    if hot == "f":  # unfollow selected channel
                        if channels:
                            removed = channels.pop(selected)
                            followed.discard(removed.lower())
                            status.pop(removed, None)
                            save_channels(channels)
                            if selected >= len(channels):
                                selected = max(len(channels) - 1, 0)
                            paint_list()
                    elif hot == "/":  # jump straight into search
                        st["mode"] = "search"
                        paint_search()
                    elif hot == "s":  # settings
                        st["mode"] = "settings"
                        st["set_section"] = 0
                        st["set_sel"] = 0
                        st["set_editing"] = False
                        paint_settings()
                    elif hot == "r":
                        live.auto_refresh = True
                        live.update(loading_panel(), refresh=True)
                        new_status = get_status(channels)
                        with lock:
                            status.clear()
                            status.update(new_status)
                            sort_channels(channels, status)
                        selected = 0
                        live.auto_refresh = False
                        paint_list()
                    elif hot == "q":
                        request_quit()
                        if st["stop"]:
                            break
                    elif (
                        not FEATURES_LOCKED and char and char.lower() in ("d", "в")
                    ):  # open recording in 2nd player (seekable)
                        if channels:
                            open_recording(channels[selected])
        finally:
            term_restore(term_state)
