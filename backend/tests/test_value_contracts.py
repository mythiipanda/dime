import pytest

from shared import store
from shared.tools.league.value_contracts import get_value_contracts


def _seed(monkeypatch, tmp_path, prod_season="2025-26"):
    path = tmp_path / "w.duckdb"
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    import duckdb
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_leaders_pts ("
        "PLAYER VARCHAR, TEAM VARCHAR, GP INTEGER, MIN DOUBLE, "
        "PTS DOUBLE, REB DOUBLE, AST DOUBLE, STL DOUBLE, BLK DOUBLE, "
        "TOV DOUBLE, _season VARCHAR, _fetched_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2026_27 BIGINT, "
        "_season VARCHAR, _fetched_at TIMESTAMP)")
    con.close()
    return path


def _load(path, prod, caps, prod_season="2025-26"):
    import duckdb
    con = duckdb.connect(str(path))
    for p in prod:
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,now())",
            [p["player"], p["team"], p["gp"], p["min"], p["pts"],
             p["reb"], p["ast"], p["stl"], p["blk"], p["tov"],
             prod_season])
    for c in caps:
        con.execute(
            "INSERT INTO silver_salaries VALUES (?,?,?,?,now())",
            [c["player"], c["team"], c["salary"], "2026-27"])
    con.close()


def _okc_prod():
    return [
        {"player": "Star Guard", "team": "OKC", "gp": 70, "min": 2380.0,
         "pts": 30.0, "reb": 5.0, "ast": 6.0, "stl": 1.5, "blk": 1.0,
         "tov": 2.0},
        {"player": "Value Wing", "team": "OKC", "gp": 72, "min": 2160.0,
         "pts": 15.0, "reb": 6.0, "ast": 3.0, "stl": 1.2, "blk": 0.8,
         "tov": 1.0},
        {"player": "Min Guy", "team": "OKC", "gp": 10, "min": 60.0,
         "pts": 2.0, "reb": 1.0, "ast": 0.5, "stl": 0.2, "blk": 0.1,
         "tov": 0.5},
    ]


def _okc_cap():
    return [
        {"player": "Star Guard", "team": "OKC", "salary": 40_000_000},
        {"player": "Value Wing", "team": "OKC", "salary": 3_000_000},
        {"player": "Min Guy", "team": "OKC", "salary": 1_000_000},
        {"player": "No Stats", "team": "OKC", "salary": 2_000_000},
    ]


def test_basic_rows_and_flags(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_prod(), _okc_cap())
    res = get_value_contracts.invoke({"team": "OKC", "season": "2025-26"})
    assert res["ok"] is True
    rows = {r["player"]: r for r in res["rows"]}
    wing = rows["Value Wing"]
    assert wing["cap_band"] == "cheap"
    assert wing["rotation"] is True
    assert wing["value_rank"] == 1
    assert wing["value_flag"] == "bargain"
    star = rows["Star Guard"]
    assert star["cap_band"] == "expensive"
    assert rows["Min Guy"]["rotation"] is False
    assert rows["Min Guy"]["value_flag"] == "unqualified"
    assert rows["No Stats"]["no_production"] is True
    assert res["summary"]["rotation_players"] == 2
    assert any(c["rule"] == "value proxy" for c in res["checks"])
    assert res["meta"]["cap"] == 165_000_000


def test_mid_band_and_overpaid(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    prod = _okc_prod()
    caps = _okc_cap()
    caps[0]["salary"] = 40_000_000
    caps.append({"player": "Mid Guard", "team": "OKC",
                 "salary": 20_000_000})
    prod.append({"player": "Mid Guard", "team": "OKC", "gp": 70,
                 "min": 1400.0, "pts": 8.0, "reb": 2.0, "ast": 2.0,
                 "stl": 0.5, "blk": 0.2, "tov": 1.5})
    _load(path, prod, caps)
    res = get_value_contracts.invoke({"team": "OKC", "season": "2025-26"})
    rows = {r["player"]: r for r in res["rows"]}
    assert rows["Mid Guard"]["cap_band"] == "mid"
    assert rows["Mid Guard"]["rotation"] is True


def test_benchmark_comparison(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    prod = _okc_prod() + [
        {"player": "Den Star", "team": "DEN", "gp": 75, "min": 2600.0,
         "pts": 28.0, "reb": 12.0, "ast": 9.0, "stl": 1.0, "blk": 0.7,
         "tov": 3.0},
        {"player": "Den Cheap", "team": "DEN", "gp": 60, "min": 1500.0,
         "pts": 12.0, "reb": 4.0, "ast": 2.0, "stl": 0.8, "blk": 0.5,
         "tov": 1.0},
    ]
    caps = _okc_cap() + [
        {"player": "Den Star", "team": "DEN", "salary": 50_000_000},
        {"player": "Den Cheap", "team": "DEN", "salary": 5_000_000},
    ]
    _load(path, prod, caps)
    res = get_value_contracts.invoke(
        {"team": "OKC", "season": "2025-26", "benchmark_team": "DEN"})
    assert res["ok"] is True
    assert res["benchmark"]["team"] == "DEN"
    assert len(res["benchmark"]["rows"]) == 2
    assert res["benchmark"]["summary"]["rotation_players"] == 2
    assert "cheap_rotation_share_delta" in res["comparison"]


def test_moved_player_marked(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    prod = _okc_prod()
    prod[1]["team"] = "CHI"
    _load(path, prod, _okc_cap())
    res = get_value_contracts.invoke({"team": "OKC", "season": "2025-26"})
    wing = next(r for r in res["rows"] if r["player"] == "Value Wing")
    assert wing["production_team"] == "CHI"


def test_missing_team_error(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_prod(), _okc_cap())
    res = get_value_contracts.invoke({"team": "SAS", "season": "2025-26"})
    assert res["ok"] is False
    assert "no salary rows" in res["error"]


def test_requires_team(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    res = get_value_contracts.invoke({"team": ""})
    assert res["ok"] is False
