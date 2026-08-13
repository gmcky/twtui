def test_roundtrip(tmp_path, monkeypatch, settings):
    from twtui import config

    p = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", str(p))
    config.SETTINGS["quality"] = "480p"
    config.SETTINGS["segment_threads"] = 3
    config.save_config()
    # reset to defaults, then load should restore the saved values
    config.SETTINGS["quality"] = "best"
    config.SETTINGS["segment_threads"] = 1
    config.load_config()
    assert config.SETTINGS["quality"] == "480p"
    assert config.SETTINGS["segment_threads"] == 3


def test_out_of_range_and_invalid(tmp_path, monkeypatch, settings):
    import json

    from twtui import config

    p = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", str(p))

    with open(p, "w", encoding="utf-8") as f:
        json.dump({"segment_threads": 999, "quality": "invalid_quality"}, f)

    config.SETTINGS["quality"] = "best"
    config.load_config()
    assert config.SETTINGS["segment_threads"] == 10  # schema max
    assert config.SETTINGS["quality"] == "best"


def test_missing_file(tmp_path, monkeypatch, settings):
    from twtui import config

    p = tmp_path / "missing.json"
    monkeypatch.setattr(config, "CONFIG_FILE", str(p))
    config.load_config()  # no exception
