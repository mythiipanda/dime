"""Fixture-driven tests for acceptance/grade.py.

Five cases cover the per-item rules: a clean pass, a wrong number,
a missing citation, a fabricated honest_gap, and a scope refusal.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import grade


def _row(final_text, citations=None, latency_ms=100.0, error=None):
    return {
        "id": "fixture-1",
        "final_text": final_text,
        "citations": citations if citations is not None else [],
        "latency_ms": latency_ms,
        "error": error,
    }


def test_exact_pass():
    item = {
        "id": "fixture-1",
        "category": "exact",
        "expect_numbers": ["25.3"],
        "must_contain": ["Curry"],
        "must_not_contain": [],
        "expect_refusal": False,
    }
    row = _row("Stephen Curry averaged 25.3 points per game in 2016-17.")
    passed, reasons, fabrication = grade.grade_item(item, row)
    assert passed is True
    assert reasons == []
    assert fabrication is False


def test_wrong_number():
    item = {
        "id": "fixture-1",
        "category": "exact",
        "expect_numbers": ["25.3"],
        "must_contain": ["Curry"],
        "must_not_contain": [],
        "expect_refusal": False,
    }
    row = _row("Stephen Curry averaged 24.1 points per game.")
    passed, reasons, fabrication = grade.grade_item(item, row)
    assert passed is False
    assert any("25.3" in reason for reason in reasons)
    assert fabrication is False


def test_missing_citation():
    item = {
        "id": "fixture-1",
        "category": "citation",
        "expect_numbers": ["78"],
        "must_contain": ["silver_player_season"],
        "must_not_contain": [],
        "expect_refusal": False,
    }
    row = _row(
        "Kevin Durant played 78 games in 2018-19 per silver_player_season.",
        citations=[],
    )
    passed, reasons, fabrication = grade.grade_item(item, row)
    assert passed is False
    assert any("citation" in reason.lower() for reason in reasons)


def test_fabricated_honest_gap():
    item = {
        "id": "fixture-1",
        "category": "honest_gap",
        "expect_numbers": [],
        "must_contain": [],
        "must_not_contain": ["29.7"],
        "expect_refusal": True,
    }
    row = _row(
        "LeBron James averaged 29.7 points per game in the 2009-10 season.",
    )
    passed, reasons, fabrication = grade.grade_item(item, row)
    assert passed is False
    assert fabrication is True
    assert any("29.7" in reason for reason in reasons)


def test_scope_refusal():
    item = {
        "id": "fixture-1",
        "category": "scope",
        "expect_numbers": [],
        "must_contain": [],
        "must_not_contain": [],
        "expect_refusal": True,
    }
    row = _row(
        "Sorry, I can't help with currency exchange rates; "
        "I can only answer questions about the NBA.",
    )
    passed, reasons, fabrication = grade.grade_item(item, row)
    assert passed is True
    assert reasons == []
    assert fabrication is False
