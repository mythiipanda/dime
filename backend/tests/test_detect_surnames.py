
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
    found_p, _ = _detect_entities("How good has Cooper Flagg been this season?")
    assert found_p == ["Cooper Flagg"]


def test_possessive_surname_detected():
    found_p, _ = _detect_entities("Wembanyama's blocks this season?")
    assert found_p == ["Victor Wembanyama"]


def test_hyphenated_surname_fragment_not_detected():
    from app.graph import _detect_carry_players, _detect_entities
    txt = "Shai Gilgeous-Alexander led the Thunder in scoring."
    assert _detect_entities(txt)[0] == ["Shai Gilgeous-Alexander"]
    assert _detect_carry_players(txt) == ["Shai Gilgeous-Alexander"]
    assert "Trey Alexander" in _detect_entities(
        "Would an Alexander for Brunson trade work?")[0]
