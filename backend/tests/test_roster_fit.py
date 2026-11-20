import duckdb
import polars as pl
import pytest

from shared import store
from shared.tools.league.roster_fit import get_roster_fit


def _players() -> pl.DataFrame:
    rows = []
    for i, ab in enumerate(["BOS", "NYK", "OKC"]):
        for j in range(8):
            rows.append({
                "PLAYER_ID": i * 100 + j + 1,
                "PLAYER": f"P{i}{j}",
                "TEAM": ab,
                "GP": 80,
                "MIN": 2000.0 - j * 150,
                "PTS": 3000.0 if j == 0 else 800.0,
                "AST": 700.0 if ab == "NYK" else 200.0,
                "STL": 160.0 if ab == "OKC" else 40.0,
                "BLK": 200.0 if ab == "OKC" else 30.0,
                "FGA": 1200.0,
                "FG3A": 700.0 if ab == "BOS" else 200.0,
                "FG3_PCT": 0.4 if ab == "BOS" else 0.3,
                "_season": "2025-26",
            })
    return pl.DataFrame(rows)


@pytest.fixture()
def fit_db(tmp_path, monkeypatch):
    db = tmp_path / "fit.duckdb"
    con = duckdb.connect(str(db))
    players = _players()
    con.execute("CREATE TABLE silver_leaders_pts AS SELECT * FROM players")
    standings = pl.DataFrame({
        'season': [2026] * 3,
        'team_id': [1610612760, 1610612738, 1610612752],
        'win_pct': [0.8, 0.6, 0.5],
    })
    con.execute("CREATE TABLE silver_hist_standings AS SELECT * FROM standings")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    yield db


def test_roster_fit_returns_dimensions(fit_db):
    res = get_roster_fit.invoke({"team": "BOS", "season": "2025-26"})
    assert res["ok"] is True
    dims = {r["dimension"]: r for r in res["rows"]}
    assert set(dims) == {"spacing", "creation", "rim_protection",
                         "defense", "depth"}
    assert dims["spacing"]["team"] == 1.0
    assert dims["defense"]["contender_avg"] is not None
    assert res["biggest_gaps"]


def test_roster_fit_gap_ranking(fit_db):
    res = get_roster_fit.invoke({"team": "NYK", "season": "2025-26"})
    assert res["ok"] is True
    assert res["biggest_gaps"][0] == "spacing"
    assert "defense" in res["biggest_gaps"]


def test_roster_fit_missing_table(tmp_path, monkeypatch):
    db = tmp_path / "empty.duckdb"
    duckdb.connect(str(db)).close()
    monkeypatch.setattr(store, "DB_PATH", db)
    res = get_roster_fit.invoke({"team": "BOS"})
    assert res["ok"] is False
    assert "silver_leaders_pts" in res["error"]
