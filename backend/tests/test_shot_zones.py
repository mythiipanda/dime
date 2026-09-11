"""get_team_shot_zones tests. Geometry, aggregation math, league deltas,
and missing-data degradation. Pure functions are hermetic; tool-level
failure cases hit only the local warehouse with seasons that hold no rows."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.zone import (ZONE_KEYS, aggregate_zones, build_rows,
                            get_team_shot_zones, league_baselines,
                            season_year, zone_of, _zone_leaders)


def _shot(team_id, x, y, value, made, abbr="TST"):
    return {"team_id": team_id, "team_abbr": abbr, "x": x, "y": y,
            "shot_value": value, "made": made}


def test_zone_of_rim():
    assert zone_of(0, 50, 2) == "rim"


def test_zone_of_short_mid():
    assert zone_of(50, 80, 2) == "short_mid"


def test_zone_of_long_mid():
    assert zone_of(100, 100, 2) == "long_mid"


def test_zone_of_corner_3():
    assert zone_of(230, 30, 3) == "corner_3"


def test_zone_of_above_break_3():
    assert zone_of(0, 250, 3) == "atb_3"


def test_zone_of_boundary_8ft_is_short_mid():
    assert zone_of(0, 80, 2) == "short_mid"


def test_zone_of_bad_coords_never_crashes():
    assert zone_of(None, None, 2) == "long_mid"


def test_season_year_maps_label_to_warehouse_int():
    assert season_year("2025-26") == 2026
    assert season_year("2021-22") == 2022


def test_aggregate_zone_math():
    shots = [
        _shot(1, 0, 50, 2, True),
        _shot(1, 0, 50, 2, True),
        _shot(1, 0, 50, 2, False),
        _shot(1, 0, 250, 3, True),
        _shot(1, 0, 250, 3, False),
    ]
    agg = aggregate_zones(shots)
    t = agg[1]
    assert t["zones"]["rim"] == {"fga": 3, "fgm": 2, "three_made": 0}
    assert t["zones"]["atb_3"] == {"fga": 2, "fgm": 1, "three_made": 1}
    assert t["zones"]["long_mid"] == {"fga": 0, "fgm": 0, "three_made": 0}


def test_aggregate_skips_shots_without_team():
    agg = aggregate_zones([{"team_id": None, "x": 0, "y": 50}])
    assert agg == {}


def test_league_baselines_pool_shots_not_averages():
    a = aggregate_zones([_shot(1, 0, 50, 2, True), _shot(1, 0, 50, 2, True),
                         _shot(1, 0, 50, 2, True), _shot(1, 0, 50, 2, True)])
    b = aggregate_zones([_shot(2, 0, 50, 2, False)] * 6
                        + [_shot(2, 0, 250, 3, False)])
    base = league_baselines({**a, **b})
    # 10 rim shots, 4 made -> efg 0.4; 11 total shots -> share 10/11
    assert base["rim"]["fga"] == 10
    assert base["rim"]["efg"] == 0.4
    assert base["rim"]["share"] == round(10 / 11, 4)
    assert base["atb_3"]["efg"] == 0.0


def test_build_rows_delta_arithmetic():
    shots = [
        _shot(1, 0, 50, 2, True, "AAA"),
        _shot(1, 0, 50, 2, True, "AAA"),
        _shot(2, 0, 250, 3, True, "BBB"),
        _shot(2, 0, 250, 3, True, "BBB"),
    ]
    agg = aggregate_zones(shots)
    base = league_baselines(agg)
    rows = build_rows(agg, baselines=base)
    assert rows[0]["team"] == "LEAGUE"
    assert rows[0]["rim_share"] == 0.5
    by_team = {r["team"]: r for r in rows[1:]}
    aaa = by_team["AAA"]
    assert aaa["rim_share"] == 1.0
    assert aaa["rim_share_delta_pp"] == 50.0
    assert aaa["rim_efg"] == 1.0
    assert aaa["rim_efg_delta_pp"] == round((1.0 - 1.0) * 100, 2)
    bbb = by_team["BBB"]
    assert bbb["atb_3_efg"] == 1.5
    assert bbb["atb_3_share_delta_pp"] == 50.0


def test_tool_rejects_season_with_no_rows():
    out = get_team_shot_zones.invoke({"teams": "league", "season": "2030-31"})
    assert out["ok"] is False
    assert "no shot rows" in out["error"]


def test_tool_rejects_unmatched_teams():
    out = get_team_shot_zones.invoke({"teams": "Not A Real Team", "season": "2025-26"})
    assert out["ok"] is False
    assert "no shot rows matched" in out["error"]


def test_tool_single_team_carries_league_baseline_row():
    out = get_team_shot_zones.invoke({"teams": "BOS", "season": "2025-26"})
    assert out["ok"] is True
    rows = out["rows"]
    assert rows[0]["team"] == "LEAGUE"
    teams = [r["team"] for r in rows[1:]]
    assert teams == ["BOS"]
    bos = rows[1]
    assert bos["shots"] > 7000
    shares = [bos[f"{k}_share"] for k in ZONE_KEYS]
    assert abs(sum(shares) - 1.0) < 0.01
    assert "data_note" in out["meta"]
    assert "2009-10 through 2025-26" in out["meta"]["data_note"]


def test_tool_mixes_known_and_unknown_teams():
    out = get_team_shot_zones.invoke({"teams": "BOS, Not A Real Team", "season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"]["unknown_teams"] == ["Not A Real Team"]
    assert [r["team"] for r in out["rows"][1:]] == ["BOS"]


def _leader_rows():
    # ZZZ sorts after AAA but leads rim on share delta: the leader must be
    # the max-delta team, never the first row scanned.
    shots = ([_shot(1, 0, 50, 2, True, "AAA")]
             + [_shot(1, 0, 250, 3, True, "AAA")] * 3
             + [_shot(2, 0, 50, 2, True, "ZZZ")] * 4)
    agg = aggregate_zones(shots)
    rows = build_rows(agg, league_baselines(agg))
    return rows


def test_zone_leader_is_max_delta_not_first_row():
    leaders = _zone_leaders(_leader_rows()[1:])
    assert leaders["rim"]["team"] == "ZZZ"
    assert leaders["rim"]["share_delta_pp"] == max(
        r["rim_share_delta_pp"] for r in _leader_rows()[1:])


def _tie_rows():
    rows = []
    for team, tid, share, delta in (("AAA", 1, 0.60, 10.0),
                                    ("ZZZ", 2, 0.62, 10.0),
                                    ("MMM", 3, 0.60, 10.0)):
        row = {"team": team, "team_id": tid, "shots": 100}
        for key in ZONE_KEYS:
            row[f"{key}_share"] = share if key == "rim" else 0.0
            row[f"{key}_share_delta_pp"] = delta if key == "rim" else 0.0
            row[f"{key}_efg"] = 0.0
            row[f"{key}_efg_delta_pp"] = 0.0
        rows.append(row)
    return rows


def test_zone_leader_tie_breaks_on_higher_share():
    # Equal delta on rim: ZZZ (0.62 share) beats AAA/MMM (0.60).
    assert _zone_leaders(_tie_rows())["rim"]["team"] == "ZZZ"


def test_zone_leader_full_tie_keeps_first_team():
    rows = _tie_rows()
    rows[1]["rim_share"] = 0.60  # now AAA, ZZZ, MMM tie fully
    assert _zone_leaders(rows)["rim"]["team"] == "AAA"


def test_tool_league_output_marks_rim_leader_nop():
    # DimeBench 2026-09-10 regression: rim share_delta_pp leader is NOP
    # +10.55, not runner-up DET +8.77.
    out = get_team_shot_zones.invoke({"teams": "league", "season": "2025-26"})
    assert out["ok"] is True
    leaders = out["zone_leaders"]
    assert leaders["rim"]["team"] == "NOP"
    assert leaders["rim"]["share_delta_pp"] == 10.55
    rows = out["rows"]
    for key, leader in leaders.items():
        flagged = [r for r in rows if r[f"is_{key}_share_leader"]]
        assert len(flagged) == 1
        assert flagged[0]["team"] == leader["team"]
        assert flagged[0][f"{key}_share_delta_pp"] == max(
            r[f"{key}_share_delta_pp"] for r in rows[1:])
