"""Delegate subagents. Supervisor calls workers as tools.

Each worker owns one desk, a small tool subset, and a tight budget.
Workers see only their task plus their results. The supervisor thread
stays lean. New desks need a decision row first.
"""

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from .providers import ProviderName, get_llm

SEASON = "2025-26"
WORKER_BUDGET = 3


def _row_count(rows: Any) -> int:
    if isinstance(rows, list):
        return len(rows)
    if isinstance(rows, dict):
        return sum(_row_count(v) for v in rows.values())
    return 1 if rows else 0


async def _run_desk(
    desk: str,
    brief: str,
    task: str,
    provider: ProviderName,
    model: str,
    tool_names: list[str],
) -> dict[str, Any]:
    from . import tools as _tools

    by_name = {t.name: t for t in _tools.v1_tools}
    subset = [by_name[n] for n in tool_names if n in by_name]
    client = get_llm(provider, model)
    if client is None:
        return {"agent": desk, "ok": False, "error": f"no key for {provider}"}
    tooled = client.bind_tools(subset)
    calls_made = 0
    collected: list[dict[str, Any]] = []
    attempts = [
        [SystemMessage(content=brief),
         HumanMessage(content=f"Season {SEASON}. Task: {task}")],
        [SystemMessage(content=brief + " Call exactly one tool now. No prose."),
         HumanMessage(content=f"Season {SEASON}. Task: {task}")],
    ]
    resp = None
    for attempt in attempts:
        try:
            resp = await tooled.ainvoke(attempt)
        except Exception as exc:
            return {"agent": desk, "ok": False, "error": str(exc)[:200]}
        if getattr(resp, "tool_calls", None):
            break
    for call in getattr(resp, "tool_calls", None) or []:
        if calls_made >= WORKER_BUDGET:
            break
        fn = by_name.get(call.get("name", ""))
        if fn is None:
            continue
        try:
            out = await fn.ainvoke(call.get("args", {}) or {})
            collected.append(out if isinstance(out, dict) else {"rows": out})
        except Exception as exc:
            collected.append({"tool": call.get("name"), "error": str(exc)[:160]})
        calls_made += 1
    has_data = any(
        isinstance(c, dict) and _row_count(c.get("rows")) > 0 for c in collected
    )
    if not has_data:
        return {"agent": desk, "ok": False,
                "error": "no evidence from warehouse or live sources"}
    try:
        summary = await client.ainvoke(
            [
                SystemMessage(
                    content="Summarize these findings in 5 short sentences max. "
                    "Use only numbers present in the evidence."
                ),
                HumanMessage(content=f"Task: {task}\nEvidence: {str(collected)[:8000]}"),
            ]
        )
        text = getattr(summary, "content", "") or ""
    except Exception as exc:
        text = ""
        collected.append({"error": str(exc)[:160]})
    return {"agent": desk, "ok": True, "summary": text, "tables": collected}


SCOUT_BRIEF = (
    "You are the player scout. Report form, splits, and shot profile. "
    "Resolve names with resolve_entity first. Use returned ids verbatim. "
    "Never invent ids. Season 2025-26 unless told otherwise."
)

TEAM_BRIEF = (
    "You are the team desk. Report record, roster, recent games, rotations, "
    "and five-man lineups by minutes with plus-minus. "
    "Use get_lineups for any who-plays-well-together question. "
    "Resolve names with resolve_entity first. Use returned ids verbatim. "
    "Never invent ids. Season 2025-26 unless told otherwise."
)

LEAGUE_BRIEF = (
    "You are the league desk. Report standings, leaders, and injuries. "
    "Season 2025-26 unless told otherwise."
)


def delegate_tools(provider: ProviderName, model: str) -> list:
    @tool("delegate_scout")
    async def delegate_scout(task: str) -> dict[str, Any]:
        """Hand player research to the scout. One player per call."""
        return await _run_desk(
            "scout", SCOUT_BRIEF, task, provider, model,
            ["resolve_entity", "search_nba", "get_player_intel",
             "get_on_off", "get_wowy", "get_four_factors",
             "get_last_x", "get_percentiles", "get_shot_zones",
             "get_trend", "get_comps"],
        )

    @tool("delegate_team")
    async def delegate_team(task: str) -> dict[str, Any]:
        """Hand team research to the team desk. One team per call."""
        return await _run_desk(
            "team", TEAM_BRIEF, task, provider, model,
            ["resolve_entity", "search_nba", "get_team_hub", "get_games_on_date",
             "get_boxscore", "get_lineups", "get_injuries", "get_preview"],
        )

    @tool("delegate_league")
    async def delegate_league(task: str) -> dict[str, Any]:
        """Hand leaguewide questions to the league desk."""
        return await _run_desk(
            "league", LEAGUE_BRIEF, task, provider, model,
            ["get_standings", "get_leaders", "get_injuries", "get_rapm"],
        )

    return [delegate_scout, delegate_team, delegate_league]
