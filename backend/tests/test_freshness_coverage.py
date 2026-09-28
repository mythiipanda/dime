"""Hermetic tests for shared.freshness.table_data_through.

Runs against a fabricated in-memory warehouse (no FastAPI, no real warehouse),
so it works in the bare sandbox as well as CI.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.freshness import table_data_through


def _cols(con, t):
    return [r[1] for r in con.execute(f"PRAGMA table_info({t})").fetchall()]


@pytest.fixture()
def warehouse():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE silver_gamelogs (GAME_DATE VARCHAR)")
    con.execute(
        "INSERT INTO silver_gamelogs VALUES "
        "('Oct 28, 2025'), ('2026-09-26'), ('not a date'), (NULL)"
    )
    con.execute("CREATE TABLE silver_team_games (GAME_DATE VARCHAR)")
    con.execute("INSERT INTO silver_team_games VALUES ('2026-09-24'), ('2026-09-20')")
    con.execute("CREATE TABLE silver_standings (TEAM VARCHAR)")
    con.execute("INSERT INTO silver_standings VALUES ('BOS')")
    con.execute("CREATE TABLE silver_empty (GAME_DATE VARCHAR)")
    con.execute("CREATE TABLE silver_junk (GAME_DATE VARCHAR)")
    con.execute("INSERT INTO silver_junk VALUES ('garbage'), ('1800-01-01')")
    yield con
    con.close()


def test_mixed_date_formats_take_max(warehouse):
    assert table_data_through(
        warehouse, "silver_gamelogs", _cols(warehouse, "silver_gamelogs")
    ) == "2026-09-26"


def test_iso_dates(warehouse):
    assert table_data_through(
        warehouse, "silver_team_games", _cols(warehouse, "silver_team_games")
    ) == "2026-09-24"


def test_no_date_column_returns_none(warehouse):
    assert table_data_through(
        warehouse, "silver_standings", _cols(warehouse, "silver_standings")
    ) is None


def test_empty_table_returns_none(warehouse):
    assert table_data_through(
        warehouse, "silver_empty", _cols(warehouse, "silver_empty")
    ) is None


def test_unparseable_and_out_of_range_clamped(warehouse):
    assert table_data_through(
        warehouse, "silver_junk", _cols(warehouse, "silver_junk")
    ) is None


def test_missing_table_never_raises(warehouse):
    assert table_data_through(warehouse, "missing_table", []) is None
