from collections.abc import Callable
import pytest

from tgmount.tglog import init_logging


@pytest.fixture()
def mnt_dir(tmpdir):
    """str(tmpdir)"""
    return str(tmpdir)


@pytest.fixture
def set_logging(caplog):
    def _inner(level: int):
        init_logging(debug_level=level)
        caplog.set_level(level)

    return _inner


FixtureSetLogging = Callable[[int], None]
