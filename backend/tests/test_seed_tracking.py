import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import seed_tracking as seed
from shared import store
from shared.sources.base import FetchMeta, FetchResult


@pytest.fixture
def scratch(monkeypatch, tmp_path):
    db = tmp_path / "tracking.duckdb"
    state = tmp_path / "state.duckdb"
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    monkeypatch.setenv("DIME_STATE_DB", str(state))
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setattr(seed, "BACKOFF_S", 0)
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return db


def _fake(season, rows):
    return FetchResult(
        frame=pl.DataFrame(rows),
        meta=FetchMeta(source="nba_api", season=season),
    )


def _count(table, season, entity):
    con = store.connect(read_only=True)
    try:
        return con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE _season = ? AND _entity = ?",
            [season, entity],
        ).fetchone()[0]
    finally:
        con.close()


def test_replace_same_unit_leaves_no_duplicates(scratch):
    entity = "ptstats:player:Drives"
    store.save_frame(seed.PT_STATS_TABLE, _fake("2024-25", {"ID": [1, 2]}),
                     entity=entity)
    store.save_frame(seed.PT_STATS_TABLE, _fake("2024-25", {"ID": [1, 2, 3]}),
                     entity=entity)
    assert _count(seed.PT_STATS_TABLE, "2024-25", entity) == 3


def test_rerun_skips_completed_units(scratch, monkeypatch):
    calls: list = []

    def fake_fetch(unit):
        calls.append(seed.unit_entity(unit))
        return _fake(unit.season, {"ID": [1]})

    monkeypatch.setattr(seed, "fetch", fake_fetch)
    assert seed.main(["--seasons", "2024-25", "--limit-units", "2"]) == 0
    assert len(calls) == 2
    assert seed.main(["--seasons", "2024-25", "--limit-units", "2"]) == 0
    assert len(calls) == 2


def test_heterogeneous_units_coexist_and_replace(scratch, monkeypatch):
    frames = {
        "ptstats:player:CatchShoot": _fake("2024-25", {"ID": [1, 2]}),
        "ptstats:player:Defense": _fake("2024-25", {"ID": [1, 2, 3],
                                                   "EXTRA": ["a", "b", "c"]}),
    }
    monkeypatch.setattr(seed, "fetch",
                        lambda unit: frames[seed.unit_entity(unit)])
    assert seed.main(["--seasons", "2024-25", "--limit-units", "2"]) == 0
    assert _count(seed.PT_STATS_TABLE, "2024-25",
                  "ptstats:player:CatchShoot") == 2
    assert _count(seed.PT_STATS_TABLE, "2024-25",
                  "ptstats:player:Defense") == 3
    frames["ptstats:player:CatchShoot"] = _fake("2024-25", {"ID": [9]})
    con = store.connect(read_only=False)
    try:
        with store.write_guard():
            con.execute("DELETE FROM fetch_log WHERE entity = ?",
                        ["ptstats:player:CatchShoot"])
    finally:
        con.close()
    assert seed.main(["--seasons", "2024-25", "--limit-units", "1"]) == 0
    assert _count(seed.PT_STATS_TABLE, "2024-25",
                  "ptstats:player:CatchShoot") == 1
    assert _count(seed.PT_STATS_TABLE, "2024-25",
                  "ptstats:player:Defense") == 3


def test_three_heterogeneous_units_all_persist(scratch, monkeypatch):
    frames = {
        "ptstats:player:CatchShoot": _fake("2024-25", {"ID": [1, 2]}),
        "ptstats:player:Defense": _fake("2024-25", {"ID": [1],
                                                   "EXTRA": ["a"]}),
        "ptstats:player:Drives": _fake("2024-25", {"ID": [5, 6, 7],
                                                  "OTHER": [1.5, 2.5, 3.5]}),
    }
    monkeypatch.setattr(seed, "fetch",
                        lambda unit: frames[seed.unit_entity(unit)])
    assert seed.main(["--seasons", "2024-25", "--limit-units", "3"]) == 0
    assert _count(seed.PT_STATS_TABLE, "2024-25",
                  "ptstats:player:CatchShoot") == 2
    assert _count(seed.PT_STATS_TABLE, "2024-25",
                  "ptstats:player:Defense") == 1
    assert _count(seed.PT_STATS_TABLE, "2024-25",
                  "ptstats:player:Drives") == 3


def test_entity_scheme_unique_and_complete():
    units = seed.planned_units(["2024-25", "2025-26"])
    keys = [(u.season, seed.unit_entity(u)) for u in units]
    assert len(units) == 52
    assert len(keys) == len(set(keys))
    entities = [seed.unit_entity(u) for u in units]
    assert "ptstats:player:CatchShoot" in entities
    assert "ptstats:team:SpeedDistance" in entities
    assert "ptdefend:Overall" in entities
    assert "ptshot:overall" in entities
    stats = {(u.season, seed.unit_entity(u)) for u in units if u.kind == "pt_stats"}
    assert len(stats) == 48


def test_fail_closed_without_warehouse(tmp_path, monkeypatch):
    monkeypatch.delenv("DIME_WAREHOUSE", raising=False)
    assert seed.main(["--dry-run"]) == 1


def test_fail_closed_on_canonical(scratch, monkeypatch):
    monkeypatch.setenv("DIME_WAREHOUSE", str(store.CANONICAL_DB_PATH))
    assert seed.main(["--dry-run"]) == 1


def test_failure_records_watermark_and_retries_next_run(scratch, monkeypatch):
    monkeypatch.setattr(
        seed, "fetch",
        lambda unit: FetchResult(frame=pl.DataFrame(),
                                 meta=FetchMeta(source="nba_api",
                                                season=unit.season),
                                 ok=False, error="boom"))
    assert seed.main(["--seasons", "2024-25", "--limit-units", "1"]) == 1
    unit = seed.planned_units(["2024-25"])[0]
    assert not seed.unit_complete(seed.unit_table(unit), unit.season,
                                  seed.unit_entity(unit))
    seen: list = []

    def ok_fetch(unit):
        seen.append(1)
        return _fake(unit.season, {"ID": [7]})

    monkeypatch.setattr(seed, "fetch", ok_fetch)
    assert seed.main(["--seasons", "2024-25", "--limit-units", "1"]) == 0
    assert len(seen) == 1
    assert _count(seed.unit_table(unit), unit.season,
                  seed.unit_entity(unit)) == 1
