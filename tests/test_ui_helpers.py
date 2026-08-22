import io

from rich.console import Console

from twtui.ui import _filter_streams, _window, render_opened


def _render(renderable):
    # Render to a throwaway console; asserts the view builds without raising.
    Console(file=io.StringIO(), width=100).print(renderable)


def test_render_opened_populated():
    status = {
        "a": {"live": True, "viewers": 100, "game": "Dota 2", "display": "A"},
        "b": {"live": False, "viewers": 0, "game": "", "display": "B"},
    }
    _render(render_opened(["a", "b"], status, 0))


def test_render_opened_empty():
    _render(render_opened([], {}, 0))


def test_render_opened_unknown_channel():
    # Channel absent from status (category launch) must not raise.
    _render(render_opened(["ghost"], {}, 0))


def test_filter_streams():
    streams = [
        {"login": "foo", "display": "Foo", "game": "G"},
        {"login": "bar", "display": "bAr", "game": "H"},
    ]
    assert len(_filter_streams(streams, "foo")) == 1
    assert _filter_streams(streams, "foo")[0]["login"] == "foo"
    assert len(_filter_streams(streams, "bar")) == 1
    assert len(_filter_streams(streams, "")) == 2


def test_window_end():
    items = list(range(10))
    vis, sel, start, end = _window(items, 9, 3)
    assert vis == [7, 8, 9]
    assert sel == 2
    assert start == 7
    assert end == 10


def test_fmt_len():
    from twtui.ui import _fmt_len

    assert _fmt_len(0) == "0:00"
    assert _fmt_len(59) == "0:59"
    assert _fmt_len(60) == "1:00"
    assert _fmt_len(3599) == "59:59"
    assert _fmt_len(3600) == "1:00:00"
    assert _fmt_len(3661) == "1:01:01"


def test_window():
    items = list(range(10))

    # n <= max_rows
    vis, rsel, start, end = _window(items, 3, 10)
    assert vis == items
    assert rsel == 3
    assert start == 0
    assert end == 10

    # n > max_rows, selection near start
    vis, rsel, start, end = _window(items, 1, 5)
    assert vis == items[0:5]
    assert rsel == 1
    assert start == 0
    assert end == 5

    # n > max_rows, selection near middle
    vis, rsel, start, end = _window(items, 5, 5)
    assert len(vis) == 5
    assert items[5] in vis

    # n > max_rows, selection near end
    vis, rsel, start, end = _window(items, 9, 5)
    assert len(vis) == 5
    assert vis[-1] == 9
