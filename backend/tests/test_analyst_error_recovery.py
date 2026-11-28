import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analyst"))

from analyst import python_tools


def test_sql_column_error_includes_recovery_contract(monkeypatch):
    import shared.tools.sql_exec

    sql_mod = sys.modules["shared.tools.sql_exec"]

    class _ColErr:
        description = "sql"

        async def ainvoke(self, args):
            return {
                "tool": "sql_exec",
                "ok": False,
                "error": "Binder Error: Referenced column \"nonexistent_col\" not found in FROM clause",
            }

    monkeypatch.setattr(sql_mod, "sql_exec", _ColErr())
    tools = python_tools.catalogue()
    res = asyncio.run(tools["sql_exec"].ainvoke({"sql": "SELECT nonexistent_col FROM silver_standings"}))
    assert res["ok"] is False
    assert isinstance(res.get("summary"), str) and res["summary"]
    assert isinstance(res.get("recovery_hint"), str)
    assert "warehouse_schema" in res["recovery_hint"]
    assert isinstance(res.get("next_actions"), list) and "warehouse_schema" in res["next_actions"]


def test_missing_table_error_includes_recovery_contract(monkeypatch):
    from shared.tools import league as league_mod

    monkeypatch.setattr(league_mod, "_get_warehouse_schema", lambda: ("", {"silver_standings": []}))
    tools = python_tools.catalogue()
    res = tools["warehouse_schema"].invoke({"tables": ["missing_table_xyz"]})
    assert res["ok"] is False
    assert "summary" in res
    assert "warehouse_schema" in res["recovery_hint"]
    assert isinstance(res["next_actions"], list) and len(res["next_actions"]) >= 1


def test_invalid_season_error_includes_season_recovery_hint(monkeypatch):
    from shared.tools import league as league_mod

    class _BadSeason:
        description = "standings"

        def invoke(self, args):
            return {"tool": "get_standings", "ok": False, "error": "Invalid season format: badseason; coverage starts 2009-10"}

    monkeypatch.setattr(league_mod, "get_standings", _BadSeason())
    tools = python_tools.catalogue()
    res = tools["get_standings"].invoke({"season": "badseason"})
    assert res["ok"] is False
    assert res["arg_miss"]["field"] == "season"
    assert res["arg_miss"]["kind"] == "season"
    assert res["arg_miss"]["value"] == "badseason"


def test_unknown_entity_error_includes_entity_recovery_hint(monkeypatch):
    from shared.tools import player as player_mod

    class _UnknownPlayer:
        description = "report"

        def invoke(self, args):
            return {"tool": "get_player_report", "ok": False, "error": "unknown player: Nobody Here"}

    monkeypatch.setattr(player_mod, "get_player_report", _UnknownPlayer())
    tools = python_tools.catalogue()
    res = tools["get_player_report"].invoke({"player": "Nobody Here"})
    assert res["ok"] is False
    assert res["arg_miss"]["field"] == "player"
    assert res["arg_miss"]["kind"] == "player"


def test_sql_column_error_attaches_schema_hint(monkeypatch):
    import shared.tools.sql_exec
    from shared.tools import league as league_mod

    sql_mod = sys.modules["shared.tools.sql_exec"]

    class _ColErr:
        description = "sql"

        async def ainvoke(self, args):
            return {
                "tool": "sql_exec",
                "ok": False,
                "error": 'Binder Error: Referenced column "TS_PCT" not found in FROM clause!',
            }

    monkeypatch.setattr(sql_mod, "sql_exec", _ColErr())
    monkeypatch.setattr(
        league_mod,
        "_get_warehouse_schema",
        lambda: (
            ["silver_player_season", "silver_hist_player_seasons"],
            {
                "silver_player_season": {"PLAYER": {}, "PPG": {}},
                "silver_hist_player_seasons": {"ts_pct": {}, "pts": {}},
            },
        ),
    )
    tools = python_tools.catalogue()
    res = asyncio.run(
        tools["sql_exec"].ainvoke({"sql": "SELECT TS_PCT FROM silver_player_season WHERE _season='2025-26'"})
    )
    assert res["ok"] is False
    hint = res["schema_hint"]
    assert hint["missing_column"] == "TS_PCT"
    assert hint["tables_with_column"] == ["silver_hist_player_seasons.ts_pct"]
    assert "silver_player_season" in hint["referenced_tables"]
    assert hint["referenced_tables"]["silver_player_season"] == ["PLAYER", "PPG"]


def test_sql_unknown_table_error_lists_declared_tables(monkeypatch):
    import shared.tools.sql_exec
    from shared.tools import league as league_mod

    sql_mod = sys.modules["shared.tools.sql_exec"]

    class _TableErr:
        description = "sql"

        async def ainvoke(self, args):
            return {
                "tool": "sql_exec",
                "ok": False,
                "error": "unknown or unavailable tables: silver_player_seasons",
            }

    monkeypatch.setattr(sql_mod, "sql_exec", _TableErr())
    monkeypatch.setattr(
        league_mod,
        "_get_warehouse_schema",
        lambda: (
            ["silver_player_season", "silver_hist_player_seasons"],
            {
                "silver_player_season": {"PLAYER": {}},
                "silver_hist_player_seasons": {"ts_pct": {}},
            },
        ),
    )
    tools = python_tools.catalogue()
    res = asyncio.run(tools["sql_exec"].ainvoke({"sql": "SELECT * FROM silver_player_seasons"}))
    assert res["ok"] is False
    hint = res["schema_hint"]
    assert hint["unknown_tables"] == ["silver_player_seasons"]
    assert hint.get("similar_tables") or hint.get("declared_tables")


def test_sql_timeout_error_has_no_schema_hint(monkeypatch):
    import shared.tools.sql_exec

    sql_mod = sys.modules["shared.tools.sql_exec"]

    class _TimeoutErr:
        description = "sql"

        async def ainvoke(self, args):
            return {"tool": "sql_exec", "ok": False, "error": "query exceeded 30s"}

    monkeypatch.setattr(sql_mod, "sql_exec", _TimeoutErr())
    tools = python_tools.catalogue()
    res = asyncio.run(tools["sql_exec"].ainvoke({"sql": "SELECT * FROM silver_standings"}))
    assert res["ok"] is False
    assert "schema_hint" not in res


def test_ok_result_does_not_add_error_recovery_keys(monkeypatch):
    from shared.tools import league as league_mod

    class _GoodStandings:
        description = "standings"

        def invoke(self, args):
            return {"tool": "get_standings", "ok": True, "rows": [{"team": "BOS", "wins": 60}]}

    monkeypatch.setattr(league_mod, "get_standings", _GoodStandings())
    tools = python_tools.catalogue()
    res = tools["get_standings"].invoke({"season": "2024-25"})
    assert res["ok"] is True
    assert "recovery_hint" not in res
    assert "next_actions" not in res
    assert "summary" not in res


def test_run_python_preserves_python_side_recovery_hint(monkeypatch, tmp_path):
    import duckdb
    from shared import store

    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    con.execute("CREATE TABLE silver_standings (TEAM TEXT, WINS INTEGER)")
    con.close()
    monkeypatch.setenv("DIME_WAREHOUSE", str(wh))
    monkeypatch.setattr(store, "WAREHOUSE", wh, raising=False)
    monkeypatch.setattr(store, "DB_PATH", wh, raising=False)
    monkeypatch.setattr(store, "connect", lambda **_kw: duckdb.connect(str(wh)))
    monkeypatch.setenv("DIME_THREAD_WORKSPACE", str(tmp_path))

    tools = python_tools.catalogue()
    res = asyncio.run(tools["run_python"].ainvoke({"code": 'x = 1\nprint("\nbroken")\nout = x'}))
    assert res["ok"] is False
    assert "unterminated" in res["error"]
    assert "triple" in res["recovery_hint"].lower()


def test_enrich_error_passes_success_shaped_payloads_without_ok_key():
    from analyst.tools.errors import enrich_error

    payload = {"threads": [{"id": "t1", "title": "x"}]}
    res = enrich_error("product_threads", dict(payload))
    assert res == payload
    assert "error" not in res
    assert "recovery_hint" not in res

    empty = {"runs": []}
    res = enrich_error("product_runs", dict(empty))
    assert res == empty
    assert "summary" not in res


def test_enrich_error_still_enriches_positive_failure_signals():
    from analyst.tools.errors import enrich_error

    explicit = enrich_error("product_x", {"ok": False, "reason": "ratings_table_empty"})
    assert "recovery_hint" in explicit
    assert explicit["error"]

    errored = enrich_error("product_y", {"error": "boom"})
    assert "next_actions" in errored
