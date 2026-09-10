"""Delegate subagents. Supervisor calls workers as tools.

Each worker owns one desk, a small tool subset, and a tight budget.
Workers see only their task plus their results. The supervisor thread
stays lean. New desks need a decision row first.
"""

from typing import Any
import re as _re
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
    force_tool: str | tuple[str, dict] | None = None,
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
    if force_tool:
        fname, fargs = (force_tool if isinstance(force_tool, tuple)
                        else (force_tool, {}))
        if fname in by_name:
            try:
                out = await by_name[fname].ainvoke(fargs)
                collected.append(out if isinstance(out, dict) else {"rows": out})
            except Exception as exc:
                collected.append({"tool": fname, "error": str(exc)[:160]})
            calls_made += 1
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
    ran_data_tool = any(
        isinstance(c, dict) and c.get("tool", "") not in
        ("resolve_entity", "search_nba") and _row_count(c.get("rows")) > 0
        for c in collected
    )
    if collected and not ran_data_tool and calls_made < WORKER_BUDGET:
        data_names = [t.name for t in subset
                      if t.name not in ("resolve_entity", "search_nba")]
        data_only = client.bind_tools(
            [t for t in subset
             if t.name not in ("resolve_entity", "search_nba")])
        try:
            resp = await data_only.ainvoke(
                [SystemMessage(content=brief + " Identity is settled, use "
                               "these ids verbatim. "
                               f"Call exactly one of these now: "
                               f"{', '.join(data_names)}. No prose."),
                 HumanMessage(content=f"Season {SEASON}. Task: {task}. "
                              f"Resolved: {str(collected)[:600]}")]
            )
        except Exception as exc:
            return {"agent": desk, "ok": False, "error": str(exc)[:200]}
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
                collected.append({"tool": call.get("name"),
                                  "error": str(exc)[:160]})
            calls_made += 1
    has_data = any(
        isinstance(c, dict) and c.get("tool", "") not in
        ("resolve_entity", "search_nba")
        and _row_count(c.get("rows")) > 0 for c in collected
    )
    if not has_data:
        return {"agent": desk, "ok": False,
                "error": "no further detail available on that angle"}
    try:
        summary = await client.ainvoke(
            [
                SystemMessage(
                    content="Summarize these findings in 5 short sentences max. "
                    "Use only numbers present in the evidence. "
                    "If the evidence has no data rows, reply exactly: NO DATA."
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
    "Splits means home/away plus wins/losses plus last-10 plus monthly "
    "PPG with FG_PCT from get_splits. get_splits also carries "
    "vs-top-10-defense and vs-rest rows for matchup context. "
    "Shot diet means zone eFG plus share from get_shot_zones. "
    "Two-player shot showdowns go to get_shot_compare. "
    "Clutch production goes to get_clutch. "
    "Playoff performance for a named player goes to get_playoff_intel. "
    "Usage, turnover rate, PIE, and rating ranks go to get_advanced. "
    "Four Factors questions (eFG%, turnover rate, rebound rate, free "
    "throw rate) go to get_four_factors with player and team ids. "
    "Career impact arcs go to get_raptor_history. "
    "Custom math over warehouse tables goes to run_python. "
    "Confirm a player's current team from get_advanced TEAM_ABBREVIATION "
    "before any team claim. Never take a team from memory. "
    "Resolve names with resolve_entity first. Use returned ids verbatim. "
    "Never invent ids. Season 2025-26 unless told otherwise."
)

TEAM_BRIEF = (
    "You are the team desk. Report record, roster, recent games, rotations, "
    "and five-man lineups by minutes with plus-minus. "
    "Use get_lineups for five-man units. Use get_wowy for two-player combinations or with-or-without-you impact. "
    "For next-opponent or matchup briefs call get_scout_pack once. "
    "For rotation health call get_rotation_check. "
    "For payroll, tax, or cap room call get_cap_ledger. "
    "For home/away or monthly team splits call get_team_splits. "
    "For injury impact (how much do injuries matter) call get_injury_impact, "
    "not get_injuries. State its impact grade, team net rating and rank, "
    "and last-10 record verbatim in the summary. "
    "When the task names a player, resolve their current team from "
    "warehouse gamelog MATCHUP or get_advanced first. Never trust a team "
    "from memory. "
    "Resolve names with resolve_entity first. Use returned ids verbatim. "
    "Never invent ids. Season 2025-26 unless told otherwise."
)

LEAGUE_BRIEF = (
    "You are the league desk. Season 2025-26 unless told otherwise. "
    "IF the task mentions playoffs, champion, finals, or rings, "
    "AND names a player, THEN call get_playoff_intel with that player "
    "name first and nothing else. "
    "IF the task mentions playoffs, champion, finals, or rings, "
    "without a player name, THEN call get_playoffs first and nothing else. "
    "IF the task mentions clutch, late game, or last 5 minutes, "
    "THEN call get_clutch. "
    "IF the task mentions offense, defense, net rating, pace, or ranks, "
    "THEN call get_ratings. "
    "IF the task mentions ELO, power ranking, or true strength, "
    "THEN call get_elo. "
    "IF the task mentions title odds, finals odds, or simulating the "
    "playoffs, THEN call get_playoff_sim. "
    "IF the task mentions overpaid, underpaid, contract value, or "
    "salary vs production, THEN call get_contract_value, passing "
    "the player name when one is named. "
    "IF the task mentions draft, prospects, or rookies, "
    "THEN call get_draft_board. "
    "IF the task mentions star probability or draft model, "
    "THEN call get_draft_model. "
    "IF the task mentions form, streaks, risers, fallers, or who is hot, "
    "THEN call get_risers. "
    "IF the task mentions trade, swap, deal, or sign-and-trade, "
    "THEN call get_trade_check with team_abbrevs and player names. "
    "If a tool reports unknown players, stop and report them exactly. "
    "Never swap in a suggested name as the requested player. "
    "IF the task mentions today, last night, tonight, or movers, "
    "THEN call get_today. "
    "IF the task asks for a morning briefing, daily recap, or brief me, "
    "THEN call get_morning_briefing. "
    "IF the task mentions hustle, deflections, screen assists, or DPOY, "
    "THEN call get_hustle_boards. "
    "IF the task mentions clutch standings, quarter splits, or bench scoring, "
    "THEN call get_standings_deep. "
    "IF the task names one stat category, THEN call get_leaders. "
    "Otherwise call get_standings."
)


def delegate_tools(provider: ProviderName, model: str) -> list:
    @tool("delegate_scout")
    async def delegate_scout(task: str) -> dict[str, Any]:
        """Hand player research to the scout. One player per call."""
        return await _run_desk(
            "scout", SCOUT_BRIEF, task, provider, model,
            ["resolve_entity", "search_nba",              "get_player_intel", "get_raptor_history",
             "get_on_off", "get_wowy", "get_four_factors",
             "get_last_x", "get_percentiles", "get_shot_zones",
             "get_shot_compare", "get_trend", "get_comps", "get_clutch",
             "get_playoff_intel",
              "get_advanced", "get_splits", "run_python", "text_to_sql"],
        )

    @tool("delegate_team")
    async def delegate_team(task: str) -> dict[str, Any]:
        """Hand team research to the team desk. One team per call."""
        force = None
        if _re.search(r"impact|how much|how bad|hurting|without|matter",
                       task, _re.IGNORECASE):
            from nba_api.stats.static import teams as _teams

            abbr = next(
                (t["abbreviation"] for t in _teams.get_teams()
                 if t["full_name"].lower() in task.lower()
                 or _re.search(r"\b" + _re.escape(t["abbreviation"]) + r"\b",
                               task, _re.IGNORECASE)),
                "",
            )
            if abbr:
                force = ("get_injury_impact", {"team": abbr})
        return await _run_desk(
            "team", TEAM_BRIEF, task, provider, model,
            ["resolve_entity", "search_nba", "get_team_hub", "get_games_on_date",
             "get_boxscore", "get_lineups", "get_wowy", "get_injuries", "get_preview",
             "get_scout_pack", "get_rotation_check", "get_cap_ledger",
             "get_team_splits", "get_injury_impact", "run_python",
             "text_to_sql"],
            force_tool=force,
        )

    @tool("delegate_league")
    async def delegate_league(task: str) -> dict[str, Any]:
        """Hand leaguewide questions to the league desk."""
        force = None
        if _re.search(r"playoff|champion|finals|\bring\b|title",
                       task, _re.IGNORECASE):
            force = "get_playoffs"
        elif _re.search(
                r"which\s+(players|teams)|what\s+(players|teams)|"
                r"top\s+\d+|\bunder\s+\d+|\bover\s+\d+|\bage\b|"
                r"\baverag\w*\b|\bat least\b|"
                r"leads?\s+the\s+league|who\s+leads\b",
                task, _re.IGNORECASE):
            force = ("text_to_sql", {"question": task.replace(
                " Answer via text_to_sql (you own that tool).", "")})
        return await _run_desk(
            "league", LEAGUE_BRIEF, task, provider, model,
            ["get_standings", "get_standings_deep", "get_leaders", "get_injuries", "get_rapm",
             "get_playoffs", "get_playoff_intel", "get_ratings", "get_clutch", "get_elo",
             "get_playoff_sim", "get_contract_value", "get_draft_board",
             "get_draft_model", "get_risers", "get_trade_check", "get_hustle_boards",
             "get_today", "get_morning_briefing",
             "run_python", "text_to_sql"],
            force_tool=force,
        )

    return [delegate_scout, delegate_team, delegate_league]
