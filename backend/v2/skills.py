"""Agent Skills discovery and progressive disclosure."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    directory: Path
    content_hash: str

    def activated_context(self) -> dict[str, Any]:
        resources = sorted(
            str(path.relative_to(self.directory))
            for folder in ("references", "scripts", "assets")
            if (root := self.directory / folder).is_dir()
            for path in root.rglob("*")
            if path.is_file()
        )
        return {
            "name": self.name,
            "instructions": self.body,
            "content_hash": self.content_hash,
            "resources": resources,
        }


class SkillLibrary:
    """Discover standard `<skill>/SKILL.md` packages under one root."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path(__file__).with_name("skills")

    @cached_property
    def skills(self) -> dict[str, Skill]:
        if not self.root.exists():
            return {}
        loaded: dict[str, Skill] = {}
        for path in sorted(self.root.glob("*/SKILL.md")):
            skill = _read_skill(path)
            if path.parent.name != skill.name:
                raise ValueError(
                    f"{path}: skill name must match directory {path.parent.name!r}"
                )
            if skill.name in loaded:
                raise ValueError(f"duplicate skill name {skill.name!r}")
            loaded[skill.name] = skill
        return loaded

    def catalog(self) -> list[dict[str, str]]:
        return [
            {"name": skill.name, "description": skill.description}
            for skill in self.skills.values()
        ]

    def activate(self, names: list[str]) -> list[dict[str, Any]]:
        unknown = sorted(set(names) - self.skills.keys())
        if unknown:
            raise ValueError(f"unknown skills: {unknown}")
        return [
            self.skills[name].activated_context()
            for name in dict.fromkeys(names)
        ]


def skill_hashes(activated: list[dict[str, Any]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for skill in activated:
        if set(skill) != {"name", "instructions", "content_hash", "resources"}:
            raise ValueError("activated skill has unexpected fields")
        name = skill["name"]
        content_hash = skill["content_hash"]
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("activated skill has invalid name")
        if (not isinstance(content_hash, str) or len(content_hash) != 64
                or any(char not in "0123456789abcdef" for char in content_hash)):
            raise ValueError("activated skill has invalid content hash")
        if name in hashes:
            raise ValueError("activated skill names must be unique")
        hashes[name] = content_hash
    return hashes


def _read_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: SKILL.md must start with YAML frontmatter")
    try:
        raw_frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(f"{path}: SKILL.md frontmatter is not closed") from exc
    metadata = yaml.safe_load(raw_frontmatter)
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not _NAME.fullmatch(name) or len(name) > 64:
        raise ValueError(f"{path}: invalid skill name")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ValueError(f"{path}: invalid skill description")
    body = body.strip()
    if not body:
        raise ValueError(f"{path}: skill instructions are required")
    return Skill(
        name=name,
        description=description.strip(),
        body=body,
        directory=path.parent,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )
