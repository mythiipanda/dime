"""Competitive ratings tests. The tool is descriptive: no verdicts, no
takeaways, numbers plus sensitivity. Padding math is hermetic; integration
tests read the real warehouse to prove the wiring and the invariants."""

import sys
import time
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import get_competitive_ratings
from app.tools._core import SEASON
from app.tools.competitive import (
    clamp_blowout_margin,
    map_season_type,
    summarize_team,
)


def _connect_retry(tries=6, sleep_s=2):
    """Open the warehouse for the test's own direct SQL verification.

    Seed jobs hold the warehouse write lock at a time; only
    lock-conflict errors retry, everything else raises. A persistent
    lock raises so the caller can skip; any other failure is a real
    error and must fail the test.
    """
    last: Exception | None = None
    for _ in range(tries):
        try:
            from app import store as _store

            return _store.connect(read_only=True)
        except (duckdb.IOException, duckdb.ConnectionException) as exc:
            if ("lock" not in str(exc).lower()
                    and "conflict" not in str(exc).lower()):
                raise
            last = exc
            time.sleep(sleep_s)
    assert last is not None
    raise last


def test_known_movs_padding_delta():
    movs = [40.0, 35.0, 2.0, 1.0, 0.0]
    row = summarize_team("AAA", movs, 20, min_games=3)
    assert row["gp"] == 5
    assert row["mov_full"] == round(sum(movs) / 5, 2)
    assert row["gp_comp"] == 3
    assert row["mov_comp"] == round((2 + 1 + 0) / 3, 2)
    assert row["padding_delta"] == round(row["mov_full"] - row["mov_comp"], 2)
    assert row["padding_delta"] == 14.6
    assert row["blowout_gp"] == 2
    assert row["blowout_wins_gp"] == 2
    assert row["blowout_losses_gp"] == 0
    assert row["blowout_wins_share"] == round(2 / 5, 3)
    assert row["blowout_losses_share"] == 0.0
    assert "blowout_share" not in row
    assert row["competitive_record"] == {"w": 2, "l": 1}
    assert "comp_record" not in row
    assert "verdict" not in row
    assert row["low_sample"] is False


def test_boundary_abs_equals_margin_stays_in():
    row = summarize_team("AAA", [20.0, -20.0, 21.0], 20, min_games=2)
    assert row["gp_comp"] == 2
    assert row["blowout_gp"] == 1
    assert row["blowout_wins_gp"] == 1
    assert row["mov_comp"] == 0.0
    assert row["competitive_record"] == {"w": 1, "l": 1}


def test_delta_sign_without_verdict():
    neg = summarize_team("AAA", [-30.0, 2.0, 3.0, 1.0], 20, min_games=1)
    assert neg["padding_delta"] < 0
    assert "verdict" not in neg
    zero = summarize_team("AAA", [35.0, -25.0, 5.0, 5.0], 20, min_games=1)
    assert zero["mov_full"] == 5.0
    assert zero["mov_comp"] == 5.0
    assert zero["padding_delta"] == 0.0
    assert "verdict" not in zero


def test_blowout_split_wins_vs_losses():
    movs = [30.0, 25.0, -35.0, 2.0, 1.0, -1.0]
    row = summarize_team("AAA", movs, 20, min_games=1)
    assert row["blowout_wins_gp"] == 2
    assert row["blowout_losses_gp"] == 1
    assert row["blowout_gp"] == 3
    assert row["blowout_wins_share"] == round(2 / 6, 3)
    assert row["blowout_losses_share"] == round(1 / 6, 3)


def test_empty_competitive_set_returns_nulls():
    row = summarize_team("AAA", [25.0, -30.0], 1)
    assert row["gp"] == 2
    assert row["mov_full"] == round(-5.0 / 2, 2)
    assert row["gp_comp"] == 0
    assert row["mov_comp"] is None
    assert row["padding_delta"] is None
    assert row["competitive_record"] == {"w": 0, "l": 0}
    assert row["low_sample"] is True
    assert "verdict" not in row
    sens = {s["blowout_margin"]: s["padding_delta"]
            for s in row["sensitivity"]}
    # at 10/20 both games are still blowouts (nulls); at 30 both stay in,
    # so delta collapses to 0.0 -- exactly the dependence the section shows
    assert sens[10] is None
    assert sens[20] is None
    assert sens[30] == 0.0


def test_fully_empty_movs():
    row = summarize_team("AAA", [], 20)
    assert row["gp"] == 0
    assert row["mov_full"] is None
    assert row["gp_comp"] == 0
    assert row["mov_comp"] is None
    assert row["padding_delta"] is None
    assert row["blowout_gp"] == 0
    assert row["blowout_wins_share"] == 0.0
    assert row["blowout_losses_share"] == 0.0
    assert row["competitive_record"] == {"w": 0, "l": 0}
    assert row["low_sample"] is True


def test_low_sample_flag_keeps_numbers():
    movs = [5.0] * 12
    row = summarize_team("AAA", movs, 20, min_games=15)
    assert row["low_sample"] is True
    assert row["gp_comp"] == 12
    assert row["mov_comp"] == 5.0
    assert row["padding_delta"] == 0.0
    ok = summarize_team("AAA", movs, 20, min_games=12)
    assert ok["low_sample"] is False


def test_sensitivity_shows_threshold_dependence():
    movs = [12.0, -25.0, 3.0, 1.0]
    row = summarize_team("AAA", movs, 20, min_games=1)
    sens = {s["blowout_margin"]: s["padding_delta"]
            for s in row["sensitivity"]}
    assert set(sens) == {10, 20, 30}
    # margin 10: comp=[3,1] -> mov_comp 2.0, full -2.25 -> delta -4.25
    assert sens[10] == -4.25
    # margin 20: comp=[12,3,1] -> mov_comp 5.33, delta -7.58
    assert sens[20] == round(-2.25 - round(16 / 3, 2), 2)
    # margin 30: nothing excluded -> delta 0.0
    assert sens[30] == 0.0


def test_blowout_margin_clamp():
    assert clamp_blowout_margin(0) == 1.0
    assert clamp_blowout_margin(100) == 40.0
    assert clamp_blowout_margin(-5) == 1.0
    assert clamp_blowout_margin(20) == 20.0
    assert clamp_blowout_margin("bogus") == 20.0


def test_season_type_mapping():
    distinct = ["Regular Season", "Playoffs"]
    assert map_season_type("regular", distinct) == "Regular Season"
    assert map_season_type("REGULAR", distinct) == "Regular Season"
    assert map_season_type("playoffs", distinct) == "Playoffs"
    assert map_season_type("playoff", distinct) == "Playoffs"
    assert map_season_type("all", distinct) == "all"
    assert map_season_type("preseason", distinct) is None
    warehouse_style = ["regular-season", "playoffs"]
    assert map_season_type("regular", warehouse_style) == "regular-season"
    assert map_season_type("playoffs", warehouse_style) == "playoffs"


def test_unknown_team_rejected():
    res = get_competitive_ratings.invoke({"team": "Not A Team"})
    assert res["ok"] is False
    assert res["tool"] == "get_competitive_ratings"
    assert "unknown team" in res["error"]


def test_bad_season_type_rejected():
    res = get_competitive_ratings.invoke({"season_type": "preseason"})
    assert res["ok"] is False
    assert "season_type" in res["error"]


def test_integration_team_matches_raw_reaggregation_real_warehouse():
    try:
        con = _connect_retry()
    except (duckdb.IOException, duckdb.ConnectionException, TimeoutError):
        pytest.skip("warehouse lock timeout; seed job holds the lock")
    try:
        raw = con.execute(
            """SELECT plus_minus FROM silver_hist_gamelogs
               WHERE _season = ? AND team_abbreviation = ?
                 AND season_type = 'regular-season'""",
            [SEASON, "BOS"],
        ).fetchall()
    finally:
        con.close()
    assert raw, f"no regular-season rows for BOS in {SEASON}"
    movs = [float(r[0]) for r in raw if r[0] is not None]
    expected = summarize_team("BOS", movs, 20, 10)
    res = get_competitive_ratings.invoke({"team": "BOS", "season": SEASON,
                                          "season_type": "regular",
                                          "blowout_margin": 20})
    assert res["ok"] is True, res.get("error")
    assert res["tool"] == "get_competitive_ratings"
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert row["team"] == "BOS"
    assert row["gp_comp"] <= row["gp"]
    for key in ("gp", "mov_full", "gp_comp", "mov_comp",
                "padding_delta", "blowout_gp", "blowout_wins_gp",
                "blowout_losses_gp", "blowout_wins_share",
                "blowout_losses_share", "competitive_record",
                "low_sample"):
        assert row[key] == expected[key], key
    assert "verdict" not in row
    assert "takeaway" not in res
    sens = {s["blowout_margin"]: s["padding_delta"]
            for s in row["sensitivity"]}
    assert set(sens) == {10, 20, 30}
    assert res["meta"]["source"] == "warehouse"
    assert res["meta"]["seasons"] == [SEASON]
    assert res["meta"]["season_scope"] == "single"
    assert res["meta"]["blowout_margin"] == 20.0
    assert "regular" in res["meta"]["season_type"].lower()
    assert isinstance(res.get("read"), str)
    assert "competitive MOV" in res["read"]
    assert "margin threshold 20" in res["read"]
    assert "padding_delta" in res["read"] or "pts" in res["read"]
    assert res["definition"] and res["caveats"]
    assert "both directions" in res["caveats"]
    assert "lens, not purification" in res["caveats"]


def test_integration_default_season_type_is_regular():
    try:
        _connect_retry().close()
    except (duckdb.IOException, duckdb.ConnectionException, TimeoutError):
        pytest.skip("warehouse lock timeout; seed job holds the lock")
    res = get_competitive_ratings.invoke({"team": "BOS", "season": SEASON})
    assert res["ok"] is True, res.get("error")
    assert "regular" in res["meta"]["season_type"].lower()
    split = res["meta"]["season_type_split"]
    assert sum(split.values()) == res["rows"][0]["gp"]


def test_integration_league_mode_flags_no_verdicts():
    try:
        _connect_retry().close()
    except (duckdb.IOException, duckdb.ConnectionException, TimeoutError):
        pytest.skip("warehouse lock timeout; seed job holds the lock")
    res = get_competitive_ratings.invoke({"team": "league",
                                          "season": SEASON})
    assert res["ok"] is True, res.get("error")
    assert len(res["rows"]) == 30
    assert "below_floor" not in res
    for r in res["rows"]:
        assert "verdict" not in r
        assert isinstance(r["low_sample"], bool)
        assert len(r["sensitivity"]) == 3
    deltas = [r["padding_delta"] for r in res["rows"]]
    non_null = [d for d in deltas if d is not None]
    assert deltas[:len(non_null)] == sorted(non_null, reverse=True)
    assert all(d is None for d in deltas[len(non_null):])


def test_integration_playoffs_team_is_low_sample_without_read():
    try:
        _connect_retry().close()
    except (duckdb.IOException, duckdb.ConnectionException, TimeoutError):
        pytest.skip("warehouse lock timeout; seed job holds the lock")
    res = get_competitive_ratings.invoke({"team": "BOS", "season": SEASON,
                                          "season_type": "playoffs"})
    assert res["ok"] is True, res.get("error")
    row = res["rows"][0]
    assert row["gp_comp"] < 10
    assert row["low_sample"] is True
    assert res["read"] is None
    assert "low-sample" in res["note"]
    assert row["mov_full"] is not None  # numbers still reported


def test_integration_pooled_season_label():
    try:
        _connect_retry().close()
    except (duckdb.IOException, duckdb.ConnectionException, TimeoutError):
        pytest.skip("warehouse lock timeout; seed job holds the lock")
    res = get_competitive_ratings.invoke({"team": "BOS", "season": "all"})
    assert res["ok"] is True, res.get("error")
    assert res["meta"]["season_scope"] == "pooled"
    assert "not a single team-season" in res["meta"]["season_note"]
    assert len(res["meta"]["seasons"]) == 5
