import duckdb
import pytest

from shared import store


@pytest.fixture
def waiver_seed(monkeypatch, tmp_path):
    counter = 0

    def seed(guaranteed):
        nonlocal counter
        counter += 1
        path = tmp_path / f"waiver-{counter}.duckdb"
        con = duckdb.connect(str(path))
        try:
            con.execute(
                "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
                "SALARY INTEGER, SALARY_2026_27 INTEGER, SALARY_2027_28 INTEGER, "
                "SALARY_2028_29 INTEGER, GUARANTEED INTEGER, _season VARCHAR, "
                "_fetched_at VARCHAR)")
            con.execute(
                "INSERT INTO silver_salaries VALUES "
                "('Alpha One', 'BOS', 10000000, 10000000, 10000000, 10000000, ?, "
                "'2026-27', '2026-10-01'), "
                "('BOS Filler', 'BOS', 90000000, 90000000, NULL, NULL, NULL, "
                "'2026-27', '2026-10-01')", [guaranteed])
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
    assert "$5,000,000 estimated dead cap" in step["detail"]
