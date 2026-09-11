"""Skills catalog: progressive disclosure. Catalog lists one line per skill,
full bodies load on demand."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.skills import catalog, load_skill

SKILLS_DIR = Path(__file__).resolve().parent.parent / "app" / "skills"

EXPECTED = sorted(
    [
        "compare_players",
        "form_check",
        "game_preview",
        "historical_leaders",
        "impact_check",
        "leaders_read",
        "lineup_wowy",
        "morning_briefing",
        "record_when_plays",
        "shot_profile",
        "standings_read",
    ]
)


def test_catalog_lists_all_skills_one_line_each():
    lines = catalog().strip().splitlines()
    assert len(lines) == len(EXPECTED)
    for name, line in zip(EXPECTED, lines):
        assert line.startswith(f"- {name}: ")
        desc = line.split(": ", 1)[1]
        assert desc
        assert len(desc) <= 150


def test_catalog_carries_descriptions_only():
    text = catalog()
    assert "Never compare without both id sets" not in text
    assert "rows.record over ALL matches" not in text
    assert " resolve_entity for each name" not in text


def test_load_skill_returns_full_bodies():
    for name in EXPECTED:
        body = load_skill(name)
        assert body
        assert "---" not in body.splitlines()[0]
        assert "name:" not in body.splitlines()[0]


def test_load_skill_bodies_match_files():
    assert "Never compare without both id sets" in load_skill("compare_players")
    assert "rows.record over ALL matches" in load_skill("record_when_plays")
    assert "never multiply a per-game average by gp" in load_skill("leaders_read").lower()
    assert "2015 to 2025" in load_skill("historical_leaders")


def test_load_skill_unknown_returns_empty():
    assert load_skill("no_such_skill") == ""


def test_frontmatter_valid_on_every_file():
    files = sorted(SKILLS_DIR.glob("*.md"))
    assert [f.stem for f in files] == EXPECTED
    for f in files:
        lines = f.read_text().strip().splitlines()
        assert lines[0].strip() == "---"
        close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        meta = {}
        for row in lines[1:close]:
            key, val = row.split(":", 1)
            meta[key.strip()] = val.strip()
        assert meta.get("name") == f.stem
        assert meta.get("description")
        assert len(meta["description"]) <= 150
        assert "\n".join(lines[close + 1 :]).strip()
