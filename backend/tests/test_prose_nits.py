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
