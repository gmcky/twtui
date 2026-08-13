from twtui.config import clip_target, vod_target


def test_vod_targets():
    assert vod_target("https://www.twitch.tv/videos/123456") == "videos/123456"
    assert vod_target("videos/987") == "videos/987"
    assert vod_target("123456") == "videos/123456"
    assert vod_target("shroud") is None
    assert vod_target(" ") is None
    assert vod_target("") is None


def test_clip_targets():
    assert (
        clip_target("https://clips.twitch.tv/AwkwardHelpfulManatee")
        == "https://clips.twitch.tv/AwkwardHelpfulManatee"
    )
    assert (
        clip_target("https://www.twitch.tv/somechan/clip/AwkwardHelpfulManatee")
        == "https://clips.twitch.tv/AwkwardHelpfulManatee"
    )
    assert (
        clip_target("https://m.twitch.tv/clip/AwkwardHelpfulManatee")
        == "https://clips.twitch.tv/AwkwardHelpfulManatee"
    )
    assert clip_target("shroud") is None
    assert clip_target("") is None
    assert vod_target("https://clips.twitch.tv/AwkwardHelpfulManatee") is None
