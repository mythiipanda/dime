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


@pytest.mark.parametrize("frontmatter,error", [
    ("name: example\ndescription: Example\ninstructions: hidden",
     "unknown frontmatter fields"),
    ("name: example", "requires name and description"),
])
def test_skill_frontmatter_contract_is_closed(tmp_path: Path, frontmatter, error):
    package = tmp_path / "example"
    package.mkdir()
    (package / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\nInstructions", encoding="utf-8",
    )
    with pytest.raises(ValueError, match=error):
        SkillLibrary(tmp_path).catalog()


def test_skill_hashes_rejects_malformed_activated_context():
    valid = SkillLibrary().activate(["trade-analysis"])[0]
    for changed, error in [
        ({**valid, "content_hash": "bad"}, "content hash"),
        ({**valid, "name": "Bad Name"}, "invalid name"),
        ({**valid, "extra": True}, "unexpected fields"),
    ]:
        with pytest.raises(ValueError, match=error):
            skill_hashes([changed])
    with pytest.raises(ValueError, match="names must be unique"):
        skill_hashes([valid, valid])


def test_activation_rejects_symlinked_resources(tmp_path: Path):
    package = tmp_path / "example"
    references = package / "references"
    references.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    (references / "private.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="cannot be symlinks"):
        SkillLibrary(tmp_path).activate(["example"])


def test_catalog_rejects_symlinked_skill_definition(tmp_path: Path):
    package = tmp_path / "example"
    package.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    (package / "SKILL.md").symlink_to(outside)
    with pytest.raises(ValueError, match="SKILL.md cannot be a symlink"):
        SkillLibrary(tmp_path).catalog()


def test_activation_hash_covers_resource_contents(tmp_path: Path):
    package = tmp_path / "example"
    references = package / "references"
    references.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    resource = references / "guide.md"
    resource.write_text("first", encoding="utf-8")
    first = SkillLibrary(tmp_path).activate(["example"])[0]["content_hash"]
    resource.write_text("second", encoding="utf-8")
    second = SkillLibrary(tmp_path).activate(["example"])[0]["content_hash"]
    assert first != second


def test_library_rejects_symlinked_root(tmp_path: Path):
    outside = tmp_path / "outside"
    package = outside / "example"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    root = tmp_path / "skills"
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="root cannot contain symlinks"):
        SkillLibrary(root).catalog()


def test_activation_rejects_resource_directory_symlink(tmp_path: Path):
    package = tmp_path / "example"
    package.mkdir()
    (package / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "guide.md").write_text("private", encoding="utf-8")
    (package / "references").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="cannot be symlinks"):
        SkillLibrary(tmp_path).activate(["example"])


def test_library_rejects_symlinked_root_ancestor(tmp_path: Path):
    outside = tmp_path / "outside"
    root = outside / "skills"
    package = root / "example"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="root cannot contain symlinks"):
        SkillLibrary(linked_parent / "skills").catalog()


def test_catalog_rejects_symlinked_skill_package(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    root = tmp_path / "skills"
    root.mkdir()
    (root / "example").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="package cannot contain symlinks"):
        SkillLibrary(root).catalog()


def test_skill_instructions_have_a_hard_size_limit(tmp_path: Path):
    package = tmp_path / "example"
    package.mkdir()
    (package / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example\n---\n" + "x" * 120_001,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="instructions are too large"):
        SkillLibrary(tmp_path).catalog()


def test_activation_rejects_oversized_resource_bundle(tmp_path: Path):
    package = tmp_path / "example"
    assets = package / "assets"
    assets.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nInstructions",
        encoding="utf-8",
    )
    (assets / "large.bin").write_bytes(b"x" * 5_000_001)

    with pytest.raises(ValueError, match="resources cannot exceed"):
        SkillLibrary(tmp_path).activate(["example"])
