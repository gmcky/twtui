import twtui.streams as streams


def _focus_entry(**kw):
    # slink_pid None so focus_channel skips the psutil children lookup.
    base = {
        "channel": "x",
        "slink_pid": None,
        "slink_create": None,
        "player_pid": 10,
        "player_create": 2.0,
    }
    base.update(kw)
    return base


def test_focus_channel_activates_by_default(monkeypatch, settings):
    captured = {}

    def fake_focus(pids, activate=True):
        captured["activate"] = activate
        return True

    monkeypatch.setattr(streams.sys, "platform", "win32")
    monkeypatch.setattr(streams, "_focus_windows", fake_focus)
    monkeypatch.setattr(streams, "_open_streams", [_focus_entry()])
    settings["keep_terminal_focus"] = False
    assert streams.focus_channel("x") is True
    assert captured["activate"] is True


def test_focus_channel_keep_terminal_focus(monkeypatch, settings):
    captured = {}

    def fake_focus(pids, activate=True):
        captured["activate"] = activate
        return True

    monkeypatch.setattr(streams.sys, "platform", "win32")
    monkeypatch.setattr(streams, "_focus_windows", fake_focus)
    monkeypatch.setattr(streams, "_open_streams", [_focus_entry()])
    settings["keep_terminal_focus"] = True
    assert streams.focus_channel("x") is True
    # keep_terminal_focus on -> raise without activating (no focus steal).
    assert captured["activate"] is False


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
