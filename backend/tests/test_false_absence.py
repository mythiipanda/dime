"""F65: false absence claims. A sentence claiming an entity's data is
missing/unavailable while that entity sits in this turn's payloads is
an evidence-window artifact - drop the sentence, keep the rest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _strip_false_absence  # noqa: E402

PAYLOAD = [{"tool": "get_standings", "ok": True, "rows": [
    {"team": "Miami Heat", "WINS": 43, "LOSSES": 39},
    {"team": "Denver Nuggets", "WINS": 54, "LOSSES": 28}]}]


def test_false_absence_dropped():
    text = ("Nuggets won 54 games and Spurs won 62. "
            "Heat win total is missing from the standings.")
    out = _strip_false_absence(text, PAYLOAD)
    assert "missing" not in out
    assert "54 games" in out


def test_true_absence_kept():
    text = "Per-game data for the Wizards is unavailable."
    assert _strip_false_absence(text, PAYLOAD) == text


def test_no_payloads_is_noop():
    text = "Heat win total is missing."
    assert _strip_false_absence(text, []) == text


def test_scrub_based_on_available_league_data():
    from app.graph import _scrub_final_text
    out = _scrub_final_text(
        "Based on the available league data, the highest score is 144.")
    assert out == "The highest score is 144."
    out2 = _scrub_final_text("He leads. Based on league data, X is next.")
    assert out2 == "He leads. X is next."


def test_newlines_preserved():
    # QA F65: the sweep used to rejoin every segment with spaces,
    # flattening markdown tables/headings/lists into one line so the UI
    # rendered the source literally ("| Metric | ...", "###", "* *").
    text = ("Here is the comparison:\n\n"
            "| Metric | Luka | SGA |\n|---|---|---|\n"
            "| PPG | 33.5 | 31.1 |\n\n"
            "**Verdict**\n* **Scoring:** Luka leads.\n"
            "* **Efficiency:** SGA leads.")
    assert _strip_false_absence(text, PAYLOAD) == text


def test_drop_keeps_line_structure():
    text = ("Nuggets won 54 games.\n"
            "Heat win total is missing from the standings.\n"
            "Spurs won 62.")
    out = _strip_false_absence(text, PAYLOAD)
    assert "missing" not in out
    assert out == "Nuggets won 54 games.\n\nSpurs won 62."


def test_standings_best_record_ledger_fact():
    # QA F67: "best record" -> "their best player" chain dead-ended
    # because the ledger carried nothing from get_standings.
    from app.graph import _extract_ledger_facts
    rows = [{"team": "Oklahoma City Thunder", "abbrev": "OKC",
             "WINS": 64, "LOSSES": 18, "Record": "64-18",
             "LeagueRank": 1.0},
            {"team": "Denver Nuggets", "abbrev": "DEN",
             "WINS": 54, "LOSSES": 28, "Record": "54-28",
             "LeagueRank": 2.0}]
    facts = _extract_ledger_facts(
        {"tool_results": [{"tool": "get_standings", "ok": True,
                           "rows": rows}]})
    assert facts == ["Best record: Oklahoma City Thunder (64-18) [OKC]"]


def test_tool_output_prefix_stripped_before_tool_sentence_drop():
    # "Based on the Get Standings output, ..." must lose the prefix
    # BEFORE the tools/errors sentence-drop, not lose the sentence.
    from app.graph import _scrub_final_text
    out = _scrub_final_text(
        "Based on the Get Standings output, the Oklahoma City Thunder "
        "had the best record with 64 wins.")
    assert out == ("The Oklahoma City Thunder had the best record "
                   "with 64 wins.")
    out2 = _scrub_final_text(
        "Based on the get_standings tool output, OKC won 64.")
    assert out2 == "OKC won 64."
