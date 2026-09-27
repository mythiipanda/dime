"""Freshness endpoint cache tests. Hermetic: tiny warehouse built in tmp_path."""

import sys
import time
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import datasets, store


@pytest.fixture()
def tiny_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE silver_a (id INTEGER, _fetched_at VARCHAR)")
    con.execute(
        "INSERT INTO silver_a VALUES "
        "(1, '2026-09-20T00:00:00+00:00'), (2, '2026-09-25T00:00:00+00:00')"
    )
    con.execute("CREATE TABLE silver_b (id INTEGER)")
    con.execute("INSERT INTO silver_b VALUES (1)")
    con.execute("CREATE TABLE bronze_ignored (id INTEGER)")
    con.close()
    # datasets does `from . import store`, so this redirects its connects too.
    monkeypatch.setattr(store, "DB_PATH", db)
    return db


@pytest.fixture()
def client(tiny_warehouse):
    app = FastAPI()
    app.include_router(datasets.router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_freshness_cache():
    datasets._FRESHNESS_CACHE["payload"] = None
    datasets._FRESHNESS_CACHE["at"] = 0.0
    yield
    datasets._FRESHNESS_CACHE["payload"] = None
    datasets._FRESHNESS_CACHE["at"] = 0.0


def test_freshness_shape_unchanged(client):
    resp = client.get("/api/v1/datasets/freshness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    rows = {r["table"]: r for r in body["rows"]}
    assert set(rows) == {"silver_a", "silver_b"}
    assert rows["silver_a"]["rows"] == 2
    assert rows["silver_a"]["last_fetch"] == "2026-09-25T00:00:00+00:00"
    assert rows["silver_b"]["rows"] == 1
    assert rows["silver_b"]["last_fetch"] is None
    for r in body["rows"]:
        assert set(r) == {"table", "rows", "last_fetch"}


def test_second_hit_served_from_cache(client, monkeypatch):
    calls = {"n": 0}
    real_connect = store.connect

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(store, "connect", counting)

    first = client.get("/api/v1/datasets/freshness").json()
    second = client.get("/api/v1/datasets/freshness").json()
    assert calls["n"] == 1, f"expected 1 warehouse query, got {calls['n']}"
    assert first == second


def test_cache_expires_after_ttl(client, monkeypatch):
    calls = {"n": 0}
    real_connect = store.connect

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(store, "connect", counting)

    client.get("/api/v1/datasets/freshness")
    assert calls["n"] == 1
    # Age the cache entry past the TTL; next hit must re-query.
    datasets._FRESHNESS_CACHE["at"] = (
        time.monotonic() - datasets._FRESHNESS_TTL_S - 1
    )
    out = client.get("/api/v1/datasets/freshness").json()
    assert calls["n"] == 2, f"expected re-query after TTL, got {calls['n']}"
    assert out["ok"] is True
    assert {r["table"] for r in out["rows"]} == {"silver_a", "silver_b"}
