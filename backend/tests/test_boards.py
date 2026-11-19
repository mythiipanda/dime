from pathlib import Path
import sys

import duckdb
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared import store
from v2.boards import service
from v2.boards.metrics import METRICS
from v2.main import app


WAREHOUSE = store.DB_PATH
client = TestClient(app)


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
    return client.post("/api/boards/fill", json={"player_ids": ids if ids is not None else [1, 2],
                                               "metric_ids": metrics if metrics is not None else ["ppg", "ts_pct"], **extra})


def test_registry_integrity_and_real_values():
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not provisioned")
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        assert len(METRICS) == 25
        for metric_id, metric in METRICS.items():
            assert metric.id == metric_id and metric.definition and metric.label
            assert metric.column in {row[0] for row in con.execute(f'DESCRIBE "{metric.table}"').fetchall()}
        ids = [201939, 203999]
        result = service._fill(con, "2025-26", ids, ["ppg", "fg_pct", "ts_pct"])
        for pid in ids:
            ppg, fg = con.execute('SELECT PPG,FG_PCT FROM silver_player_season WHERE PLAYER_ID=? AND _season=?', [pid, "2025-26"]).fetchone()
            ts = con.execute('SELECT TS_PCT FROM silver_advanced WHERE PLAYER_ID=? AND _season=?', [pid, "2025-26"]).fetchone()[0]
            assert result["cells"][str(pid)]["ppg"]["value"] == ppg
            assert result["cells"][str(pid)]["fg_pct"]["value"] == pytest.approx(fg * 100)
            assert result["cells"][str(pid)]["ts_pct"]["value"] == pytest.approx(ts * 100)


def test_registry_http(warehouse):
    response = client.get("/api/boards/metrics")
    assert response.status_code == 200
    assert len(response.json()["metrics"]) == 25
    assert {"id", "label", "category", "unit", "table", "column", "higher_is_better", "definition"} == set(response.json()["metrics"][0])


def test_real_advanced_only_player_and_seed(monkeypatch):
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not provisioned")
    monkeypatch.setattr(store, "connect", lambda **kwargs: duckdb.connect(str(WAREHOUSE), read_only=True))
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM silver_player_season WHERE PLAYER_ID=1631260 AND _season='2025-26'").fetchone()[0] == 0
        rating, name, team = con.execute("SELECT NET_RATING,PLAYER_NAME,TEAM_ABBREVIATION FROM silver_advanced WHERE PLAYER_ID=1631260 AND _season='2025-26'").fetchone()
        expected = [r[0] for r in con.execute("SELECT PLAYER_ID FROM silver_advanced WHERE _season='2025-26' AND GP>=78 AND MIN>=29.1 AND NET_RATING IS NOT NULL ORDER BY NET_RATING DESC,PLAYER_ID LIMIT 25").fetchall()]
    result = fill(ids=[1631260], metrics=["net_rating"]).json()
    assert result["cells"]["1631260"]["net_rating"]["value"] == rating
    assert result["players"]["1631260"] == {"name": name, "team": team}
    seeded = client.post("/api/boards/seed", json={"metric_id": "net_rating", "n": 25, "min_gp": 78, "min_mpg": 29.1}).json()
    assert seeded["player_ids"] == expected
    assert 1631260 in seeded["player_ids"]


def test_metric_rows_do_not_depend_on_basic_coverage(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("DELETE FROM silver_player_season WHERE PLAYER_ID=1")
    result = fill(ids=[1], metrics=["ts_pct", "ppg", "salary_2026_27"]).json()
    assert result["players"]["1"] == {"name": "Alpha Guard", "team": "AAA"}
    assert result["cells"]["1"]["ts_pct"]["value"] == 60
    assert result["cells"]["1"]["ppg"]["reason"] == "no_metric_row"
    salary = result["cells"]["1"]["salary_2026_27"]
    assert salary["value"] == 1000000
    assert salary["citation"]["identity_resolution"]["table"] == "silver_advanced"
    result = client.post("/api/boards/seed", json={"metric_id": "def_rating", "min_gp": 10, "min_mpg": 20}).json()
    assert result["player_ids"] == [1, 2]


@pytest.fixture
def real_warehouse(monkeypatch):
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not provisioned")
    monkeypatch.setattr(store, "connect", lambda **kwargs: duckdb.connect(str(WAREHOUSE), read_only=True))
    return WAREHOUSE


def test_real_salary_seed_includes_advanced_only_malachi(real_warehouse):
    with duckdb.connect(str(real_warehouse), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM silver_player_season WHERE PLAYER_ID=1641869 AND _season='2025-26'").fetchone()[0] == 0
        assert con.execute("SELECT salary FROM silver_cap_players WHERE player='Malachi Smith' AND _season='2026-27'").fetchone()[0] == 2150917
    result = client.post("/api/boards/seed", json={"metric_id": "salary_2026_27", "n": 25}).json()
    assert 1641869 in result["player_ids"]
    assert result["cells"]["1641869"]["salary_2026_27"]["value"] == 2150917
    assert result["players"]["1641869"]["name"] == "Malachi Smith"
    values = [result["cells"][str(pid)]["salary_2026_27"]["value"] for pid in result["player_ids"]]
    assert values == sorted(values)


def test_real_salary_matches_walter_alternative_spelling(real_warehouse):
    with duckdb.connect(str(real_warehouse), read_only=True) as con:
        assert con.execute("SELECT PLAYER FROM silver_player_season WHERE PLAYER_ID=1642383 AND _season='2025-26'").fetchone()[0] == "Walter Clayton"
        expected = con.execute("SELECT salary FROM silver_cap_players WHERE player='Walter Clayton Jr.' AND _season='2026-27'").fetchone()[0]
    cell = fill(ids=[1642383], metrics=["salary_2026_27"]).json()["cells"]["1642383"]["salary_2026_27"]
    assert cell["value"] == expected == 4190520
    resolution = cell["citation"]["identity_resolution"]
    assert set(resolution["spellings"]) == {"walter clayton", "walter clayton jr."}
    assert resolution["table"] == "silver_advanced"


def test_real_jaren_collision_lists_all_ids_and_tables(real_warehouse):
    result = fill(ids=[1114, 1628991], metrics=["salary_2026_27"]).json()
    for pid in [1114, 1628991]:
        cell = result["cells"][str(pid)]["salary_2026_27"]
        assert cell["value"] is None and cell["reason"] == "ambiguous_salary_name"
        collisions = cell["citation"]["identity_resolution"]["collisions"]
        assert {(ref["player_id"], ref["table"]) for ref in collisions} == {
            (1114, "silver_player_season"), (1628991, "silver_advanced")}
        for ref in collisions:
            assert ref["sql"] and ref["params"] == ["2025-26"]
            assert ref["source"] and ref["row_key"]["PLAYER_ID"] == ref["player_id"]


def test_salary_seed_only_applies_requested_filters(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("DELETE FROM silver_player_season WHERE PLAYER_ID=1")
        con.execute("UPDATE silver_advanced SET GP=NULL,MIN=NULL WHERE PLAYER_ID=1")
    assert client.post("/api/boards/seed", json={"metric_id": "salary_2026_27"}).json()["player_ids"] == [1]
    assert client.post("/api/boards/seed", json={"metric_id": "salary_2026_27", "min_gp": 0}).json()["player_ids"] == []
    assert client.post("/api/boards/seed", json={"metric_id": "salary_2026_27", "min_mpg": 0}).json()["player_ids"] == []


def test_alternative_salary_names_do_not_bypass_collisions(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("UPDATE silver_advanced SET PLAYER_NAME='Alternate Name' WHERE PLAYER_ID=1")
        con.execute("INSERT INTO silver_advanced (PLAYER_ID,PLAYER_NAME,_season) VALUES (4,'Alternate Name','2025-26')")
        con.execute("UPDATE silver_cap_players SET player='Alternate Name'")
    cell = fill(ids=[1], metrics=["salary_2026_27"]).json()["cells"]["1"]["salary_2026_27"]
    assert cell["value"] is None and cell["reason"] == "ambiguous_salary_name"
    assert {ref["player_id"] for ref in cell["citation"]["identity_resolution"]["collisions"]} == {1, 4}


def test_fill_and_replayable_citations(warehouse):
    response = fill(metrics=["ppg", "fg_pct", "ts_pct", "tov_pct", "salary_2026_27"])
    assert response.status_code == 200
    result = response.json()
    assert result["players"]["1"] == {"name": "Alpha Guard", "team": "AAA"}
    cells = result["cells"]["1"]
    assert [cells[m]["value"] for m in ["ppg", "fg_pct", "ts_pct", "tov_pct", "salary_2026_27"]] == [20, 50, 60, 12.5, 1000000]
    with duckdb.connect(str(warehouse), read_only=True) as con:
        for metric_id, cell in cells.items():
            citation = cell["citation"]
            rows = con.execute(citation["sql"], citation["params"]).fetchall()
            assert rows
            assert citation["source"] and citation["fetched_at"] and citation["row_key"]
            assert citation["table"] == METRICS[metric_id].table
            assert citation["column"] == METRICS[metric_id].column
    salary = cells["salary_2026_27"]["citation"]
    assert salary["season"] == "2026-27"
    assert salary["salary_vintage"] == {"season": "2026-27", "fetched_at": "2026-09-03"}
    assert salary["identity_resolution"]["player_id"] == 1
    assert result["cells"]["2"]["salary_2026_27"]["reason"] == "unmatched_salary_name"


def test_one_parameterized_query_per_table(warehouse, monkeypatch):
    queries = []
    connect = store.connect

    class Connection:
        def __enter__(self):
            self.con = connect(read_only=True)
            return self

        def __exit__(self, *args):
            self.con.close()

        def execute(self, sql, params):
            queries.append((sql, params))
            return self.con.execute(sql, params)

    monkeypatch.setattr(store, "connect", lambda **kwargs: Connection())
    assert fill(ids=[1, 2, 3], metrics=list(METRICS)).status_code == 200
    assert len(queries) == 3
    assert all("?" in sql and len(params) == 1 for sql, params in queries)


def test_missing_unknown_and_empty(warehouse):
    result = fill(ids=[1, 999], metrics=["not_sql; DROP TABLE x", "rpg", "ppg"]).json()
    assert result["cells"]["1"]["not_sql; DROP TABLE x"]["reason"] == "unknown_metric"
    assert result["cells"]["999"]["ppg"]["reason"] == "unknown_player"
    assert result["cells"]["1"]["rpg"]["value"] is None
    assert result["cells"]["1"]["rpg"]["reason"] == "missing_or_nonfinite_value"
    assert fill(ids=[]).json() == {"ok": True, "cells": {}, "players": {}}
    assert fill(metrics=[]).json()["cells"] == {"1": {}, "2": {}}
    assert fill(season="1999-00").json()["cells"]["1"]["ppg"]["value"] is None


@pytest.mark.parametrize("ambiguous_identity", [True, False])
def test_salary_ambiguity_never_guesses(warehouse, ambiguous_identity):
    with duckdb.connect(str(warehouse)) as con:
        if ambiguous_identity:
            con.execute("INSERT INTO silver_player_season (PLAYER_ID,PLAYER,TEAM,_season) VALUES (4,'ALPHA  GUARD','BBB','2025-26')")
        else:
            con.execute("INSERT INTO silver_cap_players SELECT * FROM silver_cap_players")
    cell = fill(ids=[1], metrics=["salary_2026_27"]).json()["cells"]["1"]["salary_2026_27"]
    assert cell["value"] is None
    assert cell["reason"] == ("ambiguous_salary_name" if ambiguous_identity else "ambiguous_salary_rows")


def test_null_names_and_nonfinite_values(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("UPDATE silver_player_season SET PLAYER=NULL,PPG='NaN'::DOUBLE WHERE PLAYER_ID=1")
        con.execute("UPDATE silver_advanced SET PLAYER_NAME=NULL WHERE PLAYER_ID=1")
        con.execute("INSERT INTO silver_cap_players VALUES (NULL,'AAA',5,'fixture','2026-27','today','league')")
    result = fill(ids=[1], metrics=["ppg", "salary_2026_27"]).json()
    assert result["cells"]["1"]["salary_2026_27"]["reason"] == "unmatched_salary_name"
    assert result["cells"]["1"]["ppg"]["value"] is None
    assert result["cells"]["1"]["ppg"]["reason"] == "missing_or_nonfinite_value"


def test_ambiguous_metric_rows_are_not_selected_arbitrarily(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("INSERT INTO silver_advanced SELECT * FROM silver_advanced WHERE PLAYER_ID=1")
    cell = fill(ids=[1], metrics=["ts_pct"]).json()["cells"]["1"]["ts_pct"]
    assert cell["value"] is None and cell["reason"] == "ambiguous_metric_rows"


@pytest.mark.parametrize("metric,expected", [("ppg", [2, 1]), ("def_rating", [1, 2])])
def test_seed_order_filters_and_citations(warehouse, metric, expected):
    response = client.post("/api/boards/seed", json={"metric_id": metric, "n": 2, "min_gp": 10, "min_mpg": 20})
    assert response.status_code == 200
    result = response.json()
    assert result["player_ids"] == expected
    assert all(result["cells"][str(pid)][metric]["citation"]["sql"] for pid in expected)
    assert result["filters"]["params"] == ["2025-26"]


def test_seed_empty_unknown_and_salary(warehouse):
    assert client.post("/api/boards/seed", json={"metric_id": "ppg", "min_gp": 100}).json()["player_ids"] == []
    assert client.post("/api/boards/seed", json={"metric_id": "salary_2026_27"}).json()["player_ids"] == [1]
    assert client.post("/api/boards/seed", json={"metric_id": "unknown"}).status_code == 422


@pytest.mark.parametrize("path,payload", [
    ("fill", {"player_ids": list(range(1, 52)), "metric_ids": ["ppg"]}),
    ("fill", {"player_ids": [1], "metric_ids": ["ppg"] * 31}),
    ("fill", {"player_ids": [-1], "metric_ids": ["ppg"]}),
    ("fill", {"player_ids": [True], "metric_ids": ["ppg"]}),
    ("fill", {"season": "bad", "player_ids": [1], "metric_ids": ["ppg"]}),
    ("seed", {"metric_id": "ppg", "n": 26}),
    ("seed", {"metric_id": "ppg", "n": 0}),
    ("seed", {"metric_id": "ppg", "min_gp": -1}),
    ("seed", {"metric_id": "ppg", "min_mpg": -1}),
    ("seed", {"metric_id": "ppg", "position": "G"}),
])
def test_validation_caps(path, payload):
    assert client.post(f"/api/boards/{path}", json=payload).status_code == 422


def test_caps_allow_boundary(warehouse):
    assert fill(ids=list(range(1, 51)), metrics=["ppg"] * 30).status_code == 200
    assert client.post("/api/boards/seed", json={"metric_id": "ppg", "n": 25}).status_code == 200


def test_warehouse_errors_are_explicit(monkeypatch):
    def unavailable(**kwargs):
        assert kwargs == {"read_only": True}
        raise duckdb.IOException("unavailable")

    monkeypatch.setattr(store, "connect", unavailable)
    for response in [fill(), client.post("/api/boards/seed", json={"metric_id": "ppg"})]:
        assert response.status_code == 503
        assert response.json()["detail"] == "Boards warehouse unavailable"
