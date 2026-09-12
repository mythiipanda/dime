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
