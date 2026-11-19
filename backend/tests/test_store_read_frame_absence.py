
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import polars as pl
import pytest

from shared import store

_PRESENT = "silver_lineups"
_ABSENT = "silver_player_season"

@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            f"CREATE TABLE {_PRESENT} (GROUP_ID VARCHAR, "
            "TEAM_ABBREVIATION VARCHAR, PTS DOUBLE)"
        )
        con.execute(
            f"INSERT INTO {_PRESENT} VALUES ('g1', 'BOS', 110.0)"
        )
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    yield path
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()

def test_absent_table_raises_typed_error(warehouse):
    with pytest.raises(store.TableAbsent) as info:
        store.read_frame(_ABSENT)
    assert info.value.table == _ABSENT
    assert str(warehouse) in info.value.warehouse
    assert warehouse.name in str(info.value)
    assert str(warehouse) not in str(info.value), (
        "the message travels into answers, so it carries the file name "
        "rather than the absolute path")

def test_absent_table_error_names_the_missing_table(warehouse):
    with pytest.raises(store.TableAbsent) as info:
        store.read_frame(_ABSENT, "_season = ?", ["2025-26"])
    assert _ABSENT in str(info.value)

def test_absence_is_a_lookup_failure(warehouse):
    assert issubclass(store.TableAbsent, LookupError)

def test_absent_table_raises_without_querying_it(warehouse, monkeypatch):
    opened = []
    real = store._connect_once

    def observed(read_only):
        opened.append(read_only)
        return real(read_only)

    monkeypatch.setattr(store, "_connect_once", observed)
    with pytest.raises(store.TableAbsent):
        store.read_frame(_ABSENT)
    assert opened == [True], "the tables probe is the only connection, and read-only"

def test_present_table_with_no_matching_rows_reads_empty(warehouse):
    frame = store.read_frame(_PRESENT, "GROUP_ID = ?", ["absent-game"])
    assert frame.height == 0
    assert frame.columns == ["GROUP_ID", "TEAM_ABBREVIATION", "PTS"]

def test_present_table_with_rows_reads_them(warehouse):
    frame = store.read_frame(_PRESENT, "GROUP_ID = ?", ["g1"])
    assert frame.height == 1
    assert frame.to_dicts() == [
        {"GROUP_ID": "g1", "TEAM_ABBREVIATION": "BOS", "PTS": 110.0}
    ]

def test_absent_and_no_matching_rows_stay_distinguishable(warehouse):
    with pytest.raises(store.TableAbsent):
        store.read_frame(_ABSENT, "GROUP_ID = ?", ["g1"])
    empty = store.read_frame(_PRESENT, "GROUP_ID = ?", ["g1-absent"])
    assert empty.height == 0

def test_explicitly_optional_absent_table_returns_empty(warehouse):
    frame = store.read_frame_optional(_ABSENT)
    assert isinstance(frame, pl.DataFrame)
    assert frame.height == 0

def test_explicitly_optional_absent_table_keeps_the_predicate(warehouse):
    frame = store.read_frame_optional(_ABSENT, "GROUP_ID = ?", ["g1"])
    assert frame.height == 0

def test_optional_present_table_returns_rows(warehouse):
    frame = store.read_frame_optional(_PRESENT)
    assert frame.height == 1

def test_optional_present_table_with_no_matching_rows_returns_empty(warehouse):
    assert store.read_frame_optional(
        _PRESENT, "GROUP_ID = ?", ["absent-game"]).height == 0

def test_concurrent_optional_reads_of_an_absent_table_all_return_empty(warehouse):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        frames = list(pool.map(
            lambda _: store.read_frame_optional(_ABSENT), range(32)))
    assert [f.height for f in frames] == [0] * 32
