import hashlib
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import store
from analyst import boards as service
from analyst.board_metrics import METRICS

@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    path = tmp_path / "boards.duckdb"
    con = duckdb.connect(str(path))
    provenance = '_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, _entity VARCHAR'
    for table in ("silver_player_season", "silver_advanced"):
        columns = sorted({m.column for m in METRICS.values() if m.table == table})
        identity = 'PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR' if table == "silver_player_season" else 'PLAYER_ID BIGINT, PLAYER_NAME VARCHAR, TEAM_ABBREVIATION VARCHAR, GP DOUBLE, MIN DOUBLE'
        con.execute(f'CREATE TABLE {table} ({identity}, {", ".join(c + " DOUBLE" for c in columns)}, {provenance})')
    con.execute(f'CREATE TABLE silver_cap_players (player VARCHAR, team VARCHAR, salary BIGINT, {provenance})')
    for pid, name, points, gp, mpg, defense in [
        (1, "Alpha Guard", 20, 50, 30, 100),
        (2, "Beta Wing", 30, 60, 35, 110),
        (3, "Gamma Center", 40, 5, 10, 90),
    ]:
        con.execute('INSERT INTO silver_player_season (PLAYER_ID,PLAYER,TEAM,PPG,GP,MPG,FG_PCT,_source,_season,_fetched_at,_entity) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    [pid, name, "AAA", points, gp, mpg, .5, "fixture", "2025-26", "2026-09-01", "league"])
        con.execute('INSERT INTO silver_advanced (PLAYER_ID,PLAYER_NAME,TEAM_ABBREVIATION,GP,MIN,TS_PCT,DEF_RATING,TM_TOV_PCT,_source,_season,_fetched_at,_entity) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    [pid, name, "AAA", gp, mpg, .6, defense, 12.5, "fixture-advanced", "2025-26", "2026-09-02", "advanced"])
    con.execute("INSERT INTO silver_cap_players VALUES ('Alpha Guard','AAA',1000000,'salary-fixture','2026-27','2026-09-03','season:2026-27')")
    con.close()
    monkeypatch.setattr(store, "connect", lambda **kwargs: duckdb.connect(str(path), read_only=kwargs.get("read_only", False)))
    return path



def fill(ids=None, metrics=None, **extra):
    return service.fill({"player_ids": [1, 2] if ids is None else ids,
                         "metric_ids": ["ppg", "ts_pct"] if metrics is None else metrics, **extra})


def test_registry_and_read_only_fills_with_replayable_citations(warehouse, monkeypatch):
    before = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    connect = store.connect
    calls = []
    def readonly(**kwargs):
        assert kwargs == {"read_only": True}
        calls.append(kwargs)
        return connect(**kwargs)
    monkeypatch.setattr(store, "connect", readonly)
    assert len(service.metrics()["metrics"]) == len(METRICS) == 25
    result = fill(metrics=["ppg", "fg_pct", "ts_pct", "tov_pct", "salary_2026_27"])
    assert result["ok"] is True
    cells = result["cells"]["1"]
    assert [cells[m]["value"] for m in ["ppg", "fg_pct", "ts_pct", "tov_pct", "salary_2026_27"]] == [20, 50, 60, 12.5, 1000000]
    with duckdb.connect(str(warehouse), read_only=True) as con:
        for cell in cells.values():
            citation = cell["citation"]
            assert con.execute(citation["sql"], citation["params"]).fetchall()
            assert citation["source"] and citation["fetched_at"] and citation["row_key"]
    assert cells["salary_2026_27"]["citation"]["salary_vintage"] == {"season": "2026-27", "fetched_at": "2026-09-03"}
    assert fill(ids=[], metrics=[]) == {"ok": True, "cells": {}, "players": {}}
    assert service.seed({"metric_id": "ppg", "n": 1})["player_ids"] == [3]
    assert calls and hashlib.sha256(warehouse.read_bytes()).hexdigest() == before


def test_accent_safe_salary_identity_and_single_vintage(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("UPDATE silver_player_season SET PLAYER='Luka Dončić' WHERE PLAYER_ID=1")
        con.execute("UPDATE silver_advanced SET PLAYER_NAME='Luka Doncic' WHERE PLAYER_ID=1")
        con.execute("UPDATE silver_cap_players SET player='  LUKA  DONCIC '")
        con.execute("INSERT INTO silver_cap_players VALUES ('Luka Doncic','OLD',1,'old','2025-26','2025-01-01','old')")
    cell = fill(ids=[1], metrics=["salary_2026_27"])["cells"]["1"]["salary_2026_27"]
    assert cell["value"] == 1000000
    assert cell["citation"]["params"] == ["2026-27"]
    assert cell["citation"]["identity_resolution"]["player_id"] == 1
    with duckdb.connect(str(warehouse)) as con:
        con.execute("UPDATE silver_advanced SET PLAYER_NAME='Luka Doncic' WHERE PLAYER_ID=2")
    cell = fill(ids=[1], metrics=["salary_2026_27"])["cells"]["1"]["salary_2026_27"]
    assert cell["value"] is None and cell["reason"] == "ambiguous_salary_name"
    assert {ref["player_id"] for ref in cell["citation"]["identity_resolution"]["collisions"]} == {1, 2}


def test_missing_reasons_and_advanced_only_identity(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("DELETE FROM silver_player_season WHERE PLAYER_ID=1")
        con.execute("UPDATE silver_advanced SET TS_PCT='NaN' WHERE PLAYER_ID=2")
    cells = fill(ids=[1, 2, 999], metrics=["ppg", "ts_pct", "salary_2026_27", "unknown"])["cells"]
    assert cells["1"]["ppg"]["reason"] == "no_metric_row"
    assert cells["1"]["salary_2026_27"]["value"] == 1000000
    assert cells["2"]["ts_pct"]["reason"] == "missing_or_nonfinite_value"
    assert cells["2"]["salary_2026_27"]["reason"] == "unmatched_salary_name"
    assert cells["999"]["ppg"]["reason"] == "unknown_player"
    assert cells["1"]["unknown"]["reason"] == "unknown_metric"
    assert fill(ids=[1], metrics=["ts_pct"])["players"]["1"]["name"] == "Alpha Guard"


def test_duplicate_rows_and_incomplete_identity_never_guess(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("INSERT INTO silver_player_season SELECT * FROM silver_player_season WHERE PLAYER_ID=1")
        con.execute("INSERT INTO silver_cap_players SELECT * FROM silver_cap_players")
    cells = fill(ids=[1], metrics=["ppg", "salary_2026_27"])["cells"]["1"]
    assert cells["ppg"]["reason"] == "ambiguous_metric_rows"
    assert cells["salary_2026_27"]["reason"] == "ambiguous_salary_rows"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("DROP TABLE silver_advanced")
    cell = fill(ids=[1], metrics=["salary_2026_27"])["cells"]["1"]["salary_2026_27"]
    assert cell["value"] is None and cell["reason"] == "identity_incomplete"
    assert service.seed({"metric_id": "salary_2026_27"})["status"] == 503
    assert fill(metrics=["ts_pct"])["status"] == 503


def test_seeds_are_deterministic_with_ties_filters_and_metric_direction(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("UPDATE silver_player_season SET PPG=20 WHERE PLAYER_ID=2")
    payload = {"metric_id": "ppg", "n": 3, "min_gp": 10, "min_mpg": 20}
    assert service.seed(payload)["player_ids"] == [1, 2]
    assert service.seed(payload) == service.seed(payload)
    assert service.seed({"metric_id": "def_rating"})["player_ids"] == [3, 1, 2]
    assert service.seed({"metric_id": "ppg", "min_gp": 100})["player_ids"] == []
    assert service.seed({"metric_id": "salary_2026_27"})["player_ids"] == [1]
    assert service.seed({"metric_id": "unknown"})["status"] == 422


@pytest.mark.parametrize("payload", [
    {"player_ids": ["1"], "metric_ids": ["ppg"]},
    {"player_ids": [True], "metric_ids": ["ppg"]},
    {"player_ids": list(range(1, 52)), "metric_ids": ["ppg"]},
    {"player_ids": [1], "metric_ids": ["ppg"], "season": "bad"},
    {"player_ids": [1], "metric_ids": ["ppg"], "extra": 1},
])
def test_validation(payload):
    assert service.fill(payload)["status"] == 422


def test_direct_catalogue_bridge(warehouse):
    from analyst.direct_data import product_board_fill, product_board_seed, product_board_metrics
    assert len(product_board_metrics.invoke({})["metrics"]) == 25
    assert product_board_fill.invoke({"payload": {"player_ids": [1], "metric_ids": ["ppg"]}})["cells"]["1"]["ppg"]["value"] == 20
    assert product_board_seed.invoke({"payload": {"metric_id": "ppg", "n": 1}})["player_ids"] == [3]
    json.dumps(product_board_fill.invoke({"payload": {"player_ids": [1], "metric_ids": list(METRICS)}}))
