from twtui.keymap import action_of, fold


def test_fold_cyrillic_positions():
    # ЙЦУКЕН folds to the latin key in the same physical spot.
    assert fold("й") == "q"
    assert fold("н") == "y"  # physical Y — the confirm "yes" key
    assert fold("т") == "n"  # physical N — the confirm "no" key
    assert fold("ы") == "s"
    assert fold("к") == "r"
    assert fold("а") == "f"


def test_fold_latin_and_case():
    assert fold("Q") == "q"
    assert fold("/") == "/"


def test_fold_rejects_non_single():
    assert fold("ENTER") is None
    assert fold("") is None
    assert fold(None) is None


def test_action_of_maps_layout():
    assert action_of("q") == "q"
    assert action_of("й") == "q"  # cyrillic quit key resolves the same
    assert action_of("ENTER") is None
    assert action_of("z") is None  # unbound
