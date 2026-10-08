
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.lineup_matrix import (
    SMALL_PAIR_POSS,
    _fallback_name,
    _pair_flags,
    _pair_row,
    _season_lineup_minutes,
    _truncate_note,
    _unit_key,
    get_lineup_matchup_matrix,
)

A, B, C = 1, 2, 3
A1 = (1, 2, 3, 4, 5)
B1 = (11, 12, 13, 14, 15)
BX = (31, 32, 33, 34, 35)

def _prow(game, n, off, deff, pts, off_unit, def_unit):
    row = {"game_id": game, "possession_number": n,
           "offense_team_id": off, "defense_team_id": deff, "points": pts}
    for i, p in enumerate(off_unit, 1):
        row[f"off_player_{i}"] = p
    for i, p in enumerate(def_unit, 1):
        row[f"def_player_{i}"] = p
    return row

def test_unit_key_sorts_five_valid_players():
    assert _unit_key([5, 3, 1, 4, 2]) == (1, 2, 3, 4, 5)
    assert _unit_key(["5", "4", "3", "2", "1"]) == (1, 2, 3, 4, 5)

def test_unit_key_missing_player_is_none():
    assert _unit_key([1, 2, None, 4, 5]) is None
    assert _unit_key([1, 2, 4, 5]) is None

def test_unit_key_non_int_is_none():
    assert _unit_key(["1", "2", "x", "4", "5"]) is None
    assert _unit_key([1, 2, 3.5j, 4, 5]) is None

def test_season_lineup_minutes_counts_both_ends():
    rows = [
        _prow("g1", 1, A, B, 2, A1, B1),
        _prow("g1", 2, B, A, 0, B1, A1),
        _prow("g1", 3, A, C, 2, A1, BX),
    ]
    assert _season_lineup_minutes(rows, A) == {A1: 3}
    assert _season_lineup_minutes(rows, B) == {B1: 2}

def test_pair_row_literal_ratings_math():
    agg = {"poss": 100, "off_poss_a": 50, "off_poss_b": 50,
           "pts_a": 60, "pts_b": 55, "blowout": 10}
    row = _pair_row(A1, B1, agg, "alpha unit", "beta unit")
    assert row == {
        "team_a_lineup": "alpha unit",
        "team_a_ids": [1, 2, 3, 4, 5],
        "team_b_lineup": "beta unit",
        "team_b_ids": [11, 12, 13, 14, 15],
        "poss": 100,
        "est_minutes": 50.0,
        "off_poss_a": 50,
        "off_poss_b": 50,
        "pts_a": 60,
        "pts_b": 55,
        "OFF_RATING_A": 120.0,
        "DEF_RATING_A": 110.0,
        "NET_RATING_A": 10.0,
        "blowout_share": 0.1,
        "flags": ["estimated-minutes: shared court time estimated from "
                  "possessions (~2 possessions per minute), "
                  "not play-clock minutes"],
    }

def test_pair_row_zero_off_poss_no_crash():
    row = _pair_row(A1, B1,
                    {"poss": 4, "off_poss_a": 0, "off_poss_b": 4,
                     "pts_a": 0, "pts_b": 8, "blowout": 0},
                    "alpha", "beta")
    assert row["OFF_RATING_A"] == 0.0
    assert row["DEF_RATING_A"] == 200.0
    assert row["NET_RATING_A"] == -200.0
    assert row["est_minutes"] == 2.0

def test_pair_flags_tiny_sample():
    flags = _pair_flags(12, 0.0)
    assert flags[0] == (f"tiny-sample: 12 shared possessions under the "
                        f"{SMALL_PAIR_POSS}-possession floor, not signal")
    assert any("estimated-minutes" in f for f in flags)
    assert not any("blowout-heavy" in f for f in flags)

def test_pair_flags_blowout_at_half_share():
    flags = _pair_flags(50, 0.5)
    assert any("blowout-heavy" in f for f in flags)
    assert "50%" in next(f for f in flags if "blowout-heavy" in f)
    assert not any("tiny-sample" in f for f in flags)
    assert any("estimated-minutes" in f for f in flags)

def test_fallback_name_all_surnames():
    surnames = {1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta",
                5: "Epsilon"}
    assert _fallback_name(A1, surnames) == (
        "Alpha, Beta, Gamma, Delta, Epsilon")

def test_fallback_name_partial_surnames():
    assert _fallback_name(A1, {1: "Alpha"}) == (
        "unit " + str(A1[0])[:6] + "…")
    assert _fallback_name(A1, None) == "unit " + str(A1[0])[:6] + "…"

def test_truncate_note_literal():
    assert _truncate_note(174, 25) == (
        "showing 25 of 174 pairs (top by estimated minutes)")

def test_tool_rejects_same_team():
    res = get_lineup_matchup_matrix.invoke({"team_a": "BOS", "team_b": "BOS"})
    assert res["ok"] is False
    assert "error" in res

def test_tool_rejects_unknown_team():
    res = get_lineup_matchup_matrix.invoke(
        {"team_a": "Not A Real Team XYZ", "team_b": "BOS"})
    assert res["ok"] is False
    assert "error" in res

def test_tool_end_to_end_warehouse_structural():
    try:
        res = get_lineup_matchup_matrix.invoke(
            {"team_a": "BOS", "team_b": "NYK"})
    except Exception as exc:
        pytest.skip(f"warehouse unavailable: {exc}")
    assert res["tool"] == "get_lineup_matchup_matrix"
    assert res["ok"] is True
    for key in ("season", "team_a", "team_b"):
        assert key in res["meta"]
    rows = res["rows"]
    if not rows:
        assert res["meta"].get("data_note", "").startswith("no play-level")
        return
    want_keys = {"team_a_lineup", "team_a_ids", "team_b_lineup",
                 "team_b_ids", "poss", "est_minutes", "off_poss_a",
                 "off_poss_b", "pts_a", "pts_b", "OFF_RATING_A",
                 "DEF_RATING_A", "NET_RATING_A", "blowout_share", "flags"}
    est = [r["est_minutes"] for r in rows]
    assert est == sorted(est, reverse=True)
    for r in rows:
        assert want_keys <= set(r)
        assert len(r["team_a_ids"]) == 5
        assert all(isinstance(i, int) for i in r["team_a_ids"])
        assert len(r["team_b_ids"]) == 5
        assert all(isinstance(i, int) for i in r["team_b_ids"])
        assert r["est_minutes"] >= 0
        assert r["NET_RATING_A"] == round(
            r["OFF_RATING_A"] - r["DEF_RATING_A"], 1)
        assert any(f.startswith("estimated-minutes") for f in r["flags"])
    for key in ("team_a_lineups", "team_b_lineups", "pairs",
                "matchup_games", "minutes_note", "qualification_note",
                "blowout_rule", "small_sample_floor",
                "truncation_note", "rows_returned"):
        assert key in res["meta"]
    assert res["meta"]["truncation_note"].startswith("showing ")
    assert res["meta"]["rows_returned"] == len(rows)
    for r in rows:
        assert r["team_a_lineup"] != (
            "unit " + "-".join(str(i) for i in r["team_a_ids"]))
        assert r["team_b_lineup"] != (
            "unit " + "-".join(str(i) for i in r["team_b_ids"]))
