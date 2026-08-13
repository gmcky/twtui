from twtui.app import sort_channels


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
