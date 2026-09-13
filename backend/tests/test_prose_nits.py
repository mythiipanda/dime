"""Prose nit batch (QA overnight chain, Sep 12): math narration leaks,
abbreviation-in-prose, scrub collisions, strip-induced fragments."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _scrub_final_text  # noqa: E402


def test_dividing_sentence_keeps_value():
    out = _scrub_final_text(
        "Luka led the league with 2143 points over 64 games. "
        "Dividing 2143 by 64 gives 33.5 points per game.")
    assert "33.5 points per game" in out
    assert "ividing" not in out


def test_parenthetical_division_stripped():
    out = _scrub_final_text("Brunson averaged 26.8 (509 ÷ 19) "
                            "across the run.")
    assert "÷" not in out and "509 /" not in out
    assert "26.8" in out


def test_slash_equals_scratch_stripped():
    out = _scrub_final_text("He is at 130/5 = 26 PPG over the stretch.")
    assert "130/5" not in out and "= " not in out
    assert "26 PPG" in out


def test_record_dash_form():
    out = _scrub_final_text(
        "The Rockets hold a 48 and 30 record across 78 games.")
    assert "48-30 record" in out


def test_franchise_abbrev_expanded():
    out = _scrub_final_text(
        "Luka Dončić plays for the LAL franchise.")
    assert "Los Angeles Lakers franchise" in out
    assert "LAL" not in out


def test_provided_by_the_data_collision():
    out = _scrub_final_text(
        "Data provided by the data and split records shows the "
        "Knicks posted 53 wins.")
    assert "provided by the dataset" in out
    assert "provided by the data " not in out


def test_and_logs_fragment():
    out = _scrub_final_text(
        "This data covers the 2025-26 season. "
        "And playoff logs, Jalen Brunson was the best player.")
    assert "And playoff logs" not in out
    assert "From the playoff logs, Jalen Brunson" in out


# --- F61 residual: coverage line must match the evidence span ---

import asyncio  # noqa: E402

from app.graph import presentation_agent  # noqa: E402


def _present(question, analysis, tool_results):
    async def _go():
        state = {"question": question, "analysis": analysis,
                 "tool_results": tool_results, "calls_made": [],
                 "history": [], "primary": "p", "model": "m"}
        out = None
        async for e in presentation_agent(state):
            if e.get("type") == "final_answer":
                out = e["data"]["text"]
        return out

    return asyncio.run(_go())


def test_coverage_line_matches_multiseason_evidence():
    trs = [{"tool": "get_historical_leaders",
            "rows": [{"PLAYER": "A", "season": "2018-19", "PTS": 30},
                     {"PLAYER": "B", "season": "2022-23", "PTS": 29},
                     {"PLAYER": "C", "season": "2024-25", "PTS": 28}]}]
    out = _present("best scoring seasons since 2018?",
                   "This data covers the 2022-23 season. Player A "
                   "averaged 30 points per game, ahead of Player B at "
                   "29 and Player C at 28.", trs)
    assert "This data covers the 2018-19 through 2024-25 seasons." in out
    assert "covers the 2022-23 season" not in out


def test_single_season_evidence_line_untouched():
    trs = [{"tool": "get_historical_leaders",
            "rows": [{"PLAYER": "A", "season": "2022-23", "PTS": 30},
                     {"PLAYER": "B", "season": "2022-23", "PTS": 29}]}]
    out = _present("best scoring season in 2022-23?",
                   "This data covers the 2022-23 season. Player A "
                   "averaged 30 points per game, ahead of Player B at "
                   "29.", trs)
    assert "This data covers the 2022-23 season." in out


def test_source_line_naming_agent_or_dataset_dropped():
    # 2026-09-13 compose probe: "Source: league agent the dataset."
    # leaked an internal agent name after the scout-summary rewrite.
    out = _present("who won the title?",
                   "This data covers the 2025-26 season.\n"
                   "Source: league agent the dataset.\n"
                   "The New York Knicks won the championship.", [])
    assert "Source:" not in out
    assert "league agent" not in out
    assert "The New York Knicks won the championship." in out


def test_real_source_citation_survives():
    out = _present("who leads scoring?",
                   "Source: Basketball-Reference. Luka leads with "
                   "2143 points.", [])
    assert "Source: Basketball-Reference." in out


def test_dangling_and_the_dataset_vocative_stripped():
    # Same probe: "And the dataset, Shai ... played 15 playoff games."
    out = _present("how did shai do in the playoffs?",
                   "And the dataset, Shai Gilgeous-Alexander played 15 "
                   "playoff games.", [])
    assert "And the dataset," not in out
    assert "Shai Gilgeous-Alexander played 15 playoff games." in out


def test_dataset_parenthetical_dropped_from_headers():
    out = _present("compare them?",
                   "### Player Comparison (the dataset)\n"
                   "Luka averages 33.5 points per game.", [])
    assert "(the dataset)" not in out
    assert "### Player Comparison" in out
    assert "Luka averages 33.5 points per game." in out
