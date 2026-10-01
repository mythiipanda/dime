import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as G

PRIOR_A = ("Nikola Jokic leads at 10.72 assists per game in 2024-25 "
           "(65 games).")


def test_context_claim_found_from_prior_answer():
    got = G._prior_context_leader_claim(
        "highest assists/game?",
        [{"role": "human", "text": "who leads in assists"},
         {"role": "assistant", "text": PRIOR_A}],
        [PRIOR_A])
    assert got is not None
    assert got[0] == "APG"
    assert got[1] == "2024-25"
    assert "10.72" in got[2]


def test_context_claim_found_from_ledger_only():
    got = G._prior_context_leader_claim("highest assists/game?", [], [PRIOR_A])
    assert got is not None and got[0] == "APG"


def test_ambiguous_context_returns_none():
    text = ("Jokic leads at 10.72 assists per game in 2024-25. "
            "Wembanyama leads at 3.8 blocks per game in 2024-25.")
    assert G._prior_context_leader_claim("highest?", [], [text]) is None


def test_explicit_season_mismatch_returns_none():
    got = G._prior_context_leader_claim(
        "highest assists/game in 2023-24?", [], [PRIOR_A])
    assert got is None


def test_claim_verified_by_value_match():
    out = {"tool": "get_leaders", "ok": True,
           "rows": [{"PLAYER": "Nikola Jokic", "APG": 10.72, "GP": 65}]}
    assert G._context_claim_verified(out, PRIOR_A, "APG") is True


def test_claim_rejected_on_value_mismatch():
    out = {"tool": "get_leaders", "ok": True,
           "rows": [{"PLAYER": "Trae Young", "APG": 11.9, "GP": 66}]}
    assert G._context_claim_verified(out, PRIOR_A, "APG") is False


def test_claim_rejected_on_tool_error():
    out = {"tool": "get_leaders", "ok": False, "error": "timeout"}
    assert G._context_claim_verified(out, PRIOR_A, "APG") is False


def test_followup_answers_from_context_with_one_lookup(monkeypatch):
    calls = []

    async def fake_triage_tool(name, args, state, holder):
        calls.append((name, dict(args)))
        holder["out"] = {"tool": name, "ok": True,
                         "rows": [{"PLAYER": "Nikola Jokic",
                                   "APG": 10.72, "GP": 65}]}
        yield {"type": "tool_result", "data": {}}

    async def fake_terminal(question, state):
        state["round"] = 99
        yield {"type": "node_update", "data": {}}

    monkeypatch.setattr(G, "_triage_tool", fake_triage_tool)
    monkeypatch.setattr(G, "_triage_terminal", fake_terminal)
    state = {
        "question": "highest assists/game?",
        "primary": "x", "model": "y", "round": 0,
        "tool_results": [], "calls_made": [],
        "history": [{"role": "human", "text": "who leads in assists"},
                    {"role": "assistant", "text": PRIOR_A}],
        "ledger": [PRIOR_A],
        "analysis": "", "suggestions": [],
        "desk_cache": {}, "entity_cache": {},
    }

    async def run():
        async for _ in G._triage_seed("highest assists/game?", "x", "y",
                                       state):
            pass

    asyncio.run(run())
    assert len(calls) == 1
    assert calls[0][0] == "get_leaders"
    assert calls[0][1]["stat_category"] == "APG"
    assert state["round"] == 99
    assert "10.72 assists per game" in state["analysis"]
    assert state.get("_analysis_final") is True


def test_followup_falls_through_when_verification_disagrees(monkeypatch):
    calls = []

    async def fake_triage_tool(name, args, state, holder):
        calls.append(name)
        holder["out"] = {"tool": name, "ok": True,
                         "rows": [{"PLAYER": "Trae Young",
                                   "APG": 11.9, "GP": 66}]}
        yield {"type": "tool_result", "data": {}}

    async def fake_terminal(question, state):
        state["round"] = 99
        yield {"type": "node_update", "data": {}}

    monkeypatch.setattr(G, "_triage_tool", fake_triage_tool)
    monkeypatch.setattr(G, "_triage_terminal", fake_terminal)
    state = {
        "question": "highest assists/game?",
        "primary": "x", "model": "y", "round": 0,
        "tool_results": [], "calls_made": [],
        "history": [{"role": "human", "text": "who leads in assists"},
                    {"role": "assistant", "text": PRIOR_A}],
        "ledger": [PRIOR_A],
        "analysis": "", "suggestions": [],
        "desk_cache": {}, "entity_cache": {},
    }

    async def run():
        async for _ in G._triage_seed("highest assists/game?", "x", "y",
                                       state):
            pass

    asyncio.run(run())
    assert state["round"] == 99
    assert "10.72 assists per game" not in state.get("analysis", "")
