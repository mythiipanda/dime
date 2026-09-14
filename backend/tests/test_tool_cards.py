"""ToolCard registry tests. Pure registry checks, no warehouse reads."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import TOOL_NAMES
from app.tools.cards import build_cards, describe, rank_tools


def test_every_tool_has_card_with_purpose():
    cards = build_cards()
    by_name = {c["name"]: c for c in cards}
    assert set(by_name) == set(TOOL_NAMES)
    for name, card in by_name.items():
        assert set(card) == {"name", "family", "purpose", "triggers", "cost"}, name
        assert card["purpose"], name
        assert card["family"], name
        assert card["triggers"], name
        assert card["cost"] in ("cheap", "medium", "heavy"), name


def test_rank_is_deterministic():
    q = "Compare LeBron James and Kevin Durant side by side"
    assert rank_tools(q) == rank_tools(q)
    assert rank_tools(q, k=3) == rank_tools(q, k=3)


def test_compare_question_ranks_get_compare():
    q = "Compare LeBron James and Kevin Durant side by side this season"
    assert "get_compare" in rank_tools(q, k=3)


def test_wpa_question_ranks_get_wpa_leaders():
    q = "Who are the WPA leaders this season by win probability added"
    assert "get_wpa_leaders" in rank_tools(q, k=3)


def test_zone_question_ranks_zone_tools():
    q = ("How do player shot zone efficiency deltas compare to the league "
         "average, and which teams take the most corner threes")
    top5 = rank_tools(q, k=5)
    assert "get_team_shot_zones" in top5
    assert "get_zone_deltas" in top5


def test_leaders_question_ranks_get_leaders():
    q = "Who are the league scoring leaders in points per game"
    assert "get_leaders" in rank_tools(q, k=3)


def test_k_cap_respected():
    q = "Who are the league scoring leaders in points per game"
    assert len(rank_tools(q, k=3)) == 3
    assert len(rank_tools(q, k=1)) == 1
    assert len(rank_tools(q, k=200)) == len(TOOL_NAMES)


def test_gibberish_still_returns_k_names():
    out = rank_tools("qxkz wubwub zzz", k=8)
    assert len(out) == 8
    assert out == sorted(out)


def test_cost_rule():
    by_name = {c["name"]: c for c in build_cards()}
    assert by_name["get_playoff_sim"]["cost"] == "heavy"
    assert by_name["get_game_prediction"]["cost"] == "heavy"
    assert by_name["get_leaders"]["cost"] == "heavy"
    assert by_name["get_wpa_leaders"]["cost"] == "heavy"
    assert by_name["get_team_shot_zones"]["cost"] == "heavy"
    assert by_name["get_compare"]["cost"] == "cheap"
    assert by_name["resolve_entity"]["cost"] == "cheap"


def test_family_follows_desk():
    by_name = {c["name"]: c for c in build_cards()}
    assert by_name["get_award_race"]["family"] == "awards"
    assert by_name["get_leaders"]["family"] == "league"
    assert by_name["get_compare"]["family"] == "player"
    assert by_name["get_team_hub"]["family"] == "team"
    assert by_name["get_wpa_leaders"]["family"] == "wpa"
    assert by_name["get_team_shot_zones"]["family"] == "zone"
    assert by_name["get_matchup_preview"]["family"] == "preview"


def test_describe_format():
    line = describe(["get_compare"])
    assert line.startswith("- get_compare (player): ")
    assert "Side-by-side compare" in line
    assert describe(["no_such_tool"]) == ""
