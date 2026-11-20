import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

import seed_recent_market as srm
import seed_transactions as txn_seed
from shared import store
from shared.contracts import salary_records


def test_transform_contracts_filters_and_maps():
    frame = pl.DataFrame([
        {
            "season_year": 2024, "season": "2024-25", "player_id": "101108",
            "player": "LeBron James", "salary": "48000000", "team_id": "13",
            "team": "Los Angeles Lakers", "team_option": "", "player_option": "TRUE",
            "qualifying_offer": "", "two_way": "FALSE", "terminated": "",
            "notes": "", "source": "fixture",
        },
        {
            "season_year": 2022, "season": "2021-22", "player_id": "1",
            "player": "Old Player", "salary": "1", "team_id": "1",
            "team": "Boston Celtics", "team_option": "", "player_option": "",
            "qualifying_offer": "", "two_way": "", "terminated": "",
            "notes": "", "source": "fixture",
        },
    ])
    out = srm.transform_contracts(frame)
    assert out.height == 1
    row = out.to_dicts()[0]
    assert row["_season"] == "2024-25"
    assert row["TEAM"] == "LAL"
    assert row["TEAM_NAME"] == "Los Angeles Lakers"
    assert row["SALARY"] == 48000000
    assert row["PLAYER_OPTION"] is True
    assert row["TWO_WAY"] is False
    assert row["SOURCE_PLAYER_ID"] == 101108


def test_transform_projections_parses_betiq_table():
    page = """
    <html><body><table>
      <tr><th>R</th><th>1W</th><th>Team</th><th>Div</th><th>W</th><th>L</th><th>WD%</th><th>PO%</th><th>R2%</th><th>CF%</th><th>F%</th><th>T%</th></tr>
      <tr><th colspan="12">header 2</th></tr>
      <tr><td>4.5</td><td>--</td><td>Boston</td><td>Atlantic</td><td>52.5</td><td>29.5</td><td data-sort="0.5">50%</td><td>80%</td><td>60%</td><td>36%</td><td>20%</td><td>12%</td></tr>
    </table></body></html>
    """
    out = srm.transform_projections(page, 2022)
    assert out.height == 1
    row = out.to_dicts()[0]
    assert row["_season"] == "2022-23"
    assert row["TEAM"] == "BOS"
    assert row["PROJECTED_WINS"] == 52.5
    assert row["PROJECTED_LOSSES"] == 29.5
    assert row["WIN_DIVISION_PCT"] == 0.5
    assert row["WIN_TITLE_PCT"] == 0.12


def test_recent_transaction_parts_filters_to_requested_seasons():
    frame = pl.DataFrame([
        {"txn_date": "2022-10-18", "txn_type": "Signing", "player": "A",
         "player_id": 1, "team": "lakers", "team_id": 1610612747, "detail": "x"},
        {"txn_date": "2021-12-15", "txn_type": "Waive", "player": "B",
         "player_id": 2, "team": "celtics", "team_id": 1610612738, "detail": "y"},
    ])
    parts = srm.recent_transaction_parts(frame)
    assert set(parts) == {"2022-23"}
    assert parts["2022-23"].height == 1
    assert txn_seed.season_for_date("2022-10-18") == "2022-23"


def test_resolve_target_refuses_missing_and_canonical(monkeypatch):
    monkeypatch.delenv("DIME_WAREHOUSE", raising=False)
    assert srm.resolve_target(None) is None
    monkeypatch.setenv("DIME_WAREHOUSE", str(store.CANONICAL_DB_PATH))
    assert srm.resolve_target(None) is None


def test_salary_records_reads_silver_contracts_history():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE silver_contracts (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY BIGINT, PLAYER_ID BIGINT, _season VARCHAR)")
    con.execute("INSERT INTO silver_contracts VALUES ('LeBron James','LAL',48000000,1,'2024-25'),('LeBron James','LAL',52000000,1,'2026-27')")
    rows = salary_records(con, salary_season="2024-25")
    assert rows and rows[0]["salary"] == 48000000
    current = salary_records(con, season="2026-27")
    assert current and current[0]["salary"] == 52000000
    con.close()
