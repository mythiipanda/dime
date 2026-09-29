"""ToolCard retrieval registry. Progressive disclosure for tools, phase 1.

A ToolCard is one dict per registered tool with keys
name, family, purpose, triggers, cost. rank_tools scores a free-text
question against cards with case-insensitive token overlap and describe
renders cards as compact prompt lines.

Family rule. Family is the owning desk, read from the tool's underlying
function module (app.tools.<desk>), e.g. awards, league, player, team.
The bench scoring map is deliberately not imported here. Tools whose
StructuredTool wrapper carries no function module are pinned by name in
DESK_OVERRIDE from backend/app/tools/__init__.py imports. DESK_OVERRIDE
is also where a genuinely cross-desk tool gets pinned.

Cost rule. A tool is heavy when its name contains one of sim, predict,
leaders, or zones (Monte Carlo sims, prediction models, and league-wide
leaderboard or zone scans). Everything else is cheap. medium is reserved
in the type and currently unused.

Scoring rule. rank_tools counts case-insensitive token overlap between
the question and each card: name tokens count double, other trigger
tokens count single, and a family-token hit adds a bonus of 2. Name
words carry the question intent most often, so they weigh most. Ties
break alphabetically, which makes every ranking deterministic.
"""

import re

Card = dict

_TOKEN_RX = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for",
    "with", "by", "as", "vs", "per", "is", "are", "was", "were",
    "be", "been", "what", "which", "who", "whom", "whose", "how",
    "do", "does", "did", "me", "my", "you", "your", "it", "its",
    "this", "that", "these", "those", "than", "from", "at", "so",
    "such", "between", "into", "over", "s", "t", "have", "has",
    "their", "there",
})

_HEAVY_SUBSTRINGS = ("sim", "predict", "leaders", "zones")

DESK_OVERRIDE = {
    "get_compare": "player",
    "get_shot_compare": "player",
    "get_preview": "team",
    "get_scout_pack": "team",
    "get_rotation_check": "team",
    "get_injury_impact": "team",
    "get_matchup_preview": "preview",
    "text_to_sql": "league",
}


def _singular(tok: str) -> str:
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _tokens(text: str) -> set[str]:
    return {
        _singular(tok)
        for tok in _TOKEN_RX.findall((text or "").lower())
        if len(tok) > 1 and tok not in _STOPWORDS
    }


def _family_for(name: str, tool) -> str:
    if name in DESK_OVERRIDE:
        return DESK_OVERRIDE[name]
    mod = getattr(getattr(tool, "func", None), "__module__", None) or ""
    if mod.startswith("app.tools."):
        return mod.rsplit(".", 1)[-1]
    return "misc"


def _cost_for(name: str) -> str:
    lowered = name.lower()
    if any(part in lowered for part in _HEAVY_SUBSTRINGS):
        return "heavy"
    return "cheap"


def build_cards() -> list[dict]:
    from . import v1_tools

    cards = []
    for tool in v1_tools:
        description = (getattr(tool, "description", None) or "").strip()
        purpose = description.splitlines()[0].strip() if description else ""
        triggers = _tokens(description)
        triggers.update(t for t in _tokens(tool.name) if t != "get")
        cards.append({
            "name": tool.name,
            "family": _family_for(tool.name, tool),
            "purpose": purpose,
            "triggers": sorted(triggers),
            "cost": _cost_for(tool.name),
        })
    return cards


def _score(question_tokens: set[str], card: dict) -> int:
    name = _tokens(card["name"]) - {"get"}
    triggers = set(card["triggers"])
    family = _tokens(card["family"])
    return (
        2 * len(question_tokens & name)
        + len(question_tokens & triggers)
        + (2 if question_tokens & family else 0)
    )


def rank_tools(question: str, k: int = 8) -> list[str]:
    cards = build_cards()
    q = _tokens(question or "")
    scored = [(_score(q, card), card["name"]) for card in cards]
    scored.sort(key=lambda item: (-item[0], item[1]))
    k = max(0, min(k, len(scored)))
    return [name for _, name in scored[:k]]


def describe(names: list[str]) -> str:
    index = {card["name"]: card for card in build_cards()}
    return "\n".join(
        f"- {name} ({index[name]['family']}): {index[name]['purpose']}"
        for name in (names or [])
        if name in index
    )
