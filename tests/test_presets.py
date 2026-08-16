from twtui.config import BUNDLE_KEYS, PRESET_CHOICES, PRESETS, apply_preset, detect_preset


def test_fresh_defaults(settings):
    assert detect_preset() == "Balanced"


def test_apply_preset(settings):
    apply_preset("High quality")
    assert settings["segment_threads"] == 2
    assert settings["preset"] == "High quality"
    assert detect_preset() == "High quality"


def test_preset_modification(settings):
    apply_preset("Balanced")
    settings["quality"] = "480p"
    assert detect_preset() == "Custom"


def test_apply_custom(settings):
    settings["quality"] = "480p"
    apply_preset("Custom")
    assert settings["quality"] == "480p"


def test_preset_definitions():
    for name in PRESET_CHOICES:
        if name != "Custom":
            assert name in PRESETS
            assert set(PRESETS[name].keys()) == set(BUNDLE_KEYS)
