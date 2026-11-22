import pytest

from shared import store
from shared.tools.league.trade_targets import get_trade_targets


def _seed(monkeypatch, tmp_path):
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
    con.execute(
        "CREATE TABLE silver_boxscores ("
        "firstName VARCHAR, familyName VARCHAR, position VARCHAR, "
        "_season VARCHAR, _fetched_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE silver_advanced ("
        "PLAYER_NAME VARCHAR, AGE INTEGER, GP INTEGER, MIN DOUBLE, "
        "DEF_RATING DOUBLE, NET_RATING DOUBLE, TS_PCT DOUBLE, "
        "USG_PCT DOUBLE, PIE DOUBLE, _season VARCHAR, "
        "_fetched_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE silver_rapm (name VARCHAR, rapm DOUBLE, "
        "possessions INTEGER, _season VARCHAR, _fetched_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE silver_hist_hustle (player_name VARCHAR, g INTEGER, "
        "deflections DOUBLE, contested_shots DOUBLE, season VARCHAR)")
    con.execute(
        "CREATE TABLE silver_cap_players (player VARCHAR, "
        "contract_type VARCHAR, player_option BOOLEAN, "
        "team_option BOOLEAN, guaranteed BIGINT)")
    return con


_PROD = [
    ("Lock Wing", "UTA", 70, 2200.0, 16.0, 6.0, 3.0, 1.6, 0.9, 1.4),
    ("Score Wing", "UTA", 72, 2300.0, 24.0, 5.0, 4.0, 1.0, 0.4, 2.2),
    ("Rich Wing", "PHX", 65, 2000.0, 18.0, 5.0, 3.0, 1.1, 0.5, 1.5),
    ("Tiny Guard", "SAC", 60, 1800.0, 14.0, 3.0, 7.0, 1.0, 0.1, 1.8),
    ("Bench Wing", "ORL", 20, 200.0, 4.0, 2.0, 1.0, 0.4, 0.3, 0.6),
    ("Home Wing", "MEM", 68, 2100.0, 15.0, 5.0, 2.0, 1.3, 0.7, 1.2),
]

_SAL = [
    ("Lock Wing", "UTA", 15000000),
    ("Score Wing", "UTA", 18000000),
    ("Rich Wing", "PHX", 25000000),
    ("Tiny Guard", "SAC", 9000000),
    ("Bench Wing", "ORL", 4000000),
    ("Home Wing", "MEM", 12000000),
]

_POS = {
    "Lock Wing": "F", "Score Wing": "F", "Rich Wing": "F",
    "Tiny Guard": "G", "Bench Wing": "F", "Home Wing": "F",
}


def _load(con):
    for p in _PROD:
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "(?,?,?,?,?,?,?,?,?,?,'2025-26',now())", list(p))
    for s in _SAL:
        con.execute(
            "INSERT INTO silver_salaries VALUES (?,?,?,'2026-27',now())",
            list(s))
    for name, pos in _POS.items():
        first, last = name.split(" ", 1)
        for _ in range(60):
            con.execute(
                "INSERT INTO silver_boxscores VALUES (?,?,?,"
                "'2024-25',now())", [first, last, pos])
    for i, (name, team, gp, mins, *_rest) in enumerate(_PROD):
        con.execute(
            "INSERT INTO silver_advanced VALUES "
            "(?,?,?,?,?,?,?,?,?,'2025-26',now())",
            [name, 26 + i, gp, mins, 108.0 + i, -1.0 + i,
             0.55 + i * 0.01, 0.20 + i * 0.02, 0.10 + i * 0.01])
        con.execute(
            "INSERT INTO silver_rapm VALUES (?,?,?,'2025-26',now())",
            [name, 1.0 + i * 0.5, 4000])
        con.execute(
            "INSERT INTO silver_hist_hustle VALUES (?,?,?,?,?)",
            [name, gp, 2.0 + i * 0.2, 6.0 + i * 0.3, "2024-25"])
        con.execute(
            "INSERT INTO silver_cap_players VALUES (?,?,?,?,?)",
            [name, "standard", False, False, 30000000])
    con.close()


def test_ranked_targets(monkeypatch, tmp_path):
    con = _seed(monkeypatch, tmp_path)
    _load(con)
    res = get_trade_targets.invoke({
        "need": "a defensive wing", "team": "MEM", "position": "wing",
        "max_salary": 20000000})
    assert res["ok"]
    names = [r["player"] for r in res["rows"]]
    assert "Home Wing" not in names
    assert "Rich Wing" not in names
    assert "Tiny Guard" not in names
    assert "Bench Wing" not in names
    assert set(names) == {"Lock Wing", "Score Wing"}
    assert names == sorted(
        names, key=lambda n: [r["target_rank"] for r in res["rows"]
                              if r["player"] == n][0])
    lock = next(r for r in res["rows"] if r["player"] == "Lock Wing")
    assert lock["position"] == "F"
    assert lock["salary"] == 15000000
    assert lock["cost_band"]
    assert lock["def_rating"] == pytest.approx(108.0)
    assert lock["rapm"] == pytest.approx(1.0)
    skipped = res["cohort"]["skipped"]
    assert skipped["acquirer"] == 1
    assert skipped["max_salary"] == 1
    assert skipped["position"] == 1
    assert skipped["floor"] == 1
    checks = {c["rule"] for c in res["checks"]}
    assert "position source" in checks
    assert any("2024-25" in c.get("note", "") for c in res["checks"]
               if c["rule"] == "position source")


def test_no_filters_returns_league_wide(monkeypatch, tmp_path):
    con = _seed(monkeypatch, tmp_path)
    _load(con)
    res = get_trade_targets.invoke({"need": "", "team": "", "position": "",
                                    "max_salary": None})
    assert res["ok"]
    names = [r["player"] for r in res["rows"]]
    assert "Tiny Guard" in names
    assert "Home Wing" in names
    assert "Bench Wing" not in names


def test_unknown_position_errors(monkeypatch, tmp_path):
    con = _seed(monkeypatch, tmp_path)
    _load(con)
    res = get_trade_targets.invoke({"need": "", "position": "wizard"})
    assert not res["ok"]
    assert res["rows"] == []
    assert res["columns"]
