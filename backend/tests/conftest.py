import pytest


@pytest.fixture(autouse=True)
def canonical_warehouse():
    from shared import store

    original = store.DB_PATH
    store.DB_PATH = store.CANONICAL_DB_PATH
    yield store.DB_PATH
    store.DB_PATH = original
