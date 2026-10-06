import json
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_transactions as seed
from shared import store
from shared.sources import nba_transactions as src

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "nba_transactions"


def _csv_text() -> str:
    return (FIXTURES / "player_trans_sample.csv").read_text(encoding="utf-8")


def _json_text() -> str:
    return (FIXTURES / "player_movement_sample.json").read_text(encoding="utf-8")


def _scratch(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "tx.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _argv(*extra: str) -> list[str]:
    return ["seed_transactions",
            "--csv-file", str(FIXTURES / "player_trans_sample.csv"),
            "--json-file", str(FIXTURES / "player_movement_sample.json"),
            *extra]


def test_parse_csv_carries_schema_and_row_count():
    frame = src.parse_csv(_csv_text())
    assert frame.schema == src.SCHEMA
    assert frame.height == 7


def test_parse_json_carries_schema_and_row_count():
    frame = src.parse_json(_json_text())
    assert frame.schema == src.SCHEMA
    assert frame.height == 5


def test_union_dedupes_overlap_and_the_survivor_names_both_sources():
    union = src.union(src.parse_csv(_csv_text()), src.parse_json(_json_text()))
    assert union.height == 9
    overlap = union.filter(
        (pl.col("TRANSACTION_DATE") == "2015-10-28")
        & (pl.col("TEAMS") == "LAL;NYK"))
    assert overlap.height == 1
    assert overlap["SOURCE"][0] == "rossgraham-csv+stats-nba-json"
    assert set(overlap["SOURCE_FILE"][0].split("+")) == {
        "DB/Player_Trans.csv", "NBA_Player_Movement.json"}
    assert overlap["FETCHED_AT"][0]


def test_provenance_on_every_row():
    union = src.union(src.parse_csv(_csv_text()), src.parse_json(_json_text()))
    assert union.filter(pl.col("SOURCE").str.len_chars() == 0).height == 0
    assert union.filter(pl.col("SOURCE_FILE").str.len_chars() == 0).height == 0
    assert union.filter(pl.col("SEASON").str.len_chars() == 0).height == 0
    assert set(union["SOURCE"]) <= {"rossgraham-csv", "stats-nba-json",
                                    "rossgraham-csv+stats-nba-json"}


def test_loud_failure_on_empty_sources():
    with pytest.raises(src.TransactionsSourceError, match="rossgraham-csv"):
        src.parse_csv("")
    with pytest.raises(src.TransactionsSourceError, match="stats-nba-json"):
        src.parse_json("{}")
    with pytest.raises(src.TransactionsSourceError, match="not JSON"):
        src.parse_json("This is not JSON")


def test_seeder_writes_every_season_with_provenance(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    progress = tmp_path / "progress.json"
    code = seed.main(_argv("--progress", str(progress)))
    assert code == 0
    con = store.connect()
    try:
        rows = con.execute(f'SELECT * FROM "{seed.TABLE}"').pl()
        assert rows.height == 9
        assert set(rows["_season"]) == {"2014-15", "2015-16", "2016-17",
                                        "2017-18", "2020-21", "2024-25"}
        assert rows["_source"].unique().to_list() == ["nba-transactions"]
        assert rows["_fetched_at"].str.len_chars().min() > 0
        assert rows["SOURCE_FILE"].str.len_chars().min() > 0
    finally:
        con.close()


def test_second_run_is_a_noop_and_table_unchanged(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    progress = tmp_path/ "progress.json"
    argv = _argv("--progress", str(progress))
    assert seed.main(argv) == 0
    con = store.connect()
    first = con.execute(f'SELECT * FROM "{seed.TABLE}"').pl()
    con.close()
    assert seed.main(argv) == 0
    con = store.connect()
    second = con.execute(f'SELECT * FROM "{seed.TABLE}"').pl()
    con.close()
    assert first.equals(second)


def test_rerun_without_progress_still_changes_nothing(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    progress = tmp_path / "progress.json"
    argv = _argv("--progress", str(progress))
    assert seed.main(argv) == 0
    progress.unlink()
    con = store.connect()
    first = con.execute(f'SELECT * FROM "{seed.TABLE}"').pl()
    con.close()
    assert seed.main(argv) == 0
    con = store.connect()
    second = con.execute(f'SELECT * FROM "{seed.TABLE}"').pl()
    con.close()
    assert first.equals(second)
    assert first["FETCHED_AT"].equals(second["FETCHED_AT"])


def test_dry_run_reports_without_writing(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    progress = tmp_path / "progress.json"
    code = seed.main(_argv("--progress", str(progress), "--dry-run"))
    assert code == 0
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables").fetchall()}
        assert seed.TABLE not in tables
        assert not progress.exists()
    finally:
        con.close()


def test_progress_marks_done_seasons_resume(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    progress = tmp_path / "progress.json"
    progress.write_text(json.dumps(
        {"done": ["2014-15", "2015-16"], "failed": {}}))
    argv = _argv("--progress", str(progress),
                 "--seasons", "2014-15,2015-16,2016-17")
    assert seed.main(argv) == 0
    con = store.connect()
    try:
        seasons = {r[0] for r in con.execute(
            f'SELECT DISTINCT _season FROM "{seed.TABLE}"').fetchall()}
        assert seasons == {"2016-17"}
    finally:
        con.close()


def test_missing_season_slice_fails_loudly(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    progress = tmp_path / "progress.json"
    code = seed.main(_argv("--progress", str(progress),
                           "--seasons", "1999-00"))
    assert code == 1
    assert "1999-00" in progress.read_text()
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables").fetchall()}
        assert seed.TABLE not in tables
    finally:
        con.close()


def test_seed_season_empty_slice_raises_naming_season_and_source():
    union = src.union(src.parse_csv(_csv_text()), src.parse_json(_json_text()))
    with pytest.raises(seed.SeederError,
                       match="season 1999-00.*rossgraham-csv.*stats-nba-json"):
        seed.seed_season("1999-00", union, None, Path("/tmp/unused.json"),
                         dry_run=False)
