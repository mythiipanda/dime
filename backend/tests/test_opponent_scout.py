import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _scratch_db(tmp_path):
    import duckdb

    db = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "create table silver_team_games (Team_ID BIGINT, Game_ID VARCHAR, "
        "GAME_DATE VARCHAR, MATCHUP VARCHAR, WL VARCHAR, MIN DOUBLE, "
        "FGM BIGINT, FG3M BIGINT, FGA BIGINT, FTM BIGINT, FTA BIGINT, "
        "OREB BIGINT, DREB BIGINT, REB BIGINT, AST BIGINT, STL BIGINT, "
        "BLK BIGINT, TOV BIGINT, PF BIGINT, PTS BIGINT, "
        "_season VARCHAR, _entity VARCHAR)")
    games = [
        (1610612752, "001", "APR 12, 2026", "NYK vs. CHA", "L", 240.0,
         34, 9, 80, 19, 24, 9, 30, 39, 20, 6, 4, 12, 18, 96, "2025-26",
         "team:1610612752"),
        (1610612766, "001", "APR 12, 2026", "NYK vs. CHA", "W", 240.0,
         40, 12, 88, 18, 22, 11, 33, 44, 25, 8, 3, 14, 19, 110, "2025-26",
         "team:1610612766"),
        (1610612752, "002", "APR 09, 2026", "NYK vs. BOS", "W", 240.0,
         42, 14, 90, 14, 16, 10, 34, 44, 27, 7, 5, 11, 20, 112, "2025-26",
         "team:1610612752"),
        (1610612738, "002", "APR 09, 2026", "NYK vs. BOS", "L", 240.0,
         38, 11, 85, 19, 22, 8, 36, 44, 24, 6, 6, 15, 21, 106, "2025-26",
         "team:1610612738"),
    ]
    con.executemany("insert into silver_team_games values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", games)
    con.execute(
        "create table silver_shots (TEAM_ID BIGINT, SHOT_ZONE_BASIC VARCHAR, "
        "SHOT_ATTEMPTED_FLAG BIGINT, SHOT_MADE_FLAG BIGINT, _season VARCHAR)")
    con.executemany(
        "insert into silver_shots values (1610612752, ?, ?, ?, '2025-26')",
        [("Restricted Area", 10, 8), ("Mid-Range", 10, 4),
         ("Above the Break 3", 20, 7)])
    con.execute(
        "create table silver_lineups (TEAM_ID BIGINT, GROUP_NAME VARCHAR, "
        "MIN DOUBLE, PLUS_MINUS DOUBLE, W BIGINT, L BIGINT, _season VARCHAR)")
    con.execute(
        "insert into silver_lineups values "
        "(1610612752, 'A - B - C - D - E', 120.0, 8.0, 9, 4, '2025-26')")
    con.execute(
        "create table silver_injury_entries (PLAYER VARCHAR, TEAM VARCHAR, "
        "TEAM_ABBR VARCHAR, STATUS VARCHAR, INJURY VARCHAR, "
        "RETURN_ESTIMATE VARCHAR, REPORT_DATE VARCHAR, _season VARCHAR)")
    con.execute(
        "insert into silver_injury_entries values "
        "('Jalen Brunson', 'New York Knicks', 'NYK', 'Out', 'ankle', "
        "'day-to-day', '2026-04-11', '2025-26')")
    return con


@pytest.fixture
def wh(tmp_path, monkeypatch):
    from shared import store

    _scratch_db(tmp_path).close()
    db = (tmp_path / "wh.duckdb").resolve()
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", db.parent / ".write.lock")
    yield db


def test_scout_sections(wh):
    from shared.tools.team.scouting import get_opponent_scout

    res = get_opponent_scout.invoke(
        {"team": "BOS", "opponent": "NYK", "season": "2025-26"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["opponent"]["abbrev"] == "NYK"
    form = rows["recent_form"]["rows"]
    assert form["last10_record"] == "1-1"
    assert len(form["games"]) == 2
    ff = rows["four_factors"]["rows"]
    assert ff["offense"]["efg_pct"] == pytest.approx((76 + 11.5) / 170, abs=1e-3)
    assert ff["defense"]["tov_pct"] > 0
    shots = rows["shot_profile"]["rows"]
    assert shots[0]["zone"] == "Above the Break 3"
    assert shots[0]["share"] == pytest.approx(0.5)
    assert shots[0]["fg_pct"] == pytest.approx(0.35)
    assert rows["top_lineups"]["rows"][0]["min"] == 120.0
    assert rows["injuries"]["rows"][0]["player"] == "Jalen Brunson"
    h2h = rows["head_to_head"]["rows"]
    assert h2h["record"] == "1-0"
    assert h2h["games"][0]["opp_pts"] == 106
    for section in ("recent_form", "four_factors", "shot_profile",
                    "top_lineups", "injuries", "head_to_head"):
        assert rows[section]["season"] == "2025-26"
        assert rows[section]["source"].startswith("silver_")


def test_scout_missing_tables(tmp_path, monkeypatch):
    import duckdb
    from shared import store

    db = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(db))
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db.resolve())
    monkeypatch.setattr(store, "LOCK_PATH", db.parent / ".write.lock")
    from shared.tools.team.scouting import get_opponent_scout

    res = get_opponent_scout.invoke(
        {"team": "BOS", "opponent": "NYK", "season": "2025-26"})
    assert res["ok"] is True
    assert res["rows"]["recent_form"]["note"] == "table not in warehouse"
    assert res["rows"]["injuries"]["note"] == "no injury table in warehouse"


def test_scout_bad_input(wh):
    from shared.tools.team.scouting import get_opponent_scout

    res = get_opponent_scout.invoke(
        {"team": "BOS", "opponent": "BOS", "season": "2025-26"})
    assert res["ok"] is False
    assert "different teams" in res["error"]
    res = get_opponent_scout.invoke(
        {"team": "", "opponent": "NYK", "season": "2025-26"})
    assert res["ok"] is False
