"""Team-name resolution regression tests.

'Celtics', 'BOS', and 'Boston Celtics' must resolve to the SAME team
entity end to end: _detect_entities, _direct_named_teams, and _team_row.
Abbreviation matching stays case-sensitive (F68/F69): lowercase 'bos'
/ 'was' must not resolve. Deterministic and hermetic: static tables
only, no warehouse, no LLM, no network.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import (  # noqa: E402
    _detect_entities,
    _direct_named_teams,
    _team_row,
)

QUESTIONS = [
    "What is the Celtics record?",
    "What is the BOS record?",
    "What is the Boston Celtics record?",
]

FULL_ROWS = [
    {"team": "Boston Celtics", "net": 2.4},
    {"team": "Detroit Pistons", "net": 0.0},
]

ABBR_ROWS = [
    {"team": "Boston Celtics", "abbreviation": "BOS", "net": 2.4},
    {"team": "Detroit Pistons", "abbreviation": "DET", "net": 0.0},
]


def test_detect_entities_unified():
    seen = [_detect_entities(q)[1] for q in QUESTIONS]
    assert seen[0] == ["Boston Celtics"]
    assert seen[1] == seen[0]
    assert seen[2] == seen[0]


def test_direct_named_teams_unified():
    seen = [_direct_named_teams(q, _detect_entities(q)[1])
            for q in QUESTIONS]
    assert seen[0] == ["Boston Celtics"]
    assert seen[1] == seen[0]
    assert seen[2] == seen[0]


def test_team_row_unified_full_name_rows():
    bound = [_team_row(FULL_ROWS, t)
             for t in ("Celtics", "BOS", "Boston Celtics")]
    assert bound[0] is FULL_ROWS[0]
    assert bound[1] is FULL_ROWS[0]
    assert bound[2] is FULL_ROWS[0]


def test_team_row_unified_abbr_rows():
    bound = [_team_row(ABBR_ROWS, t)
             for t in ("Celtics", "BOS", "Boston Celtics")]
    assert all(b is ABBR_ROWS[0] for b in bound)


def test_abbreviation_guard_stays_case_sensitive():
    # F68/F69: lowercase must never read as an abbreviation.
    assert "Boston Celtics" not in _detect_entities(
        "What is the bos record?")[1]
    assert _team_row(ABBR_ROWS, "bos") is None
    assert _team_row(ABBR_ROWS, "was") is None
