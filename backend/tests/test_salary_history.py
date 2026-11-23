import os
from pathlib import Path

import duckdb
import pytest

os.environ["DIME_WAREHOUSE"] = str(Path("/tmp/salary-test.duckdb"))

from shared.tools import get_salary_history  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def seed_scratch():
    db = Path("/tmp/salary-test.duckdb")
    if db.exists():
        yield
        return
    from shared.sources.cap_history import history as cap_history
    from shared.sources.hist_salaries import history as sal_history
    con = duckdb.connect(str(db))
    con.register("capframe", cap_history().frame.to_arrow())
    con.execute("CREATE TABLE silver_cap_history AS SELECT * FROM capframe")
    res = sal_history()
    assert res.ok
    con.register("salframe", res.frame.to_arrow())
    con.execute("CREATE TABLE silver_hist_salaries AS SELECT * FROM salframe")
    con.close()
    yield


def test_registered_in_catalogue():
    from analyst import python_tools
    assert "get_salary_history" in python_tools.catalogue()


def test_player_mode_career_and_cap_share():
    r = get_salary_history.invoke({"player": "Tim Duncan"})
    assert r["ok"] is True
    assert len(r["rows"]) >= 15
    first = r["rows"][0]
    assert first["PLAYER_NAME"] == "Tim Duncan"
    assert first["SEASON"] == "1997-98"
    assert first["salary_cap"] > 0
    assert 0 < first["share_of_cap"] < 1


def test_team_mode_payroll_vs_cap():
    r = get_salary_history.invoke({"team": "LAL", "season": "2003-04"})
    assert r["ok"] is True
    s = r["summary"]
    assert s["payroll"] > 0
    assert s["payroll_rank"] is not None
    assert s["salary_cap"] == 43840000.0
    assert s["over_tax"] is True
    assert sum(row["salary"] for row in r["rows"]) <= s["payroll"]


def test_league_mode_landscape():
    r = get_salary_history.invoke({"season": "2003-04"})
    assert r["ok"] is True
    s = r["summary"]
    assert s["players"] > 400
    assert s["max_salary"] == 28000000
    assert r["rows"][0]["salary"] == s["max_salary"]


def test_cap_table_mode_lists_every_season():
    r = get_salary_history.invoke({})
    assert r["ok"] is True
    assert len(r["rows"]) >= 42
    last = r["rows"][-1]
    assert last["season"] == "2025-26"
    assert last["apron_1"] > 0


def test_player_and_team_is_an_error():
    r = get_salary_history.invoke({"player": "Kobe Bryant", "team": "LAL"})
    assert r["ok"] is False
    assert r["rows"] == []


def test_unknown_player_is_an_error():
    r = get_salary_history.invoke({"player": "Notareal Player"})
    assert r["ok"] is False
    assert r["rows"] == [] and r["columns"] == []
