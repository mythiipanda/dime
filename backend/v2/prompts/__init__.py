"""External Markdown prompts for the v2 runtime.

One cached loader over plain files: no template dependency, no registry.
Prompts are static text; callers pass structured input alongside them.
"""

from functools import lru_cache
from pathlib import Path
import re

_PROMPTS_DIR = Path(__file__).parent
_PROMPT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Return the verbatim text of prompts/<name>.md."""
    if not isinstance(name, str) or not _PROMPT_NAME.fullmatch(name):
        raise ValueError("prompt name must use lowercase letters, numbers, and underscores")
    path = _PROMPTS_DIR / f"{name}.md"
    if _PROMPTS_DIR.is_symlink() or any(
        component.is_symlink() for component in _PROMPTS_DIR.parents
    ):
        raise ValueError("prompt directory cannot be a symlink")
    if path.is_symlink():
        raise ValueError("prompt file cannot be a symlink")
    return path.read_text(encoding="utf-8")
