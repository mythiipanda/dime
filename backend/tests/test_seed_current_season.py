import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import seed_current_season as seed
from shared import store


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "warehouse.duckdb"
    import duckdb
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE TABLE silver_hist_gamelogs (season_id VARCHAR, "
        "team_id INTEGER, team_abbreviation VARCHAR, team_name VARCHAR, "
        "game_id VARCHAR, game_date VARCHAR, matchup VARCHAR, wl VARCHAR, "
        "min DOUBLE, fgm DOUBLE, fga DOUBLE, fg_pct DOUBLE, fg3m DOUBLE, "
        "fg3a DOUBLE, fg3_pct DOUBLE, ftm DOUBLE, fta DOUBLE, ft_pct DOUBLE, "
        "oreb DOUBLE, dreb DOUBLE, reb DOUBLE, ast DOUBLE, stl DOUBLE, "
        "blk DOUBLE, tov DOUBLE, pf DOUBLE, pts DOUBLE, plus_minus DOUBLE, "
        "video_available INTEGER, season INTEGER, season_type VARCHAR, "
        "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, "
        "_entity VARCHAR)")
    con.execute(
        "CREATE TABLE silver_team_games (\"Team_ID\" INTEGER, "
        "\"Game_ID\" VARCHAR, \"GAME_DATE\" VARCHAR, \"MATCHUP\" VARCHAR, "
        "\"WL\" VARCHAR, \"W\" BIGINT, \"L\" BIGINT, \"W_PCT\" DOUBLE, "
        "\"MIN\" DOUBLE, \"FGM\" DOUBLE, \"FGA\" DOUBLE, \"FG_PCT\" DOUBLE, "
        "\"FG3M\" DOUBLE, \"FG3A\" DOUBLE, \"FG3_PCT\" DOUBLE, "
        "\"FTM\" DOUBLE, \"FTA\" DOUBLE, \"FT_PCT\" DOUBLE, "
        "\"OREB\" DOUBLE, \"DREB\" DOUBLE, \"REB\" DOUBLE, \"AST\" DOUBLE, "
        "\"STL\" DOUBLE, \"BLK\" DOUBLE, \"TOV\" DOUBLE, \"PF\" DOUBLE, "
        "\"PTS\" DOUBLE, _source VARCHAR, _season VARCHAR, "
        "_fetched_at VARCHAR, _entity VARCHAR)")
    con.execute(
        "CREATE TABLE silver_player_gamelogs (\"SEASON_ID\" VARCHAR, "
        "\"Player_ID\" INTEGER, \"Game_ID\" VARCHAR, \"GAME_DATE\" VARCHAR, "
        "\"MATCHUP\" VARCHAR, \"WL\" VARCHAR, \"MIN\" DOUBLE, \"FGM\" DOUBLE, "
        "\"FGA\" DOUBLE, \"FG_PCT\" DOUBLE, \"FG3M\" DOUBLE, \"FG3A\" DOUBLE, "
        "\"FG3_PCT\" DOUBLE, \"FTM\" DOUBLE, \"FTA\" DOUBLE, "
        "\"FT_PCT\" DOUBLE, \"OREB\" DOUBLE, \"DREB\" DOUBLE, "
        "\"REB\" DOUBLE, \"AST\" DOUBLE, \"STL\" DOUBLE, \"BLK\" DOUBLE, "
        "\"TOV\" DOUBLE, \"PF\" DOUBLE, \"PTS\" DOUBLE, "
        "\"PLUS_MINUS\" DOUBLE, \"VIDEO_AVAILABLE\" INTEGER, "
        "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, "
        "_entity VARCHAR)")
    con.execute(
        "CREATE TABLE silver_player_season (\"PLAYER_ID\" INTEGER, "
        "\"PLAYER\" VARCHAR, \"TEAM\" VARCHAR, \"AGE\" DOUBLE, \"GP\" BIGINT, "
        "\"GS\" INTEGER, \"MPG\" DOUBLE, \"PPG\" DOUBLE, \"RPG\" DOUBLE, "
        "\"APG\" DOUBLE, \"SPG\" DOUBLE, \"BPG\" DOUBLE, \"FG_PCT\" DOUBLE, "
        "\"FG3_PCT\" DOUBLE, \"FT_PCT\" DOUBLE, _source VARCHAR, "
        "_season VARCHAR, _fetched_at VARCHAR, _entity VARCHAR)")
    con.close()
    return db


PGL = pl.DataFrame({
    "season_id": ["22026", "22026"],
    "player_id": [1, 1],
    "player_name": ["Test Player", "Test Player"],
    "team_id": [10, 10],
    "team_abbreviation": ["BOS", "BOS"],
    "team_name": ["Boston Celtics", "Boston Celtics"],
    "game_id": ["0022600001", "0022600002"],
    "game_date": ["2026-10-20", "2026-10-22"],
    "matchup": ["BOS @ DET", "BOS vs. MIA"],
    "wl": ["W", "L"],
    "min": [30.0, 34.0],
    "fgm": [10.0, 8.0], "fga": [20.0, 20.0],
    "fg_pct": [0.5, 0.4], "fg3m": [2.0, 1.0],
    "fg3a": [5.0, 4.0], "fg3_pct": [0.4, 0.25],
    "ftm": [4.0, 5.0], "fta": [5.0, 6.0],
    "ft_pct": [0.8, 0.833],
    "oreb": [1.0, 0.0], "dreb": [5.0, 6.0], "reb": [6.0, 6.0],
    "ast": [7.0, 9.0], "stl": [1.0, 2.0], "blk": [0.0, 1.0],
    "tov": [3.0, 2.0], "pf": [2.0, 4.0],
    "pts": [26.0, 22.0], "plus_minus": [5.0, -3.0],
    "season_type": ["regular-season", "regular-season"],
})

TGL = pl.DataFrame({
    "season_id": ["22026", "22026"],
    "team_id": [10, 10],
    "team_abbreviation": ["BOS", "BOS"],
    "team_name": ["Boston Celtics", "Boston Celtics"],
    "game_id": ["0022600001", "0022600002"],
    "game_date": ["2026-10-20", "2026-10-22"],
    "matchup": ["BOS @ DET", "BOS vs. MIA"],
    "wl": ["W", "L"],
    "min": [240.0, 240.0],
    "fgm": [40.0, 38.0], "fga": [90.0, 88.0],
    "fg_pct": [0.444, 0.432], "fg3m": [15.0, 12.0],
    "fg3a": [40.0, 38.0], "fg3_pct": [0.375, 0.316],
    "ftm": [18.0, 20.0], "fta": [22.0, 25.0],
    "ft_pct": [0.818, 0.8],
    "oreb": [10.0, 8.0], "dreb": [30.0, 32.0], "reb": [40.0, 40.0],
    "ast": [25.0, 22.0], "stl": [8.0, 6.0], "blk": [5.0, 4.0],
    "tov": [12.0, 14.0], "pf": [18.0, 20.0],
    "pts": [113.0, 108.0], "plus_minus": [5.0, -5.0],
    "video_available": [1, 1],
    "season_type": ["regular-season", "regular-season"],
})

PSS = pl.DataFrame({
    "player_id": [1],
    "player_name": ["Test Player"],
    "team_abbreviation": ["BOS"],
    "age": [27.0],
    "gp": [2],
    "min": [32.0],
    "season_type": ["regular-season"],
})


def _add_legacy_ts_rows(db: Path,
                        rows: list[tuple[int, str, str | None]]) -> None:
    con = duckdb.connect(str(db))
    try:
        con.execute(
            'ALTER TABLE silver_player_season ADD COLUMN "TS_PCT" VARCHAR')
        con.execute(
            'ALTER TABLE silver_player_season ADD COLUMN "_prov_TS_PCT" VARCHAR')
        con.executemany(
            'INSERT INTO silver_player_season ("PLAYER_ID", "PLAYER", '
            '"TEAM", "TS_PCT", "_prov_TS_PCT", _source, _season, '
            '_fetched_at, _entity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [(pid, name, "BOS", value, f"prov:{pid}", "fixture",
              "2025-26", "2026-01-01", "league")
             for pid, name, value in rows])
    finally:
        con.close()


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setattr(store, "CANONICAL_DB_PATH",
                        tmp_path / "canonical.duckdb")
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    frames = {
        "team_game_logs": TGL,
        "player_game_logs": PGL,
        "player_season_stats": PSS,
    }

    def fake_read(url):
        for key, frame in frames.items():
            if key in url:
                return frame
        raise AssertionError(url)

    monkeypatch.setattr(seed.pl, "read_parquet", fake_read)
    return db


def test_end_year():
    assert seed.end_year("2026-27") == 2027
    with pytest.raises(ValueError):
        seed.end_year("2027")


def test_resolve_target_refuses_canonical(monkeypatch, tmp_path):
    canon = tmp_path / "canon.duckdb"
    monkeypatch.setattr(store, "CANONICAL_DB_PATH", canon.resolve())
    monkeypatch.setenv("DIME_WAREHOUSE", str(canon))
    assert seed.resolve_target(None) is None


def test_load_hist_gamelogs(scratch):
    n = seed.load_hist_gamelogs("2026-27", dry_run=False)
    assert n == 2
    con = store.connect()
    rows = con.execute(
        "SELECT season, season_type, _source, _season FROM "
        "silver_hist_gamelogs").fetchall()
    con.close()
    assert rows == [(2027, "regular-season",
                     seed.SRC_TGL, "2026-27")] * 2


def test_load_player_gamelogs(scratch):
    n = seed.load_player_gamelogs("2026-27", dry_run=False)
    assert n == 2
    con = store.connect()
    row = con.execute(
        "SELECT \"Player_ID\", \"GAME_DATE\", \"PTS\", _season FROM "
        "silver_player_gamelogs ORDER BY \"Game_ID\" LIMIT 1").fetchone()
    con.close()
    assert row == (1, "Oct 20, 2026", 26.0, "2026-27")


def test_build_team_games(scratch):
    seed.load_hist_gamelogs("2026-27", dry_run=False)
    n = seed.build_team_games("2026-27", dry_run=False)
    assert n == 2
    con = store.connect()
    rows = con.execute(
        "SELECT \"W\", \"L\", \"W_PCT\", \"GAME_DATE\" FROM "
        "silver_team_games ORDER BY \"Game_ID\"").fetchall()
    con.close()
    assert rows == [(1, 0, 1.0, "OCT 20, 2026"),
                    (1, 1, 0.5, "OCT 22, 2026")]


def test_load_player_season(scratch):
    n = seed.load_player_season("2026-27", dry_run=False)
    assert n == 1
    con = store.connect()
    row = con.execute(
        "SELECT \"PLAYER\", \"GP\", \"MPG\", \"PPG\", \"FG_PCT\", \"AGE\" "
        "FROM silver_player_season").fetchone()
    con.close()
    assert row == ("Test Player", 2, 32.0, 24.0, 0.45, 27.0)


def test_load_player_season_populates_ts_pct(scratch):
    n = seed.load_player_season("2026-27", dry_run=False)
    assert n == 1
    con = store.connect()
    row = con.execute(
        "SELECT \"TS_PCT\" FROM silver_player_season").fetchone()
    con.close()
    assert row is not None and row[0] is not None
    assert abs(row[0] - 0.535) < 0.002


def test_load_player_season_repairs_legacy_varchar_ts_pct(scratch):
    _add_legacy_ts_rows(scratch, [
        (900, "Legacy Number", "0.616"),
        (901, "Legacy Null", None),
        (902, "Legacy Nan", "-nan"),
    ])

    n = seed.load_player_season("2026-27", dry_run=False)

    assert n == 1
    con = store.connect()
    rows = con.execute(
        "SELECT \"PLAYER_ID\", \"TS_PCT\", typeof(\"TS_PCT\"), _source, "
        "_season, \"_prov_TS_PCT\" FROM silver_player_season "
        "ORDER BY \"PLAYER_ID\"").fetchall()
    con.close()
    by_id = {r[0]: r for r in rows}
    assert [r[2] for r in rows] == ["DOUBLE"] * 4
    assert by_id[1][1] == pytest.approx(0.535)
    assert by_id[900][1] == pytest.approx(0.616)
    assert by_id[901][1] is None
    assert by_id[902][1] is None
    assert by_id[1][3:5] == (seed.SRC_PSS, "2026-27")
    assert by_id[900][3:] == ("fixture", "2025-26", "prov:900")
    assert by_id[902][5] == "prov:902"


def test_load_player_season_rejects_nonnumeric_legacy_ts_pct(scratch):
    _add_legacy_ts_rows(scratch, [(900, "Legacy Bad", "not-a-number")])

    with pytest.raises(duckdb.ConversionException, match="Could not convert"):
        seed.load_player_season("2026-27", dry_run=False)

    con = store.connect()
    rows = con.execute(
        "SELECT \"TS_PCT\", typeof(\"TS_PCT\"), COUNT(*) FILTER "
        "(_season = '2026-27') FROM silver_player_season "
        "GROUP BY \"TS_PCT\"").fetchall()
    con.close()
    assert rows == [("not-a-number", "VARCHAR", 0)]


def test_load_player_season_dry_run_preserves_legacy_ts_pct_schema(scratch):
    _add_legacy_ts_rows(scratch, [(900, "Legacy Number", "0.616")])

    n = seed.load_player_season("2026-27", dry_run=True)

    assert n == 0
    con = store.connect()
    row = con.execute(
        "SELECT \"TS_PCT\", typeof(\"TS_PCT\") FROM silver_player_season"
    ).fetchone()
    con.close()
    assert row == ("0.616", "VARCHAR")


def test_load_player_season_zero_attempt_ts_pct_is_null(scratch, monkeypatch):
    zero = PGL.with_columns([
        pl.lit(0.0).alias("pts"),
        pl.lit(0.0).alias("fga"),
        pl.lit(0.0).alias("fta"),
    ])
    frames = {
        "team_game_logs": TGL,
        "player_game_logs": zero,
        "player_season_stats": PSS,
    }

    def fake_read(url):
        for key, frame in frames.items():
            if key in url:
                return frame
        raise AssertionError(url)

    monkeypatch.setattr(seed.pl, "read_parquet", fake_read)
    n = seed.load_player_season("2026-27", dry_run=False)

    assert n == 1
    con = store.connect()
    row = con.execute(
        "SELECT \"TS_PCT\", typeof(\"TS_PCT\") FROM silver_player_season"
    ).fetchone()
    con.close()
    assert row == (None, "DOUBLE")


def test_main_dry_run(scratch, capsys):
    rc = seed.main(["--scratch-db", str(scratch), "--season", "2026-27",
                    "--dry-run", "--skip-live"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    con = store.connect()
    assert con.execute("SELECT COUNT(*) FROM silver_hist_gamelogs"
                       ).fetchone()[0] == 0
    con.close()
