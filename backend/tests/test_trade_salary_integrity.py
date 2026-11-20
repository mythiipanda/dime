import duckdb
import pytest

from shared import store
from shared.tools import get_trade_check
from shared.tools.league import _payroll, _salary_vintage


def test_trade_check_fails_closed_on_salary_vintage_mismatch():
    out = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo",
        "season": "2025-26",
    })
    assert out["ok"] is False
    assert "salary data is for 2026-27, not 2025-26" in out["error"]
    assert "not calculated" in out["error"]


@pytest.mark.parametrize("salary_sheet",[True,False])
def test_payroll_and_checker_use_latest_vintage(tmp_path,monkeypatch,salary_sheet):
    path=tmp_path/"vintages.duckdb"
    monkeypatch.setattr(store,"DB_PATH",path)
    with duckdb.connect(str(path)) as con:
        con.execute('''CREATE TABLE silver_cap_players (
            player VARCHAR, team VARCHAR, salary BIGINT, _season VARCHAR, _fetched_at VARCHAR)''')
        con.execute('''CREATE TABLE silver_salaries (
            PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2025_26 BIGINT, _season VARCHAR, _fetched_at VARCHAR)''')
        rows=[]
        for season,multiplier in (("2024-25",10),("2025-26",10),("2026-27",1)):
            rows.extend([(name,team,salary*multiplier,season,"2026-01-01") for name,team,salary in (
                ("Alpha Guard","OKC",40_000_000),("Alpha Wing","OKC",10_000_000),
                ("Beta Guard","LAL" if multiplier==1 else "BKN",50_000_000))])
        con.executemany("INSERT INTO silver_cap_players VALUES (?,?,?,?,?)",rows)
        if salary_sheet:
            con.executemany("INSERT INTO silver_salaries VALUES (?,?,?,?,?)",rows)
        assert _salary_vintage(con)==("2026-27",3,"2026-01-01")
        for team in ("OKC","LAL"):
            total,players=_payroll(team,con)
            assert total==50_000_000
            assert sum(p["salary"] for p in players)==total
    args={"team_a":"OKC","team_b":"LAL","players_a":"Alpha Guard","players_b":"Beta Guard","season":"2026-27"}
    result=get_trade_check.invoke(args)
    assert result["ok"],result
    for key in ("team_a","team_b"):
        assert result["rows"][key]["payroll"]==50_000_000
        assert result["rows"][key]["over_apron1"] is False
        assert result["rows"][key]["over_apron2"] is False
    assert result["rows"]["team_a"]["out"]==40_000_000
    assert result["rows"]["team_a"]["allowed_in"]==50_250_000
    assert result["rows"]["legal"] is True
    mismatch=get_trade_check.invoke({**args,"season":"2025-26"})
    assert mismatch["ok"] is False
    assert "salary data is for 2026-27, not 2025-26" in mismatch["error"]


def test_payroll_preserves_single_vintage_without_metadata():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE TABLE silver_cap_players (player VARCHAR,team VARCHAR,salary BIGINT)")
        con.execute("INSERT INTO silver_cap_players VALUES ('Alpha Guard','OKC',40000000)")
        assert _payroll("OKC",con)==(40_000_000,[{"player":"Alpha Guard","salary":40_000_000}])
        assert _payroll("LAL",con)==(0,[])
