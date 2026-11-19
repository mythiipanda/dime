import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl
import pytest

from shared import store
from shared.sources.base import FetchMeta, FetchResult

TABLE = "test_save_frame_drill"

@pytest.fixture
def scratch(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "saveframe.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    return tmp_path

def _res(rows, season="2024-25", source="t"):
    return FetchResult(
        frame=pl.DataFrame(rows),
        meta=FetchMeta(source=source, season=season,
                       fetched_at="2026-01-01T00:00:00"),
    )

def _seeded_count():
    return store.read_frame(
        TABLE, where="_season = ? AND _entity = ?", params=["2024-25", "E1"]
    ).height

def _e1_rows():
    return store.read_frame(
        TABLE, where="_season = ? AND _entity = ?", params=["2024-25", "E1"]
    ).sort("GID")

def test_crash_mid_schema_mismatch_keeps_committed_rows(scratch):
    store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 10},
                                  {"GID": "G2", "PTS": 20},
                                  {"GID": "G3", "PTS": 30}]), entity="E1")
    assert _seeded_count() == 3
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.save_frame(TABLE, _res([{"GID": "G9", "PTS": 99, "AST": 7}]),
                         entity="E2", _fault="after_delete")
    got = _e1_rows()
    assert got.height == 3
    assert got["PTS"].to_list() == [10, 20, 30]

def test_crash_same_entity_delete_rolls_back(scratch):
    store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 10},
                                  {"GID": "G2", "PTS": 20}]), entity="E1")
    assert _seeded_count() == 2
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 99, "AST": 7}]),
                         entity="E1", _fault="after_delete")
    got = _e1_rows()
    assert got.height == 2
    assert got["PTS"].to_list() == [10, 20]

def test_crash_after_insert_rolls_back_without_wiping_history(scratch):
    store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 10},
                                  {"GID": "G2", "PTS": 20}]), entity="E1")
    assert _seeded_count() == 2
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.save_frame(TABLE, _res([{"GID": "G9", "PTS": 99, "AST": 7}]),
                         entity="E2", _fault="after_insert")
    got = _e1_rows()
    assert got.height == 2
    assert got["PTS"].to_list() == [10, 20]

def test_multi_column_mismatch_rolls_back_then_merges(scratch):
    store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 10}]), entity="E1")
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.save_frame(TABLE, _res([{"GID": "G9", "PTS": 99,
                                       "AST": 7, "REB": 5}]),
                         entity="E2", _fault="after_delete")
    assert _e1_rows()["PTS"].to_list() == [10]
    store.save_frame(TABLE, _res([{"GID": "G9", "PTS": 99,
                                   "AST": 7, "REB": 5}]), entity="E2")
    merged = store.read_frame(TABLE)
    assert merged.columns == ["GID", "PTS", "_source", "_season",
                              "_fetched_at", "_entity", "AST", "REB"]
    assert _e1_rows()["AST"].to_list() == [None]
    assert merged.height == 2

def test_schema_mismatch_merges_without_wiping_other_entities(scratch):
    store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 10},
                                  {"GID": "G2", "PTS": 20}]), entity="E1")
    store.save_frame(TABLE, _res([{"GID": "G9", "PTS": 99, "AST": 7}]),
                     entity="E2")
    old = _e1_rows()
    assert old.height == 2
    assert old["PTS"].to_list() == [10, 20]
    assert old["AST"].to_list() == [None, None]
    new = store.read_frame(
        TABLE, where="_season = ? AND _entity = ?", params=["2024-25", "E2"]
    )
    assert new.height == 1
    assert new["AST"].to_list() == [7]
    assert store.read_frame(TABLE).height == 3

def test_happy_path_replace_semantics_unchanged(scratch):
    store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 10}]), entity="E1")
    first = store.read_frame(TABLE)
    store.save_frame(TABLE, _res([{"GID": "G1", "PTS": 42}]), entity="E1")
    second = store.read_frame(TABLE)
    assert second.height == 1
    assert second["PTS"].to_list() == [42]
    assert second.columns == first.columns
