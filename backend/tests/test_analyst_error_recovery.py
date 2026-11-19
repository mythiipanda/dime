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
    assert "2024-25" in res["recovery_hint"]
    assert "get_warehouse_freshness" in res["next_actions"]


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
    assert isinstance(res["summary"], str) and "get_player_report" in res["summary"]
    assert "get_standings" in res["next_actions"]


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
