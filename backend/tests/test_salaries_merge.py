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
