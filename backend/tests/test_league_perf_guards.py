
import copy
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools import league


@pytest.fixture()
def small_warehouse(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    try:
        con.execute("CREATE TABLE silver_standings (TEAM TEXT, WINS INTEGER, _season TEXT)")
        con.execute("INSERT INTO silver_standings VALUES ('OKC', 68, '2025-26')")
        con.execute("CREATE TABLE silver_leaders_pts (PLAYER TEXT, PTS INTEGER, RANK INTEGER, _season TEXT)")
        con.execute("INSERT INTO silver_leaders_pts VALUES ('A', 2400, 1, '2025-26')")
    finally:
        con.close()
    monkeypatch.setattr(store, "connect", lambda **_kw: duckdb.connect(str(wh)))
    league._clear_warehouse_schema_cache()
    yield wh
    league._clear_warehouse_schema_cache()


def test_schema_cache_second_call_issues_no_queries(small_warehouse):
    present1, cols1 = league._get_warehouse_schema()
    assert "silver_standings" in present1
    assert cols1["silver_standings"][:3] == ["TEAM", "WINS", "_season"]
    info1 = league._warehouse_schema_cache_info()
    assert info1["misses"] == 1

    calls = {"connect": 0}
    real_connect = store.connect

    def counting_connect(**kw):
        calls["connect"] += 1
        return real_connect(**kw)

    store.connect = counting_connect
    try:
        present2, cols2 = league._get_warehouse_schema()
    finally:
        store.connect = real_connect
    assert present2 == present1
    assert cols2 == cols1
    assert calls["connect"] == 0
    info2 = league._warehouse_schema_cache_info()
    assert info2["hits"] >= 1
    assert info2["misses"] == 1


def test_schema_cache_clear_rebuilds(small_warehouse):
    league._get_warehouse_schema()
    league._clear_warehouse_schema_cache()
    info = league._warehouse_schema_cache_info()
    assert info["hits"] == 0 and info["misses"] == 0
    present, cols = league._get_warehouse_schema()
    assert "silver_standings" in present
    assert league._warehouse_schema_cache_info()["misses"] == 1


def _leader_rows():
    return [
        {"PLAYER": "A", "RANK": 1},
        {"PLAYER": "B", "RANK": 2},
        {"PLAYER": "C", "RANK": 50},
        {"PLAYER": "D", "RANK": 0},
        {"PLAYER": "E"},
    ]


@pytest.mark.parametrize("category", ["PTS", "REB", "AST"])
def test_get_leaders_single_read_byte_identical(monkeypatch, category):
    total = 200
    template = _leader_rows()

    def fake_warehouse(table, where, params, fetch, season, **kw):
        assert table == f"silver_leaders_{category.lower()}"
        return copy.deepcopy(template), {"rows": total, "cached": True, "source": "test"}

    monkeypatch.setattr(league, "_warehouse_or_live", fake_warehouse)
    read_calls = {"n": 0}

    def counting_read_frame(*a, **k):
        read_calls["n"] += 1
        raise AssertionError("second read_frame must not run")

    monkeypatch.setattr("shared.store.read_frame", counting_read_frame)

    res = league.get_leaders.invoke({"stat_category": category})
    assert res["ok"] is True
    assert read_calls["n"] == 0
    assert res["rows"] != template
    assert all("PERCENTILE" not in r for r in res["rows"])
    assert res["meta"]["qualification"].startswith("Season totals summed from warehouse game logs")
    assert res["meta"]["coverage"].startswith("Full player population in warehouse game logs")
    assert res["meta"]["season"] == "2025-26"
    assert all(r.get("PLAYER_ID") is not None and r.get("PLAYER_NAME") for r in res["rows"])

    fallback_rows, fallback_meta = league._completed_season_totals(category, res["meta"]["season"], "DESC")
    assert json.dumps(res["meta"], sort_keys=True, default=str) == json.dumps(fallback_meta, sort_keys=True, default=str)

    def norm(rows):
        out = []
        for r in rows:
            out.append({"PLAYER": r["PLAYER"], category: r[category], "TEAM": r["TEAM"],
                        "GP": r["GP"], "PLAYER_ID": r["PLAYER_ID"], "PLAYER_NAME": r["PLAYER_NAME"]})
        return sorted(out, key=lambda d: (-d[category], d["PLAYER"]))

    assert json.dumps(norm(res["rows"]), sort_keys=True, default=str) == json.dumps(norm(fallback_rows), sort_keys=True, default=str)
    expected = {"tool": "get_leaders", "ok": True, "rows": norm(res["rows"]), "meta": fallback_meta}
    assert json.dumps({"tool": res["tool"], "ok": res["ok"], "rows": norm(res["rows"]), "meta": res["meta"]}, sort_keys=True, default=str) == json.dumps(expected, sort_keys=True, default=str)
