
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph  # noqa: E402
from app.graph import (  # noqa: E402
    _bare_season,
    _compute_fallback,
    _default_season,
    _explicit_season,
    presentation_agent,
)

Q7 = ("How did LeBron play in the 2014 season? "
      "Give me a full season summary.")


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
                "('0021900001', '2019-20', 'game:0021900001'),"
                "('0022400001', '2024-25', 'game:0022400001')")
    con.execute("CREATE TABLE silver_player_season "
                "(PLAYER_ID INTEGER, PLAYER VARCHAR, TEAM VARCHAR, "
                " GP INTEGER, MPG DOUBLE, PPG DOUBLE, RPG DOUBLE, "
                " APG DOUBLE, FG_PCT DOUBLE, FG3_PCT DOUBLE, "
                " FT_PCT DOUBLE, TS_PCT DOUBLE, _season VARCHAR)")
    con.execute("INSERT INTO silver_player_season VALUES "
                "(2544, 'LeBron James', 'LAL', 67, 34.6, 25.3, 7.8, 10.2, "
                " 0.49, 0.348, 0.693, 0.577, '2019-20'),"
                "(2544, 'LeBron James', 'LAL', 70, 35.0, 24.4, 7.8, 8.2, "
                " 0.51, 0.376, 0.750, 0.600, '2024-25')")
    con.execute("CREATE TABLE silver_hist_player_seasons "
                "(player_id INTEGER, player_name VARCHAR, "
                " team_abbreviation VARCHAR, age INTEGER, gp INTEGER, "
                " min DOUBLE, pts DOUBLE, reb DOUBLE, ast DOUBLE, "
                " stl DOUBLE, blk DOUBLE, fg_pct DOUBLE, fg3_pct DOUBLE, "
                " ft_pct DOUBLE, ts_pct DOUBLE, _season VARCHAR)")
    con.close()
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    monkeypatch.setattr(store, "DB_PATH", db)
    core.last_completed_season_cache_clear()
    cov.coverage_cache_clear()
    return db


def test_bare_year_resolves_to_prior_slug():
    assert _bare_season(Q7) == "2013-14"
    assert _bare_season("best in the 1998 season") == "1997-98"
    assert _bare_season("how is scoring this season?") is None
    assert _bare_season("who led in 2019-20?") is None


def test_default_and_explicit_season_honor_bare_year():
    assert _default_season(Q7) == "2013-14"
    assert _explicit_season(Q7) == "2013-14"


def test_fallback_copy_has_no_plumbing_string():
    assert "didn't come back from the dataset" not in _compute_fallback()
    assert "Finals" in _compute_fallback()


def test_uncovered_season_fails_closed_with_coverage(warehouse):
    from shared.tools.player import get_season_averages

    out = get_season_averages.invoke(
        {"player_id": 2544, "season": "2013-14"})
    assert out.get("ok") is False
    assert out.get("season_error") is True
    assert "2013-14" in out.get("error")
    assert "2019-20" in out.get("error")
    assert "2024-25" in out.get("error")


def test_covered_season_returns_line(warehouse):
    from shared.tools.player import get_season_averages

    out = get_season_averages.invoke(
        {"player_id": 2544, "season": "2019-20"})
    assert out.get("ok") is True
    assert out["rows"][0]["PPG"] == 25.3


def test_player_report_propagates_season_error(warehouse):
    from shared.tools.player import get_player_report

    out = get_player_report.invoke(
        {"player": 2544, "season": "2013-14"})
    assert out.get("ok") is False
    assert out.get("season_error") is True


def test_presentation_surfaces_season_refusal(warehouse):
    from shared.tools.player import get_season_averages

    refused = get_season_averages.invoke(
        {"player_id": 2544, "season": "2013-14"})

    async def _go():
        state = {"question": Q7,
                 "analysis": "No data came back.",
                 "tool_results": [dict(refused)],
                 "calls_made": [], "history": [],
                 "primary": "p", "model": "m"}
        async for event in presentation_agent(state):
            if event.get("type") == "final_answer":
                return event["data"]["text"]
        raise AssertionError("no final answer")

    answer = asyncio.run(_go())
    assert "2013-14" in answer
    assert "didn't come back from the dataset" not in answer
    assert graph._compute_fallback() not in answer
