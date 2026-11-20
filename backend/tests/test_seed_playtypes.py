import sys
from pathlib import Path

import duckdb
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_playtypes as seed
from shared import store
from shared.sources.base import FetchMeta, FetchResult


def _frame(kind, side):
    row = {name: None for name in seed.nba_stats.PLAYTYPE_SCHEMA}
    row.update({
        "subject_kind": kind,
        "subject_id": 1628369 if kind == "player" else 1610612738,
        "subject_name": "Jayson Tatum" if kind == "player" else "Boston Celtics",
        "team_id": 1610612738,
        "team_abbreviation": "BOS",
        "side": side,
        "play_type": "Transition",
        "percentile": 0.725,
        "gp": 72,
        "poss_pct": 0.114,
        "ppp": 1.237,
        "fg_pct": 0.586,
        "efg_pct": 0.676,
        "poss": 211,
        "pts": 261,
        "fgm": 95,
        "fga": 162,
    })
    return pl.DataFrame([row])


def _fetch(calls):
    def fake(season, player_or_team, type_grouping):
        calls.append((season, player_or_team, type_grouping))
        kind = "player" if player_or_team == "P" else "team"
        side = "offense" if type_grouping == "offensive" else "defense"
        return FetchResult(frame=_frame(kind, side),
                           meta=FetchMeta(source="nba_api", season=season))
    return fake


def _scratch(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return db


def test_planned_units_cover_kind_side_and_entity():
    units = seed.planned_units(["2025-26"])
    assert units == [
        ("2025-26", "player", "offense"),
        ("2025-26", "player", "defense"),
        ("2025-26", "team", "offense"),
        ("2025-26", "team", "defense"),
    ]
    assert seed.unit_entity("player", "offense") == "league:player:offense"


def test_run_unit_writes_provenance_and_marks_complete(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    calls = []
    assert seed.run_unit(("2025-26", "player", "offense"),
                         fetch_fn=_fetch(calls)) is True
    assert calls == [("2025-26", "P", "offensive")]
    frame = store.read_frame(seed.TABLE, "_entity = ?",
                             ["league:player:offense"])
    assert frame.height == 1
    row = frame.to_dicts()[0]
    assert row["_source"] == "nba_api"
    assert row["_season"] == "2025-26"
    assert row["_fetched_at"]
    assert row["_entity"] == "league:player:offense"
    assert row["subject_id"] == 1628369
    assert seed.unit_complete("2025-26", "player", "offense") is True
    assert seed.unit_complete("2025-26", "team", "offense") is False


def test_main_dry_run_plans_without_writes_or_fetches(tmp_path, monkeypatch, capsys):
    db = tmp_path / "warehouse.duckdb"
    calls = []
    monkeypatch.setattr(seed.nba_stats, "synergy_playtypes", _fetch(calls))
    assert seed.main(["--seasons", "2025-26", "--scratch-db", str(db),
                      "--dry-run"]) == 0
    assert calls == []
    assert not db.exists()
    out = capsys.readouterr().out
    assert "silver_playtypes 2025-26 league:player:offense" in out
    assert "units: 4" in out


def test_main_seeds_once_then_skips_completed_units(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    calls = []
    monkeypatch.setattr(seed.nba_stats, "synergy_playtypes", _fetch(calls))
    argv = ["--seasons", "2025-26", "--scratch-db", str(db), "--sleep", "0"]
    assert seed.main(argv) == 0
    assert len(calls) == 4
    assert seed.main(argv) == 0
    assert len(calls) == 4
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute(
            f'SELECT COUNT(*) FROM "{seed.TABLE}"').fetchone()[0]
        logs = con.execute(
            "SELECT COUNT(*) FROM fetch_log WHERE dataset = ?",
            [seed.TABLE]).fetchone()[0]
    finally:
        con.close()
    assert rows == 4
    assert logs == 4


def test_failed_unit_is_logged_and_retried(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    calls = []

    def bad(season, player_or_team, type_grouping):
        calls.append((season, player_or_team, type_grouping))
        return FetchResult(frame=pl.DataFrame(),
                           meta=FetchMeta(source="nba_api", season=season),
                           ok=False, error="upstream unavailable")

    assert seed.run_unit(("2025-26", "player", "offense"), fetch_fn=bad) is False
    assert seed.unit_complete("2025-26", "player", "offense") is False
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True)
    try:
        rows = con.execute(
            "SELECT rows FROM fetch_log WHERE dataset = ? AND season = ? "
            "AND entity = ?",
            [seed.TABLE, "2025-26", "league:player:offense"]).fetchall()
    finally:
        con.close()
    assert rows == [(-1,)]
    assert seed.run_unit(("2025-26", "player", "offense"),
                         fetch_fn=_fetch(calls)) is True
    assert len(calls) == 2
    assert seed.unit_complete("2025-26", "player", "offense") is True
