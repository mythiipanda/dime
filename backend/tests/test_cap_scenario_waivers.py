import duckdb
import pytest

from shared import store


@pytest.fixture
def waiver_seed(monkeypatch, tmp_path):
    counter = 0

    def seed(guaranteed, final_option=None):
        nonlocal counter
        counter += 1
        path = tmp_path / f"waiver-{counter}.duckdb"
        con = duckdb.connect(str(path))
        try:
            con.execute(
                "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
                "SALARY INTEGER, SALARY_2026_27 INTEGER, SALARY_2027_28 INTEGER, "
                "SALARY_2028_29 INTEGER, OPTION_2027_28 VARCHAR, "
                "OPTION_2028_29 VARCHAR, GUARANTEED INTEGER, _season VARCHAR, "
                "_fetched_at VARCHAR)")
            con.execute(
                "INSERT INTO silver_salaries VALUES "
                "('Alpha One', 'BOS', 10000000, 10000000, 10000000, 10000000, "
                "NULL, ?, ?, '2026-27', '2026-10-01'), "
                "('BOS Filler', 'BOS', 90000000, 90000000, NULL, NULL, NULL, "
                "NULL, NULL, '2026-27', '2026-10-01')",
                [final_option, guaranteed])
        finally:
            con.close()
        monkeypatch.setattr(store, "DB_PATH", path)
        monkeypatch.setattr(store, "LOCK_PATH", tmp_path / f"waiver-{counter}.lock")
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
        return path

    yield seed
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _cap_scenario(payload):
    from shared.tools import get_cap_scenario

    return get_cap_scenario.invoke(payload)


def test_waive_retains_dead_cap_and_trade_out_still_removes_salary(waiver_seed):
    waiver_seed(15_000_000)
    waived = _cap_scenario({
        "team": "BOS", "waive_players": "Alpha One", "season": "2026-27",
    })
    assert waived["ok"] is True
    assert waived["summary"]["payroll_before"] == 100_000_000
    assert waived["summary"]["payroll_after"] == 100_000_000
    waive_step = next(row for row in waived["rows"] if row["kind"] == "waive")
    assert waive_step["delta"] == 0
    assert "$10,000,000 estimated dead cap" in waive_step["detail"]
    assert "per-year guarantee allocations are unavailable" in waived["meta"]["waiver_basis"]

    traded = _cap_scenario({
        "team": "BOS", "trade_out_players": "Alpha One", "season": "2026-27",
    })
    assert traded["ok"] is True
    assert traded["summary"]["payroll_after"] == 90_000_000
    trade_step = next(row for row in traded["rows"] if row["kind"] == "trade_out")
    assert trade_step["delta"] == -10_000_000


def test_waiver_dead_money_distinguishes_missing_zero_and_partial_guarantees():
    from shared.tools.league.waivers import waiver_dead_money

    partial = waiver_dead_money(10_000_000, 5_000_000, 3)
    assert partial["dead_cap"] == 5_000_000
    assert partial["relief"] == 5_000_000
    zero = waiver_dead_money(10_000_000, 0, 3)
    assert zero["dead_cap"] == 0
    assert zero["relief"] == 10_000_000
    missing = waiver_dead_money(10_000_000, None, 3)
    assert missing["dead_cap"] == 10_000_000
    assert missing["relief"] == 0


def test_waive_stretch_uses_pre_september_formula(waiver_seed):
    waiver_seed(28_000_000)
    out = _cap_scenario({
        "team": "BOS", "waive_players": "Alpha One", "stretch": True,
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 94_000_000
    step = next(row for row in out["rows"] if row["kind"] == "waive")
    assert step["delta"] == -6_000_000
    assert "pre-Sep-1 stretch estimate over 7y" in step["detail"]


def test_pre_september_stretch_excludes_team_option_year_reviewer_pin(waiver_seed):
    waiver_seed(20_000_000, final_option="team")
    out = _cap_scenario({
        "team": "BOS", "waive_players": "Alpha One", "stretch": True,
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 94_000_000
    step = next(row for row in out["rows"] if row["kind"] == "waive")
    assert step["delta"] == -6_000_000
    assert step["dead_cap"] == 4_000_000
    assert step["guaranteed"] == 20_000_000
    assert step["stretch_years"] == 5
    assert step["waiver_window"] == "pre_sep1"
    assert step["waiver_date_defaulted"] is True
    assert "team-option years excluded" in step["estimate_basis"]


def test_pre_september_stretch_counts_player_option_year(waiver_seed):
    waiver_seed(20_000_000, final_option="player")
    out = _cap_scenario({
        "team": "BOS", "waive_players": "Alpha One", "stretch": True,
        "season": "2026-27",
    })
    assert out["ok"] is True
    step = next(row for row in out["rows"] if row["kind"] == "waive")
    assert step["stretch_years"] == 7
    assert step["dead_cap"] == 2_857_143
    assert step["delta"] == -7_142_857


def test_post_september_stretch_keeps_current_allocation_and_stretches_future(waiver_seed):
    waiver_seed(20_000_000, final_option="team")
    out = _cap_scenario({
        "team": "BOS", "waive_players": "Alpha One", "stretch": True,
        "season": "2026-27", "waiver_date": "2026-11-15",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 100_000_000
    step = next(row for row in out["rows"] if row["kind"] == "waive")
    assert step["delta"] == 0
    assert step["dead_cap"] == 10_000_000
    assert step["guaranteed"] == 20_000_000
    assert step["stretched_amount"] == 10_000_000
    assert step["stretched_dead_cap"] == 3_333_333
    assert step["stretch_years"] == 3
    assert step["waiver_window"] == "post_sep1"
    assert step["waiver_date"] == "2026-11-15"
    assert "current-season allocation unchanged" in step["estimate_basis"]
    assert out["meta"]["waiver_timing"] == {
        "window": "post_sep1", "date": "2026-11-15", "defaulted": False,
    }


def test_waiver_date_outside_scenario_league_year_fails_closed(waiver_seed):
    waiver_seed(20_000_000, final_option="team")
    out = _cap_scenario({
        "team": "BOS", "waive_players": "Alpha One", "stretch": True,
        "season": "2026-27", "waiver_date": "2027-07-15",
    })
    assert out["ok"] is False
    assert "inside the 2026-27 league year" in out["error"]


def test_waiver_timing_window_boundaries():
    from shared.tools.league.waivers import resolve_waiver_timing

    august, august_error = resolve_waiver_timing("2027-08-31", "2027-28")
    september, september_error = resolve_waiver_timing("2027-09-01", "2027-28")
    june, june_error = resolve_waiver_timing("2028-06-30", "2027-28")
    assert august_error is None and august["window"] == "pre_sep1"
    assert september_error is None and september["window"] == "post_sep1"
    assert june_error is None and june["window"] == "post_sep1"
    invalid, invalid_error = resolve_waiver_timing("not-a-date", "2027-28")
    assert invalid is None
    assert "YYYY-MM-DD" in invalid_error


def test_retired_out_players_input_fails_closed(waiver_seed):
    waiver_seed(15_000_000)
    out = _cap_scenario({
        "team": "BOS", "out_players": "Alpha One", "season": "2026-27",
    })
    assert out["ok"] is False
    assert "out_players is retired" in out["error"]
    assert "trade_out_players" in out["error"]
    assert "waive_players" in out["error"]


def test_same_player_cannot_be_traded_and_waived(waiver_seed):
    waiver_seed(15_000_000)
    out = _cap_scenario({
        "team": "BOS", "trade_out_players": "Alpha One",
        "waive_players": "Alpha One", "season": "2026-27",
    })
    assert out["ok"] is False
    assert "cannot be both traded out and waived" in out["error"]


def test_stretch_requires_waive_players(waiver_seed):
    waiver_seed(15_000_000)
    out = _cap_scenario({
        "team": "BOS", "trade_out_players": "Alpha One", "stretch": True,
        "season": "2026-27",
    })
    assert out["ok"] is False
    assert "stretch requires waive_players" in out["error"]


def test_cap_sheet_waive_uses_shared_dead_money(waiver_seed):
    path = waiver_seed(5_000_000)
    from shared.tools.league.cap_sheet import evaluate_cap_scenario

    con = duckdb.connect(str(path), read_only=True)
    try:
        out = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2026-27",
            "moves": [{"kind": "waive", "player": "Alpha One"}],
        })
    finally:
        con.close()
    assert out["ok"] is True
    assert out["pay_after"] == 95_000_000
    step = next(row for row in out["steps"] if row["kind"] == "waive")
    assert step["delta"] == -5_000_000
    assert step["dead_cap"] == 5_000_000
    assert step["guaranteed"] == 5_000_000
    assert step["estimate_basis"]
    assert "$5,000,000 estimated dead cap" in step["detail"]


def test_cap_sheet_waive_post_september_stretch_uses_timing_input(waiver_seed):
    path = waiver_seed(20_000_000, final_option="team")
    from shared.tools.league.cap_sheet import evaluate_cap_scenario

    con = duckdb.connect(str(path), read_only=True)
    try:
        out = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2026-27", "waiver_date": "2026-11-15",
            "moves": [{"kind": "waive", "player": "Alpha One", "stretch": True}],
        })
    finally:
        con.close()
    assert out["ok"] is True
    assert out["pay_after"] == 100_000_000
    step = next(row for row in out["steps"] if row["kind"] == "waive")
    assert step["dead_cap"] == 10_000_000
    assert step["stretched_amount"] == 10_000_000
    assert step["stretched_dead_cap"] == 3_333_333
    assert step["stretch_years"] == 3
    assert step["waiver_window"] == "post_sep1"
    assert out["meta"]["waiver_timing"]["date"] == "2026-11-15"
