from pathlib import Path


def test_exactness_skill_teaches_writing_time_derivation_parity():
    text = Path("backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "Arithmetic you perform while writing counts as derivation" in text
    assert "its own artifact row or column" in text
