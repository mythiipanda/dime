"""search_shots tests. Pure helpers and filter parsing only; no warehouse,
no network. Synthetic shot dicts use the normalized shape (zone, made,
period, game_id) consumed by the summarize helpers."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.shots import (ZONE_KEYS, ZONE_LABEL_MAP, disambiguate_last_name,
                             efficiency, format_clock, is_heave, parse_made,
                             parse_late_clock, parse_periods, parse_zones,
                             period_matches, seconds_left, summarize,
                             summarize_by_period, summarize_by_zone,
                             zone_of_label)


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
