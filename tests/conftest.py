import copy

import pytest

from twtui import config


@pytest.fixture
def settings():
    """Yield the live SETTINGS dict with defaults, restored after the test.
    Mutate SETTINGS in-place inside a test; it is snapshotted and rolled back."""
    snapshot = copy.deepcopy(config.SETTINGS)
    yield config.SETTINGS
    config.SETTINGS.clear()
    config.SETTINGS.update(snapshot)
