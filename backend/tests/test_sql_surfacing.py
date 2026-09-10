"""Verification surfacing: text_to_sql's executed SQL must travel the full
pipeline — tool output -> desk trace -> SSE tool_result payload -> UI.

ROADMAP Phase 1 #1 (first half). Hermetic: no network, no LLM, no real
warehouse.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools
from app import providers
from app import store
from app.graph import _tool_result_payload, _trace_replay_events
from app.subagents import _trace_sql


def _warehouse_with_standings(tmp_path):
    import duckdb

    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    try:
        con.execute(
            "CREATE TABLE silver_standings "
            "(TEAM TEXT, WINS INTEGER, LOSSES INTEGER, _season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_standings VALUES ('OKC', 68, 14, '2025-26')"
        )
    finally:
        con.close()
    return wh


def test_text_to_sql_output_carries_executed_sql(monkeypatch, tmp_path):
    """The real executed SQL lands in a top-level `sql` field."""
    import asyncio

    import duckdb

    wh = _warehouse_with_standings(tmp_path)
    sql = (
        "SELECT WINS, LOSSES FROM silver_standings "
        "WHERE TEAM = 'OKC' AND _season = '2025-26'"
    )

    class _Resp:
        content = sql

    async def _fake_invoke(*_a, **_k):
        return _Resp()

    monkeypatch.setattr(providers, "invoke_with_fallback", _fake_invoke)
    monkeypatch.setattr(store, "connect", lambda: duckdb.connect(str(wh)))

    res = asyncio.run(
        tools.text_to_sql.ainvoke({"question": "OKC record this season"})
    )
    assert res["ok"] is True
    assert res["sql"] == sql
    assert res["rows"][0]["WINS"] == 68


def test_trace_sql_prefers_top_level_then_meta():
    assert _trace_sql({"sql": "SELECT 1"}) == "SELECT 1"
    assert _trace_sql({"meta": {"sql": "SELECT 2"}}) == "SELECT 2"
    assert _trace_sql({"ok": True}) is None
    assert _trace_sql({}) is None


def test_tool_result_payload_lifts_sql():
    sql = "SELECT WINS FROM silver_standings"
    out = {"tool": "text_to_sql", "ok": True, "rows": [{"WINS": 68}],
           "sql": sql}
    payload = _tool_result_payload("data_retrieval", "text_to_sql", out, 12)
    assert payload["sql"] == sql
    assert payload["status"] == "ok"
    assert payload["rows"] == 1
    assert payload["ms"] == 12


def test_tool_result_payload_falls_back_to_meta_sql():
    out = {"tool": "text_to_sql", "ok": True, "rows": [{"WINS": 68}],
           "meta": {"sql": "SELECT 1", "source": "warehouse"}}
    payload = _tool_result_payload("data_retrieval", "text_to_sql", out, 5)
    assert payload["sql"] == "SELECT 1"


def test_tool_result_payload_omits_sql_when_absent():
    out = {"tool": "get_briefing", "ok": True, "rows": []}
    payload = _tool_result_payload("data_retrieval", "get_briefing", out, 3)
    assert "sql" not in payload


def test_trace_replay_carries_sql_to_sse():
    out = {
        "agent": "league", "ok": True,
        "tool_trace": [
            {"name": "text_to_sql", "label": "Querying the warehouse",
             "ms": 40, "rows": 1, "status": "ok",
             "sql": "SELECT WINS FROM silver_standings"},
        ],
    }
    events = _trace_replay_events(out)
    results = [e["data"] for e in events if e["type"] == "tool_result"]
    assert len(results) == 1
    assert results[0]["sql"] == "SELECT WINS FROM silver_standings"
    assert results[0]["name"] == "text_to_sql"
