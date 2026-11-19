import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "canonical_warehouse: pinned to the canonical warehouse build, "
        "not the published release pack that CI fetches")


@pytest.fixture(autouse=True)
def canonical_warehouse():
    from shared import store

    original = store.DB_PATH
    store.DB_PATH = store.CANONICAL_DB_PATH
    yield store.DB_PATH
    store.DB_PATH = original
