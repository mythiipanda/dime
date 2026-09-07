"""Analyst skills. Markdown playbooks loaded once and injected to prompts."""

from pathlib import Path

_DIR = Path(__file__).resolve().parent / "skills"
_cache: str | None = None


def catalog() -> str:
    global _cache
    if _cache is None:
        parts = []
        for f in sorted(_DIR.glob("*.md")):
            parts.append(f.read_text().strip())
        _cache = "\n\n".join(parts)
    return _cache
