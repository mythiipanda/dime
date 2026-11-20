
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import providers, store, tools
from shared.config import settings
from shared.tools import league as _league
from shared.tools.league import _describe_warehouse_schema

WH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

def _leaders_cols():
    cols = [f"C{i}" for i in range(32)]
    cols[0] = "PLAYER_ID"
    cols[20] = "STL"
    cols[21] = "BLK"
    cols[24] = "PTS"
    return cols

def test_schema_description_keeps_late_leader_columns():
    out = _describe_warehouse_schema({"silver_leaders_stl": _leaders_cols()})
    assert "STL" in out
    assert "BLK" in out
    assert "PTS" in out

def test_schema_description_truncates_wide_tables():
    wide = [f"C{i}" for i in range(60)]
    out = _describe_warehouse_schema({"wide_table": wide})
    parts = out.split(": ", 1)[1].split(", ")
    assert len(parts) == 40
    assert "C39" in out
    assert "C59" not in out
    assert "schema truncated: showing 40 of 60 columns; 20 omitted" in out

@pytest.fixture()
def memory_warehouse(monkeypatch):
    con = duckdb.connect(":memory:")
    calls: list[str] = []
    try:
        con.execute(
            "CREATE TABLE silver_standings "
            "(TEAM TEXT, WINS INTEGER, _season TEXT)")
        con.execute(
            "INSERT INTO silver_standings VALUES "
            "('OKC', 68, '2025-26'), ('BOS', 64, '2025-26')")

        class SharedConnection:
            def __init__(self, real):
                self._real = real

            @property
            def description(self):
                return self._real.description

            def execute(self, *args, **kwargs):
                if args:
                    calls.append(str(args[0]))
                return self._real.execute(*args, **kwargs)

            def close(self):
                pass

        monkeypatch.setattr(store, "connect",
                            lambda **_kw: SharedConnection(con))
        _league._clear_warehouse_schema_cache()
        yield con, calls
    finally:
        _league._clear_warehouse_schema_cache()
        con.close()

def _stub_model(monkeypatch, replies):
    model_calls: list = []

    async def _fake(primary, model, messages, **kwargs):
        model_calls.append(messages)
        reply = replies[min(len(model_calls) - 1, len(replies) - 1)]
        return SimpleNamespace(content=reply)

    monkeypatch.setattr(providers, "invoke_with_fallback", _fake)
    return model_calls

_DUP_SQL = "SELECT 1 AS n, 2 AS n FROM silver_standings"
_FIXED_SQL = ("SELECT WINS AS wins, TEAM AS team "
              "FROM silver_standings ORDER BY TEAM")

def test_text_to_sql_duplicate_repaired_with_unique_alias(
        memory_warehouse, monkeypatch):
    _con, calls = memory_warehouse
    model_calls = _stub_model(monkeypatch, [_DUP_SQL, _FIXED_SQL])
    res = asyncio.run(tools.text_to_sql.ainvoke(
        {"question": "wins by team"}))
    assert res["ok"] is True, res
    assert res["rows"] == [
        {"wins": 64, "team": "BOS"}, {"wins": 68, "team": "OKC"}]
    assert len(model_calls) == 2
    second = str(getattr(model_calls[1][-1], "content", ""))
    assert "duplicate output column name" in second
    assert "'n'" in second
    assert "unique alias" in second
    assert calls.count(_DUP_SQL) == 1
    assert calls.count(_FIXED_SQL) == 1

def test_text_to_sql_terminal_when_all_replies_duplicate(
        memory_warehouse, monkeypatch):
    _con, calls = memory_warehouse
    model_calls = _stub_model(monkeypatch, [_DUP_SQL, _DUP_SQL])
    res = asyncio.run(tools.text_to_sql.ainvoke(
        {"question": "wins by team"}))
    assert res["ok"] is False
    assert "rows" not in res
    assert "did not succeed after several attempts" in res["error"]
    assert len(model_calls) == 2
    assert calls.count(_DUP_SQL) == 2

def test_steals_leader_matches_warehouse():
    import asyncio

    import duckdb

    if not WH.exists():
        pytest.skip("warehouse missing")
    if not settings.mistral_api_key:
        pytest.skip("no Mistral API key")
    try:
        con = duckdb.connect(str(WH), read_only=True)
        try:
            expected = con.execute(
                "SELECT PLAYER, STL FROM silver_leaders_stl"
                " WHERE _season = '2025-26' ORDER BY STL DESC LIMIT 1"
            ).fetchone()
        finally:
            con.close()
    except Exception:
        pytest.skip("silver_leaders_stl unavailable")
    if not expected:
        pytest.skip("no 2025-26 steals leader row")
    res = asyncio.run(
        tools.text_to_sql.ainvoke(
            {"question": "who led the 2025-26 season in steals"}
        )
    )
    assert res["ok"] is True
    first = res["rows"][0]
    assert first["PLAYER"] == expected[0]
    assert int(first["STL"]) == int(expected[1])
