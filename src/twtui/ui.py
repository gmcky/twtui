"""Rich rendering: views and layout helpers."""
from rich.align import Align
from rich.console import Console, Group
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from twtui.api import OFFLINE
from twtui.config import SETTINGS, SETTINGS_SCHEMA, THEME

console = Console()


def loading_panel(msg="checking channels"):
    spinner = Spinner("dots", text=Text(f" {msg} …", style="cyan"), style=THEME["accent"])
    return Panel(
        Align.center(spinner, vertical="middle"),
        title=f"[bold {THEME['accent']}]twitch — followed channels[/]",
        border_style=THEME["accent"],
        padding=(2, 4),
    )


def render(channels, status, selected, checking, opened, failed):
    table = Table(show_header=True, box=None, padding=(0, 1), header_style="bold dim", expand=True)
    table.add_column("", width=2, no_wrap=True)
    table.add_column("", width=2, no_wrap=True)
    table.add_column("Status", width=6, no_wrap=True)
    table.add_column("Channel", ratio=2, no_wrap=True, overflow="ellipsis")
    table.add_column("Viewers", justify="right", width=9, no_wrap=True)
    table.add_column("Game", ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column("", width=8, no_wrap=True)

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

        cursor = Text("❱", style=f"bold {THEME['cursor']}") if is_sel else Text(" ")
        name_style = f"bold white on {THEME['highlight_bg']}" if is_sel else "white"
        if ch in failed:
            watching = Text("✗ failed", style="bold red")
        elif ch in opened:
            watching = Text("▶ open", style=f"bold {THEME['open']}")
        else:
            watching = Text("")
        viewers = f"{meta['viewers']:,}" if (not checking and live) else ""
        game = meta["game"] if (not checking and live) else ""
        name = Text(f" {ch} ", style=name_style)
        disp = meta.get("display", "")
        if disp and disp.lower() != ch.lower():
            name.append(f"({disp}) ", style="dim")
        table.add_row(
            cursor,
            Text(dot, style=THEME["live"] if (not checking and live) else "dim"),
            Text(tag, style=tag_style),
            name,
            Text(viewers, style=THEME["live"] if live else "dim"),
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
        subtitle="[dim]↑↓ move · enter watch · f unfollow · r refresh · tab search · s settings · q quit[/]",
        border_style=THEME["accent"],
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
        return f"[bold {THEME['accent']}]{base}[/] [dim]{start + 1}-{end}/{n}[/]"
    return f"[bold {THEME['accent']}]{base}[/]"


def _tabs(active):
    # Streamers / Categories switcher header; active tab highlighted, both legible.
    def seg(label, key):
        return f"[black on {THEME['tab']}] {label} [/]" if active == key else f"[{THEME['tab']}] {label} [/]"
    return Align.center(Text.from_markup(seg("Streamers", "search") + "   " + seg("Categories", "cats")))


def _channel_table(results, sel, opened, followed, failed=None):
    if failed is None: failed = {}
    # Shared by the search view and the in-category view.
    table = Table(show_header=True, box=None, padding=(0, 1), header_style="bold dim", expand=True)
    table.add_column("", width=2, no_wrap=True)
    table.add_column("", width=2, no_wrap=True)
    table.add_column("Channel", ratio=2, no_wrap=True, overflow="ellipsis")
    table.add_column("Viewers", justify="right", width=9, no_wrap=True)
    table.add_column("Game", ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column("", width=10, no_wrap=True)
    for i, res in enumerate(results):
        is_sel = i == sel
        live_ = res["live"]
        cursor = Text("❱", style=f"bold {THEME['cursor']}") if is_sel else Text(" ")
        dot = Text("●", style=f"bold {THEME['live']}") if live_ else Text("○", style="dim")
        name_style = f"bold white on {THEME['highlight_bg']}" if is_sel else ("white" if live_ else "dim")
        viewers = f"{res['viewers']:,}" if live_ else "—"
        # Star (followed) and open marker are independent; show both when both apply.
        watching = Text()
        if res["login"].lower() in followed:
            watching.append("★ ", style=THEME["open"])
        if res["login"] in failed:
            watching.append("✗ failed", style="bold red")
        elif res["login"] in opened:
            watching.append("▶ open", style=f"bold {THEME['open']}")
        # login + dim display name when they differ.
        name = Text(f" {res['login']} ", style=name_style)
        if res["display"] and res["display"].lower() != res["login"].lower():
            name.append(f"({res['display']}) ", style="dim")
        table.add_row(
            cursor, dot, name,
            Text(viewers, style=THEME["live"] if live_ else "dim"),
            Text(res["game"], style="cyan" if live_ else "dim"),
            watching,
        )
    return table


def render_search(st, opened, followed):
    q = st["query"]
    query_text = Text.assemble(("❱ ", f"bold {THEME['cursor']}"), (q, "white"), ("▉", THEME["cursor"]))
    search_panel = Panel(
        query_text,
        title=f"[bold {THEME['accent']}]search twitch[/]",
        subtitle="[dim]type · ←/→ switch · ↑↓ move · enter watch · ctrl+f follow · esc list · ctrl+q quit[/]",
        border_style=THEME["accent"],
        padding=(0, 1),
    )

    results = st["results"]
    title = f"[bold {THEME['accent']}]streamers[/]"
    if st["searching"] and not results:
        inner = Align.center(
            Spinner("dots", text=Text(" searching …", style="cyan"), style=THEME["accent"]),
            vertical="middle",
        )
    elif not results:
        msg = "no matches" if q.strip() else "start typing to search all of twitch"
        inner = Align.center(Text(msg, style="dim"), vertical="middle")
    else:
        vis, rsel, start, end = _window(results, st["sel"], _max_rows(9))
        inner = _channel_table(vis, rsel, opened, followed, st.get("failed", {}))
        title = _scroll_title("streamers", start, end, len(results))

    results_panel = Panel(inner, title=title, border_style=THEME["accent"], padding=(1, 2))
    return Group(_tabs("search"), search_panel, results_panel)


def render_cats(st):
    q = st["cat_query"]
    query_text = Text.assemble(("❱ ", f"bold {THEME['cursor']}"), (q, "white"), ("▉", THEME["cursor"]))
    search_panel = Panel(
        query_text,
        title=f"[bold {THEME['accent']}]search categories[/]",
        subtitle="[dim]type · ←/→ switch · ↑↓ move · enter open · esc back · ctrl+q quit[/]",
        border_style=THEME["accent"],
        padding=(0, 1),
    )
    results = st["cat_results"]
    title = f"[bold {THEME['accent']}]categories[/]"
    if st["cat_searching"] and not results:
        inner = Align.center(
            Spinner("dots", text=Text(" loading …", style="cyan"), style=THEME["accent"]),
            vertical="middle",
        )
    elif not results:
        inner = Align.center(Text("no categories", style="dim"), vertical="middle")
    else:
        vis, rsel, start, end = _window(results, st["cat_sel"], _max_rows(9))
        table = Table(show_header=True, box=None, padding=(0, 1), header_style="bold dim", expand=True)
        table.add_column("", width=2, no_wrap=True)
        table.add_column("Category", ratio=1, no_wrap=True, overflow="ellipsis")
        table.add_column("Viewers", justify="right", width=12, no_wrap=True)
        for i, g in enumerate(vis):
            is_sel = i == rsel
            cursor = Text("❱", style=f"bold {THEME['cursor']}") if is_sel else Text(" ")
            name_style = f"bold white on {THEME['highlight_bg']}" if is_sel else "white"
            table.add_row(
                cursor,
                Text(f" {g['display']} ", style=name_style),
                Text(f"{g['viewers']:,}", style=THEME["live"]),
            )
        inner = table
        title = _scroll_title("categories", start, end, len(results))
    body = Panel(inner, title=title, border_style=THEME["accent"], padding=(1, 2))
    return Group(_tabs("cats"), search_panel, body)


def render_cat(st, opened, followed):
    q = st["cat_ch_query"]
    streams = st["cat_streams"]
    g = st["game_display"]
    query_text = Text.assemble(("❱ ", f"bold {THEME['cursor']}"), (q, "white"), ("▉", THEME["cursor"]))
    search_panel = Panel(
        query_text,
        title=f"[bold {THEME['accent']}]{g} — top channels[/]",
        subtitle="[dim]filter · ↑↓ move · enter watch · ctrl+f follow · esc categories · ctrl+q quit[/]",
        border_style=THEME["accent"],
        padding=(0, 1),
    )
    title = f"[bold {THEME['accent']}]channels[/]"
    if st["cat_searching"] and not streams:
        inner = Align.center(
            Spinner("dots", text=Text(" loading …", style="cyan"), style=THEME["accent"]),
            vertical="middle",
        )
    elif not streams:
        inner = Align.center(
            Text(f"no streams found for '{g}'", style="dim"),
            vertical="middle",
        )
    else:
        filtered = _filter_streams(streams, q)
        if not filtered:
            inner = Align.center(Text(f"no streams match '{q}'", style="dim"), vertical="middle")
        else:
            vis, rsel, start, end = _window(filtered, st["cat_ch_sel"], _max_rows(8))
            inner = _channel_table(vis, rsel, opened, followed, st.get("failed", {}))
            title = _scroll_title("channels", start, end, len(filtered))
    body = Panel(inner, title=title, border_style=THEME["accent"], padding=(1, 2))
    return Group(search_panel, body)


def _setting_tabs(active_idx):
    segs = []
    for i, (name, _) in enumerate(SETTINGS_SCHEMA):
        if i == active_idx:
            segs.append(f"[black on {THEME['tab']}] {name} [/]")
        else:
            segs.append(f"[{THEME['tab']}] {name} [/]")
    return Align.center(Text.from_markup("   ".join(segs)))

def _render_picker(st):
    sec = SETTINGS_SCHEMA[st["set_section"]]
    f = sec[1][st["set_sel"]]
    opts = f["choices"]
    
    vis, rsel, start, end = _window(opts, st["pick_sel"], _max_rows(8))
    table = Table(show_header=False, box=None, padding=(0, 1))
    
    for i, opt in enumerate(vis):
        is_sel = (i == rsel)
        cursor = Text("❱", style=f"bold {THEME['cursor']}") if is_sel else Text(" ")
        
        label = Text()
        if f["type"] == "color":
            label.append(str(opt), style=opt)
            label.append(" ")
            label.append("  ", style=f"on {opt}")
        else:
            style = f"bold white on {THEME['highlight_bg']}" if is_sel else "white"
            label.append(str(opt), style=style)
            
        if opt == SETTINGS.get(f["key"]):
            label.append(" ● current", style="dim")
            
        table.add_row(cursor, label)
        
    panel = Panel(
        table,
        title=_scroll_title(f["label"], start, end, len(opts)),
        subtitle="[dim]↑↓ move · enter select · esc cancel[/]",
        border_style=THEME["accent"],
        padding=(1, 2)
    )
    return Align.center(panel, vertical="middle")

def render_settings(st):
    if st.get("set_picking"):
        return _render_picker(st)

    sec_idx = st["set_section"]
    sec_name, fields = SETTINGS_SCHEMA[sec_idx]
    
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("", width=2)
    table.add_column("", no_wrap=True)
    table.add_column("Setting")
    
    for i, f in enumerate(fields):
        is_sel = i == st["set_sel"]
        key = f["key"]
        val = SETTINGS.get(key, "")
        
        cursor = Text("❱", style=f"bold {THEME['cursor']}") if is_sel else Text(" ")
        
        val_col = Text()
        if f["type"] == "bool":
            val_col.append("[on]" if val else "[off]", style=f"bold {THEME['live']}" if val else "dim")
        elif f["type"] in ("choice", "preset"):
            val_col.append("‹ ", style="dim")
            val_col.append(str(val), style="white")
            val_col.append(" ›", style="dim")
        elif f["type"] == "text":
            if is_sel and st.get("set_editing"):
                val_col.append(st["set_buf"], style="white")
                val_col.append("▉", style=THEME["cursor"])
            else:
                if val:
                    val_col.append(str(val), style="white")
                else:
                    val_col.append("type to set…", style="dim")
        elif f["type"] == "int":
            if is_sel and st.get("set_editing"):
                val_col.append(st["set_buf"], style="white")
                val_col.append("▉", style=THEME["cursor"])
            else:
                val_col.append(f"{val}{f.get('unit', '')}", style="white")
        elif f["type"] == "color":
            val_col.append("‹ ", style="dim")
            val_col.append(str(val), style=str(val))
            val_col.append(" ", style="dim")
            val_col.append("  ", style=f"on {val}")
            val_col.append(" ›", style="dim")
        elif f["type"] == "key":
            if is_sel and st.get("set_capturing"):
                val_col.append("press a key…", style=THEME["cursor"])
            else:
                val_col.append(str(val), style="white")
                    
        name = Text(f" {f['label']} ", style=f"bold white on {THEME['highlight_bg']}" if is_sel else "white")
        name.append(f"  {f['help']}", style="dim")
        
        table.add_row(cursor, val_col, name)
        
    body = Panel(
        table,
        title=f"[bold {THEME['accent']}]settings[/]",
        subtitle="[dim]↑↓ move · ←→ section · enter toggle/edit · esc back · ctrl+q quit[/]",
        border_style=THEME["accent"],
        padding=(1, 2),
    )
    return Group(_setting_tabs(sec_idx), body)


def render_confirm(open_count):
    msg = f"Quit? {open_count} stream{'s' if open_count != 1 else ''} still open — [y]es / [n]o"
    return Align.center(
        Panel(
            Text(msg, justify="center"),
            border_style=THEME["open"],
            padding=(1, 4)
        ),
        vertical="middle"
    )

