import asyncio

import duckdb
import pytest

from shared import store
from shared.tools.sql_exec import season_scope_warning, sql_exec


@pytest.fixture
def warehouse(monkeypatch, tmp_path):
    db = tmp_path / "seasons.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE silver_hist_shots(game_id VARCHAR, shot_value INTEGER, _season VARCHAR)")
    con.execute("INSERT INTO silver_hist_shots VALUES ('0022500001', 3, '2025-26'), ('0022400001', 3, '2024-25')")
    con.execute("CREATE TABLE silver_rapm(name VARCHAR, _season VARCHAR)")
    con.execute("INSERT INTO silver_rapm VALUES ('A', '2025-26')")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_pool_clear()
    yield db
    store.warehouse_pool_clear()


def test_warns_when_multi_season_table_has_no_season_filter(warehouse):
    warning = season_scope_warning("SELECT count(*) FROM silver_hist_shots WHERE game_id LIKE '002%'", ["silver_hist_shots"])
    assert "silver_hist_shots holds 2 seasons" in warning


def test_no_warning_when_season_is_filtered(warehouse):
    assert season_scope_warning("SELECT count(*) FROM silver_hist_shots WHERE _season = '2025-26'", ["silver_hist_shots"]) is None


def test_no_warning_for_single_season_table(warehouse):
    assert season_scope_warning("SELECT count(*) FROM silver_rapm", ["silver_rapm"]) is None
