import duckdb
import polars as pl
import pytest

from shared import store
from shared.tools.league.expectations import get_expectations


@pytest.fixture()
def exp_db(tmp_path, monkeypatch):
    db = tmp_path / "exp.duckdb"
    con = duckdb.connect(str(db))
    proj = pl.DataFrame({
            'TEAM': ['BOS'] * 4,
            'TEAM_NAME': ['Boston Celtics'] * 4,
            'PROJECTED_WINS': [50.5, 55.0, 57.3, 55.0],
            'PROJECTED_LOSSES': [31.5, 27.0, 24.7, 27.0],
            'MAKE_PLAYOFFS_PCT': [0.9, 0.95, 1.0, 0.9],
            'WIN_TITLE_PCT': [0.1, 0.12, 0.15, 0.1],
            'RATING': [3.0, 5.0, 6.1, 4.0],
            'PROJECTION_MODEL': ['betiq_power_index'] * 4,
            'PROJECTION_SOURCE': ['teamrankings:betiq'] * 4,
            '_season': ['2024-25', '2025-26', '2026-27', '2027-28'],
            '_fetched_at': ['2026-11-19T00:00:00+00:00'] * 4,
        })
    con.execute("CREATE TABLE silver_preseason_projections AS SELECT * FROM proj")
    hist = pl.DataFrame({
            'season': [2025, 2026],
            'team_id': [1610612738, 1610612738],
            'wins': [61, 56],
            'losses': [21, 26],
            'win_pct': [0.744, 0.683],
        })
    con.execute("CREATE TABLE silver_hist_standings AS SELECT * FROM hist")
    gl = pl.DataFrame({
            'season': [2025] * 4,
            'team_id': [1610612738, 1610612752, 1610612738, 1610612752],
            'game_id': ['0022400001', '0022400001', '0022400002', '0022400002'],
            'pts': [120, 110, 115, 100],
            'fga': [90.0, 90.0, 90.0, 90.0],
            'fta': [20.0, 20.0, 20.0, 20.0],
            'tov': [12.0, 12.0, 12.0, 12.0],
            'oreb': [10.0, 10.0, 10.0, 10.0],
        })
    con.execute("CREATE TABLE silver_hist_gamelogs AS SELECT * FROM gl")
    cur = pl.DataFrame({
            'TeamID': [1610612738, 1610612738],
            'WINS': [10, 56], 'LOSSES': [5, 26], 'WinPCT': [0.667, 0.683],
            '_season': ['2026-27', '2025-26'],
        })
    con.execute("CREATE TABLE silver_standings AS SELECT * FROM cur")
    ratings = pl.DataFrame({
            'TEAM_ID': [1610612738], 'NET_RATING': [8.3],
            '_season': ['2026-27'],
        })
    con.execute("CREATE TABLE silver_team_ratings AS SELECT * FROM ratings")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    yield db


def test_expectations_completed_season(exp_db):
    res = get_expectations.invoke({"team": "BOS", "season": "2024-25"})
    assert res["ok"] is True
    row = res["rows"][0]
    assert row["projected_wins"] == 50.5
    assert row["actual_wins"] == 61
    assert row["status"] == "completed"
    assert row["wins_vs_projection"] == pytest.approx(10.5)
    assert row["net_rating"] is not None


def test_expectations_recent_seasons(exp_db):
    res = get_expectations.invoke({"team_id": 1610612738, "seasons": 2})
    assert res["ok"] is True
    assert [r["season"] for r in res["rows"]] == ["2026-27", "2027-28"]
    assert res["rows"][0]["status"] == "in_progress"
    assert res["rows"][0]["net_rating"] == 8.3
    assert "status" not in res["rows"][1]


def test_expectations_unplayed_season_has_no_actuals(exp_db):
    res = get_expectations.invoke({"team": "BOS", "season": "2027-28"})
    assert res["ok"] is True
    row = res["rows"][0]
    assert row["projected_wins"] == 55.0
    assert "actual_wins" not in row
    assert "status" not in row
    assert "wins_vs_projection" not in row


def test_expectations_standings_row_scoped_to_season(exp_db):
    res = get_expectations.invoke({"team": "BOS", "season": "2026-27"})
    assert res["ok"] is True
    row = res["rows"][0]
    assert row["actual_wins"] == 10
    assert row["games_played"] == 15
    assert row["status"] == "in_progress"


def test_expectations_missing_table(tmp_path, monkeypatch):
    db = tmp_path / "empty.duckdb"
    duckdb.connect(str(db)).close()
    monkeypatch.setattr(store, "DB_PATH", db)
    res = get_expectations.invoke({"team": "BOS"})
    assert res["ok"] is False
    assert "silver_preseason_projections" in res["error"]
