
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402

EDWARDS = "Anthony Edwards"
LUKA = "Luka Don\u010di\u0107"

Q_DIET = f"Compare {EDWARDS}' shot diet to {LUKA}'s."
Q_LINE = (f"Compare how {EDWARDS} and {LUKA} generate their scoring "
          f"this season: who leans more on getting to the line?")


@pytest.fixture
def warehouse(monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools import _core as core
    from v2.adapters import coverage as cov

    db = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE silver_boxscores "
                "(GAME_ID VARCHAR, _season VARCHAR, _entity VARCHAR)")
    con.execute("INSERT INTO silver_boxscores VALUES "
                "('0022400001', '2024-25', 'game:0022400001'),"
                "('0022500001', '2025-26', 'game:0022500001')")
    con.close()
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    monkeypatch.setattr(store, "DB_PATH", db)
    core.last_completed_season_cache_clear()
    cov.coverage_cache_clear()
    return db


def _side(name, team, clutch):
    return {
        "name": name, "team": team, "gp": 20, "ppg": 28.0, "rpg": 6.0,
        "apg": 5.0, "ts_pct": 0.61, "efg_pct": 0.55,
        "rim_share": 0.375, "three_share": 0.5,
        "ft_points_share": 0.179, "fg_points_share": 0.821,
        "clutch_pts": clutch, "net_onoff": 7.0,
    }


def _compare_out(a, b, note=None):
    return {
        "tool": "get_compare", "ok": True,
        "rows": {"a": a, "b": b,
                 "pair": {"h2h_meetings": [], "note": note}},
        "meta": {"source": "warehouse", "season": "2024-25"},
    }


class _FakeCompare:
    name = "get_compare"

    def __init__(self, out):
        self._out = out

    async def ainvoke(self, args):
        return dict(self._out)


def _drain(question, out, monkeypatch):
    import shared.tools as tools_mod

    monkeypatch.setattr(tools_mod, "v1_tools", [_FakeCompare(out)])

    async def _go():
        state = {"question": question, "history": [],
                 "tool_results": [], "calls_made": [], "round": 0}
        async for _e in _triage_seed(question, "primary", "model", state):
            pass
        return state

    return asyncio.run(_go())


def _answer(state):
    meta = state["tool_results"][-1].get("meta") or {}
    return meta.get("deterministic_answer") or ""


def test_shot_diet_lines_rendered(monkeypatch, warehouse):
    out = _compare_out(_side(EDWARDS, "MIN", 88),
                       _side(LUKA, "DAL", 121))
    ans = _answer(_drain(Q_DIET, out, monkeypatch))
    assert "37.5% at the rim" in ans
    assert "50.0% from three" in ans


def test_scoring_source_lines_and_line_verdict(monkeypatch, warehouse):
    out = _compare_out(_side(EDWARDS, "MIN", 88),
                       _side(LUKA, "DAL", 121))
    ans = _answer(_drain(Q_LINE, out, monkeypatch))
    assert "17.9% of scoring from free throws" in ans
    assert "82.1% from field goals" in ans
    assert "leans more on getting to the line" not in ans


def test_line_lean_verdict_names_higher_share(monkeypatch, warehouse):
    a = _side(EDWARDS, "MIN", 88)
    b = _side(LUKA, "DAL", 121)
    b["ft_points_share"] = 0.25
    b["fg_points_share"] = 0.75
    ans = _answer(_drain(Q_LINE, _compare_out(a, b), monkeypatch))
    assert f"{LUKA} leans more on getting to the line" in ans
    assert "25.0% vs 17.9%" in ans


def test_clutch_line_rendered(monkeypatch, warehouse):
    out = _compare_out(_side(EDWARDS, "MIN", 88),
                       _side(LUKA, "DAL", 121))
    ans = _answer(_drain(Q_DIET, out, monkeypatch))
    assert f"Clutch scoring: {EDWARDS} 88 pts vs {LUKA} 121 pts" in ans


def test_missing_dims_keep_base_lines(monkeypatch, warehouse):
    a = {"name": EDWARDS, "team": "MIN", "gp": 20, "ppg": 28.0,
         "rpg": 6.0, "apg": 5.0, "ts_pct": 0.61,
         "rim_share": None, "three_share": None,
         "ft_points_share": None, "fg_points_share": None,
         "clutch_pts": None}
    b = dict(a)
    b["name"] = LUKA
    ans = _answer(_drain(Q_DIET, _compare_out(a, b), monkeypatch))
    assert EDWARDS in ans and LUKA in ans
    assert "shot diet" not in ans
    assert "free throws" not in ans
    assert "Clutch scoring" not in ans
