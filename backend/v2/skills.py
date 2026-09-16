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
        _reject_symlinked_path(self.directory, "skill package")
        resources: list[str] = []
        for folder in ("references", "scripts", "assets"):
            root = self.directory / folder
            if root.is_symlink():
                raise ValueError(f"{root}: skill resources cannot be symlinks")
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.is_symlink():
                    raise ValueError(f"{path}: skill resources cannot be symlinks")
                if not path.is_file():
                    continue
                try:
                    path.resolve().relative_to(self.directory.resolve())
                except ValueError as exc:
                    raise ValueError(
                        f"{path}: skill resource escapes its package") from exc
                resources.append(str(path.relative_to(self.directory)))
        resources.sort()
        if len(resources) > 256:
            raise ValueError("skill package cannot contain more than 256 resources")
        digest = hashlib.sha256()
        digest.update((self.directory / "SKILL.md").read_bytes())
        for resource in resources:
            digest.update(resource.encode())
            digest.update((self.directory / resource).read_bytes())
        return {
            "name": self.name,
            "instructions": self.body,
            "content_hash": digest.hexdigest(),
            "resources": resources,
        }


class SkillLibrary:
    """Discover standard `<skill>/SKILL.md` packages under one root."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path(__file__).with_name("skills")

    @cached_property
    def skills(self) -> dict[str, Skill]:
        _reject_symlinked_path(self.root, "skill library root")
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


def _reject_symlinked_path(path: Path, label: str) -> None:
    if any(component.is_symlink() for component in (path, *path.parents)):
        raise ValueError(f"{label} cannot contain symlinks")


def _read_skill(path: Path) -> Skill:
    _reject_symlinked_path(path.parent, "skill package")
    if path.is_symlink():
        raise ValueError(f"{path}: SKILL.md cannot be a symlink")
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
    unknown = sorted(set(metadata) - {"name", "description"})
    if unknown:
        raise ValueError(f"{path}: unknown frontmatter fields: {unknown}")
    if set(metadata) != {"name", "description"}:
        raise ValueError(f"{path}: frontmatter requires name and description")
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not _NAME.fullmatch(name) or len(name) > 64:
        raise ValueError(f"{path}: invalid skill name")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ValueError(f"{path}: invalid skill description")
    body = body.strip()
    if not body:
        raise ValueError(f"{path}: skill instructions are required")
    if len(body) > 120_000:
        raise ValueError(f"{path}: skill instructions are too large")
    return Skill(
        name=name,
        description=description.strip(),
        body=body,
        directory=path.parent,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )
