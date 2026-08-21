from twtui.config import (
    BUNDLE_KEYS,
    PRESET_CHOICES,
    PRESETS,
    apply_preset,
    detect_preset,
    sync_preset_from_settings,
)


def test_fresh_defaults(settings):
    assert detect_preset() == "Low latency"


def test_apply_preset(settings):
    apply_preset("High quality")
    assert settings["segment_threads"] == 2
    assert settings["preset"] == "High quality"
    assert detect_preset() == "High quality"


def test_preset_modification(settings):
    apply_preset("Low latency")
    settings["quality"] = "480p"
    assert detect_preset() == "Custom"


def test_sync_flips_to_custom_on_edit(settings):
    apply_preset("High quality")
    settings["segment_threads"] = 8
    sync_preset_from_settings()
    assert settings["preset"] == "Custom"


def test_sync_snaps_back_to_named_preset(settings):
    apply_preset("High quality")
    settings["quality"] = "480p"
    sync_preset_from_settings()
    assert settings["preset"] == "Custom"
    settings["quality"] = "best"  # back to the High quality fingerprint
    sync_preset_from_settings()
    assert settings["preset"] == "High quality"


def test_apply_custom(settings):
    settings["quality"] = "480p"
    apply_preset("Custom")
    assert settings["quality"] == "480p"


def test_preset_definitions():
    for name in PRESET_CHOICES:
        if name != "Custom":
            assert name in PRESETS
            assert set(PRESETS[name].keys()) == set(BUNDLE_KEYS)
