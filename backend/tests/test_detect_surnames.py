"""Surname-only player references must be detected when unambiguous.

2026-09-13 probe: "Is a Brunson for Wembanyama trade legal?" detected no
players, the deterministic legality pin never fired, and the planner
answered trade VALUE instead of legality. Active-pool unique surnames,
capitalized in the question, now resolve.
"""

from app.graph import _detect_entities


def test_unique_surnames_detected():
    found_p, _ = _detect_entities("Is a Brunson for Wembanyama trade legal?")
    assert "Jalen Brunson" in found_p
    assert "Victor Wembanyama" in found_p


def test_lowercase_common_word_not_a_player():
    found_p, _ = _detect_entities("is love in the air tonight?")
    assert found_p == []


def test_shared_surname_stays_ambiguous():
    found_p, _ = _detect_entities("Who wins: Brown or Brown?")
    assert found_p == []


def test_full_name_matching_unchanged():
    found_p, _ = _detect_entities("How did Luka Doncic do last night?")
    assert found_p == ["Luka Dončić"]


def test_first_name_position_does_not_detect_other_player():
    # "Cooper Flagg" must not pull in Sharife Cooper via surname Cooper.
    found_p, _ = _detect_entities("How good has Cooper Flagg been this season?")
    assert found_p == ["Cooper Flagg"]


def test_possessive_surname_detected():
    found_p, _ = _detect_entities("Wembanyama's blocks this season?")
    assert found_p == ["Victor Wembanyama"]


def test_hyphenated_surname_fragment_not_detected():
    # The "Alexander" in "Gilgeous-Alexander" is not a mention of Trey
    # Alexander - it added a phantom second player to carry scans and
    # flaked the F67 T3 playoff pin (battery run8/run12, 2026-09-13).
    from app.graph import _detect_carry_players, _detect_entities
    txt = "Shai Gilgeous-Alexander led the Thunder in scoring."
    assert _detect_entities(txt)[0] == ["Shai Gilgeous-Alexander"]
    assert _detect_carry_players(txt) == ["Shai Gilgeous-Alexander"]
    # A standalone surname mention still resolves.
    assert "Trey Alexander" in _detect_entities(
        "Would an Alexander for Brunson trade work?")[0]
