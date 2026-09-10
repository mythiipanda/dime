"""search_shots tests.

Pure helpers are tested without the warehouse. Integration tests call the
tool itself against the real silver_shots warehouse (2025-26, 233,632 rows)
via search_shots.invoke -- no network, no mocks.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.shots import (ZONE_KEYS, ZONE_LABEL_MAP, disambiguate_last_name,
                             efficiency, fold_ot, format_clock, group_row,
                             is_heave, parse_group_by, parse_include_ot,
                             parse_made, parse_late_clock, parse_periods,
                             parse_zones, period_matches, search_shots,
                             seconds_left, summarize, summarize_by_period,
                             summarize_by_zone, zone_of_label)


def _shot(zone, made, period=4, game="g1"):
    return {"zone": zone, "made": made, "period": period, "game_id": game}


def test_zone_of_label_maps_all_six_values():
    assert zone_of_label("Restricted Area") == "rim"
    assert zone_of_label("In The Paint (Non-RA)") == "short_mid"
    assert zone_of_label("Mid-Range") == "long_mid"
    assert zone_of_label("Left Corner 3") == "corner_3"
    assert zone_of_label("Right Corner 3") == "corner_3"
    assert zone_of_label("Above the Break 3") == "atb_3"
    assert set(ZONE_LABEL_MAP) == {
        "Restricted Area", "In The Paint (Non-RA)", "Mid-Range",
        "Left Corner 3", "Right Corner 3", "Above the Break 3"}


def test_zone_of_label_unknown_returns_none():
    assert zone_of_label("Half Court") is None
    assert zone_of_label(None) is None


def test_parse_zones_defaults_to_all_and_rejects_unknown():
    assert parse_zones("") == set(ZONE_KEYS)
    assert parse_zones("corner_3, atb_3") == {"corner_3", "atb_3"}
    with pytest.raises(ValueError, match="unknown zone"):
        parse_zones("corner_3, paint")


def test_parse_periods_tokens():
    assert parse_periods("") is None
    assert parse_periods("4th") == {4}
    assert parse_periods("ot") == {5}
    assert parse_periods("1h") == {1, 2}
    assert parse_periods("2h") == {3, 4}
    assert parse_periods("1,2") == {1, 2}


def test_parse_periods_rejects_unknown():
    with pytest.raises(ValueError, match="unknown period"):
        parse_periods("q5")


def test_period_matches_groups_ot():
    assert period_matches(4, {4}) is True
    assert period_matches(5, {5}) is True
    assert period_matches(7, {5}) is True
    assert period_matches(5, {4}) is False
    assert period_matches(3, None) is True
    assert period_matches(None, {4}) is False


def test_parse_group_by():
    assert parse_group_by("") == ""
    assert parse_group_by("player") == "player"
    assert parse_group_by("TEAM") == "team"
    with pytest.raises(ValueError, match="invalid group_by"):
        parse_group_by("zone")


def test_parse_include_ot():
    assert parse_include_ot("", True) is True
    assert parse_include_ot("auto", False) is False
    assert parse_include_ot("yes", False) is True
    assert parse_include_ot("no", True) is False
    assert parse_include_ot("TRUE", True) is True
    with pytest.raises(ValueError, match="invalid include_ot"):
        parse_include_ot("maybe", True)


def test_fold_ot():
    assert fold_ot({4}, True) == {4, 5}
    assert fold_ot({4}, False) == {4}
    assert fold_ot({1, 2}, True) == {1, 2, 5}
    assert fold_ot({5}, False) == {5}
    assert fold_ot(None, True) is None


def test_group_row_small_sample_flag():
    big = group_row(50, 25, 10, games=12)
    assert big["attempts"] == 50
    assert big["efg_pct"] == 0.6
    assert big["points"] == 2 * 25 + 10
    assert big["small_sample"] is False
    small = group_row(5, 3, 2)
    assert small["small_sample"] is True
    assert "games" not in small


def test_is_heave_boundary():
    assert is_heave(29, 0, 3) is False
    assert is_heave(30, 0, 3) is True
    assert is_heave(30, 0, 4) is False
    assert is_heave(35, 0, 0) is True
    assert is_heave(30, None, None) is False
    assert is_heave(None, 0, 1) is False


def test_efficiency_efg_math():
    # 2/4 with one three: (2 + 0.5) / 4 = 0.625.
    assert efficiency(4, 2, 1) == {"fg_pct": 0.5, "efg_pct": 0.625}
    assert efficiency(0, 0, 0) == {"fg_pct": 0.0, "efg_pct": 0.0}


def test_parse_made_validation():
    assert parse_made("MADE") == "made"
    assert parse_made("any") == "any"
    with pytest.raises(ValueError, match="invalid made filter"):
        parse_made("sometimes")


def test_parse_late_clock_validation():
    assert parse_late_clock("") is None
    assert parse_late_clock("30") == 30
    with pytest.raises(ValueError, match="invalid late_clock"):
        parse_late_clock("abc")
    with pytest.raises(ValueError, match="invalid late_clock"):
        parse_late_clock("Q4:30")


def test_disambiguate_last_name_unique_and_ambiguous():
    unique = disambiguate_last_name(
        "gilgeous-alexander", [("Gilgeous-Alexander", 1628983)])
    assert unique == {"player_id": 1628983,
                      "candidates": [{"player": "Gilgeous-Alexander",
                                      "player_id": 1628983}],
                      "ambiguous": False}
    shared = disambiguate_last_name(
        "Williams", [("Williams", 101), ("Williams", 202)])
    assert shared["ambiguous"] is True
    assert shared["player_id"] is None
    assert [c["player_id"] for c in shared["candidates"]] == [101, 202]
    missing = disambiguate_last_name("Nobody", [("Williams", 101)])
    assert missing == {"player_id": None, "candidates": [],
                       "ambiguous": False}


def test_summarize_overall_and_by_zone_and_period():
    shots = [_shot("corner_3", True, 4, "g1"),
             _shot("corner_3", False, 4, "g1"),
             _shot("rim", True, 5, "g2"),
             _shot("atb_3", False, 6, "g2")]
    agg = summarize(shots)
    assert agg["attempts"] == 4
    assert agg["makes"] == 2
    assert agg["threes_made"] == 1
    assert agg["games"] == 2
    assert agg["efg_pct"] == 0.625
    by_zone = {r["zone"]: r for r in summarize_by_zone(shots)}
    assert by_zone["corner_3"]["attempts"] == 2
    assert by_zone["corner_3"]["makes"] == 1
    assert by_zone["rim"]["attempts"] == 1
    assert by_zone["long_mid"]["attempts"] == 0
    by_period = {r["period"]: r for r in summarize_by_period(shots)}
    assert by_period[4]["attempts"] == 2
    assert by_period["OT"]["attempts"] == 2
    assert by_period["OT"]["makes"] == 1


def test_seconds_left_and_clock_format():
    assert seconds_left(1, 5) == 65
    assert seconds_left(None, 5) is None
    assert format_clock(1, 5) == "1:05"
    assert format_clock(None, None) == "unknown"


# ---------------------------------------------------------------------------
# Integration tests against the real warehouse (2025-26 silver_shots).


def test_tool_tatum_corner3_4th_matches_verified_numbers():
    res = search_shots.invoke(
        {"player": "Tatum", "zones": "corner_3", "periods": "4th"})
    assert res["ok"] is True
    agg = res["aggregate"]
    assert agg["attempts"] == 5
    assert agg["makes"] == 3
    assert agg["efg_pct"] == 0.9
    # S2: tiny sample must be flagged.
    assert agg["small_sample"] is True
    assert "sample_warning" in res["meta"]


def test_tool_small_sample_flag_off_for_big_lines():
    res = search_shots.invoke({"team": "BOS", "zones": "rim"})
    assert res["ok"] is True
    agg = res["aggregate"]
    assert agg["attempts"] > 100
    assert agg["small_sample"] is False
    assert "sample_warning" not in res["meta"]


def test_tool_group_by_player_leaderboard():
    res = search_shots.invoke({"periods": "4th", "group_by": "player"})
    assert res["ok"] is True
    rows = res["by_player"]
    assert len(rows) > 100  # league-wide scan, one call
    attempts = [r["attempts"] for r in rows]
    assert attempts == sorted(attempts, reverse=True)
    top = rows[0]
    assert top["player_id"]
    assert top["player"]  # full name resolved
    assert top["efg_pct"] > 0
    assert "small_sample" in top
    assert res["filters"]["group_by"] == "player"


def test_tool_group_by_team():
    res = search_shots.invoke({"periods": "4th", "group_by": "team"})
    assert res["ok"] is True
    rows = res["by_team"]
    assert len(rows) == 30
    assert all(r["team"] and len(r["team"]) == 3 for r in rows)
    attempts = [r["attempts"] for r in rows]
    assert attempts == sorted(attempts, reverse=True)


def test_tool_4th_includes_ot_by_default():
    default = search_shots.invoke({"periods": "4th"})
    no_ot = search_shots.invoke({"periods": "4th", "include_ot": "no"})
    assert default["ok"] and no_ot["ok"]
    assert default["aggregate"]["attempts"] >= no_ot["aggregate"]["attempts"]
    assert default["filters"]["include_ot"] is True
    assert no_ot["filters"]["include_ot"] is False
    assert "OT" in default["filters"]["periods"]
    assert "OT" not in no_ot["filters"]["periods"]
    # OT bucket present by default (the season has OT games).
    assert any(r["period"] == "OT" for r in default["by_period"])
    assert not any(r["period"] == "OT" for r in no_ot["by_period"])


def test_tool_disambiguation_returns_candidates():
    res = search_shots.invoke({"player": "Williams"})
    assert res["ok"] is True
    assert "disambiguation" in res
    cands = res["disambiguation"]["candidates"]
    assert len(cands) > 1
    attempts = [c["attempts"] for c in cands]
    assert attempts == sorted(attempts, reverse=True)
    for c in cands:
        assert c["player_id"]
        assert c["player"]  # full name, not just last name
        assert isinstance(c["teams"], list) and c["teams"]
        assert "small_sample" in c


def test_tool_unknown_player_still_errors():
    res = search_shots.invoke({"player": "Nobody McNobodyface"})
    assert res["ok"] is False
    assert "unknown player" in res["error"]


def test_tool_clutch_safe_flag():
    res = search_shots.invoke({"periods": "4th", "late_clock": "300"})
    assert res["ok"] is True
    assert res["meta"]["clutch_safe"] is False
    assert res["meta"]["score_aware"] is False


def test_tool_heave_disabled_meta_says_included():
    res = search_shots.invoke({"periods": "4th", "exclude_heaves": False})
    assert res["ok"] is True
    assert res["meta"]["heaves_excluded"] == 0
    assert "INCLUDED" in res["meta"]["data_note"]
    on = search_shots.invoke({"periods": "4th", "exclude_heaves": True})
    assert "excluded here" in on["meta"]["data_note"]


def test_tool_conflicting_filters_explain_zero_rows():
    res = search_shots.invoke({"periods": "1h", "late_clock": "60"})
    assert res["ok"] is True
    assert res["aggregate"]["attempts"] == 0
    assert "note" in res["meta"]
    assert "late_clock" in res["meta"]["note"]
    # Generic zero-match also explains instead of silent zeros.
    res2 = search_shots.invoke({"player": "Tatum", "periods": "1",
                                "late_clock": "5", "made": "made",
                                "zones": "corner_3", "three_only": True})
    if res2["aggregate"]["attempts"] == 0:
        assert "note" in res2["meta"]


def test_tool_by_zone_only_requested_zones():
    res = search_shots.invoke({"zones": "rim"})
    assert res["ok"] is True
    assert res["by_zone"]
    assert all(r["zone"] == "rim" for r in res["by_zone"])
    assert all(r["zone"] in {"rim", "corner_3"}
               for r in search_shots.invoke(
                   {"zones": "rim,corner_3"})["by_zone"])


def test_tool_sample_rows_are_a_season_mix():
    res = search_shots.invoke({"periods": "4th", "limit": 25})
    assert res["ok"] is True
    shots = res["shots"]
    assert len(shots) == 25
    gids = [s["game_id"] for s in shots]
    assert len(set(gids)) > 1
    # Not reverse-chronological (the old latest-GAME_IDs-first skew).
    assert gids != sorted(gids, reverse=True)


def test_tool_performance_smoke():
    start = time.perf_counter()
    res = search_shots.invoke(
        {"periods": "4th", "late_clock": "300", "group_by": "player"})
    elapsed = time.perf_counter() - start
    assert res["ok"] is True
    assert res["aggregate"]["attempts"] > 20000
    assert elapsed < 2.0, f"search_shots took {elapsed:.2f}s"
