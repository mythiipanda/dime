import json
import re
from pathlib import Path


def test_visual_artifacts_skill_has_verified_bar_and_line_examples():
    text = Path("backend/analyst/skills/visual-artifacts/SKILL.md").read_text()
    for kind in ("line", "bar"):
        match = re.search(r'```json\n(\{[^`]*?"kind": "%s"[^`]*?\})\n```' % kind, text, re.DOTALL)
        assert match, f"missing {kind} example"
        spec = json.loads(match.group(1))
        assert spec["kind"] == kind
        for series in spec["series"]:
            assert len(series["values"]) == len(spec["xLabels"])
    assert "coexist" in text
    assert "chart` does not satisfy" in text
