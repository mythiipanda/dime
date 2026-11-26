import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pytest

from shared import store

SEASON = "2021-22"

STATIC_PLAYERS = [
    {"id": 990000001, "full_name": "Milos Vesely"},
    {"id": 990000002, "full_name": "Dangelo Morris"},
    {"id": 990000003, "full_name": "Marcus Bell"},
    {"id": 990000004, "full_name": "Emir Kovic"},
]


def _seed(path):
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_raptor_player ("
            "PLAYER_NAME VARCHAR, SEASON BIGINT, RAPTOR_OFFENSE DOUBLE, "
            "RAPTOR_DEFENSE DOUBLE, RAPTOR_TOTAL DOUBLE, WAR_TOTAL DOUBLE, "
            "_season VARCHAR)"
        )
        con.executemany(
            "INSERT INTO silver_raptor_player VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("Miloš Veselý", 2022, 4.0, 1.0, 5.0, 8.0, SEASON),
                ("D'Angelo Morris", 2022, 1.0, 2.0, 3.0, 4.0, SEASON),
                ("Marcus Bell Jr.", 2022, 0.5, 1.5, 2.0, 3.0, SEASON),
                ("Emir Ković", 2021, 9.0, 1.0, 10.0, 12.0, "2020-21"),
            ],
        )
    finally:
        con.close()


@pytest.fixture()
def raptor_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "compare-metrics.duckdb"
    _seed(db)
    monkeypatch.setattr(store, "connect", lambda **_kw: duckdb.connect(str(db), read_only=True))
    return db


@pytest.fixture()
def static_names(monkeypatch):
    from nba_api.stats.static import players as static_players

    monkeypatch.setattr(static_players, "get_players", lambda: [dict(p) for p in STATIC_PLAYERS])


def test_compare_metrics_normalizes_cross_feed_raptor_names(raptor_warehouse, static_names):
    from shared.tools.player import compare_metrics

    out = compare_metrics.invoke({"a": "990000001", "b": "990000002", "season": SEASON})
    assert out["ok"] is True
    metrics = {row["metric"]: row for row in out["rows"]["metrics"]}
    assert metrics["raptor"]["a"] == 5.0
    assert metrics["raptor"]["b"] == 3.0
    assert metrics["raptor_o"]["a"] == 4.0
    assert metrics["raptor_d"]["b"] == 2.0
    assert metrics["war"]["a"] == 8.0
    assert out["meta"]["raptor_gap"] is False


@pytest.mark.parametrize(
    ("pid", "name", "total"),
    [
        (990000001, "Milos Vesely", 5.0),
        (990000002, "Dangelo Morris", 3.0),
        (990000003, "Marcus Bell", 2.0),
    ],
)
def test_metric_player_stats_matches_accent_punctuation_and_suffix_variants(
        raptor_warehouse, pid, name, total):
    from shared.tools.player.comparisons import _metric_player_stats

    row = _metric_player_stats(pid, name, SEASON)
    assert row["RAPTOR_TOTAL"] == total
    assert row["raptor_season"] == SEASON


def test_wrong_season_raptor_is_not_current_verdict_evidence(raptor_warehouse, static_names):
    from shared.tools.player import compare_metrics

    out = compare_metrics.invoke({"a": "990000004", "b": "990000003", "season": SEASON})
    assert out["ok"] is True
    assert out["meta"]["raptor_season_a"] == "2020-21"
    assert out["meta"]["raptor_season_b"] == SEASON
    assert out["meta"]["raptor_gap"] is True
    historical = out["rows"]["metrics"][:4]
    assert all(not row["eligible_for_verdict"] for row in historical)
    assert all("Historical context only" in row["note"] for row in historical)


def test_player_name_key_sql_matches_contract_normalization():
    from shared.contracts import normalize_name
    from shared.tools.player.comparisons import _player_name_key_sql

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
