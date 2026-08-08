#!/usr/bin/env python3
"""Arrow-key TUI to check which followed Twitch channels are live and launch streamlink."""
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time

from rich.align import Align
from rich.console import Console
from rich.console import Group
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from twtui.api import (
    OFFLINE, get_status, twitch_search, top_games, search_games, game_streams,
)
from twtui.keys import read_key, term_setup, term_restore, _hotkey, SPECIAL

STREAMLINK = "streamlink"
FLAGS = ["best", "--twitch-low-latency", "--hls-live-edge", "1"]

# Runtime settings, editable in the settings view and persisted to config.json.
SETTINGS = {
    "hide_stream_console": False,   # run streamlink with no console window
    "kill_streams_on_exit": False,  # terminate launched streams when client exits
}
# (key, label, help) in display order.
SETTINGS_META = [
    ("hide_stream_console", "Hide streamlink console", "run streams without a console window"),
    ("kill_streams_on_exit", "Kill streams on exit", "close all open streams when you quit"),
]

_children = []                 # Popen handles of launched streams

# App dir (frozen exe or source); used only to find a legacy channels.txt / *.bat.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

BAT_DIR = getattr(sys, "_MEIPASS", APP_DIR)

console = Console()


def _config_dir():
    # Per-user writable config dir (source / frozen exe / pipx install).
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "twitch-tui")
    os.makedirs(d, exist_ok=True)
    return d


# TWITCH_TUI_CHANNELS overrides the path (testing / multiple profiles).
CHANNELS_FILE = os.environ.get("TWITCH_TUI_CHANNELS") or os.path.join(_config_dir(), "channels.txt")

CHANNELS_HEADER = "# One Twitch channel per line. Blank lines and #comments ignored.\n"

CONFIG_FILE = os.path.join(_config_dir(), "config.json")


def load_config():
    try:
        data = json.load(open(CONFIG_FILE, encoding="utf-8"))
    except Exception:
        return
    for k in SETTINGS:
        if isinstance(data.get(k), bool):
            SETTINGS[k] = data[k]


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, indent=2)
    except Exception:
        pass


def _read_channels(path):
    chans = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            chans.append(line)
    return chans


def load_channels():
    if os.path.exists(CHANNELS_FILE):
        return _read_channels(CHANNELS_FILE)

    # First run: seed from a legacy channels.txt next to the app, else *.bat, else empty.
    legacy = os.path.join(APP_DIR, "channels.txt")
    if os.path.exists(legacy):
        channels = _read_channels(legacy)
    else:
        channels = []
        for path in sorted(glob.glob(os.path.join(BAT_DIR, "*.bat"))):
            if os.path.basename(path).lower() == "watch.bat":
                continue
            text = open(path, encoding="utf-8").read()
            m = re.search(r"twitch\.tv/(\S+)", text)
            if m:
                channels.append(m.group(1))
    save_channels(channels)   # create the user file so follow/unfollow persist
    return channels


def save_channels(channels):
    os.makedirs(os.path.dirname(CHANNELS_FILE) or ".", exist_ok=True)
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        f.write(CHANNELS_HEADER)
        for c in channels:
            f.write(c + "\n")


def loading_panel(msg="checking channels"):
    spinner = Spinner("dots", text=Text(f" {msg} …", style="cyan"), style="magenta")
    return Panel(
        Align.center(spinner, vertical="middle"),
        title="[bold magenta]twitch — followed channels[/]",
        border_style="magenta",
        padding=(2, 4),
    )


def render(channels, status, selected, checking, opened):
    table = Table(show_header=True, box=None, padding=(0, 1), header_style="bold dim")
    table.add_column("", width=2)
    table.add_column("", width=2)
    table.add_column("Status", width=6)
    table.add_column("Channel")
    table.add_column("Viewers", justify="right", width=9)
    table.add_column("Game")
    table.add_column("", width=8)

    vis, rsel, start, end = _window(channels, selected, _max_rows(6))
    for j, ch in enumerate(vis):
        is_sel = j == rsel
        meta = status.get(ch) or OFFLINE
        live = meta["live"]
        if checking:
            dot, tag, tag_style = "•", "...", "dim"
        elif live:
            dot, tag, tag_style = "●", "LIVE", "bold green"
        else:
            dot, tag, tag_style = "○", "off", "dim"

        cursor = Text("❱", style="bold cyan") if is_sel else Text(" ")
        name_style = "bold white on grey19" if is_sel else "white"
        watching = Text("▶ open", style="bold yellow") if ch in opened else Text("")
        viewers = f"{meta['viewers']:,}" if (not checking and live) else ""
        game = meta["game"] if (not checking and live) else ""
        name = Text(f" {ch} ", style=name_style)
        disp = meta.get("display", "")
        if disp and disp.lower() != ch.lower():
            name.append(f"({disp}) ", style="dim")
        table.add_row(
            cursor,
            Text(dot, style="green" if (not checking and live) else "dim"),
            Text(tag, style=tag_style),
            name,
            Text(viewers, style="green" if live else "dim"),
            Text(game, style="cyan" if live else "dim"),
            watching,
        )

    inner = table if channels else Align.center(
        Text("no followed channels — press tab to search & follow", style="dim"),
        vertical="middle",
    )
    body = Panel(
        inner,
        title=_scroll_title("twitch — followed channels", start, end, len(channels)),
        subtitle="[dim]↑↓ move · enter watch · f unfollow · r refresh · tab search · ctrl+g games · s settings · q quit[/]",
        border_style="magenta",
        padding=(1, 2),
    )
    return body


def _filter_streams(streams, q):
    q = q.strip().lower()
    if not q:
        return streams
    return [s for s in streams if q in s["login"].lower() or q in s["display"].lower()]


def _max_rows(reserve):
    # Rows that fit in the current terminal after fixed chrome (borders/header).
    return max(3, console.size.height - reserve)


def _window(items, sel, max_rows):
    # Scroll window around the selection -> (items, rel_sel, start, end).
    n = len(items)
    if n <= max_rows or max_rows <= 0:
        return items, sel, 0, n
    start = max(0, min(sel - max_rows // 2, n - max_rows))
    return items[start:start + max_rows], sel - start, start, start + max_rows


def _scroll_title(base, start, end, n):
    # Panel title with a scroll indicator when the list overflows the window.
    if n > end - start:
        return f"[bold magenta]{base}[/] [dim]{start + 1}-{end}/{n}[/]"
    return f"[bold magenta]{base}[/]"


def _tabs(active):
    # Streamers / Categories switcher header; active tab highlighted, both legible.
    def seg(label, key):
        return f"[black on yellow] {label} [/]" if active == key else f"[yellow] {label} [/]"
    return Align.center(Text.from_markup(seg("Streamers", "search") + "   " + seg("Categories", "cats")))


def _channel_table(results, sel, opened, followed):
    # Shared by the search view and the in-category view.
    table = Table(show_header=True, box=None, padding=(0, 1), header_style="bold dim")
    table.add_column("", width=2)
    table.add_column("", width=2)
    table.add_column("Channel")
    table.add_column("Viewers", justify="right", width=9)
    table.add_column("Game")
    table.add_column("", width=10)
    for i, res in enumerate(results):
        is_sel = i == sel
        live_ = res["live"]
        cursor = Text("❱", style="bold cyan") if is_sel else Text(" ")
        dot = Text("●", style="bold green") if live_ else Text("○", style="dim")
        name_style = "bold white on grey19" if is_sel else ("white" if live_ else "dim")
        viewers = f"{res['viewers']:,}" if live_ else "—"
        # Star (followed) and open marker are independent; show both when both apply.
        watching = Text()
        if res["login"].lower() in followed:
            watching.append("★ ", style="yellow")
        if res["login"] in opened:
            watching.append("▶ open", style="bold yellow")
        # login + dim display name when they differ.
        name = Text(f" {res['login']} ", style=name_style)
        if res["display"] and res["display"].lower() != res["login"].lower():
            name.append(f"({res['display']}) ", style="dim")
        table.add_row(
            cursor, dot, name,
            Text(viewers, style="green" if live_ else "dim"),
            Text(res["game"], style="cyan" if live_ else "dim"),
            watching,
        )
    return table


def render_search(st, opened, followed):
    q = st["query"]
    query_text = Text.assemble(("❱ ", "bold cyan"), (q, "white"), ("▉", "cyan"))
    search_panel = Panel(
        query_text,
        title="[bold magenta]search twitch[/]",
        subtitle="[dim]type · ←/→ switch · ↑↓ move · enter watch · ctrl+f follow · esc list · ctrl+q quit[/]",
        border_style="cyan",
        padding=(0, 1),
    )

    results = st["results"]
    title = "[bold magenta]streamers[/]"
    if st["searching"] and not results:
        inner = Align.center(
            Spinner("dots", text=Text(" searching …", style="cyan"), style="magenta"),
            vertical="middle",
        )
    elif not results:
        msg = "no matches" if q.strip() else "start typing to search all of twitch"
        inner = Align.center(Text(msg, style="dim"), vertical="middle")
    else:
        vis, rsel, start, end = _window(results, st["sel"], _max_rows(9))
        inner = _channel_table(vis, rsel, opened, followed)
        title = _scroll_title("streamers", start, end, len(results))

    results_panel = Panel(inner, title=title, border_style="magenta", padding=(1, 2))
    return Group(_tabs("search"), search_panel, results_panel)


def render_cats(st):
    q = st["cat_query"]
    query_text = Text.assemble(("❱ ", "bold cyan"), (q, "white"), ("▉", "cyan"))
    search_panel = Panel(
        query_text,
        title="[bold magenta]search categories[/]",
        subtitle="[dim]type · ←/→ switch · ↑↓ move · enter open · esc back · ctrl+q quit[/]",
        border_style="cyan",
        padding=(0, 1),
    )
    results = st["cat_results"]
    title = "[bold magenta]categories[/]"
    if st["cat_searching"] and not results:
        inner = Align.center(
            Spinner("dots", text=Text(" loading …", style="cyan"), style="magenta"),
            vertical="middle",
        )
    elif not results:
        inner = Align.center(Text("no categories", style="dim"), vertical="middle")
    else:
        vis, rsel, start, end = _window(results, st["cat_sel"], _max_rows(9))
        table = Table(show_header=True, box=None, padding=(0, 1), header_style="bold dim")
        table.add_column("", width=2)
        table.add_column("Category")
        table.add_column("Viewers", justify="right", width=11)
        for i, g in enumerate(vis):
            is_sel = i == rsel
            cursor = Text("❱", style="bold cyan") if is_sel else Text(" ")
            name_style = "bold white on grey19" if is_sel else "white"
            table.add_row(
                cursor,
                Text(f" {g['display']} ", style=name_style),
                Text(f"{g['viewers']:,}", style="green"),
            )
        inner = table
        title = _scroll_title("categories", start, end, len(results))
    body = Panel(inner, title=title, border_style="magenta", padding=(1, 2))
    return Group(_tabs("cats"), search_panel, body)


def render_cat(st, opened, followed):
    q = st["cat_ch_query"]
    filtered = _filter_streams(st["cat_streams"], q)
    query_text = Text.assemble(("❱ ", "bold cyan"), (q, "white"), ("▉", "cyan"))
    search_panel = Panel(
        query_text,
        title=f"[bold magenta]{st['game_display']} — top channels[/]",
        subtitle="[dim]filter · ↑↓ move · enter watch · ctrl+f follow · esc categories · ctrl+q quit[/]",
        border_style="cyan",
        padding=(0, 1),
    )
    title = "[bold magenta]channels[/]"
    if st["cat_searching"] and not st["cat_streams"]:
        inner = Align.center(
            Spinner("dots", text=Text(" loading …", style="cyan"), style="magenta"),
            vertical="middle",
        )
    elif not filtered:
        msg = "no live channels" if not st["cat_streams"] else "no matches"
        inner = Align.center(Text(msg, style="dim"), vertical="middle")
    else:
        vis, rsel, start, end = _window(filtered, st["cat_ch_sel"], _max_rows(8))
        inner = _channel_table(vis, rsel, opened, followed)
        title = _scroll_title("channels", start, end, len(filtered))
    body = Panel(inner, title=title, border_style="magenta", padding=(1, 2))
    return Group(search_panel, body)


def render_settings(st):
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("", width=2)
    table.add_column("", width=5)
    table.add_column("Setting")
    for i, (key, label, help_) in enumerate(SETTINGS_META):
        is_sel = i == st["set_sel"]
        cursor = Text("❱", style="bold cyan") if is_sel else Text(" ")
        on = SETTINGS[key]
        toggle = Text("[on]" if on else "[off]", style="bold green" if on else "dim")
        name = Text(f" {label} ", style="bold white on grey19" if is_sel else "white")
        name.append(f"  {help_}", style="dim")
        table.add_row(cursor, toggle, name)
    return Panel(
        table,
        title="[bold magenta]settings[/]",
        subtitle="[dim]↑↓ move · enter/space toggle · esc back · ctrl+q quit[/]",
        border_style="magenta",
        padding=(1, 2),
    )


def launch(channel):
    # Start streamlink detached so the menu keeps running and multiple streams
    # can be open at once. Tracked so KILL_STREAMS_ON_EXIT can clean up.
    cmd = [STREAMLINK, f"twitch.tv/{channel}", *FLAGS]
    hide = SETTINGS["hide_stream_console"]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW if hide else subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["start_new_session"] = True   # detach from our controlling terminal
        if hide:
            kwargs["stdout"] = kwargs["stderr"] = subprocess.DEVNULL
    _children.append(subprocess.Popen(cmd, **kwargs))


def kill_streams():
    # Best-effort terminate of launched streams (used only when the toggle is on).
    for p in _children:
        if p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass


def sort_channels(channels, status):
    channels.sort(key=lambda c: (not (status.get(c) or OFFLINE)["live"], -(status.get(c) or OFFLINE)["viewers"]))


def main():
    load_config()
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
        "set_sel": 0,        # settings view cursor
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
                    elif mode == "settings":
                        st["set_sel"] = (st["set_sel"] + delta) % len(SETTINGS_META)
                        paint_settings()
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

                if mode == "settings":
                    if tok == "ENTER" or char == " ":
                        key = SETTINGS_META[st["set_sel"]][0]
                        SETTINGS[key] = not SETTINGS[key]
                        save_config()
                        paint_settings()
                    elif tok == "ESC":
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
                        st["set_sel"] = 0
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

    if SETTINGS["kill_streams_on_exit"]:
        kill_streams()


if __name__ == "__main__":
    main()
