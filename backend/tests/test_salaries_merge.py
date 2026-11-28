import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

import seed_salaries as seed


def _frame(rows):
    return pl.DataFrame(rows)


def _new(player, team, sal26, guaranteed=100):
    return {
        "PLAYER_NAME": player,
        "TEAM": team,
        "BREF_SLUG": player.lower().replace(" ", ""),
        "SALARY_2026_27": sal26,
        "SALARY": sal26,
        "GUARANTEED": guaranteed,
    }


OLD = [
    {"PLAYER_NAME": "Stayer One", "TEAM": "BOS",
     "SALARY_2025_26": 500, "GUARANTEED": 500},
    {"PLAYER_NAME": "Departed Two", "TEAM": "WSH",
     "SALARY_2025_26": 700, "GUARANTEED": 700},
    {"PLAYER_NAME": "Dual Three", "TEAM": "MIL",
     "SALARY_2025_26": 900, "GUARANTEED": 900},
]


def test_prior_season_carried_to_continuing_player():
    frame = _frame([_new("Stayer One", "BOS", 600)])
    out = seed.merge_contracts(frame, OLD)
    row = out.row(0, named=True)
    assert row["SALARY_2025_26"] == 500
    assert row["SALARY_2026_27"] == 600


def test_departed_player_kept_with_last_team():
    frame = _frame([_new("Stayer One", "BOS", 600)])
    out = seed.merge_contracts(frame, OLD)
    rows = {r["PLAYER_NAME"]: r for r in out.to_dicts()}
    assert "Departed Two" in rows
    assert rows["Departed Two"]["TEAM"] == "WAS"
    assert rows["Departed Two"]["SALARY_2025_26"] == 700
    assert rows["Departed Two"]["SALARY_2026_27"] is None


def test_dead_money_dual_rows_both_kept():
    frame = _frame([
        _new("Dual Three", "MIL", 200),
        _new("Dual Three", "POR", 150),
    ])
    out = seed.merge_contracts(frame, OLD)
    teams = sorted(
        r["TEAM"] for r in out.to_dicts()
        if r["PLAYER_NAME"] == "Dual Three")
    assert teams == ["MIL", "POR"]


def test_merge_is_idempotent():
    frame = _frame([_new("Stayer One", "BOS", 600)])
    first = seed.merge_contracts(frame, OLD)
    second = seed.merge_contracts(frame, first.to_dicts())
    assert second.height == first.height


def test_empty_old_rows_returns_scrape():
    frame = _frame([_new("Stayer One", "BOS", 600)])
    out = seed.merge_contracts(frame, [])
    assert out.height == 1
    assert "SALARY_2025_26" not in out.columns


def test_moved_player_not_carried_under_old_team():
    frame = _frame([_new("Stayer One", "BOS", 600), _new("Dual Three", "LAC", 950)])
    out = seed.merge_contracts(frame, OLD)
    rows = [r for r in out.to_dicts() if r["PLAYER_NAME"] == "Dual Three"]
    assert len(rows) == 1
    assert rows[0]["TEAM"] == "LAC"


def test_departed_player_still_carried_when_absent_from_fresh_frame():
    frame = _frame([_new("Stayer One", "BOS", 600), _new("Dual Three", "LAC", 950)])
    out = seed.merge_contracts(frame, OLD)
    names = {r["PLAYER_NAME"] for r in out.to_dicts()}
    assert "Departed Two" in names


def _txn_con(rows):
    import duckdb
    con = duckdb.connect()
    con.execute("CREATE TABLE silver_transactions (player VARCHAR, txn_type VARCHAR, team VARCHAR, txn_date VARCHAR)")
    for r in rows:
        con.execute("INSERT INTO silver_transactions VALUES (?, ?, ?, ?)", r)
    return con


def _kind_frame(rows):
    return pl.DataFrame(rows)


def test_dead_money_annotated_for_waive_then_sign_elsewhere():
    frame = _kind_frame([
        _new("Klay Example", "DAL", 7660317),
        _new("Klay Example", "MIA", 5600000),
    ])
    con = _txn_con([
        ("klay-example", "Waive", "mavericks", "2026-08-21"),
        ("klay-example", "Signing", "heat", "2026-08-23"),
    ])
    out = seed.annotate_row_kinds(frame, con)
    kinds = {(r["TEAM"]): r["ROW_KIND"] for r in out.to_dicts()}
    assert kinds["MIA"] == "roster"
    assert kinds["DAL"] == "dead_money"


def test_single_row_waived_and_unsigned_is_dead_money():
    frame = _kind_frame([_new("Waiver Wire", "PHX", 19383010)])
    con = _txn_con([
        ("waiver-wire", "Waive", "suns", "2026-07-16"),
    ])
    out = seed.annotate_row_kinds(frame, con)
    assert out.row(0, named=True)["ROW_KIND"] == "dead_money"


def test_single_row_signed_player_stays_roster():
    frame = _kind_frame([_new("Stayer One", "BOS", 600)])
    con = _txn_con([
        ("stayer-one", "Signing", "celtics", "2026-07-01"),
    ])
    out = seed.annotate_row_kinds(frame, con)
    assert out.row(0, named=True)["ROW_KIND"] == "roster"


def test_multi_team_without_evidence_defaults_roster():
    frame = _kind_frame([
        _new("Mystery Man", "DAL", 100),
        _new("Mystery Man", "MIA", 200),
    ])
    con = _txn_con([])
    out = seed.annotate_row_kinds(frame, con)
    assert all(r["ROW_KIND"] == "roster" for r in out.to_dicts())


def test_no_transactions_table_does_not_crash():
    import duckdb
    frame = _kind_frame([_new("Stayer One", "BOS", 600)])
    con = duckdb.connect()
    out = seed.annotate_row_kinds(frame, con)
    assert out.row(0, named=True)["ROW_KIND"] == "roster"
