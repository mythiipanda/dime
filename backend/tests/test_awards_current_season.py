import sys
from pathlib import Path

import duckdb
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

BOTH_SEASONS = ("2025-26", "2026-27")
PRIOR_ONLY = ("2025-26",)
GAME_IDS = {"2025-26": "0022500001", "2026-27": "0022600001"}
PREFIXES = {"2025-26": "Prior", "2026-27": "Current"}


def _insert_player_rows(con, season: str, prefix: str) -> None:
    players = [
        (1, f"{prefix} Alpha", "BOS", 1, 50, 1650, 1250, 500, 400, 400, 70, 40, 1100, season),
        (2, f"{prefix} Beta", "LAL", 2, 50, 1650, 1500, 250, 180, 200, 50, 25, 1000, season),
        (3, f"{prefix} Gamma", "NYK", 3, 50, 1650, 1100, 350, 280, 300, 55, 30, 900, season),
    ]
    con.executemany("INSERT INTO silver_leaders_pts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", players)
    advanced = [
        (1, 25.0, 0.620, 8.0, 105.0, season),
        (2, 25.0, 0.590, 1.0, 112.0, season),
        (3, 25.0, 0.570, 4.0, 108.0, season),
    ]
    con.executemany("INSERT INTO silver_advanced VALUES (?,?,?,?,?,?)", advanced)
    standings = [
        (1, 39, 11, 110.0, season),
        (2, 20, 30, 116.0, season),
        (3, 28, 22, 113.0, season),
    ]
    con.executemany("INSERT INTO silver_standings VALUES (?,?,?,?,?)", standings)


@pytest.fixture()
def awards_warehouse(monkeypatch, tmp_path, request):
    boxscore_seasons, leader_seasons = getattr(
        request, "param", (BOTH_SEASONS, BOTH_SEASONS))
    path = tmp_path / "awards.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE silver_boxscores (GAME_ID VARCHAR, _season VARCHAR)")
        con.executemany(
            "INSERT INTO silver_boxscores VALUES (?, ?)",
            [(GAME_IDS[season], season) for season in boxscore_seasons],
        )
        con.execute(
            "CREATE TABLE silver_leaders_pts (PLAYER_ID INTEGER, PLAYER VARCHAR, "
            "TEAM VARCHAR, TEAM_ID INTEGER, GP INTEGER, MIN DOUBLE, PTS DOUBLE, "
            "REB DOUBLE, DREB DOUBLE, AST DOUBLE, STL DOUBLE, BLK DOUBLE, "
            "EFF DOUBLE, _season VARCHAR)"
        )
        con.execute(
            "CREATE TABLE silver_advanced (PLAYER_ID INTEGER, AGE DOUBLE, "
            "TS_PCT DOUBLE, NET_RATING DOUBLE, DEF_RATING DOUBLE, _season VARCHAR)"
        )
        con.execute(
            "CREATE TABLE silver_standings (TeamID INTEGER, WINS INTEGER, "
            "LOSSES INTEGER, OppPointsPG DOUBLE, _season VARCHAR)"
        )
        for season in leader_seasons:
            _insert_player_rows(con, season, PREFIXES[season])
    finally:
        con.close()

    from shared import coverage, store
    from shared.tools import _core

    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    store.warehouse_identity_cache_clear()
    coverage.coverage_cache_clear()
    _core.last_completed_season_cache_clear()
    yield path
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    store.warehouse_identity_cache_clear()
    coverage.coverage_cache_clear()
    _core.last_completed_season_cache_clear()


def test_award_race_defaults_to_latest_covered_input_season(awards_warehouse):
    from shared.tools.awards import get_award_race

    race = get_award_race.invoke({"award": "MVP"})

    assert race["ok"] is True, race
    assert race["meta"]["season"] == "2026-27"
    assert {row["player"] for row in race["rows"]["candidates"]} <= {
        "Current Alpha", "Current Beta", "Current Gamma"
    }


@pytest.mark.parametrize("awards_warehouse", [(PRIOR_ONLY, BOTH_SEASONS)], indirect=True)
def test_award_race_default_follows_leaders_when_leaders_are_ahead(awards_warehouse):
    from shared.tools.awards import get_award_race

    race = get_award_race.invoke({"award": "MVP"})

    assert race["ok"] is True, race
    assert race["meta"]["season"] == "2026-27"
    assert {row["player"] for row in race["rows"]["candidates"]} <= {
        "Current Alpha", "Current Beta", "Current Gamma"
    }


@pytest.mark.parametrize("awards_warehouse", [(BOTH_SEASONS, PRIOR_ONLY)], indirect=True)
def test_award_race_default_stays_on_prior_leaders_season(awards_warehouse):
    from shared.tools.awards import get_award_race

    race = get_award_race.invoke({"award": "MVP"})

    assert race["ok"] is True, race
    assert race["meta"]["season"] == "2025-26"
    assert {row["player"] for row in race["rows"]["candidates"]} <= {
        "Prior Alpha", "Prior Beta", "Prior Gamma"
    }


def test_product_awards_season_uses_latest_covered_input_season(awards_warehouse):
    from analyst.direct_data import product_awards

    payload = product_awards.invoke({"season": ""})

    assert payload["season"] == "2026-27"
    boards = {board["award"]: board for board in payload["awards"]}
    assert boards["MVP"]["season"] == "2026-27"


def test_team_win_percentage_driver_remains_fraction_scale(awards_warehouse):
    from shared.tools.awards import get_award_race

    race = get_award_race.invoke({"award": "MVP", "season": "2026-27"})

    assert race["ok"] is True, race
    alpha = next(row for row in race["rows"]["candidates"] if row["player"] == "Current Alpha")
    driver = next(row for row in alpha["drivers"] if row["stat"] == "team win%")
    assert driver["value"] == pytest.approx(0.78)
    assert "team win% at 78.0" in alpha["case_for"]
