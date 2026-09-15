from pathlib import Path

import pytest

from v2.skills import SkillLibrary, skill_hashes


def test_builtin_catalog_is_agent_skills_metadata_only():
    library = SkillLibrary()
    catalog = library.catalog()
    assert {item["name"] for item in catalog} == {
        "trade-analysis", "injury-impact", "player-comparison"
    }
    assert all(set(item) == {"name", "description"} for item in catalog)
    assert all("# " not in item["description"] for item in catalog)


def test_activation_progressively_discloses_selected_skill_and_hash():
    activated = SkillLibrary().activate(["trade-analysis"])
    assert len(activated) == 1
    assert "trade-legality gap" not in activated[0]["instructions"]
    assert "legality gap" in activated[0]["instructions"]
    assert skill_hashes(activated) == {
        "trade-analysis": activated[0]["content_hash"]
    }


def test_activation_preserves_order_and_deduplicates():
    names = [item["name"] for item in SkillLibrary().activate([
        "player-comparison", "trade-analysis", "player-comparison"
    ])]
    assert names == ["player-comparison", "trade-analysis"]


def test_unknown_skill_fails_closed():
    with pytest.raises(ValueError, match="unknown skills"):
        SkillLibrary().activate(["made-up"])


def test_invalid_agent_skill_package_fails_closed(tmp_path: Path):
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / "SKILL.md").write_text("# no frontmatter", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML frontmatter"):
        SkillLibrary(tmp_path).catalog()
