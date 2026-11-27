from __future__ import annotations

from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.cap_sheet import (
    column_season, horizon_seasons, unroll_player_contract,
    unroll_team_sheet, year_committed, year_pending_option)

BACKEND = Path(__file__).resolve().parent.parent
WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

SEASONS = ["2025-26", "2026-27", "2027-28", "2028-29"]


def _row(salaries, guaranteed, options=None, name="Test Player", pid=1):
    row = {"PLAYER_NAME": name, "PLAYER_ID": pid, "TEAM": "TST",
           "GUARANTEED": guaranteed}
    for season, salary in salaries.items():
        row["SALARY_" + season.replace("-", "_")] = salary
    for season, opt in (options or {}).items():
        row["OPTION_" + season.replace("-", "_")] = opt
    return row


def test_column_season_roundtrip():
    assert column_season("SALARY_2026_27") == "2026-27"
    assert column_season("OPTION_2031_32") == "2031-32"
    assert column_season("PLAYER_NAME") is None
    assert column_season("GUARANTEED") is None


def test_guarantee_pool_walks_in_chronological_order():
    row = _row({"2026-27": 100, "2027-28": 100, "2028-29": 100}, 250)
    out = unroll_player_contract(row, SEASONS, "2026-27")
    flags = {y["season"]: y["guaranteed"] for y in out["years"]
             if y["season"] >= "2026-27"}
    assert flags == {"2026-27": True, "2027-28": True, "2028-29": False}


def test_walk_stops_at_first_non_guaranteed_year():
    row = _row({"2026-27": 100, "2027-28": 350, "2028-29": 100}, 400)
    out = unroll_player_contract(row, SEASONS, "2026-27")
    flags = {y["season"]: y["guaranteed"] for y in out["years"]
             if y["season"] >= "2026-27"}
    assert flags == {"2026-27": True, "2027-28": False, "2028-29": False}


def test_exact_pool_coverage_is_guaranteed():
    row = _row({"2026-27": 58456566, "2027-28": 62786682,
                "2028-29": 67116798}, 188360046)
    out = unroll_player_contract(row, SEASONS, "2026-27")
    assert all(y["guaranteed"] for y in out["years"]
               if y["season"] >= "2026-27" and y["salary"])


def test_team_option_excluded_from_committed_player_option_counted():
    row = _row({"2026-27": 100, "2027-28": 200, "2028-29": 300}, 600,
               options={"2027-28": "team", "2028-29": "player"})
    sheet = unroll_team_sheet([row], "2026-27", SEASONS)
    assert sheet["totals"]["2027-28"]["committed"] == 0
    assert sheet["totals"]["2027-28"]["pending_option"] == 200
    assert sheet["totals"]["2028-29"]["committed"] == 300
    assert sheet["totals"]["2028-29"]["pending_option"] == 0
    assert sheet["totals"]["2026-27"]["committed"] == 100


def test_pre_start_years_do_not_count_in_totals():
    row = _row({"2025-26": 999, "2026-27": 100}, 100)
    sheet = unroll_team_sheet([row], "2026-27", SEASONS)
    assert sheet["totals"]["2025-26"]["committed"] == 0
    assert sheet["totals"]["2025-26"]["pending_option"] == 0
    assert sheet["totals"]["2026-27"]["committed"] == 100


def test_missing_salary_years_are_holes_not_zeroes():
    row = _row({"2026-27": 100, "2028-29": 100}, 200)
    out = unroll_player_contract(row, SEASONS, "2026-27")
    hole = next(y for y in out["years"] if y["season"] == "2027-28")
    assert hole["salary"] is None
    assert hole["guaranteed"] is None
    assert out["years"][-1]["guaranteed"] is True


def test_zero_guarantee_pool_makes_everything_unguaranteed():
    row = _row({"2026-27": 100}, 0)
    out = unroll_player_contract(row, SEASONS, "2026-27")
    year = next(y for y in out["years"] if y["season"] == "2026-27")
    assert year["guaranteed"] is False
    assert year_committed(year) == 100


def test_year_helpers_ignore_pre_start_rows():
    year = {"season": "2025-26", "salary": 500, "option": None,
            "guaranteed": None}
    assert year_committed(year) == 0
    assert year_pending_option(year) == 0


def test_horizon_seasons_detected_from_columns():
    rows = [_row({"2026-27": 1, "2030-31": 2}, 3)]
    assert horizon_seasons(rows) == ["2026-27", "2030-31"]


def test_players_sorted_by_start_season_salary_desc():
    small = _row({"2026-27": 10}, 10, name="Small")
    big = _row({"2026-27": 99}, 99, name="Big")
    sheet = unroll_team_sheet([small, big], "2026-27", SEASONS)
    assert [p["player"] for p in sheet["players"]] == ["Big", "Small"]


warehouse_marks = pytest.mark.skipif(
    not WAREHOUSE.exists(), reason="warehouse absent")


@warehouse_marks
def test_real_tatum_unroll_matches_spec_example():
    import duckdb
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        cols = con.execute(
            "select column_name from information_schema.columns "
            "where table_name='silver_salaries'").fetchall()
        names = [c[0] for c in cols]
        row = con.execute(
            "select * from silver_salaries where PLAYER_ID = 1628369"
        ).fetchone()
    finally:
        con.close()
    if row is None:
        pytest.skip("Tatum row absent")
    data = dict(zip(names, row))
    out = unroll_player_contract(data, sorted(
        s for s in horizon_seasons([data]) if s >= "2026-27"), "2026-27")
    first = out["years"][0]
    assert first["season"] == "2026-27"
    assert first["salary"] == 58456566
    assert first["guaranteed"] is True
    salaried = [y for y in out["years"] if y["salary"] is not None]
    total = sum(y["salary"] for y in salaried[:3])
    assert total == 188360046
    assert all(y["guaranteed"] for y in salaried[:3])


@warehouse_marks
def test_real_team_sheet_shape_and_totals_consistency():
    import duckdb
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        cols = con.execute(
            "select column_name from information_schema.columns "
            "where table_name='silver_salaries'").fetchall()
        names = [c[0] for c in cols]
        rows = con.execute(
            "select * from silver_salaries where TEAM = 'BOS'").fetchall()
    finally:
        con.close()
    if not rows:
        pytest.skip("no BOS rows")
    dicts = [dict(zip(names, r)) for r in rows]
    sheet = unroll_team_sheet(dicts, "2026-27")
    assert sheet["players"]
    assert "2026-27" in sheet["totals"]
    tot = sheet["totals"]["2026-27"]
    assert tot["committed"] > 100_000_000
    per_player_sum = 0
    for player in sheet["players"]:
        year = next((y for y in player["years"]
                     if y["season"] == "2026-27"), None)
        if year and year["salary"] and year["option"] != "team":
            per_player_sum += year["salary"]
    assert per_player_sum == tot["committed"]
    for player in sheet["players"]:
        assert "player_id" in player
        for y in player["years"]:
            assert set(y) == {"season", "salary", "option", "guaranteed"}
            assert y["option"] in (None, "player", "team")
