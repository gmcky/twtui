from twtui.config import vod_target


def test_vod_targets():
    assert vod_target("https://www.twitch.tv/videos/123456") == "videos/123456"
    assert vod_target("videos/987") == "videos/987"
    assert vod_target("123456") == "videos/123456"
    assert vod_target("shroud") is None
    assert vod_target(" ") is None
    assert vod_target("") is None
