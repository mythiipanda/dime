from pathlib import Path


def test_inline_json_spec_section_present():
    text = Path("backend/analyst/skills/visual-artifacts/SKILL.md").read_text()
    assert '"kind": "line"' in text
    assert "Inline JSON specs" in text
    assert "do not satisfy a spec-shaped ask" in text


def test_frontmatter_single_description():
    text = Path("backend/analyst/skills/visual-artifacts/SKILL.md").read_text()
    head = text.split("---")[1]
    assert head.count("description:") == 1
