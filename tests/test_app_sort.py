from twtui.app import sort_channels, sort_opened


def test_sort_channels():
    channels = ["a", "b", "c", "d"]
    status = {
        "a": {"live": True, "viewers": 10},
        "b": {"live": False, "viewers": 0},
        "c": {"live": True, "viewers": 100},
        "d": {"live": True, "viewers": 5},
    }

    sort_channels(channels, status)
    # Live first, then by viewers descending. Offline last.
    # 'c' (100) -> 'a' (10) -> 'd' (5) -> 'b' (offline)
    assert channels == ["c", "a", "d", "b"]


def test_sort_opened():
    opened = {"a", "b", "c", "d"}
    status = {
        "a": {"live": True, "viewers": 10},
        "b": {"live": False, "viewers": 0},
        "c": {"live": True, "viewers": 100},
        "d": {"live": True, "viewers": 5},
    }
    # Same order as sort_channels; takes a set, returns a new sorted list.
    assert sort_opened(opened, status) == ["c", "a", "d", "b"]


def test_sort_opened_unknown_channel():
    # A channel opened from a category may not be in status -> treated as offline.
    assert sort_opened({"ghost"}, {}) == ["ghost"]
