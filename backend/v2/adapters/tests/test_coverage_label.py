import duckdb
import pytest
from v2.adapters import coverage


RANGE_SEASONS = ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24"]
RANGE_LABEL = "2019-20\u20132023-24"
FUTURE_SEASON = "2025-26"
SINGLE_SEASON = "2023-24"


def _create_table_with_seasons(con, table, seasons):
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"CREATE TABLE {table} (_season VARCHAR)")
    for season in seasons:
        con.execute(f"INSERT INTO {table} VALUES (?)", [season])


def _create_table_without_season_column(con, table):
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"CREATE TABLE {table} (id INTEGER)")


def _build_warehouse(path, seasons):
    con = duckdb.connect(str(path))
    try:
        for table in coverage.KNOWN_TABLES:
            _create_table_with_seasons(con, table, seasons)
    finally:
        con.close()


def _build_empty_warehouse_no_rows(path):
    con = duckdb.connect(str(path))
    try:
        for table in coverage.KNOWN_TABLES:
            _create_table_with_seasons(con, table, [])
    finally:
        con.close()


def _build_empty_warehouse_no_column(path):
    con = duckdb.connect(str(path))
    try:
        for table in coverage.KNOWN_TABLES:
            _create_table_without_season_column(con, table)
    finally:
        con.close()


def _point_coverage_at(monkeypatch, path):
    monkeypatch.setattr(coverage, "warehouse_path", lambda: path)
    coverage.coverage_cache_clear()


def test_range_label_and_bounds(monkeypatch, tmp_path):
    path = tmp_path / "range.duckdb"
    _build_warehouse(path, RANGE_SEASONS)
    _point_coverage_at(monkeypatch, path)
    assert coverage.coverage_label() == RANGE_LABEL
    assert coverage.coverage_bounds() == ("2019-20", "2023-24")
    assert coverage.coverage_label().count("\u2013") == 1
    coverage.coverage_cache_clear()


def test_empty_warehouse_no_rows_label_is_none(monkeypatch, tmp_path):
    path = tmp_path / "empty_rows.duckdb"
    _build_empty_warehouse_no_rows(path)
    _point_coverage_at(monkeypatch, path)
    assert coverage.coverage_label() is None
    assert coverage.coverage_bounds() is None
    coverage.coverage_cache_clear()


def test_empty_warehouse_no_column_label_is_none(monkeypatch, tmp_path):
    path = tmp_path / "empty_cols.duckdb"
    _build_empty_warehouse_no_column(path)
    _point_coverage_at(monkeypatch, path)
    assert coverage.coverage_label() is None
    assert coverage.coverage_bounds() is None
    coverage.coverage_cache_clear()


def test_fallback_builders_have_no_future_season(monkeypatch, tmp_path):
    path = tmp_path / "fabricated.duckdb"
    _build_warehouse(path, RANGE_SEASONS)
    _point_coverage_at(monkeypatch, path)
    assert coverage.coverage_label() == RANGE_LABEL
    assert FUTURE_SEASON not in (coverage.coverage_label() or "")
    pytest.importorskip("pydantic_ai")
    graph = pytest.importorskip("app.graph")
    assert FUTURE_SEASON not in graph._coverage_claim()
    assert FUTURE_SEASON not in graph._coverage_span_line()
    assert FUTURE_SEASON not in graph._coverage_phrase()
    assert FUTURE_SEASON not in graph._compute_fallback()
    assert FUTURE_SEASON not in graph._analyst_system_content()
    coverage.coverage_cache_clear()


def test_single_season_label(monkeypatch, tmp_path):
    path = tmp_path / "single.duckdb"
    _build_warehouse(path, [SINGLE_SEASON])
    _point_coverage_at(monkeypatch, path)
    assert coverage.coverage_label() == SINGLE_SEASON
    assert coverage.coverage_bounds() == (SINGLE_SEASON, SINGLE_SEASON)
    coverage.coverage_cache_clear()


def test_league_seasons_missing_table_returns_empty_and_warns(
        monkeypatch, tmp_path, caplog):
    import logging

    path = tmp_path / "empty.duckdb"
    duckdb.connect(str(path)).close()
    _point_coverage_at(monkeypatch, path)
    with caplog.at_level(logging.WARNING, logger=coverage.__name__):
        assert coverage.league_seasons("silver_boxscores", "TEAM_ID", 30) == ()
    assert any("league_seasons" in record.message
               and "unreadable" in record.message
               for record in caplog.records)


def test_league_seasons_unexpected_error_propagates(monkeypatch, tmp_path):
    path = tmp_path / "empty.duckdb"
    duckdb.connect(str(path)).close()
    _point_coverage_at(monkeypatch, path)
    monkeypatch.setattr(
        coverage, "_read_league_seasons",
        lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic")))
    with pytest.raises(RuntimeError, match="synthetic"):
        coverage.league_seasons("silver_boxscores", "TEAM_ID", 30)
