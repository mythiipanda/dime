"""Five nodes. Typed state. Tool budget plus dedupe plus parallel exec.

Event dicts stream out in the frontend contract: node_update,
thought_stream, message, final_answer, suggestions, graph_end, error.
"""

import asyncio
import json
import re
from collections.abc import AsyncGenerator
from typing import Any, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage

from .providers import (
    astream_with_fallback,
    get_llm,
    invoke_with_fallback,
    resolve_model_id,
)
from .skills import catalog as skills_catalog
from .subagents import delegate_tools
from .tools import v1_tools

ANALYST_SYSTEM = (
    "You are Dime, an NBA data analyst assistant. "
    "Answer ONLY from the tool results you receive. "
    "Every number you state must appear in the evidence. "
    "Never invent streaks, averages, or ranks. "
    "Never list months, dates, or specifics absent from evidence. "
    "Name the tool output you used. Say when data is missing. "
    "Keep answers short and specific with numbers."
)

PLANNER_SYSTEM = (
    "You are the retrieval supervisor. Your tools: resolve_entity, "
    "get_compare, get_preview, get_briefing, delegate_scout, "
    "delegate_team, delegate_league. Workers behind the delegates own "
    "every granular dataset, including text_to_sql. "
    "Delegate multi-part work (comparisons, previews, roundups) to one delegate per entity. "
    "Pass the user's question to the delegate unchanged as the task. "
    "For cross-season history delegate to the right desk and tell it to use text_to_sql. "
    "For single-season leaders, standings, injuries, playoffs, ratings, "
    "clutch, ELO, or title odds, call delegate_league. "
    "For two-player compares call get_compare once and nothing else. "
    "For two-team previews call get_preview once and nothing else. "
    "After a composite call, make no further tool calls this turn. "
    "Resolve calls alone never answer a question. "
    "Always follow identity results with data calls in the next round. "
    "Resolve every name with resolve_entity first when the task lacks an explicit id. "
    "Id params also accept names directly and resolve internally. "
    "Use returned ids verbatim. Never invent or recall ids from memory. "
    "Plan the SMALLEST set of calls that answers the question. "
    "Prefer one call. Never repeat a call with the same args. "
    "Batch independent calls together. "
    "Call search_nba first when you lack an id. "
    "The current season is 2025-26. Pass season 2025-26 always, "
    "unless the user names a different season explicitly."
    "\n\nAnalyst skills. Match the question to one skill and follow it:\n"
    + skills_catalog()
)

MAX_TOOL_ROUNDS = 3
MAX_TOOL_CALLS = 8


class DimeState(TypedDict):
    question: str
    primary: str
    model: str
    round: int
    tool_results: list[dict[str, Any]]
    calls_made: list[str]
    history: list[dict[str, str]]
    analysis: str
    suggestions: list[str]


def _call_key(name: str, args: dict[str, Any]) -> str:
    return name + ":" + json.dumps(args, sort_keys=True, default=str)


def _all_tools(state: DimeState) -> list:
    return list(v1_tools) + delegate_tools(state["primary"], state["model"])  # type: ignore[arg-type]


SUPERVISOR_TOOL_NAMES = frozenset({
    "resolve_entity", "get_compare", "get_preview", "get_briefing",
    "delegate_scout", "delegate_team", "delegate_league",
})


def _supervisor_tools(state: DimeState) -> list:
    return [t for t in _all_tools(state) if t.name in SUPERVISOR_TOOL_NAMES]


def _flatten_tables(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        nested = r.get("tables")
        if isinstance(nested, list) and r.get("agent"):
            for t in nested:
                if isinstance(t, dict):
                    flat.append(t)
        else:
            flat.append(r)
    return flat


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?(?:-\d+)?%?", text)


def _event(kind: str, payload: Any) -> dict[str, Any]:
    return {"type": kind, "data": payload}


async def entry_node(state: DimeState) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "entry", "status": "running"})
    yield _event("node_update", {"node": "entry", "status": "complete"})


async def data_retrieval_agent(
    state: DimeState,
) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "data_retrieval", "status": "running"})
    client = get_llm(state["primary"], state["model"])  # type: ignore[arg-type]
    if client is None:
        yield _event("error", {"node": "data_retrieval", "message": "no key"})
        return
    tooled = client.bind_tools(_supervisor_tools(state))
    prior = ""
    if state["history"]:
        turns = state["history"][-6:]
        prior += "\nConversation so far:\n" + "\n".join(
            f"{t['role']}: {t['text'][:600]}" for t in turns
        )
    if state["tool_results"]:
        prior += "\nPrior tool results this turn: " + str(state["tool_results"])[:4000]
    budget_left = MAX_TOOL_CALLS - len(state["calls_made"])
    if budget_left <= 0:
        yield _event("thought_stream", {"node": "data_retrieval",
                                        "text": "Tool budget spent. Answering from evidence."})
        state["round"] = MAX_TOOL_ROUNDS
        yield _event("node_update", {"node": "data_retrieval", "status": "complete"})
        return
    try:
        resp = await tooled.ainvoke(
            [SystemMessage(content=PLANNER_SYSTEM + prior), HumanMessage(content=state["question"])]
        )
    except Exception as exc:
        yield _event("error", {"node": "data_retrieval", "message": str(exc)[:200]})
        return
    calls = getattr(resp, "tool_calls", None) or []
    fresh = []
    for call in calls:
        key = _call_key(call.get("name", ""), call.get("args", {}) or {})
        if key in state["calls_made"]:
            continue
        state["calls_made"].append(key)
        fresh.append(call)
        if len(state["calls_made"]) >= MAX_TOOL_CALLS:
            break
    if not fresh:
        thought = getattr(resp, "content", "") or ""
        if thought:
            yield _event("thought_stream", {"node": "data_retrieval", "text": thought[:500]})
        state["round"] = MAX_TOOL_ROUNDS
    else:
        for call in fresh:
            yield _event("message", {"node": "data_retrieval", "tool_call": call})
        state["_pending_calls"] = fresh  # type: ignore[typeddict-unknown-key]
        names = sorted({c.get("name", "") for c in fresh})
        yield _event("thought_stream", {"node": "data_retrieval",
                                        "text": "Plan: " + ", ".join(names)})
    yield _event("node_update", {"node": "data_retrieval", "status": "complete"})


async def actual_tool_node(state: DimeState) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "tools", "status": "running"})
    by_name = {t.name: t for t in _all_tools(state)}
    pending = state.pop("_pending_calls", [])  # type: ignore[typeddict-unknown-key]

    async def _run(call: dict[str, Any]) -> dict[str, Any]:
        name = call.get("name", "")
        args = call.get("args", {}) or {}
        fn = by_name.get(name)
        if fn is None:
            return {"tool": name, "ok": False, "error": "unknown tool"}
        try:
            out = await fn.ainvoke(args)
            return out if isinstance(out, dict) else {"tool": name, "rows": out}
        except Exception as exc:
            return {"tool": name, "ok": False, "error": str(exc)[:200]}

    results = await asyncio.gather(*(_run(c) for c in pending))
    for result in results:
        state["tool_results"].append(result)
        yield _event("message", {"node": "tools", "tool_result": result})
    state["round"] += 1
    yield _event("node_update", {"node": "tools", "status": "complete"})


def _suggest(
    question: str, results: list[dict[str, Any]], calls_made: list[str],
) -> list[str]:
    tools_used = {r.get("tool", "") for r in results if isinstance(r, dict)}
    used_cats: list[str] = []
    for key in calls_made:
        try:
            name, _, argstr = key.partition(":")
            if name == "get_leaders":
                cat = json.loads(argstr).get("stat_category", "")
                if cat and cat not in used_cats:
                    used_cats.append(cat)
        except Exception:
            pass
    out: list[str] = []
    if "get_player_intel" in tools_used:
        out.append("Show shot chart for this player")
        out.append("Compare with another player")
    if "get_team_hub" in tools_used:
        out.append("Show roster details")
        out.append("Show recent boxscores")
    if "get_standings" in tools_used:
        out.append("Show scoring leaders")
        out.append("Show injury report")
    if "get_leaders" in tools_used:
        for cat in ["PTS", "REB", "AST", "STL", "BLK"]:
            if cat not in used_cats:
                out.append(f"Show {cat} leaders")
                if len(out) >= 4:
                    break
    if "get_boxscore" in tools_used:
        out.append("Show shot chart for the top scorer")
    if not out:
        out = ["Summarize this season", "Show scoring leaders", "Show standings"]
    seen: list[str] = []
    for s in out:
        if s not in seen:
            seen.append(s)
    return seen[:3]


async def analytics_agent(state: DimeState) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "analytics", "status": "running"})
    def _has_rows(rows: Any) -> bool:
        if isinstance(rows, list):
            return len(rows) > 0
        if isinstance(rows, dict):
            return any(_has_rows(v) for v in rows.values())
        return bool(rows)

    evidenced = [
        r for r in _flatten_tables(state["tool_results"])
        if isinstance(r, dict) and _has_rows(r.get("rows"))
    ]
    if not evidenced:
        tried = [k.split(":", 1)[0] for k in state["calls_made"]][:6]
        state["analysis"] = (
            "The research step came back empty, so there is nothing to report. "
            "Ask again or ask something narrower."
            + (f" Tried: {', '.join(tried)}." if tried else "")
        )
        yield _event(
            "custom_data", {"node": "analytics", "tables": _flatten_tables(state["tool_results"])}
        )
        yield _event("node_update", {"node": "analytics", "status": "complete"})
        return
    evidence = str(state["tool_results"])[:12000]
    try:
        parts: list[str] = []
        async for chunk in astream_with_fallback(
            state["primary"],  # type: ignore[arg-type]
            state["model"],
            [
                SystemMessage(content=ANALYST_SYSTEM),
                HumanMessage(
                    content=f"Question: {state['question']}\nEvidence: {evidence}"
                ),
            ],
        ):
            parts.append(chunk["text"])
            yield _event("token", {"text": chunk["text"]})
        state["analysis"] = "".join(parts)
    except Exception as exc:
        state["analysis"] = ""
        yield _event("error", {"node": "analytics", "message": str(exc)[:200]})
    unverified = [
        n for n in _numbers(state["analysis"])
        if n not in evidence and len(n) > 2
    ][:5]
    if unverified:
        yield _event("custom_data", {"node": "analytics",
                                     "unverified_numbers": unverified})
    yield _event(
        "custom_data", {"node": "analytics", "tables": _flatten_tables(state["tool_results"])}
    )
    yield _event("node_update", {"node": "analytics", "status": "complete"})


async def presentation_agent(state: DimeState) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "presentation", "status": "running"})
    text = state.get("analysis", "") or "No data came back. Try a player or team name."
    yield _event("final_answer", {"text": text})
    state["suggestions"] = _suggest(
        state["question"], state["tool_results"], state["calls_made"]
    )
    yield _event("suggestions", {"items": state["suggestions"]})
    yield _event("node_update", {"node": "presentation", "status": "complete"})


async def run_chat(
    question: str,
    model_id: str | None,
    history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    primary, model = resolve_model_id(model_id)
    state = DimeState(
        question=question, primary=primary, model=model, round=0,
        tool_results=[], calls_made=[], history=history or [],
        analysis="", suggestions=[],
    )
    async for e in entry_node(state):
        yield e
    while state["round"] < MAX_TOOL_ROUNDS:
        async for e in data_retrieval_agent(state):
            yield e
        if "_pending_calls" not in state:
            break
        async for e in actual_tool_node(state):
            yield e
    async for e in analytics_agent(state):
        yield e
    async for e in presentation_agent(state):
        yield e
    yield _event("graph_end", {"ok": True})
