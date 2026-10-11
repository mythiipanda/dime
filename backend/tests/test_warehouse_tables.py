from pathlib import Path

from fastapi.testclient import TestClient


ALLOWED_BADGES = {"nba_official", "bbref", "derived", "internal"}


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
