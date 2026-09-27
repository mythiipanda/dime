"""Desk-failure recovery: a failed team desk must not surface the canned
"I could not find that in the dataset" fallback.

Regression for the "boston celtics stats" prod incident (2026-09-26):
the team desk timed out and the turn collapsed into the generic dataset
fallback, which reads as hardcoded. Expected behavior now:
1. a delegate_* desk that fails is retried once with a simpler task,
2. if it still fails, presentation names the desk and the error instead
   of the canned fallback.

Hermetic: fabricated desk, no LLM, no network.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.graph as g  # noqa: E402

CANNED = "I could not find that in the dataset"


def _final_text(state):
    out = None

    async def _go():
        nonlocal out
        async for e in g.presentation_agent(state):
            if e.get("type") == "final_answer":
                out = e["data"]["text"]

    asyncio.run(_go())
    return out


def test_team_desk_timeout_no_canned_fallback():
    state = {
        "question": "boston celtics stats",
        "analysis": "",
        "tool_results": [
            {"tool": "delegate_team", "ok": False,
             "error": "timed out after 120s",
             "desk_retried": True,
             "first_error": "timed out after 120s"},
        ],
        "calls_made": [], "history": [],
        "primary": "p", "model": "m",
    }
    text = _final_text(state)
    assert CANNED not in text, f"canned fallback leaked: {text!r}"
    assert "team desk" in text
    assert "didn't respond in time" in text
    # sanitized: no raw error text, no internal detail, no question echo
    assert "120s" not in text
    assert "boston celtics" not in text.lower()
    # "underlying data is there" is only claimed when rows came back
    assert "underlying data" not in text.lower()


def test_team_desk_error_no_canned_fallback():
    state = {
        "question": "boston celtics stats",
        "analysis": "",
        "tool_results": [
            {"tool": "delegate_team", "ok": False,
             "error": "Traceback: /srv/app/desks.py line 42 boom"},
        ],
        "calls_made": [], "history": [],
        "primary": "p", "model": "m",
    }
    text = _final_text(state)
    assert CANNED not in text, f"canned fallback leaked: {text!r}"
    assert "team desk" in text
    assert "ran into a problem" in text
    assert "Traceback" not in text and "/srv/app" not in text
    assert "boston celtics" not in text.lower()


def test_desk_note_mentions_evidence_only_when_present():
    base = {"question": "q", "analysis": "", "calls_made": [], "history": [],
            "primary": "p", "model": "m"}
    failed = {"tool": "delegate_team", "ok": False, "error": "boom"}
    t1 = _final_text({**base, "tool_results": [failed]})
    assert "evidence panel" not in t1
    t2 = _final_text({**base, "tool_results": [
        failed, {"tool": "get_leaders", "ok": True,
                 "rows": [{"PLAYER": "X"}]}]})
    assert "evidence panel" in t2


class _DelegateStub:
    name = "delegate_team"

    async def ainvoke(self, args):
        raise AssertionError("delegate desks run via run_desk_streaming")


def test_desk_retries_once_with_simpler_task(monkeypatch):
    calls = []

    async def _fake_desk(name, task, primary, model, on_token=None):
        calls.append((name, task))
        return {"tool": name, "ok": False, "error": "boom"}

    monkeypatch.setattr(g, "run_desk_streaming", _fake_desk)
    monkeypatch.setattr(g, "_supervisor_tools", lambda s: [_DelegateStub()])
    monkeypatch.setattr(g, "DESK_CALL_TIMEOUT_S", 5.0)

    async def _go(state):
        async for _e in g.actual_tool_node(state):
            pass
        return state

    state = {"question": "boston celtics stats", "primary": "p", "model": "m",
             "round": 0, "tool_results": [], "calls_made": [], "history": [],
             "_pending_calls": [{"name": "delegate_team",
                                "args": {"task": "get celtics team stats"}}]}
    state = asyncio.run(_go(state))
    assert len(calls) == 2, f"expected 1 retry, got {len(calls)} attempts"
    assert "simplest" in calls[1][1] or "Retry" in calls[1][1]
    res = state["tool_results"][-1]
    assert res["ok"] is False
    assert res.get("desk_retried") is True
    assert res.get("first_error") == "boom"


def test_desk_retry_success_uses_second_result(monkeypatch):
    attempts = []

    async def _fake_desk(name, task, primary, model, on_token=None):
        attempts.append(task)
        if len(attempts) == 1:
            return {"tool": name, "ok": False, "error": "boom"}
        return {"tool": name, "ok": True, "rows": [{"TEAM": "Celtics"}]}

    monkeypatch.setattr(g, "run_desk_streaming", _fake_desk)
    monkeypatch.setattr(g, "_supervisor_tools", lambda s: [_DelegateStub()])
    monkeypatch.setattr(g, "DESK_CALL_TIMEOUT_S", 5.0)

    async def _go(state):
        async for _e in g.actual_tool_node(state):
            pass
        return state

    state = {"question": "boston celtics stats", "primary": "p", "model": "m",
             "round": 0, "tool_results": [], "calls_made": [], "history": [],
             "_pending_calls": [{"name": "delegate_team",
                                "args": {"task": "get celtics team stats"}}]}
    state = asyncio.run(_go(state))
    assert len(attempts) == 2
    res = state["tool_results"][-1]
    assert res.get("ok") is True
    assert res["rows"] == [{"TEAM": "Celtics"}]


def test_desk_retry_bounded_within_wall_budget(monkeypatch):
    import time as _time

    async def _slow_desk(name, task, primary, model, on_token=None):
        await asyncio.sleep(30)
        return {"tool": name, "ok": True, "rows": []}

    monkeypatch.setattr(g, "run_desk_streaming", _slow_desk)
    monkeypatch.setattr(g, "_supervisor_tools", lambda s: [_DelegateStub()])
    monkeypatch.setattr(g, "DESK_CALL_TIMEOUT_S", 0.3)
    monkeypatch.setattr(g, "_DESK_WALL_BUDGET_S", 0.8)

    async def _go(state):
        async for _e in g.actual_tool_node(state):
            pass
        return state

    state = {"question": "q", "primary": "p", "model": "m",
             "round": 0, "tool_results": [], "calls_made": [], "history": [],
             "_pending_calls": [{"name": "delegate_team",
                                "args": {"task": "slow task"}}]}
    t0 = _time.time()
    state = asyncio.run(_go(state))
    total = _time.time() - t0
    res = state["tool_results"][-1]
    assert res.get("desk_retried") is True
    # first attempt 0.3s + retry capped so the pair stays in budget
    assert total < 0.8 + 0.5, f"retry blew the budget: {total:.2f}s"


def test_margin_claim_must_carry_operands():
    # "DET trails SAS by 2.4" is fake even though 2.4 appears in the
    # payload (as DET's own rating, not the margin).
    state = {"tool_results": [{"tool": "get_team_compare", "ok": True,
              "rows": [{"TEAM": "DET", "NET": 2.4},
                       {"TEAM": "SAS", "NET": 1.1}]}],
             "ledger": []}
    claims = g._verify_numeral_claims(state, "DET trails SAS by 2.4.")
    assert [n for _, n in claims] == ["2.4"], f"fake margin passed: {claims}"
    # the true margin with operands recomputes and survives
    ok = g._verify_numeral_claims(
        state, "DET trails SAS by 1.3 (2.4 - 1.1 = 1.3).")
    assert ok == [], f"honest margin flagged: {ok}"
    # a plain payload restatement still passes without operands
    plain = g._verify_numeral_claims(state, "DET's net rating is 2.4.")
    assert plain == [], f"plain restatement flagged: {plain}"


def test_bad_bullet_does_not_kill_good_bullet():
    state = {"tool_results": [{"tool": "x", "ok": True,
                               "rows": [{"a": 8.5}]}],
             "ledger": []}
    text = "- DET's net rating is 8.5\n- SAS scores 999.9 per game"
    claims = g._verify_numeral_claims(state, text)
    assert [n for _, n in claims] == ["999.9"]
    bad = {s for s, _ in claims}
    kept = "".join(u + sep for u, sep in g._iter_units(text)
                   if not (u.strip() and u in bad)).strip()
    assert "8.5" in kept and "999.9" not in kept
