import twtui.streams as streams


def test_close_channel_unknown(monkeypatch):
    monkeypatch.setattr(streams, "_open_streams", [])
    assert streams.close_channel("nobody") is False


def test_close_channel_kills(monkeypatch):
    calls = []
    monkeypatch.setattr(streams, "kill_tree", lambda pid, ct: calls.append((pid, ct)))
    monkeypatch.setattr(streams, "sync_state", lambda: None)
    monkeypatch.setattr(
        streams,
        "_open_streams",
        [
            {
                "channel": "shroud",
                "slink_pid": 111,
                "slink_create": 1.5,
                "player_pid": None,
                "player_create": None,
            }
        ],
    )
    assert streams.close_channel("shroud") is True
    assert calls == [(111, 1.5)]


def test_close_channel_kills_orphan_player(monkeypatch):
    # streamlink + a separately-tracked player both get killed.
    calls = []
    monkeypatch.setattr(streams, "kill_tree", lambda pid, ct: calls.append((pid, ct)))
    monkeypatch.setattr(streams, "sync_state", lambda: None)
    monkeypatch.setattr(
        streams,
        "_open_streams",
        [
            {
                "channel": "shroud",
                "slink_pid": 111,
                "slink_create": 1.5,
                "player_pid": 222,
                "player_create": 2.5,
            }
        ],
    )
    assert streams.close_channel("shroud") is True
    assert (111, 1.5) in calls and (222, 2.5) in calls
