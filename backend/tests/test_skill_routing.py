"""Skill routing: progressive disclosure for the planner prompt.

The planner prompt always carries the one-line descriptions catalog and
appends full skill bodies only for skills matched deterministically from
the question text (keyword table in app/graph.py, capped at 2 per turn).

All hermetic: match_skills and build_planner_prompt read local files
only. No LLM, no network, no stubs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph  # noqa: E402
from app.graph import build_planner_prompt, match_skills  # noqa: E402
from app.skills import catalog, load_skill  # noqa: E402


def test_compare_players_fires():
    assert match_skills(
        "Compare Victor Wembanyama and Cooper Flagg, who is better?"
    ) == ["compare_players"]


def test_form_check_fires():
    assert match_skills(
        "Is Jayson Tatum in a slump over his last 10 games?"
    ) == ["form_check"]


def test_game_preview_fires():
    assert match_skills(
        "Preview the Lakers matchup tonight, who ya got?"
    ) == ["game_preview"]


def test_impact_check_fires_on_lebron_raptor_arc():
    assert match_skills(
        "What is LeBron James's RAPTOR history and career arc?"
    ) == ["impact_check"]


def test_lineup_wowy_fires():
    assert match_skills(
        "Which lineup plays well together for Boston by plus-minus?"
    ) == ["lineup_wowy"]


def test_morning_briefing_fires():
    assert match_skills(
        "Give me a briefing on last night's standouts"
    ) == ["morning_briefing"]


def test_shot_profile_fires():
    assert match_skills(
        "Show me his shot chart and zone efficiency"
    ) == ["shot_profile"]


def test_standings_read_fires():
    assert match_skills(
        "Who clinches the top seed in the standings?"
    ) == ["standings_read"]


def test_leaders_read_fires():
    assert match_skills(
        "Who leads the league in scoring, who wins the scoring title?"
    ) == ["leaders_read"]


def test_record_when_plays_fires():
    assert match_skills(
        "What is Boston's record when Jayson Tatum plays?"
    ) == ["record_when_plays"]


def test_record_when_plays_fires_on_sits_phrasing():
    assert "record_when_plays" in match_skills(
        "How do the Lakers do when LeBron sits?"
    )


def test_historical_leaders_fires_on_each_season():
    assert match_skills(
        "Who led each season in scoring since 2015?"
    ) == ["historical_leaders"]


def test_historical_leaders_fires_on_all_time_single_season():
    assert "historical_leaders" in match_skills(
        "Rank the all-time best single-season scoring leaders"
    )


def test_no_match_on_unrelated_questions():
    assert match_skills("How tall is Victor Wembanyama?") == []
    assert match_skills("Who coaches the Spurs?") == []
    assert match_skills("When was the NBA founded?") == []


def test_match_is_case_insensitive():
    assert match_skills("What is LEBRON's RAPTOR IMPACT?") == ["impact_check"]
    assert "historical_leaders" in match_skills(
        "ALL-TIME scoring leaders by decade")


def test_cap_respected_in_table_order():
    q = ("Compare LeBron and MJ, who is better? Preview their matchup "
         "tonight, plus a briefing recap of last night's standouts and "
         "the scoring title race.")
    assert len(match_skills(q, limit=99)) > 2
    assert match_skills(q) == ["compare_players", "game_preview"]
    assert match_skills(q, limit=1) == ["compare_players"]


def test_prompt_always_includes_descriptions():
    prompt = build_planner_prompt("How tall is Victor Wembanyama?")
    for line in catalog().strip().splitlines():
        assert line in prompt


def test_prompt_appends_full_body_only_for_matches():
    prompt = build_planner_prompt("Who leads the league in scoring?")
    assert "never multiply a per-game average" in prompt.lower()
    assert "rows.record over ALL matches" not in prompt
    assert "Never compare without both id sets" not in prompt


def test_prompt_with_no_match_carries_no_bodies():
    prompt = build_planner_prompt("How tall is Victor Wembanyama?")
    assert "Pitfalls" not in catalog()
    assert "Pitfalls" not in prompt
    for name in ("compare_players", "leaders_read", "record_when_plays",
                 "historical_leaders", "impact_check"):
        assert load_skill(name) not in prompt


def test_prompt_appends_historical_body():
    prompt = build_planner_prompt(
        "Who led each season in scoring since 2015?")
    assert "2015 to 2025" in prompt
