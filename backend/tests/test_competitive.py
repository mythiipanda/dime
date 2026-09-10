"""Competitive ratings tests. Padding math is hermetic; one integration
test reads the real warehouse to prove the wiring and the invariants."""

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
    row = summarize_team("AAA", movs, 20)
    assert row["gp"] == 5
    assert row["mov_full"] == round(sum(movs) / 5, 2)
    assert row["gp_comp"] == 3
    assert row["mov_comp"] == round((2 + 1 + 0) / 3, 2)
    assert row["padding_delta"] == round(row["mov_full"] - row["mov_comp"], 2)
    assert row["padding_delta"] == 14.6
    assert row["blowout_gp"] == 2
    assert row["blowout_share"] == round(2 / 5, 3)
    assert row["comp_record"] == {"w": 2, "l": 1}
    assert row["verdict"] == "padded"


def test_boundary_abs_equals_margin_stays_in():
    row = summarize_team("AAA", [20.0, -20.0, 21.0], 20)
    assert row["gp_comp"] == 2
    assert row["blowout_gp"] == 1
    assert row["mov_comp"] == 0.0
    assert row["comp_record"] == {"w": 1, "l": 1}


def test_gritty_sign_and_neutral_band():
    gritty = summarize_team("AAA", [-30.0, 2.0, 3.0, 1.0], 20)
    assert gritty["padding_delta"] < -0.5
    assert gritty["verdict"] == "gritty"
    neutral = summarize_team("AAA", [35.0, -25.0, 5.0, 5.0], 20)
    assert neutral["mov_full"] == 5.0
    assert neutral["mov_comp"] == 5.0
    assert neutral["padding_delta"] == 0.0
    assert neutral["verdict"] == "neutral"


def test_empty_movs_zeros():
    row = summarize_team("AAA", [], 20)
    assert row["gp"] == 0
    assert row["mov_full"] == 0.0
    assert row["gp_comp"] == 0
    assert row["mov_comp"] == 0.0
    assert row["padding_delta"] == 0.0
    assert row["blowout_gp"] == 0
    assert row["blowout_share"] == 0.0
    assert row["comp_record"] == {"w": 0, "l": 0}
    assert row["verdict"] == "neutral"


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
    expected = summarize_team("BOS", movs, 20)
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
                "padding_delta", "blowout_gp", "blowout_share",
                "comp_record", "verdict"):
        assert row[key] == expected[key], key
    assert res["meta"]["source"] == "warehouse"
    assert res["meta"]["seasons"] == [SEASON]
    assert res["meta"]["blowout_margin"] == 20.0
    assert res["definition"] and res["caveats"]
    assert res["takeaway"] and "BOS" in res["takeaway"]
