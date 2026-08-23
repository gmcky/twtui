from twtui.config import FEATURES_LOCKED, build_stream_cmd


def test_live_defaults(settings):
    settings["low_latency"] = True
    cmd = build_stream_cmd("foo")
    assert cmd[:3] == ["streamlink", "twitch.tv/foo", "best"]
    assert "--twitch-low-latency" in cmd
    # low latency must force edge=1.
    assert cmd[cmd.index("--hls-live-edge") + 1] == "1"


def test_dvr_restart_suppressed_by_low_latency(settings):
    # --hls-live-restart contradicts LL. Must be dropped.
    settings["low_latency"] = True
    settings["dvr_restart"] = True
    cmd = build_stream_cmd("foo")
    assert "--hls-live-restart" not in cmd


def test_dvr_restart_without_low_latency(settings):
    settings["low_latency"] = False
    settings["dvr_restart"] = True
    cmd = build_stream_cmd("foo")
    if FEATURES_LOCKED:
        # DVR restart is gated off.
        assert "--hls-live-restart" not in cmd
    else:
        assert "--hls-live-restart" in cmd


def test_low_latency_off(settings):
    settings["low_latency"] = False
    settings["live_edge"] = 3
    cmd = build_stream_cmd("foo")
    assert "--twitch-low-latency" not in cmd
    assert "--hls-live-edge" in cmd
    assert cmd[cmd.index("--hls-live-edge") + 1] == "3"


def test_quality(settings):
    settings["quality"] = "720p60"
    cmd = build_stream_cmd("foo")
    assert cmd[2] == "720p60"


def test_codecs(settings):
    settings["twitch_codecs"] = "h264"
    cmd1 = build_stream_cmd("foo")
    assert "--twitch-supported-codecs" not in cmd1

    settings["twitch_codecs"] = "av1,h264"
    cmd2 = build_stream_cmd("foo")
    assert "--twitch-supported-codecs" in cmd2
    assert cmd2[cmd2.index("--twitch-supported-codecs") + 1] == "av1,h264"


def test_player(settings):
    settings["player_path"] = " /bin/mpv "
    settings["player_args"] = " --fs "
    cmd = build_stream_cmd("foo")
    assert "--player" in cmd
    assert cmd[cmd.index("--player") + 1] == "/bin/mpv"
    assert "--player-args" in cmd
    assert cmd[cmd.index("--player-args") + 1] == "--fs"


def test_retries(settings):
    settings["retry_streams"] = 2
    settings["retry_max"] = 5
    settings["retry_open"] = 3
    cmd = build_stream_cmd("foo")
    assert "--retry-streams" in cmd
    assert cmd[cmd.index("--retry-streams") + 1] == "2"
    assert "--retry-max" in cmd
    assert cmd[cmd.index("--retry-max") + 1] == "5"
    assert "--retry-open" in cmd
    assert cmd[cmd.index("--retry-open") + 1] == "3"


def test_other_flags(settings):
    settings["stream_timeout"] = 30
    settings["ringbuffer_size"] = "32M"
    settings["segment_threads"] = 4
    settings["http_proxy"] = "http://proxy"
    settings["ip_version"] = "ipv4"
    cmd = build_stream_cmd("foo")
    assert "--stream-timeout" in cmd
    assert cmd[cmd.index("--stream-timeout") + 1] == "30"
    assert "--ringbuffer-size" in cmd
    assert cmd[cmd.index("--ringbuffer-size") + 1] == "32M"
    assert "--stream-segment-threads" in cmd
    assert cmd[cmd.index("--stream-segment-threads") + 1] == "4"
    assert "--http-proxy" in cmd
    assert cmd[cmd.index("--http-proxy") + 1] == "http://proxy"
    assert "--ipv4" in cmd


def test_custom_flags(settings):
    settings["custom_flags"] = "--foo --bar"
    cmd = build_stream_cmd("foo")
    assert "--foo" in cmd
    assert "--bar" in cmd

    settings["custom_flags"] = '"'
    cmd2 = build_stream_cmd("foo")
    assert "streamlink" in cmd2


def test_vod_target(settings):
    settings["low_latency"] = True
    settings["retry_streams"] = 2
    settings["dvr_restart"] = True
    cmd = build_stream_cmd("videos/123")
    assert cmd[1] == "twitch.tv/videos/123"
    assert "--twitch-low-latency" not in cmd
    assert "--hls-live-edge" not in cmd
    assert "--retry-streams" not in cmd
    assert "--hls-live-restart" not in cmd


def test_full_url(settings):
    cmd = build_stream_cmd("https://twitch.tv/foo")
    assert cmd[1] == "https://twitch.tv/foo"


def test_clip_target(settings):
    settings["low_latency"] = True
    settings["retry_streams"] = 2
    settings["dvr_restart"] = True
    cmd = build_stream_cmd("https://clips.twitch.tv/Foo")
    assert cmd[1] == "https://clips.twitch.tv/Foo"
    assert "--twitch-low-latency" not in cmd
    assert "--hls-live-edge" not in cmd
    assert "--retry-streams" not in cmd
    assert "--hls-live-restart" not in cmd


def test_safe_filename():
    from twtui.config import _safe_filename

    assert _safe_filename("https://twitch.tv/videos/123") == "https---twitch.tv-videos-123"


def test_record_clip(settings, tmp_path):
    settings["record_streams"] = True
    settings["record_dir"] = str(tmp_path)
    cmd = build_stream_cmd("https://clips.twitch.tv/Foo")
    if FEATURES_LOCKED:
        # Recording is gated off.
        assert "--record" not in cmd
        return
    assert "--record" in cmd
    record_path = cmd[cmd.index("--record") + 1]
    import os

    basename = os.path.basename(record_path)
    assert not any(c in basename for c in [":", "/", "\\", "?", "*"])
