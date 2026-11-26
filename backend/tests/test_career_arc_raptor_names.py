import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pytest

from shared import store

END_YEAR = 2022


def _hist_row(pid, name, team="DEN", season=END_YEAR):
    return (
        pid, name, team, season, 68, 31.0, 20.0, 5.0, 4.0,
        1.0, 0.5, 2.0, 0.50, 0.35, 0.80, 0.60,
    )


def _seed(path):
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_hist_player_seasons ("
            "player_id BIGINT, player_name VARCHAR, team_abbreviation VARCHAR, "
            "season INTEGER, gp BIGINT, min DOUBLE, pts DOUBLE, reb DOUBLE, "
            "ast DOUBLE, stl DOUBLE, blk DOUBLE, tov DOUBLE, fg_pct DOUBLE, "
            "fg3_pct DOUBLE, ft_pct DOUBLE, ts_pct DOUBLE)"
        )
        con.executemany(
            "INSERT INTO silver_hist_player_seasons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                _hist_row(770000001, "Milos Vesely"),
                _hist_row(770000002, "Dangelo Morris", "BOS"),
                _hist_row(770000003, "Marcus\u00a0Bell", "NYK"),
                _hist_row(770000004, "Emir Kovic", "CHI", 2023),
            ],
        )
        con.execute(
            "CREATE TABLE silver_leaders_pts ("
            "PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR, GP BIGINT, "
            "MIN BIGINT, PTS BIGINT, REB BIGINT, AST BIGINT, STL BIGINT, "
            "BLK BIGINT, FG_PCT DOUBLE, FG3_PCT DOUBLE, FT_PCT DOUBLE, "
            "_season VARCHAR)"
        )
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "(770000005, 'Rui Santos', 'DEN', 10, 300, 200, 50, 40, "
            "8, 2, 0.50, 0.40, 0.80, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_raptor_player ("
            "PLAYER_NAME VARCHAR, SEASON BIGINT, RAPTOR_TOTAL DOUBLE, _season VARCHAR)"
        )
        con.executemany(
            "INSERT INTO silver_raptor_player VALUES (?, ?, ?, ?)",
            [
                ("Miloš Veselý", 2021, 9.0, "2020-21"),
                ("Miloš Veselý", 2022, 5.0, "2021-22"),
                ("D'Angelo Morris", 2022, 3.0, "2021-22"),
                ("Marcus Bell Jr.", 2022, 2.0, "2021-22"),
                ("Emir Ković", 2021, 10.0, "2020-21"),
            ],
        )
    finally:
        con.close()


@pytest.fixture()
def raptor_name_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "career-arc.duckdb"
    _seed(db)
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return db


@pytest.mark.parametrize(
    ("pid", "total"),
    [
        (770000001, 5.0),
        (770000002, 3.0),
        (770000003, 2.0),
    ],
)
def test_arc_normalizes_cross_feed_raptor_names(raptor_name_warehouse, pid, total):
    from shared.tools import career_arc as arc

    rows = arc.arc_for_id(pid)
    row = next(r for r in rows if r["end_year"] == END_YEAR)
    assert row["raptor"] == total
    assert row["raptor_gap"] is False


def test_raptor_map_returns_exact_end_year_keys(raptor_name_warehouse):
    from shared.tools import career_arc as arc

    assert arc.raptor_map("Milos Vesely", 770000001) == {2021: 9.0, 2022: 5.0}


def test_prior_raptor_vintage_is_not_substituted(raptor_name_warehouse):
    from shared.tools import career_arc as arc

    rows = arc.arc_for_id(770000004)
    row = next(r for r in rows if r["end_year"] == 2023)
    assert row["raptor"] is None
    assert row["raptor_gap"] is True


def test_get_career_arc_uses_normalized_cross_feed_raptor_name(raptor_name_warehouse):
    from shared.tools.career_arc import get_career_arc

    out = get_career_arc.invoke({"player": "Milos Vesely"})
    assert out["ok"] is True
    row = next(r for r in out["rows"] if r["end_year"] == END_YEAR)
    assert row["raptor"] == 5.0


@pytest.mark.parametrize(
    ("name", "pid"),
    [
        ("Miloš Veselý", 770000001),
        ("D'Angelo Morris", 770000002),
        ("Marcus Bell Jr.", 770000003),
    ],
)
def test_get_career_arc_normalizes_exact_player_resolution(raptor_name_warehouse, name, pid):
    from shared.tools.career_arc import get_career_arc

    out = get_career_arc.invoke({"player": name})
    assert out["ok"] is True
    assert out["player_id"] == pid


def test_hist_rows_name_fallback_normalizes_cross_feed_variants(raptor_name_warehouse):
    from shared.tools import career_arc as arc

    rows = arc._hist_rows(0, "D'Angelo Morris")
    assert rows
    assert rows[0]["player_id"] == 770000002


def test_get_career_arc_normalizes_current_feed_player_resolution(raptor_name_warehouse):
    from shared.tools.career_arc import get_career_arc

    out = get_career_arc.invoke({"player": "Rúi Sántos"})
    assert out["ok"] is True
    assert out["player_id"] == 770000005
    assert out["rows"][0]["source"] == "current"


def test_player_name_key_sql_matches_contract_normalization():
    from shared.contracts import normalize_name
    from shared.tools.career_arc import _player_name_key_sql

    names = [
        "Miloš Veselý",
        "D'Angelo Morris",
        "Marcus Bell Jr.",
        "Marcus Bell Jr III",
        "  Milos   Vesely  ",
        "Anne-Marie D'Souza Sr.",
        "Jokic\u0301",
        "Marcus\u00a0Bell Jr.",
    ]
    con = duckdb.connect(":memory:")
    try:
        for name in names:
            key = con.execute(
                f"SELECT {_player_name_key_sql('?')}", [name]
            ).fetchone()[0]
            assert key == normalize_name(name)
    finally:
        con.close()
