import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import get_salary_history


def _probe():
    r = get_salary_history.invoke({})
    if r["ok"] is False and "not seeded" in r.get("error", ""):
        pytest.skip(f"salary tables absent in this warehouse: {r['error']}")
    return r


def test_registered_in_tool_registry():
    from shared import tools
    assert "get_salary_history" in tools.TOOL_NAMES


def test_player_mode_career_and_cap_share():
    _probe()
    r = get_salary_history.invoke({"player": "Tim Duncan"})
    assert r["ok"] is True
    assert len(r["rows"]) >= 15
    first = r["rows"][0]
    assert first["PLAYER_NAME"] == "Tim Duncan"
    assert first["SEASON"] == "1997-98"
    assert first["salary_cap"] > 0
    assert 0 < first["share_of_cap"] < 1


def test_team_mode_payroll_vs_cap():
    _probe()
    r = get_salary_history.invoke({"team": "LAL", "season": "2003-04"})
    assert r["ok"] is True
    s = r["summary"]
    assert s["payroll"] > 0
    assert s["payroll_rank"] is not None
    assert s["salary_cap"] == 43840000.0
    assert s["over_tax"] is True
    assert sum(row["salary"] for row in r["rows"]) <= s["payroll"]


def test_league_mode_landscape():
    _probe()
    r = get_salary_history.invoke({"season": "2003-04"})
    assert r["ok"] is True
    s = r["summary"]
    assert s["players"] > 400
    assert s["max_salary"] == 28000000
    assert r["rows"][0]["salary"] == s["max_salary"]


def test_cap_table_mode_lists_every_season():
    r = _probe()
    assert r["ok"] is True
    assert len(r["rows"]) >= 42
    last = r["rows"][-1]
    assert last["season"] == "2026-27"
    assert last["apron_1"] > 0


def test_player_and_team_is_an_error():
    r = get_salary_history.invoke({"player": "Kobe Bryant", "team": "LAL"})
    assert r["ok"] is False
    assert r["rows"] == []


def test_unknown_player_is_an_error():
    _probe()
    r = get_salary_history.invoke({"player": "Notareal Player"})
    assert r["ok"] is False
    assert r["rows"] == [] and r["columns"] == []
