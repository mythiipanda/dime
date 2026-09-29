
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store as _store  # noqa: E402
from shared.tools import league as _league  # noqa: E402

SEASON = "2025-26"
REPO_WAREHOUSE = (
    Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"
)


class _FakeResult:
    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _FakeResult()

    def close(self):
        pass


@pytest.fixture()
def fake_con(monkeypatch):
    con = _FakeConn()
    monkeypatch.setattr(_store, "connect", lambda read_only=True: con)
    return con


@pytest.fixture()
def warehouse(tmp_path, monkeypatch):
    db = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE silver_leaders_stl ("
            "PLAYER TEXT, TEAM TEXT, GP INTEGER, MIN DOUBLE, STL INTEGER, "
            "_season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_leaders_stl VALUES "
            "('One Game Wonder', 'XYZ', 2, 10.0, 8, '2025-26'),"
            "('Steady Thief', 'ABC', 70, 2000.0, 140, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_advanced ("
            "PLAYER_NAME TEXT, TEAM_ABBREVIATION TEXT, GP INTEGER, "
            "MIN DOUBLE, TS_PCT DOUBLE, _season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_advanced VALUES "
            "('Garbage Time', 'XYZ', 2, 8.0, 0.75, '2025-26'),"
            "('Real Shooter', 'ABC', 70, 30.0, 0.60, '2025-26')"
        )
    finally:
        con.close()
    monkeypatch.setattr(_store, "DB_PATH", db)
    monkeypatch.setattr(_store, "LOCK_PATH", tmp_path / ".write.lock")
    return db


def _sql_text(fake_con):
    return "\n".join(sql for sql, _params in fake_con.calls)


def test_spg_zero_floor_still_carries_500_minute_floor(fake_con):
    res = _league.get_leaders.invoke(
        {"stat_category": "SPG", "season": SEASON, "min_attempts": 0}
    )
    assert res["ok"] is True
    assert "MIN >= 500" in _sql_text(fake_con)
    assert res["meta"]["qualification"] == "500+ total minutes"
    assert "500" in res["meta"]["qualification"]


@pytest.mark.parametrize("min_attempts", [0, 1, 499, 5000])
@pytest.mark.parametrize("direction", ["desc", "asc"])
def test_spg_floor_survives_any_caller_floor_and_direction(
    fake_con, min_attempts, direction
):
    res = _league.get_leaders.invoke(
        {"stat_category": "SPG", "season": SEASON,
         "ranking_direction": direction, "min_attempts": min_attempts}
    )
    assert res["ok"] is True
    assert "MIN >= 500" in _sql_text(fake_con)
    assert res["meta"]["qualification"] == "500+ total minutes"


def test_spg_scrub_excluded_empirically(warehouse):
    res = _league.get_leaders.invoke(
        {"stat_category": "SPG", "season": SEASON, "min_attempts": 0}
    )
    assert res["ok"] is True
    names = [r["PLAYER"] for r in res["rows"]]
    assert "One Game Wonder" not in names
    assert "Steady Thief" in names


def test_ts_pct_zero_floor_uses_1000_minutes(fake_con):
    res = _league.get_leaders.invoke(
        {"stat_category": "TS_PCT", "season": SEASON, "min_attempts": 0}
    )
    assert res["ok"] is True
    sql = _sql_text(fake_con)
    assert "GP * MIN >=" in sql
    bound = max(p for _sql, params in fake_con.calls for p in params
                if isinstance(p, (int, float)))
    assert bound == 1000
    assert "1,000" in res["meta"]["qualification"]


@pytest.mark.parametrize(
    "min_attempts, expected", [(0, 1000), (500, 1000), (2000, 2000)]
)
def test_ts_pct_caller_can_raise_but_not_lower_floor(
    fake_con, min_attempts, expected
):
    res = _league.get_leaders.invoke(
        {"stat_category": "TS_PCT", "season": SEASON,
         "min_attempts": min_attempts}
    )
    assert res["ok"] is True
    bound = max(p for _sql, params in fake_con.calls for p in params
                if isinstance(p, (int, float)))
    assert bound == expected


def test_ts_pct_scrub_excluded_empirically(warehouse):
    res = _league.get_leaders.invoke(
        {"stat_category": "TS_PCT", "season": SEASON, "min_attempts": 0}
    )
    assert res["ok"] is True
    names = [r["PLAYER"] for r in res["rows"]]
    assert "Garbage Time" not in names
    assert "Real Shooter" in names
    for r in res["rows"]:
        assert r["GP"] * r["MPG"] >= 1000


def _live_tables():
    if not REPO_WAREHOUSE.exists():
        return None
    con = duckdb.connect(str(REPO_WAREHOUSE), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    if not {"silver_leaders_stl", "silver_advanced"} <= tables:
        return None
    return tables


def test_live_warehouse_no_floor_violations(monkeypatch):
    if _live_tables() is None:
        pytest.skip(
            "no live warehouse with leaders tables at "
            "backend/data/warehouse.duckdb; skipping empirical check"
        )
    monkeypatch.setattr(_store, "DB_PATH", REPO_WAREHOUSE)
    con = duckdb.connect(str(REPO_WAREHOUSE), read_only=True)
    try:
        seasons = [r[0] for r in con.execute(
            "SELECT DISTINCT _season FROM silver_leaders_stl").fetchall()]
    finally:
        con.close()
    for season in seasons:
        spg = _league.get_leaders.invoke(
            {"stat_category": "SPG", "season": season})
        assert spg["ok"] is True
        names = {r["PLAYER"] for r in spg["rows"]}
        con = duckdb.connect(str(REPO_WAREHOUSE), read_only=True)
        try:
            sub = {r[0] for r in con.execute(
                "SELECT PLAYER FROM silver_leaders_stl "
                "WHERE _season = ? AND MIN < 500", [season]).fetchall()}
        finally:
            con.close()
        assert names.isdisjoint(sub), \
            f"sub-floor rows leaked in {season}: {names & sub}"
        ts = _league.get_leaders.invoke(
            {"stat_category": "TS_PCT", "season": season,
             "min_attempts": 0})
        assert ts["ok"] is True
        for r in ts["rows"]:
            assert r["GP"] * r["MPG"] >= 1000
