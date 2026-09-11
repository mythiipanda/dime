import asyncio
import re
import unicodedata
import uuid

import pytest

from app.config import settings
from app.graph import run_chat

HAS_KEY = bool(
    settings.mistral_api_key
    or settings.openrouter_api_key
    or settings.inception_api_key
    or settings.groq_api_key
)

pytestmark = pytest.mark.skipif(
    not HAS_KEY, reason="no provider key in backend/.env"
)

TURN_TIMEOUT_S = 40
SNIP = 500


async def _ask(question, history):
    answer = ""
    async for event in run_chat(question, None, history):
        kind = event.get("type", "")
        data = event.get("data", {}) or {}
        if kind == "final_answer":
            answer = str(data.get("text", "") or "")
        elif kind == "graph_end":
            break
    return answer


def _run(question, history):
    return asyncio.run(asyncio.wait_for(_ask(question, history), TURN_TIMEOUT_S))


def _two_turns(q1, q2):
    thread = "gauntlet-%s" % uuid.uuid4().hex[:8]
    history: list[dict[str, str]] = []
    a1 = _run(q1, history)
    history += [
        {"role": "human", "text": q1},
        {"role": "ai", "text": a1},
    ]
    a2 = _run(q2, history)
    return thread, a1[:SNIP], a2[:SNIP]


def _fold(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(c)
    )


def _names(text):
    found = set()
    for m in re.findall(r"[A-Z][a-z]+\s[A-Z][a-zA-Z\-']+", _fold(text)):
        low = m.lower()
        if low in {"denver nuggets", "golden state", "league leaders"}:
            continue
        found.add(low)
    return found


def test_followup_resolution_carries_thread():
    _, _, second = _two_turns(
        "Who leads the league in assists?",
        "Who has the most assists per game?",
    )
    low = _fold(second).lower()
    assert "jokic" in low, "turn2 missing per-game leader: %r" % second[:200]
    assert re.search(r"\d+\.\d+", second), (
        "turn2 states no per-game number: %r" % second[:200]
    )


def test_repeat_consistency_same_leader():
    _, first, second = _two_turns(
        "Who leads the league in assists?",
        "Who leads the league in assists?",
    )
    assert "assist" in first.lower() and "assist" in second.lower(), (
        "off-topic repeat: %r / %r" % (first[:150], second[:150])
    )
    shared = _names(first) & _names(second)
    assert shared, "contradiction or unnamed leader: %r / %r" % (
        first[:200],
        second[:200],
    )


def test_record_when_jokic_plays():
    _, _, second = _two_turns(
        "Which team does Nikola Jokic play for?",
        "What is Denver's record when Jokic plays?",
    )
    assert "43-22" in second, "missing 43-22: %r" % second[:200]


def test_totals_vs_rate_honesty():
    _, first, _ = _two_turns(
        "Who leads the league in assists?",
        "And how many games did he play?",
    )
    assert re.search(r"\b\d{3,4}\b", first), (
        "missing totals number: %r" % first[:200]
    )
    assert re.search(r"\d+\.\d+|\bGP\b|\bgames\b|per game", first, re.IGNORECASE), (
        "missing per-game number or GP: %r" % first[:200]
    )
