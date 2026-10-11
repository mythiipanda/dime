from pathlib import Path

from fastapi.testclient import TestClient


ALLOWED_BADGES = {"nba_official", "bbref", "derived", "internal", "unknown"}


def _client(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    db = root / "warehouse-runtime.duckdb"
    assert db.is_file()
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    import warehouse_tables

    warehouse_tables.snapshot_clear()
    import entrypoint

    return TestClient(entrypoint.app), db


def _by_name(tables, name):
    for table in tables:
        if table["name"] == name:
            return table
    raise AssertionError(f"missing table {name}")


def test_lists_real_tables_with_badges(monkeypatch):
    client, _ = _client(monkeypatch)
    response = client.get("/api/v2/warehouse/tables")
    assert response.status_code == 200
    tables = response.json()
    assert isinstance(tables, list)
    assert len(tables) == 52
    shots = _by_name(tables, "silver_hist_shots")
    assert shots["row_count"] == 3729459
    assert shots["column_count"] == 22
    assert shots["source_badge"] == "nba_official"
    assert shots["season_range"] == {"min": "2010", "max": "2026"}
    salaries = _by_name(tables, "silver_salaries")
    assert salaries["source_badge"] == "bbref"
    awards = _by_name(tables, "silver_bbref_awards")
    assert awards["source_badge"] == "bbref"
    fetch_log = _by_name(tables, "fetch_log")
    assert fetch_log["source_badge"] == "internal"
    assert fetch_log["season_range"] is None
    raptor = _by_name(tables, "silver_raptor_player")
    assert raptor["source_badge"] == "derived"
    assert raptor["season_range"] == {"min": "1977", "max": "2022"}
    for table in tables:
        assert set(table) == {
            "name",
            "row_count",
            "column_count",
            "season_range",
            "source_badge",
            "description",
        }
        assert table["source_badge"] in ALLOWED_BADGES
        assert isinstance(table["row_count"], int)
        assert isinstance(table["column_count"], int)
        assert table["column_count"] > 0
        assert table["description"]
        if table["season_range"] is not None:
            assert set(table["season_range"]) == {"min", "max"}


def test_thin_tables_are_visible(monkeypatch):
    client, _ = _client(monkeypatch)
    tables = client.get("/api/v2/warehouse/tables").json()
    assert _by_name(tables, "silver_four_factors")["row_count"] == 2
    assert _by_name(tables, "silver_wowy")["row_count"] == 1
    assert _by_name(tables, "silver_on_off")["row_count"] == 7476


def test_catalog_is_cached(monkeypatch):
    client, _ = _client(monkeypatch)
    first = client.get("/api/v2/warehouse/tables").json()
    second = client.get("/api/v2/warehouse/tables").json()
    assert first == second


def test_endpoint_is_read_only(monkeypatch):
    client, db = _client(monkeypatch)
    before_stat = db.stat()
    before = (before_stat.st_mtime_ns, before_stat.st_size)
    for _ in range(3):
        response = client.get("/api/v2/warehouse/tables")
        assert response.status_code == 200
    after_stat = db.stat()
    assert (after_stat.st_mtime_ns, after_stat.st_size) == before
    assert list(db.parent.glob(db.name + "*wal")) == []


def test_default_path_matches_analysis_store(monkeypatch):
    monkeypatch.delenv("DIME_WAREHOUSE", raising=False)
    import warehouse_tables
    import shared.store as store

    got = warehouse_tables.warehouse_path()
    expected = Path(warehouse_tables.__file__).resolve().parent / "data" / "warehouse.duckdb"
    assert got == expected
    store_default = Path(store.__file__).resolve().parent.parent / "data" / "warehouse.duckdb"
    assert got == store_default


def test_env_override_selects_configured_path(monkeypatch, tmp_path):
    custom = tmp_path / "custom.duckdb"
    monkeypatch.setenv("DIME_WAREHOUSE", str(custom))
    import warehouse_tables

    assert warehouse_tables.warehouse_path() == custom


def test_espn_tables_are_not_certified_official(monkeypatch):
    client, _ = _client(monkeypatch)
    tables = client.get("/api/v2/warehouse/tables").json()
    injuries = _by_name(tables, "silver_injuries")
    assert injuries["source_badge"] == "unknown"
    schedule = _by_name(tables, "silver_schedule")
    assert schedule["source_badge"] == "unknown"
    four_factors_team = _by_name(tables, "silver_four_factors_team")
    assert four_factors_team["source_badge"] == "unknown"


def test_source_badge_never_guesses_official():
    import warehouse_tables

    assert warehouse_tables.source_badge_for("silver_future_xyz") == "unknown"
    assert warehouse_tables.source_badge_for("silver_future_xyz", []) == "unknown"
    assert warehouse_tables.source_badge_for("silver_injuries", ["espn"]) == "unknown"
    assert warehouse_tables.source_badge_for("silver_schedule", ["espn:team_schedule"]) == "unknown"
    assert warehouse_tables.source_badge_for("silver_boxscores", ["nba_api"]) == "nba_official"
    assert warehouse_tables.source_badge_for("silver_bbref_awards", ["basketball-reference"]) == "bbref"
    assert warehouse_tables.source_badge_for("silver_rapm", ["rapm-lite"]) == "derived"
    assert warehouse_tables.source_badge_for("fetch_log", []) == "internal"


def test_cache_key_includes_size_and_content_signal(tmp_path):
    import os
    import warehouse_tables

    first = tmp_path / "a.duckdb"
    second = tmp_path / "b.duckdb"
    first.write_bytes(b"x" * 16)
    second.write_bytes(b"x" * 32)
    same_ns = 1700000000000000000
    os.utime(first, ns=(same_ns, same_ns))
    os.utime(second, ns=(same_ns, same_ns))
    assert warehouse_tables._stat_key(first) != warehouse_tables._stat_key(second)


def test_cache_invalidates_when_mtime_restored(tmp_path):
    import os
    import duckdb
    import warehouse_tables

    db = tmp_path / "cache.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE silver_probe (id INTEGER, _source VARCHAR)")
    con.execute("INSERT INTO silver_probe VALUES (1, 'nba_api')")
    con.close()
    warehouse_tables.snapshot_clear()
    before = warehouse_tables.load_snapshot(db)
    assert [t for t in before if t["name"] == "silver_probe"][0]["row_count"] == 1
    st = db.stat()
    original_mtime = st.st_mtime_ns
    con = duckdb.connect(str(db))
    con.execute("INSERT INTO silver_probe VALUES (2, 'nba_api'), (3, 'nba_api')")
    con.close()
    os.utime(db, ns=(original_mtime, original_mtime))
    after = warehouse_tables.load_snapshot(db)
    assert [t for t in after if t["name"] == "silver_probe"][0]["row_count"] == 3
    warehouse_tables.snapshot_clear()
