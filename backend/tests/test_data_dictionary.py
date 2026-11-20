import json
import sys
from pathlib import Path

import duckdb
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))
sys.path.insert(0, str(BACKEND / "scripts"))

import build_data_dictionary as bdd
import publish_warehouse as pw
import refresh_warehouse as rw
from analyst import python_tools
from shared import store
from shared.tools import league
from shared.tools.data_dictionary import (
    clear_data_dictionary_cache,
    dictionary_for_tables,
    load_data_dictionary,
)


def _make_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_player_gamelogs ("
            "Player_ID INTEGER, Game_ID VARCHAR, _season VARCHAR, "
            "PTS INTEGER, _source VARCHAR, _entity VARCHAR, "
            "_fetched_at VARCHAR)")
        con.execute(
            "INSERT INTO silver_player_gamelogs VALUES "
            "(1, '0022500001', '2025-26', 30, 'nba_api', 'g:1', '2026-09-30'),"
            "(2, '0022500001', '2024-25', 22, 'nba_api', 'g:1', '2026-09-30')")
        con.execute(
            "CREATE TABLE silver_advanced ("
            "PLAYER_NAME VARCHAR, TEAM_ABBREVIATION VARCHAR, GP INTEGER, "
            "MIN DOUBLE, TS_PCT DOUBLE, _season VARCHAR)")
        con.execute(
            "INSERT INTO silver_advanced VALUES "
            "('Someone', 'AAA', 16, 32.6, 0.54, '2025-26')")
        con.execute("CREATE TABLE runs (id INTEGER)")
    finally:
        con.close()
    return path


def test_build_dictionary_fields(tmp_path):
    db = _make_db(tmp_path / "w.duckdb")
    doc = bdd.build_dictionary(db)
    assert doc["warehouse_file"] == "w.duckdb"
    assert len(doc["warehouse_sha256"]) == 64
    tables = doc["tables"]
    gamelogs = tables["silver_player_gamelogs"]
    assert gamelogs["rows"] == 2
    assert gamelogs["seasons"] == "2024-25 – 2025-26"
    assert gamelogs["join_keys"] == ["Player_ID", "Game_ID", "_season"]
    assert gamelogs["provenance"]["sources"] == ["nba_api"]
    assert gamelogs["provenance"]["last_fetch"] == "2026-09-30"
    assert "caveats" in gamelogs
    assert "purpose" in gamelogs
    advanced = tables["silver_advanced"]
    assert advanced["caveats"] == [
        "MIN is per-game minutes, not season totals; use MIN * GP for total minutes."]
    assert advanced["join_keys"] == ["TEAM_ABBREVIATION", "_season"]
    assert tables["runs"]["purpose"] == "internal pipeline table"
    assert tables["runs"]["seasons"] is None


def test_write_dictionary_lands_beside_warehouse(tmp_path):
    db = _make_db(tmp_path / "w.duckdb")
    out = bdd.write_dictionary(db)
    assert out == tmp_path / "data_dictionary.json"
    doc = json.loads(out.read_text())
    assert "silver_player_gamelogs" in doc["tables"]


def test_loader_reads_dictionary_next_to_db(tmp_path, monkeypatch):
    db = _make_db(tmp_path / "w.duckdb")
    bdd.write_dictionary(db)
    monkeypatch.setattr(store, "DB_PATH", db)
    clear_data_dictionary_cache()
    doc = load_data_dictionary()
    assert doc is not None
    entries = dictionary_for_tables(["silver_advanced", "missing_table"])
    assert entries is not None
    assert list(entries["entries"]) == ["silver_advanced"]
    assert entries["entries"]["silver_advanced"]["rows"] == 1


def test_loader_missing_file_returns_none(tmp_path, monkeypatch):
    db = _make_db(tmp_path / "w.duckdb")
    monkeypatch.setattr(store, "DB_PATH", db)
    clear_data_dictionary_cache()
    assert load_data_dictionary() is None
    assert dictionary_for_tables(["silver_advanced"]) is None


def test_warehouse_schema_surfaces_dictionary(tmp_path, monkeypatch):
    db = _make_db(tmp_path / "w.duckdb")
    bdd.write_dictionary(db)
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    clear_data_dictionary_cache()
    tools = python_tools.catalogue()
    res = tools["warehouse_schema"].invoke({"tables": ["silver_advanced"]})
    assert res["ok"] is True
    dictionary = res["data_dictionary"]
    assert dictionary["entries"]["silver_advanced"]["rows"] == 1
    assert dictionary["entries"]["silver_advanced"]["join_keys"] == [
        "TEAM_ABBREVIATION", "_season"]
    assert dictionary["warehouse_sha256"]


def test_warehouse_schema_without_dictionary(tmp_path, monkeypatch):
    db = _make_db(tmp_path / "w.duckdb")
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    clear_data_dictionary_cache()
    tools = python_tools.catalogue()
    res = tools["warehouse_schema"].invoke({"tables": ["silver_advanced"]})
    assert res["ok"] is True
    assert "data_dictionary" not in res


class _FakeOp:
    def __init__(self, path_in_repo, path_or_fileobj):
        self.path_in_repo = path_in_repo
        self.path_or_fileobj = path_or_fileobj


@pytest.fixture()
def hf_stub(monkeypatch):
    module = type(sys)("huggingface_hub")
    module.CommitOperationAdd = _FakeOp
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    return module


class _FakeApi:
    def __init__(self):
        self.operations = None

    def create_repo(self, **kwargs):
        pass

    def update_repo_settings(self, **kwargs):
        pass

    def hf_hub_download(self, **kwargs):
        raise FileNotFoundError("not found")

    def create_commit(self, commit_message=None, operations=None, **kwargs):
        self.operations = operations
        return type("Info", (), {"commit_url": "fake://commit"})()


def test_publish_uploads_dictionary_when_present(tmp_path, hf_stub):
    db = _make_db(tmp_path / "w.duckdb")
    bdd.write_dictionary(db)
    api = _FakeApi()
    verdict = pw.publish(db, api=api, commit_message="test")
    names = sorted(op.path_in_repo for op in api.operations)
    assert "data_dictionary.json" in names
    assert verdict["dictionary_file"] == "data_dictionary.json"


def test_publish_skips_dictionary_when_absent(tmp_path, hf_stub):
    db = _make_db(tmp_path / "w.duckdb")
    api = _FakeApi()
    pw.publish(db, api=api, commit_message="test")
    names = sorted(op.path_in_repo for op in api.operations)
    assert "data_dictionary.json" not in names


def test_refresh_regenerates_dictionary(tmp_path, monkeypatch):
    local = _make_db(tmp_path / "local.duckdb")
    monkeypatch.setattr(rw, "LOCAL_WAREHOUSE", local)
    work = tmp_path / "work"
    rc = rw.main(["--from-local", "--skip-seed", "--skip-publish",
                  "--work-dir", str(work)])
    assert rc == 0
    staged = work / "data_dictionary.json"
    assert staged.is_file()
    doc = json.loads(staged.read_text())
    assert "silver_player_gamelogs" in doc["tables"]
    assert (local.parent / "data_dictionary.json").is_file()
