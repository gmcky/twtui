"""Rich rendering: views and layout helpers."""
from rich.align import Align
from rich.console import Console, Group
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from twtui.api import OFFLINE
from twtui.config import SETTINGS, SETTINGS_META

console = Console()


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

