import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import polars as pl
import pytest

import seed_stints as seed
from shared import store

GAME = "0042500405"
HOME = 1610612759
AWAY = 1610612752
HOME_FLOOR = [1628368, 1630170, 1630577, 1641705, 1642264]
AWAY_FLOOR = [1626157, 1628384, 1628404, 1628969, 1628973]
ALT_HOME = [1628368, 1630170, 1630577, 1641705, 200001]


def _poss(game, n, offense, points, start_sec, end_sec, off, deff):
    row = {
        "game_id": game,
        "possession_number": n,
        "period": 1,
        "start_seconds_remaining": start_sec,
        "end_seconds_remaining": end_sec,
        "offense_team_id": offense,
        "points": points,
        "_season": "2025-26",
    }
    for i, pid in enumerate(off, 1):
        row[f"off_player_{i}"] = pid
    for i, pid in enumerate(deff, 1):
        row[f"def_player_{i}"] = pid
    return row


def _source_rows():
    return [
        _poss(GAME, 1, AWAY, 0, 720.0, 692.0, AWAY_FLOOR, HOME_FLOOR),
        _poss(GAME, 2, HOME, 2, 672.0, 668.0, HOME_FLOOR, AWAY_FLOOR),
        _poss(GAME, 3, AWAY, 3, 645.0, 643.0, AWAY_FLOOR, ALT_HOME),
    ]


def _gamelogs():
    return [
        {"game_id": GAME, "team_id": HOME, "matchup": "SAS vs. NYK",
         "team_abbreviation": "SAS"},
        {"game_id": GAME, "team_id": AWAY, "matchup": "NYK @ SAS",
         "team_abbreviation": "NYK"},
    ]


@pytest.fixture
def dbs(monkeypatch, tmp_path):
    source = tmp_path / "source.duckdb"
    con = duckdb.connect(str(source))
    con.execute("DROP TABLE IF EXISTS silver_hist_possessions")
    con.execute("DROP TABLE IF EXISTS silver_hist_gamelogs")
    pframe = pl.DataFrame(_source_rows())
    con.register("_p", pframe.to_arrow())
    con.execute(
        "CREATE TABLE silver_hist_possessions AS SELECT * FROM _p")
    con.unregister("_p")
    gframe = pl.DataFrame(_gamelogs())
    con.register("_g", gframe.to_arrow())
    con.execute(
        "CREATE TABLE silver_hist_gamelogs AS SELECT * FROM _g")
    con.unregister("_g")
    con.close()
    target = tmp_path / "stints.duckdb"
    monkeypatch.setattr(store, "DB_PATH", target)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    return source, target


def _source_con(path):
    return duckdb.connect(str(path), read_only=True)


def _target_rows(game):
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_stints" not in tables:
            return []
        return con.execute(
            "SELECT stint_number, poss_start, poss_end, score_home_out, "
            "score_away_out, home_swing FROM silver_stints "
            "WHERE game_id = ? ORDER BY stint_number",
            [game]).fetchall()
    finally:
        con.close()


def test_materialize_game_writes_stints_and_watermark(dbs):
    source, _ = dbs
    con = _source_con(source)
    try:
        ok, note = seed.materialize_game(con, GAME)
    finally:
        con.close()
    assert ok
    assert note == "2 stints"
    assert _target_rows(GAME) == [
        (1, 1, 2, 2, 0, 2),
        (2, 3, 3, 2, 3, -3),
    ]
    assert store.last_fetch("silver_stints", "2025-26", GAME)


def test_materialize_game_rerun_is_idempotent(dbs):
    source, _ = dbs
    con = _source_con(source)
    try:
        assert seed.materialize_game(con, GAME)[0]
        assert seed.materialize_game(con, GAME)[0]
    finally:
        con.close()
    assert len(_target_rows(GAME)) == 2
    assert store.last_fetch("silver_stints", "2025-26", GAME)


def test_materialize_unknown_game_reports_no_rows(dbs):
    source, _ = dbs
    con = _source_con(source)
    try:
        ok, note = seed.materialize_game(con, "0000000000")
    finally:
        con.close()
    assert not ok
    assert note == "no possession rows"
    assert "0000000000" not in seed._completed_entities("2025-26")


def test_crash_before_watermark_leaves_clean_resume(dbs):
    source, _ = dbs
    con = _source_con(source)
    rows, season = seed.load_possessions(con, GAME)
    placed = seed.resolve_home_away(con, GAME)
    con.close()
    assert placed is not None
    frame = seed.stints_frame(GAME, rows, season, placed)
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.write_unit(
            "silver_stints", frame, season, seed.SOURCE, GAME,
            "game_id = ?", [GAME], _fault="after_insert")
    assert _target_rows(GAME) == []
    assert not store.last_fetch("silver_stints", season, GAME)
    con = _source_con(source)
    try:
        ok, _ = seed.materialize_game(con, GAME)
    finally:
        con.close()
    assert ok
    assert len(_target_rows(GAME)) == 2
    assert store.last_fetch("silver_stints", season, GAME)


def test_resolve_home_away_from_matchups(dbs):
    source, _ = dbs
    con = _source_con(source)
    try:
        assert seed.resolve_home_away(con, GAME) == (
            HOME, AWAY, "SAS", "NYK")
    finally:
        con.close()


def test_resolve_home_away_unknown_game_is_none(dbs):
    source, _ = dbs
    con = _source_con(source)
    try:
        assert seed.resolve_home_away(con, "0000000000") is None
    finally:
        con.close()


def test_materialize_games_skips_completed_entities(dbs):
    source, _ = dbs
    done, skipped, failed = seed._materialize_games(
        ["2025-26"], {"2025-26": [GAME]}, str(source))
    assert (done, skipped, failed) == (1, 0, 0)
    done, skipped, failed = seed._materialize_games(
        ["2025-26"], {"2025-26": [GAME]}, str(source))
    assert (done, skipped, failed) == (0, 1, 0)


def test_materialize_games_budget_stops_cleanly(dbs):
    source, _ = dbs
    done, skipped, failed = seed._materialize_games(
        ["2025-26"], {"2025-26": [GAME]}, str(source),
        budget_seconds=1e-9)
    assert (done, skipped, failed) == (0, 0, 0)


def test_main_dry_run_prints_season_plan(monkeypatch, tmp_path, capsys):
    source = tmp_path / "unused.duckdb"
    monkeypatch.setattr(seed, "season_games", lambda db, season: ["game-a"])
    target = tmp_path / "target.duckdb"
    result = seed.main([
        "--db", str(target), "--source-db", str(source),
        "--season", "2024-25", "--dry-run",
    ])
    assert result == 0
    assert capsys.readouterr().out.splitlines()[-2:] == [
        f"{seed.TABLE} 2024-25 game-a",
        "games: 1",
    ]
