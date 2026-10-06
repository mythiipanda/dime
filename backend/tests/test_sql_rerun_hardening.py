import asyncio
import sys
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import rate_limit, store
from shared.config import settings
from shared.tools.league import _validate_readonly_sql, rerun_sql

@pytest.fixture(autouse=True)
def _clean_limiter():
    rate_limit.reset()
    yield
    rate_limit.reset()

@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    try:
        con.execute(
            "CREATE TABLE silver_standings "
            "(TEAM TEXT, WINS INTEGER, _season TEXT)")
        con.execute(
            "INSERT INTO silver_standings VALUES ('OKC', 68, '2025-26')")
    finally:
        con.close()
    monkeypatch.setattr(store, "connect",
                        lambda **_kw: duckdb.connect(str(wh)))
    return wh

def _cors_client():
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)

def test_check_sql_rerun_trips_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("DIME_SQL_RERUN_RATE_LIMIT", "2")
    rate_limit.check_sql_rerun("10.0.0.1")
    rate_limit.check_sql_rerun("10.0.0.1")
    with pytest.raises(HTTPException) as excinfo:
        rate_limit.check_sql_rerun("10.0.0.1")
    assert excinfo.value.status_code == 429
    assert "Retry-After" in excinfo.value.headers
    assert int(excinfo.value.headers["Retry-After"]) >= 1
    rate_limit.check_sql_rerun("10.0.0.2")

def test_handler_returns_429_when_limit_tripped(monkeypatch):
    import shared.tools.league as league
    from v2.api import routes

    async def fake_rerun(sql):
        assert sql == "SELECT 1"
        return {"ok": True, "columns": ["a"], "rows": [{"a": 1}],
                "ms": 1, "capped": False}

    monkeypatch.setenv("DIME_SQL_RERUN_RATE_LIMIT", "1")
    monkeypatch.setattr(league, "rerun_sql", fake_rerun)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    client = TestClient(app)
    first = client.post("/api/sql/rerun", json={"sql": "SELECT 1"})
    assert first.status_code == 200
    second = client.post("/api/sql/rerun", json={"sql": "SELECT 1"})
    assert second.status_code == 429
    lowered = {k.lower(): v for k, v in second.headers.items()}
    assert "retry-after" in lowered
    assert int(lowered["retry-after"]) >= 1

def test_cors_allows_only_listed_origins():
    assert "http://localhost:3000" in settings.cors_origins
    assert "https://dime-fawn.vercel.app" in settings.cors_origins
    assert "http://127.0.0.1:3000" in settings.cors_origins
    assert "https://evil.example.com" not in settings.cors_origins
    assert "*" not in settings.cors_origins

def test_cors_preflight_rejects_unknown_origin():
    resp = _cors_client().options(
        "/ping",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in resp.headers

def test_cors_preflight_echoes_allowed_origin():
    resp = _cors_client().options(
        "/ping",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == (
        "http://localhost:3000")

def test_cors_get_rejects_unknown_origin():
    resp = _cors_client().get(
        "/ping", headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers

def test_cors_get_echoes_allowed_origin():
    resp = _cors_client().get(
        "/ping", headers={"Origin": "https://dime-fawn.vercel.app"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == (
        "https://dime-fawn.vercel.app")

@pytest.mark.parametrize("bad", [
    "DROP TABLE silver_standings",
    "INSERT INTO silver_standings VALUES ('X', 1, '2025-26')",
    "UPDATE silver_standings SET WINS = 99",
    "DELETE FROM silver_standings",
    "SELECT WINS FROM silver_standings; DROP TABLE silver_standings",
    "SELECT WINS FROM silver_standings; SELECT WINS FROM silver_standings",
])
def test_validate_rejects_write_sql(bad):
    with pytest.raises(ValueError):
        _validate_readonly_sql(bad, {"silver_standings"})

@pytest.mark.parametrize("bad", [
    "DROP TABLE silver_standings",
    "INSERT INTO silver_standings VALUES ('X', 1, '2025-26')",
    "SELECT WINS FROM silver_standings; DROP TABLE silver_standings",
])
def test_rerun_sql_rejects_write_sql(warehouse, bad):
    out = asyncio.run(rerun_sql(bad))
    assert out["ok"] is False
    assert out["error"]
    con = store.connect()
    try:
        n = con.execute("SELECT COUNT(*) FROM silver_standings").fetchone()[0]
    finally:
        con.close()
    assert n == 1
