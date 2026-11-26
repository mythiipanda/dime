import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pytest

from shared import store

SEASON = "2021-22"
PRIOR_SEASON = "2020-21"


def _seed(path):
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_raptor_player ("
            "PLAYER_ID BIGINT, PLAYER_NAME VARCHAR, SEASON BIGINT, POSS DOUBLE, MP DOUBLE, "
            "RAPTOR_BOX_TOTAL DOUBLE, RAPTOR_ONOFF_TOTAL DOUBLE, RAPTOR_TOTAL DOUBLE, "
            "RAPTOR_OFFENSE DOUBLE, RAPTOR_DEFENSE DOUBLE, WAR_TOTAL DOUBLE, _season VARCHAR)"
        )
        con.executemany(
            "INSERT INTO silver_raptor_player VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (880000001, "Miloš Veselý", 2022, 3000.0, 2200.0, 4.0, 2.0, 4.8, 4.0, 1.0, 8.0, SEASON),
                (880000002, "D'Angelo Morris", 2022, 2800.0, 2100.0, 2.0, 1.0, 3.0, 1.0, 2.0, 4.0, SEASON),
                (880000003, "Marcus Bell Jr.", 2022, 2600.0, 2000.0, 1.5, 0.5, 2.0, 0.5, 1.5, 3.0, SEASON),
                (880000004, "Emir Ković", 2021, 3200.0, 2400.0, 8.0, 2.0, 10.0, 9.0, 1.0, 12.0, PRIOR_SEASON),
            ],
        )
        con.execute(
            "CREATE TABLE silver_raptor_team ("
            "TEAM VARCHAR, _season VARCHAR, PLAYER_NAME VARCHAR, SEASON_TYPE VARCHAR)"
        )
        con.executemany(
            "INSERT INTO silver_raptor_team VALUES (?, ?, ?, ?)",
            [
                ("DEN", SEASON, "Miloš Veselý", "RS"),
                ("BOS", SEASON, "D'Angelo Morris", "RS"),
                ("NYK", SEASON, "Marcus Bell Jr.", "RS"),
                ("CHI", PRIOR_SEASON, "Emir Ković", "RS"),
            ],
        )
    finally:
        con.close()


@pytest.fixture()
def raptor_name_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "clutch-splits.duckdb"
    _seed(db)
    monkeypatch.setattr(store, "connect", lambda **_kw: duckdb.connect(str(db), read_only=True))
    return db


@pytest.mark.parametrize(
    ("name", "total"),
    [
        ("Milos Vesely", 4.8),
        ("Dangelo Morris", 3.0),
        ("Marcus Bell", 2.0),
        ("Marcus\u00a0Bell Jr", 2.0),
    ],
)
def test_raptor_row_normalizes_cross_feed_name_variants(raptor_name_warehouse, name, total):
    from shared.tools.player.clutch_splits import _raptor_row

    row = _raptor_row(990000001, name, SEASON)
    assert row is not None
    assert row["RAPTOR_TOTAL"] == total


def test_raptor_row_keeps_exact_season_vintage(raptor_name_warehouse):
    from shared.tools.player.clutch_splits import _raptor_row

    assert _raptor_row(990000001, "Emir Kovic", SEASON) is None
    prior = _raptor_row(990000001, "Emir Kovic", PRIOR_SEASON)
    assert prior is not None
    assert prior["RAPTOR_TOTAL"] == 10.0


def test_stale_raptor_normalizes_name_and_keeps_prior_vintage(raptor_name_warehouse):
    from shared.tools.player.clutch_splits import _stale_raptor

    stale = _stale_raptor(990000001, "Emir Kovic", SEASON)
    assert stale is not None
    assert stale["_season"] == PRIOR_SEASON
    assert stale["RAPTOR_TOTAL"] == 10.0
    assert _stale_raptor(990000001, "Emir Kovic", PRIOR_SEASON) is None


def test_get_impact_estimate_uses_normalized_cross_feed_name(raptor_name_warehouse, monkeypatch):
    import shared.tools.player as player_tools

    monkeypatch.setattr(player_tools, "coerce_player_id", lambda _value: 990000001)
    out = player_tools.get_impact_estimate.invoke({"player": "Milos Vesely", "season": SEASON})
    assert out["ok"] is True
    assert out["method"] == "raptor_components"
    assert out["player"]["name"] == "Miloš Veselý"
    assert out["measured"]["total_per_100"] == 4.8


def test_raptor_history_normalizes_cross_feed_input_and_team_lookup(raptor_name_warehouse):
    from shared.tools.player import get_raptor_history

    out = get_raptor_history.invoke({"player": "Milos Vesely", "season": SEASON})
    assert out["ok"] is True, out
    assert out["rows"][0]["TEAM"] == "DEN"
    assert out["rows"][0]["RAPTOR"] == 4.8


def test_player_name_key_sql_matches_contract_normalization():
    from shared.contracts import normalize_name
    from shared.tools.player.clutch_splits import _player_name_key_sql

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
