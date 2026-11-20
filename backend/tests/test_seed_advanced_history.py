
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_advanced_history as seed
from shared import store
from shared.sources.base import FetchMeta, FetchResult

ROWS = 4
PRELOADED = "2025-26"

def _frame() -> pl.DataFrame:
    return pl.DataFrame({
        "PLAYER_ID": [201939, 1628988, 1627846, 2544],
        "PLAYER_NAME": ["Alpha", "Bravo", "Charlie", "Delta"],
        "TEAM_ID": [1610612737, 1610612755, 1610612760, 1610612748],
        "TEAM_ABBREVIATION": ["ATL", "CHI", "PHX", "MIL"],
        "AGE": [24.0, 23.0, 26.0, 21.0],
        "GP": [70, 60, 55, 40],
        "MIN": [2100.0, 1800.0, 1500.0, 900.0],
        "OFF_RATING": [112.1, 110.4, 109.8, 108.2],
        "DEF_RATING": [109.7, 111.2, 112.0, 113.4],
        "NET_RATING": [2.4, -0.8, -2.2, -5.2],
        "TS_PCT": [0.612, 0.588, 0.571, 0.549],
        "USG_PCT": [0.29, 0.24, 0.21, 0.18],
        "PIE": [0.19, 0.15, 0.13, 0.09],
        "FG_PCT": [0.481, 0.455, 0.44, 0.42],
    })

def _result(frame: pl.DataFrame, season: str, ok: bool = True,
            error: str = "") -> FetchResult:
    return FetchResult(frame=frame, meta=FetchMeta(source=seed.SOURCE, season=season),
                       ok=ok, error=error)

def _transport(calls: list[str] | None = None):
    def fetch(season: str) -> FetchResult:
        if calls is not None:
            calls.append(season)
        return _result(_frame(), season)
    return fetch

def _scratch(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "warehouse.duckdb"
    duckdb.connect(str(path)).close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    return path

def _query(path: Path, sql: str) -> list[tuple]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()

def _columns(path: Path, table: str) -> set[str]:
    return {r[1] for r in _query(path, f"PRAGMA table_info({table})")}

def _seasons(path: Path, table: str) -> set[str]:
    return {r[0] for r in _query(path, f"SELECT DISTINCT _season FROM {table}")}

def _award_inputs(path: Path, seasons: list[str], preloaded: str) -> None:
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE silver_leaders_pts (PLAYER_ID BIGINT, _season VARCHAR)")
    con.execute("CREATE TABLE silver_standings (TeamID BIGINT, _season VARCHAR)")
    con.execute(f"CREATE TABLE {seed.TABLE} (PLAYER_ID BIGINT, _season VARCHAR)")
    con.executemany("INSERT INTO silver_leaders_pts VALUES (?, ?)",
                    [(1, s) for s in seasons])
    con.executemany("INSERT INTO silver_standings VALUES (?, ?)",
                    [(1, s) for s in seasons])
    con.execute(f"INSERT INTO {seed.TABLE} VALUES (1, ?)", [preloaded])
    con.close()

def test_writes_every_fetched_column_with_provenance(tmp_path, monkeypatch):
    path = _scratch(tmp_path, monkeypatch)

    report = seed.run(["2024-25"], fetch=_transport(), delay_s=0)

    assert report["loaded"] == {"2024-25": ROWS}
    assert report["skipped"] == []
    assert report["rows"] == ROWS
    assert _columns(path, seed.TABLE) == (
        set(_frame().columns) | set(store.PROVENANCE_COLS) | {"_entity"})
    assert _query(
        path,
        f"SELECT PLAYER_ID, PLAYER_NAME, AGE, TS_PCT, NET_RATING, DEF_RATING,"
        f" _source, _season, _entity FROM {seed.TABLE}"
        f" ORDER BY PLAYER_ID") == [
        (2544, "Delta", 21.0, 0.549, -5.2, 113.4, seed.SOURCE, "2024-25", seed.ENTITY),
        (201939, "Alpha", 24.0, 0.612, 2.4, 109.7, seed.SOURCE, "2024-25", seed.ENTITY),
        (1627846, "Charlie", 26.0, 0.571, -2.2, 112.0, seed.SOURCE, "2024-25", seed.ENTITY),
        (1628988, "Bravo", 23.0, 0.588, -0.8, 111.2, seed.SOURCE, "2024-25", seed.ENTITY),
    ]
    assert _query(
        path,
        "SELECT dataset, season, entity, source, rows FROM fetch_log"
        " ORDER BY season") == [
        (seed.TABLE, "2024-25", seed.ENTITY, seed.SOURCE, ROWS),
    ]

def test_a_season_missing_a_column_keeps_the_table_shape(tmp_path, monkeypatch):
    path = _scratch(tmp_path, monkeypatch)
    thin = _frame().drop("FG_PCT")

    def fetch(season: str) -> FetchResult:
        return _result(_frame() if season == "2024-25" else thin, season)

    seed.run(["2024-25", "2023-24"], fetch=fetch, delay_s=0)

    assert _columns(path, seed.TABLE) == (
        set(_frame().columns) | set(store.PROVENANCE_COLS) | {"_entity"})
    assert _query(
        path,
        f"SELECT _season, FG_PCT IS NULL FROM {seed.TABLE}"
        " GROUP BY 1, 2 ORDER BY 1") == [("2023-24", True), ("2024-25", False)]

def test_second_run_changes_nothing_and_refetches_nothing(tmp_path, monkeypatch):
    path = _scratch(tmp_path, monkeypatch)
    calls: list[str] = []
    seasons = ["2024-25", "2022-23"]

    first = seed.run(seasons, fetch=_transport(calls), delay_s=0)
    before = _query(path, f"SELECT * FROM {seed.TABLE} ORDER BY _season, PLAYER_ID")

    second = seed.run(seasons, fetch=_transport(calls), delay_s=0)

    assert first["loaded"] == {"2024-25": ROWS, "2022-23": ROWS}
    assert calls == seasons
    assert second == {"loaded": {}, "skipped": seasons, "rows": 0}
    assert calls == seasons
    assert _query(path, f"SELECT * FROM {seed.TABLE} ORDER BY _season, PLAYER_ID") == before
    assert _query(path, "SELECT COUNT(*) FROM fetch_log") == [(2,)]

def test_empty_fetch_names_the_season_and_writes_nothing(tmp_path, monkeypatch):
    path = _scratch(tmp_path, monkeypatch)
    wanted = ["2024-25", "2022-23", "2021-22"]
    calls: list[str] = []

    def fetch(season: str) -> FetchResult:
        calls.append(season)
        if season == "2022-23":
            return _result(pl.DataFrame(), season, ok=False,
                           error="empty upstream response")
        return _result(_frame(), season)

    with pytest.raises(seed.SeasonFetchError, match="2022-23"):
        seed.run(wanted, fetch=fetch, delay_s=0)

    assert calls == ["2024-25", "2022-23"]
    assert _seasons(path, seed.TABLE) == {"2024-25"}
    assert _query(path, "SELECT DISTINCT season FROM fetch_log") == [("2024-25",)]

def test_fetch_missing_a_consumed_column_fails_loudly(tmp_path, monkeypatch):
    path = _scratch(tmp_path, monkeypatch)
    frame = _frame().drop("AGE")

    with pytest.raises(seed.SeasonFetchError, match="AGE"):
        seed.run(["2024-25"], fetch=lambda s: _result(frame, s), delay_s=0)

    assert {r[0] for r in _query(path, "SHOW TABLES")} == {"fetch_log"}

def test_rerun_resumes_after_the_failed_season(tmp_path, monkeypatch):
    path = _scratch(tmp_path, monkeypatch)
    wanted = ["2024-25", "2022-23", "2021-22"]
    calls: list[str] = []

    def broken(season: str) -> FetchResult:
        calls.append(season)
        if season == "2022-23":
            return _result(pl.DataFrame(), season, ok=False, error="boom")
        return _result(_frame(), season)

    with pytest.raises(seed.SeasonFetchError):
        seed.run(wanted, fetch=broken, delay_s=0)

    calls.clear()
    resumed = seed.run(wanted, fetch=_transport(calls), delay_s=0)

    assert calls == ["2022-23", "2021-22"]
    assert resumed["skipped"] == ["2024-25"]
    assert sorted(resumed["loaded"]) == ["2021-22", "2022-23"]
    assert _seasons(path, seed.TABLE) == set(wanted)
    assert _query(
        path, f"SELECT _season, COUNT(*) FROM {seed.TABLE} GROUP BY 1 ORDER BY 1"
    ) == [(s, ROWS) for s in sorted(wanted)]

def test_every_award_input_season_ends_up_in_silver_advanced(tmp_path, monkeypatch):
    path = _scratch(tmp_path, monkeypatch)
    targets = seed.season_slugs()
    _award_inputs(path, list(targets) + [PRELOADED], PRELOADED)

    report = seed.run(targets + [PRELOADED], fetch=_transport(), delay_s=0)

    needed = (_seasons(path, "silver_leaders_pts")
              & _seasons(path, "silver_standings"))
    assert needed == set(targets) | {PRELOADED}
    assert needed <= _seasons(path, seed.TABLE)
    assert report["skipped"] == [PRELOADED]
    assert sorted(report["loaded"]) == sorted(targets)

def test_season_range_is_a_closed_interval():
    assert seed.season_slugs() == [
        "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
    assert seed.season_slugs("2023-24", "2023-24") == ["2023-24"]
    for bad in ("2019", "2019-2", "19-20", "2019-22", ""):
        with pytest.raises(ValueError):
            seed.season_slugs(bad, "2024-25")
    with pytest.raises(ValueError):
        seed.season_slugs("2024-25", "2019-20")
