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


def test_dataset_data_collision_collapsed():
    out = _present("compare efficiency?",
                   "**the dataset data shows:**\nShai leads.", [])
    assert "dataset data" not in out
    assert "Shai leads." in out


def test_refusal_never_contradicts_attached_evidence():
    # f62 (2026-09-13 prod QA): thin analysis + rich tool rows must not
    # ship "I could not find that in the dataset."
    trs = [{"tool": "get_playoff_intel",
            "rows": [{"PLAYER": "Jalen Brunson", "GAME_DATE": "2026-06-13",
                      "PTS": 45, "MIN": 41}]}]
    out = _present("How did Brunson do in Game 5 of the Finals?",
                   "This data covers the 2025-26 season.", trs)
    assert "could not find" not in out.lower()
    assert "evidence panel" in out


def test_refusal_still_fires_with_empty_evidence():
    out = _present("what is the airspeed of a swallow?",
                   "This data covers the 2025-26 season.", [])
    assert "could not find that in the dataset" in out


def test_empty_backtick_citation_line_dropped():
    out = _present("best rookies?",
                   "This data covers the 2025-26 season.\n"
                   "Analysis based on ``.\n"
                   "**Takeaways**\n1. Cooper Flagg leads scoring.", [])
    assert "Analysis based on" not in out
    assert "Cooper Flagg leads scoring." in out


def test_output_subject_sentences_dropped():
    from app.graph import _scrub_final_text
    txt = ("Nikola Jokić led with 10.7 assists per game. "
           "The output confirms he holds the top rank.")
    out = _scrub_final_text(txt)
    assert "output" not in out.lower()
    assert "10.7 assists" in out


def test_estimate_output_rewrite_keeps_fact():
    from app.graph import _scrub_final_text
    txt = "The statistical estimate output reports a net rating lift of 0.16 per 100 possessions."
    out = _scrub_final_text(txt)
    assert "output" not in out.lower()
    assert "estimate reports a net rating lift of 0.16" in out


def test_renumber_lists_after_strip():
    from app.graph import _renumber_lists
    txt = "Takeaways\n2. The estimate values his impact.\n3. He recorded 5026 possessions."
    out = _renumber_lists(txt)
    assert "\n1. The estimate values" in out
    assert "\n2. He recorded 5026" in out
    # Separate blocks restart at 1.
    txt2 = "1. a\n2. b\n\nSome prose.\n5. c\n7. d"
    out2 = _renumber_lists(txt2)
    assert out2 == "1. a\n2. b\n\nSome prose.\n1. c\n2. d"
    # Non-list text untouched.
    assert _renumber_lists("No lists here.") == "No lists here."


def test_space_before_punctuation_collapsed():
    from app.graph import _scrub_final_text
    out = _scrub_final_text("He averaged 10.7 assists per game . Next line , too .")
    assert "game." in out
    assert "line, too." in out
    # Decimals survive.
    assert "0.665" in _scrub_final_text("He shot 0.665 from the line .")


def test_empty_section_headers_dropped():
    from app.graph import _scrub_final_text
    txt = ("This data covers the 2025-26 season.\n\n**Takeaways:**\n\n"
           "**Verdict:**\nThe evidence does not show a rate split.")
    out = _scrub_final_text(txt)
    assert "**Takeaways" not in out
    # A Verdict header followed by real prose survives.
    assert "**Verdict:**" in out
    assert "rate split" in out
    # A Takeaways section with items survives.
    txt2 = "Intro.\n\n**Takeaways**\n1. First point.\n\n**Verdict**\nDone."
    out2 = _scrub_final_text(txt2)
    assert "**Takeaways**" in out2 and "1. First point." in out2


def test_first_person_tool_narration_dropped():
    from app.graph import _scrub_final_text
    txt = ("I used the provided game logs and summary to show the "
           "Finals matchups against SAS. Brunson scored 45 in Game 5.")
    out = _scrub_final_text(txt)
    assert "I used" not in out
    assert "45 in Game 5" in out


def test_leaders_output_rewritten():
    from app.graph import _scrub_final_text
    out = _scrub_final_text("The league leaders output lists totals.")
    assert "output" not in out.lower()
    assert "league leaders table" in out


def test_any_empty_bold_header_dropped():
    from app.graph import _scrub_final_text
    txt = "Intro line.\n\n**Finals Game Log**\n\n**Takeaways**\n1. A point."
    out = _scrub_final_text(txt)
    assert "Finals Game Log" not in out
    assert "1. A point." in out


def test_duplicated_list_word_collapsed():
    from app.graph import _scrub_final_text
    out = _scrub_final_text("Ranked on points, efficiency, and efficiency.")
    assert "and efficiency." in out
    assert "efficiency, and efficiency" not in out
