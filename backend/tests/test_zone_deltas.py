"""get_zone_deltas tests. Warehouse reads only; player-vs-league FG%
deltas, attempts floors, and honest empty states."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.zonedelta import (build_deltas, clamp_floor,
                                 clamp_season_year, fold_zones,
                                 get_zone_deltas)

PLAYER = "Shai Gilgeous-Alexander"
SEASON = 2025


def test_happy_path_shape_and_sort():
    out = get_zone_deltas.invoke({"player": PLAYER, "season": SEASON})
    assert out["ok"] is True
    assert out["rows"]["player"] == PLAYER
    zones = out["rows"]["zones"]
    assert len(zones) == 4
    for z in zones:
        assert set(z) >= {"zone", "attempts", "makes", "fg_pct",
                          "league_fg_pct", "delta_pp", "league_attempts"}
        assert z["fg_pct"] == round(z["makes"] / z["attempts"], 3)
        assert abs(z["delta_pp"]
                   - (z["fg_pct"] - z["league_fg_pct"]) * 100) < 0.11
    deltas = [z["delta_pp"] for z in zones]
    assert deltas == sorted(deltas, reverse=True)
    assert zones[0]["zone"] == "long_mid"
    assert out["meta"]["source"] == "warehouse silver_hist_shots"


def test_floor_enforcement_excludes_thin_zones():
    loose = get_zone_deltas.invoke({"player": PLAYER, "season": SEASON,
                                    "min_attempts": 10})
    assert loose["ok"] is True
    assert len(loose["rows"]["zones"]) == 5
    assert loose["meta"]["excluded_zones"] == []
    strict = get_zone_deltas.invoke({"player": PLAYER, "season": SEASON,
                                     "min_attempts": 200})
    assert strict["ok"] is True
    kept = {z["zone"] for z in strict["rows"]["zones"]}
    assert kept == {"rim", "short_mid", "long_mid", "atb_3"}
    assert strict["meta"]["excluded_zones"] == ["corner_3"]


def test_unknown_player_is_honest():
    out = get_zone_deltas.invoke({"player": "Not A Real Player XYZ",
                                  "season": SEASON})
    assert out["ok"] is False
    assert "unknown player" in out["error"]


def test_player_without_coverage_is_honest():
    out = get_zone_deltas.invoke({"player": PLAYER, "season": 2010})
    assert out["ok"] is False
    assert "no shot rows for player" in out["error"]


def test_season_clamp_flows_through_tool():
    assert clamp_season_year(2005) == 2010
    assert clamp_season_year(9999) == 2025
    assert clamp_season_year("garbage") == 2025
    low = get_zone_deltas.invoke({"player": PLAYER, "season": 2005})
    assert low["ok"] is False
    assert low["meta"]["season"] == 2010
    high = get_zone_deltas.invoke({"player": PLAYER, "season": 9999})
    assert high["ok"] is True
    assert high["meta"]["season"] == 2025


def test_floor_clamp_bounds():
    assert clamp_floor(5) == 10
    assert clamp_floor(500) == 200
    assert clamp_floor("garbage") == 50
    out = get_zone_deltas.invoke({"player": PLAYER, "season": SEASON,
                                  "min_attempts": 500})
    assert out["meta"]["min_attempts"] == 200
    assert {z["zone"] for z in out["rows"]["zones"]} == {
        "rim", "short_mid", "long_mid", "atb_3"}


def test_league_average_sanity_vs_raw_sql():
    from app import store

    con = store.connect(read_only=True)
    try:
        rows = con.execute(
            "SELECT x_legacy, y_legacy, shot_value, shot_result "
            "FROM silver_hist_shots WHERE season = ?", [SEASON]).fetchall()
    finally:
        con.close()

    def _zone(x, y, v):
        try:
            dist = math.hypot(float(x), float(y)) / 10.0
        except (TypeError, ValueError):
            dist = 999.0
        try:
            ax = abs(float(x))
        except (TypeError, ValueError):
            ax = 0.0
        three = int(v or 0) == 3
        if dist < 8.0:
            return "rim"
        if three and ax >= 220:
            return "corner_3"
        if three:
            return "atb_3"
        if dist < 14.0:
            return "short_mid"
        return "long_mid"

    agg: dict[str, list[int]] = {}
    for x, y, v, r in rows:
        slot = agg.setdefault(_zone(x, y, v), [0, 0])
        slot[1] += 1
        if str(r or "").lower() == "made":
            slot[0] += 1
    out = get_zone_deltas.invoke({"player": PLAYER, "season": SEASON,
                                  "min_attempts": 10})
    assert out["ok"] is True
    for z in out["rows"]["zones"]:
        made, att = agg[z["zone"]]
        assert z["league_fg_pct"] == round(made / att, 3)
        assert z["league_attempts"] == att


def test_fully_excluded_view_has_note_and_lists():
    out = get_zone_deltas.invoke({"player": "Terry Taylor", "season": SEASON,
                                  "min_attempts": 10})
    assert out["ok"] is True
    assert out["rows"]["zones"] == []
    assert out["meta"]["note"]
    assert set(out["meta"]["excluded_zones"]) == {
        "rim", "short_mid", "long_mid", "corner_3", "atb_3"}


def test_season_2026_clamps_with_warning():
    out = get_zone_deltas.invoke({"player": PLAYER, "season": 2026})
    assert out["ok"] is True
    assert out["meta"]["season"] == 2025
    assert "warning" in out["meta"]
    assert "2026" in out["meta"]["warning"] and "2025" in out["meta"]["warning"]


def test_floor_clamp_warns():
    out = get_zone_deltas.invoke({"player": PLAYER, "season": SEASON,
                                  "min_attempts": 500})
    assert out["meta"]["min_attempts"] == 200
    assert "warning" in out["meta"]
    assert "500" in out["meta"]["warning"] and "200" in out["meta"]["warning"]


def test_error_meta_season_label_consistent():
    unknown = get_zone_deltas.invoke({"player": "Not A Real Player XYZ",
                                      "season": SEASON})
    assert unknown["ok"] is False
    assert unknown["meta"]["season_label"] == "2024-25"
    nocov = get_zone_deltas.invoke({"player": PLAYER, "season": 2010})
    assert nocov["ok"] is False
    assert nocov["meta"]["season_label"] == "2009-10"


def test_pure_helpers_fold_and_delta_math():
    shots = ([{"x": 0, "y": 50, "shot_value": 2, "shot_result": "Made"}] * 3
             + [{"x": 0, "y": 50, "shot_value": 2, "shot_result": "Missed"}]
             + [{"x": 0, "y": 250, "shot_value": 3, "shot_result": "Made"}])
    folded = fold_zones(shots)
    assert folded["rim"] == {"fga": 4, "fgm": 3}
    assert folded["atb_3"] == {"fga": 1, "fgm": 1}
    league = {k: {"fga": 100, "fgm": 50} for k in folded}
    rows, excluded = build_deltas(folded, league, 1)
    assert excluded == ["corner_3", "short_mid", "long_mid"]
    by_zone = {r["zone"]: r for r in rows}
    assert by_zone["rim"]["delta_pp"] == round((0.75 - 0.5) * 100, 2)
    assert rows[0]["zone"] == "atb_3"
