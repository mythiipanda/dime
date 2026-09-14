"""External Markdown prompts for the v2 runtime.

One cached loader over plain files: no template dependency, no registry.
Prompts are static text; callers pass structured input alongside them.
"""

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Return the verbatim text of prompts/<name>.md."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
