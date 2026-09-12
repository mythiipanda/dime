"""Pure assertion engine for the benchmark pack. No network, no LLM.

A Turn transcript is a dict: {"text": str, "seconds": float,
"tool_calls": int, "streamed_chars": int}. Assertions come from
scenarios.json. Everything here is unit-testable hermetically.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BANNED_KEY = "banned_everywhere"


def load_pack(path: str | Path) -> dict[str, Any]:
    pack = json.loads(Path(path).read_text())
    validate_pack(pack)
    return pack


def validate_pack(pack: dict[str, Any]) -> None:
    assert pack.get("scenarios"), "pack has no scenarios"
    ids = [s["id"] for s in pack["scenarios"]]
    assert len(ids) == len(set(ids)), f"duplicate scenario ids: {ids}"
    for s in pack["scenarios"]:
        assert s.get("chain"), f"{s['id']}: empty chain"
        has_turns = bool(s.get("expect_turns"))
        has_flat = bool(s.get("expect"))
        assert has_turns != has_flat or (has_flat and len(s["chain"]) == 1), (
            f"{s['id']}: use 'expect' for single-turn, 'expect_turns' for chains")
        if has_turns:
            assert len(s["expect_turns"]) == len(s["chain"]), (
                f"{s['id']}: expect_turns must match chain length")


def check_text(text: str, expect: dict[str, Any],
               banned: list[str]) -> list[str]:
    """Return a list of failures (empty = pass)."""
    low = text.lower()
    fails: list[str] = []
    for needle in expect.get("contains", []):
        if needle.lower() not in low:
            fails.append(f"missing expected text: {needle!r}")
    for needle in list(expect.get("not_contains", [])) + list(banned):
        if needle.lower() in low:
            fails.append(f"contains banned text: {needle!r}")
    return fails


def check_budget(turn: dict[str, Any], budget: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    cap = budget.get("max_seconds")
    if cap is not None and turn.get("seconds", 0) > cap:
        fails.append(f"latency {turn['seconds']:.1f}s > {cap}s budget")
    cap = budget.get("max_tool_calls")
    if cap is not None and turn.get("tool_calls", 0) > cap:
        fails.append(f"{turn['tool_calls']} tool calls > {cap} budget")
    return fails


def evaluate_scenario(scenario: dict[str, Any],
                      turns: list[dict[str, Any]],
                      banned: list[str]) -> dict[str, Any]:
    """Grade one scenario's recorded turns."""
    fails: list[str] = []
    if len(turns) != len(scenario["chain"]):
        return {"id": scenario["id"], "pass": False,
                "fails": [f"expected {len(scenario['chain'])} turns, "
                          f"got {len(turns)}"], "xfail": bool(scenario.get("xfail"))}
    if "expect_turns" in scenario:
        expects = scenario["expect_turns"]
    else:
        expects = [scenario.get("expect", {})]
    for i, (turn, expect) in enumerate(zip(turns, expects)):
        for f in check_text(turn.get("text", ""), expect, banned):
            fails.append(f"T{i + 1}: {f}")
    budget = dict(scenario.get("budget", {}))
    per_turn = budget.pop("max_seconds_per_turn", None)
    if per_turn is not None:
        for i, turn in enumerate(turns):
            for f in check_budget(turn, {"max_seconds": per_turn}):
                fails.append(f"T{i + 1}: {f}")
    if budget and turns:
        total = dict(turns[-1])
        total["seconds"] = sum(t.get("seconds", 0) for t in turns)
        total["tool_calls"] = sum(t.get("tool_calls", 0) for t in turns)
        for f in check_budget(total, budget):
            fails.append(f"total: {f}")
    return {"id": scenario["id"], "pass": not fails, "fails": fails,
            "xfail": bool(scenario.get("xfail")),
            "seconds": round(sum(t.get("seconds", 0) for t in turns), 2),
            "tool_calls": sum(t.get("tool_calls", 0) for t in turns),
            "streamed_chars": sum(t.get("streamed_chars", 0) for t in turns)}
