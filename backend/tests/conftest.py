import pytest


@pytest.fixture(autouse=True)
def canonical_warehouse():
    from shared import store
    from v2.api import routes

    original = store.DB_PATH
    store.DB_PATH = store.CANONICAL_DB_PATH
    store.warehouse_identity_cache_clear()
    routes.runtime_warehouse_identity.cache_clear()
    routes.runtime_asset_manifest.cache_clear()
    yield store.DB_PATH
    store.DB_PATH = original
    store.warehouse_identity_cache_clear()
    routes.runtime_warehouse_identity.cache_clear()
    routes.runtime_asset_manifest.cache_clear()