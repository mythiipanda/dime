"""Analyst skills. Progressive disclosure: catalog carries one line per
skill, full bodies load on demand via load_skill."""

from pathlib import Path

_DIR = Path(__file__).resolve().parent / "skills"
_cache: str | None = None
_bodies: dict[str, str] | None = None


def _split(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                desc = ""
                for meta in lines[1:i]:
                    if ":" in meta:
                        key, val = meta.split(":", 1)
                        if key.strip().lower() == "description":
                            desc = val.strip()
                if len(desc) > 150:
                    desc = desc[:147] + "..."
                return desc, "\n".join(lines[i + 1 :]).strip()
    return "", text.strip()


def _load() -> tuple[str, dict[str, str]]:
    lines = []
    bodies = {}
    for f in sorted(_DIR.glob("*.md")):
        desc, body = _split(f.read_text().strip())
        lines.append(f"- {f.stem}: {desc}")
        bodies[f.stem] = body
    return "\n".join(lines), bodies


def catalog() -> str:
    global _cache, _bodies
    if _cache is None or _bodies is None:
        _cache, _bodies = _load()
    return _cache


def load_skill(name: str) -> str:
    global _cache, _bodies
    if _cache is None or _bodies is None:
        _cache, _bodies = _load()
    assert _bodies is not None
    return _bodies.get(name, "")
