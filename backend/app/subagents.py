"""Delegate subagents. Supervisor calls workers as tools.

Each worker owns one desk, a small tool subset, and a tight budget.
Workers see only their task plus their results. The supervisor thread
stays lean. New desks need a decision row first.
"""

from typing import Any
import re as _re
import time as _time
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from .providers import (ProviderName, get_llm, astream_chunks_with_fallback,
                       accumulate_tool_calls, fallback_order)

SEASON = "2025-26"
WORKER_BUDGET = 3


def _desk_tool_label(name: str) -> str:
    labels = {
        "resolve_entity": "Identifying players and teams",
        "search_nba": "Searching league coverage",
        "get_compare": "Comparing players",
        "delegate_scout": "Scouting players",
        "delegate_team": "Scouting teams",
        "delegate_league": "Scanning league data",
        "run_python": "Warehouse query",
        "text_to_sql": "Warehouse query",
        "get_playoff_intel": "Pulling playoff logs",
        "get_trade_check": "Checking trade math",
        "get_trade_value": "Grading trade value",
        "get_award_race": "Ranking award races",
        "get_matchup_preview": "Previewing the matchup",
        "get_impact_estimate": "Estimating impact",
    }
    if not name:
        return "Checking data"
    if name in labels:
        return labels[name]
    return name.replace("_", " ").strip().title() or "Checking data"


def _trace_status(out: Any) -> str:
    try:
        if isinstance(out, dict) and (out.get("ok") is False or out.get("error")):
            return "fail"
    except Exception:
        pass
    return "ok"


def _trace_sql(out: Any) -> str | None:
    """Lift the executed SQL off a tool output into the desk trace."""
    try:
        if not isinstance(out, dict):
            return None
        sql = out.get("sql")
        if not sql and isinstance(out.get("meta"), dict):
            sql = out["meta"].get("sql")
        sql = str(sql or "").strip()
        return sql or None
    except Exception:
        return None

def _trace_error(out: Any) -> str | None:
    try:
        if isinstance(out, dict) and out.get("error"):
            return str(out.get("error"))[:160]
    except Exception:
        pass
    return None


def _row_count(rows: Any) -> int:
    if isinstance(rows, list):
        return len(rows)
    if isinstance(rows, dict):
        return sum(_row_count(v) for v in rows.values())
    return 1 if rows else 0


async def _stream_text(provider: ProviderName, model: str,
                       messages: list, on_token=None) -> str:
    """Stream a plain LLM call, forwarding text chunks to on_token. Returns full text."""
    parts: list[str] = []
    async for item in astream_chunks_with_fallback(provider, model, messages):
        t = getattr(item["chunk"], "content", "") or ""
        if t:
            parts.append(str(t))
            if on_token is not None:
                await on_token(str(t))
    return "".join(parts)


async def _stream_tooled(provider: ProviderName, model: str,
                         messages: list, tools: list,
                         on_token=None) -> tuple[str, list[dict]]:
    """Stream a tool-bound LLM call. Forwards text chunks to on_token live,
    returns (full_text, tool_calls). Tries providers in fallback order."""
    text_parts: list[str] = []
    tc_chunks: list[dict] = []
    errors: list[str] = []
    for name in fallback_order(provider):
        client = get_llm(name, model if name == provider else None)
        if client is None:
            errors.append(f"{name}: missing key")
            continue
        try:
            bound = client.bind_tools(tools)
            async for chunk in bound.astream(messages):
                t = getattr(chunk, "content", "") or ""
                if t:
                    text_parts.append(str(t))
                    if on_token is not None:
                        await on_token(str(t))
                for tc in getattr(chunk, "tool_call_chunks", None) or []:
                    tc_chunks.append(dict(tc) if isinstance(tc, dict) else tc)
            return "".join(text_parts), accumulate_tool_calls(tc_chunks)
        except Exception as exc:
            errors.append(f"{name}: {str(exc)[:160]}")
    raise RuntimeError("all providers failed: " + " | ".join(errors))


async def _run_desk(
    desk: str,
    brief: str,
    task: str,
    provider: ProviderName,
    model: str,
    tool_names: list[str],
    force_tool: str | tuple[str, dict] | None = None,
    on_token=None,
) -> dict[str, Any]:
    """Run one desk. on_token, if given, is an async callable receiving each
    LLM text chunk as it streams, so callers can pipe live tokens to SSE."""
    from . import tools as _tools

    by_name = {t.name: t for t in _tools.v1_tools}
    subset = [by_name[n] for n in tool_names if n in by_name]
    client = get_llm(provider, model)
    if client is None:
        return {"agent": desk, "ok": False, "error": f"no key for {provider}",
                "tool_trace": []}
    calls_made = 0
    collected: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    if force_tool:
        fname, fargs = (force_tool if isinstance(force_tool, tuple)
                        else (force_tool, {}))
        if fname in by_name:
            _t0 = _time.time()
            try:
                out = await by_name[fname].ainvoke(fargs)
                collected.append(out if isinstance(out, dict) else {"rows": out})
            except Exception as exc:
                out = {"tool": fname, "error": str(exc)[:160]}
                collected.append(out)
            _ms = int((_time.time() - _t0) * 1000)
            _rows = _row_count(out.get("rows")) if isinstance(out, dict) else _row_count(out)
            _st = _trace_status(out)
            _te: dict[str, Any] = {
                "name": fname, "label": _desk_tool_label(fname),
                "ms": _ms, "rows": _rows, "status": _st,
            }
            _sql = _trace_sql(out)
            if _sql:
                _te["sql"] = _sql
            _err = _trace_error(out)
            if _err:
                _te["error"] = _err
            trace.append(_te)
            calls_made += 1
    attempts = [
        [SystemMessage(content=brief),
         HumanMessage(content=f"Season {SEASON}. Task: {task}")],
        [SystemMessage(content=brief + " Call exactly one tool now. No prose."),
         HumanMessage(content=f"Season {SEASON}. Task: {task}")],
    ]
    tool_calls: list[dict] = []
    for attempt in attempts:
        try:
            _t, tool_calls = await _stream_tooled(
                provider, model, attempt, subset, on_token)
        except Exception as exc:
            return {"agent": desk, "ok": False, "error": str(exc)[:200],
                    "tool_trace": trace}
        if tool_calls:
            break
    for call in tool_calls:
        if calls_made >= WORKER_BUDGET:
            break
        fname = call.get("name", "")
        fn = by_name.get(fname)
        if fn is None:
            continue
        _t0 = _time.time()
        try:
            out = await fn.ainvoke(call.get("args", {}) or {})
            collected.append(out if isinstance(out, dict) else {"rows": out})
        except Exception as exc:
            out = {"tool": fname, "error": str(exc)[:160]}
            collected.append(out)
        _ms = int((_time.time() - _t0) * 1000)
        _rows = _row_count(out.get("rows")) if isinstance(out, dict) else _row_count(out)
        _st = _trace_status(out)
        _te = {
            "name": fname, "label": _desk_tool_label(fname),
            "ms": _ms, "rows": _rows, "status": _st,
        }
        _sql = _trace_sql(out)
        if _sql:
            _te["sql"] = _sql
        _err = _trace_error(out)
        if _err:
            _te["error"] = _err
        trace.append(_te)
        calls_made += 1
    ran_data_tool = any(
        isinstance(c, dict) and c.get("tool", "") not in
        ("resolve_entity", "search_nba") and _row_count(c.get("rows")) > 0
        for c in collected
    )
    if collected and not ran_data_tool and calls_made < WORKER_BUDGET:
        data_names = [t.name for t in subset
                      if t.name not in ("resolve_entity", "search_nba")]
        data_tools = [t for t in subset
                      if t.name not in ("resolve_entity", "search_nba")]
        try:
            _t2, tool_calls2 = await _stream_tooled(
                provider, model,
                [SystemMessage(content=brief + " Identity is settled, use "
                               "these ids verbatim. "
                               f"Call exactly one of these now: "
                               f"{', '.join(data_names)}. No prose."),
                 HumanMessage(content=f"Season {SEASON}. Task: {task}. "
                              f"Resolved: {str(collected)[:600]}")],
                data_tools, on_token,
            )
        except Exception as exc:
            return {"agent": desk, "ok": False, "error": str(exc)[:200],
                    "tool_trace": trace}
        for call in tool_calls2:
            if calls_made >= WORKER_BUDGET:
                break
            fn = by_name.get(call.get("name", ""))
            if fn is None:
                continue
            _t0 = _time.time()
            _cname = str(call.get("name", ""))
            try:
                out = await fn.ainvoke(call.get("args", {}) or {})
                collected.append(out if isinstance(out, dict) else {"rows": out})
            except Exception as exc:
                out = {"tool": _cname, "error": str(exc)[:160]}
                collected.append(out)
            _ms = int((_time.time() - _t0) * 1000)
            _te = {
                "name": _cname, "label": _desk_tool_label(_cname),
                "ms": _ms,
                "rows": _row_count(out.get("rows")) if isinstance(out, dict) else 0,
                "status": _trace_status(out),
            }
            _sql = _trace_sql(out)
            if _sql:
                _te["sql"] = _sql
            _err = _trace_error(out)
            if _err:
                _te["error"] = _err
            trace.append(_te)
            calls_made += 1
    has_data = any(
        isinstance(c, dict) and c.get("tool", "") not in
        ("resolve_entity", "search_nba")
        and _row_count(c.get("rows")) > 0 for c in collected
    )
    if not has_data:
        return {"agent": desk, "ok": False,
                "error": "no further detail available on that angle",
                "tool_trace": trace}
    try:
        text = await _stream_text(
            provider, model,
            [
                SystemMessage(
                    content="Summarize these findings in 5 short sentences max. "
                    "Use only numbers present in the evidence. "
                    "If the evidence has no data rows, reply exactly: NO DATA."
                ),
                HumanMessage(content=f"Task: {task}\nEvidence: {str(collected)[:8000]}"),
            ],
            on_token,
        )
    except Exception as exc:
        text = ""
        collected.append({"error": str(exc)[:160]})
    return {"agent": desk, "ok": True, "summary": text, "tables": collected,
            "tool_trace": trace}


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
    "IF the task asks for a player's impact and no RAPTOR, RAPM, or BPM "
    "row covers them, THEN call get_impact_estimate; its output is always "
    "an estimate, so say so and never present it as a measured metric. "
    "Custom math over warehouse tables goes to run_python. "
    "Confirm a player's current team from get_advanced TEAM_ABBREVIATION "
    "before any team claim. Never take a team from memory. "
    "Situational matchup splits (defense tier, home/away, rest days) over "
    "the last N games go to get_matchup_splits. Sustainability checks on "
    "a hot stat line go to get_regression_check. "
    "Streak questions (longest or active streaks, N-game streaks) go to "
    "get_streaks with the stat, threshold, and scope. "
    "Head-to-head history for one player against one opponent team "
    "(game logs, averages vs the season baseline, deltas, team record, "
    "small-sample flag) goes to get_head_to_head. "
    "Filtered game-log searches (40-point games, games vs an opponent, "
    "triple-doubles in a month, home/away or date windows) go to "
    "search_game_logs. "
    "Resolve names with resolve_entity first. Use returned ids verbatim. "
    "Never invent ids. Season 2025-26 unless told otherwise."
)

TEAM_BRIEF = (
    "You are the team desk. Report record, roster, recent games, rotations, "
    "and five-man lineups by minutes with plus-minus. "
    "Use get_lineups for five-man units. Use get_lineup_stats for lineup "
    "ratings: it hides units under 100 possessions and flags blowout-heavy "
    "minutes. Best lineup means the highest NET_RATING among units meeting "
    "the possession floor (the unit flagged is_best_net_unit and returned "
    "as best_net_unit), never the most-used unit. "
    "Use get_wowy for two-player combinations or with-or-without-you impact. "
    "For next-opponent or matchup briefs call get_scout_pack once. "
    "For a scheduled-game narrative preview (form, star matchups, injuries, "
    "x-factors, why-watch) call get_matchup_preview once; it never predicts "
    "scores. For a pre-game prediction (win probability, projected score "
    "and total) call get_game_prediction; its output is a model estimate "
    "with documented methodology, never a betting pick. "
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
    "THEN call get_elo_standings (implied win pct, win equivalents, "
    "Elo-implied spreads). "
    "IF the task mentions title odds, finals odds, or simulating the "
    "playoffs, THEN call get_playoff_sim. "
    "IF the task asks who wins an upcoming game, the win probability of a "
    "scheduled game, or a projected total, THEN call get_game_prediction "
    "(pre-game estimates; it is not a betting pick). "
    "IF the task asks for a live in-game win probability, "
    "THEN call get_win_prob. "
    "IF the task mentions overpaid, underpaid, contract value, or "
    "salary vs production, THEN call get_contract_value, passing "
    "the player name when one is named. "
    "IF the task mentions draft, prospects, or rookies, "
    "THEN call get_draft_board. "
    "IF the task mentions star probability or draft model, "
    "THEN call get_draft_model. "
    "IF the task mentions streaks (longest or active, player or team), "
    "THEN call get_streaks. "
    "IF the task asks how a player has done against one opponent team, "
    "THEN call get_head_to_head. "
    "IF the task mentions shot zones, shot diet, rim rate, corner threes, "
    "or where teams shoot from, THEN call get_team_shot_zones with teams "
    "or 'league'; its deltas are vs the league baseline in percentage points. "
    "When asked which team leads a zone, name the explicitly marked "
    "zone_leaders (highest share_delta_pp per zone), never the first row "
    "scanned. "
    "IF the task mentions form, risers, fallers, or who is hot, "
    "THEN call get_risers. Its rows are TEAM-level streaks; say so "
    "and never claim player-level risers from it. "
    "IF the task mentions trade, swap, deal, or sign-and-trade, "
    "THEN call get_trade_check with team_abbrevs and player names. "
    "IF the task asks who wins a trade, trade value, fair value, or grades, "
    "THEN call get_trade_value. "
    "If a tool reports unknown players, stop and report them exactly. "
    "Never swap in a suggested name as the requested player. "
    "IF the task mentions freshness, stale data, last updated, or data currency, "
    "THEN call get_warehouse_freshness. "
    "IF the task asks for a player's impact and no RAPTOR, RAPM, or BPM row "
    "covers them, THEN call get_impact_estimate; its output is always an "
    "estimate, so say so and never present it as a measured metric. "
    "IF the task names one stat category, THEN call get_leaders. "
    "Otherwise call get_standings."
)

# Shot-zone phrasing the league desk brief routes to get_team_shot_zones.
# The list-question force regexes below (and the _LIST_RX fast-path in
# graph.py) would otherwise hijack these into text_to_sql: the SQL answer
# is correct but takes ~30s vs the fast tool, and the purpose-built
# zone_leaders never run. Guard both force sites with this regex so the
# task falls through to the LLM brief, which already owns the routing.
_SHOT_ZONE_RX = _re.compile(
    r"shot\s*zones?|shot\s*diet|rim\s*rate|\bat\s+the\s+rim\b|"
    r"corner\s*threes?|corner\s*3s?|"
    r"efg\s*(by|per|in|across|within)\s*zones?|zone.{0,16}\befg\b|"
    r"where\s+teams?\s+shoot\s+from",
    _re.IGNORECASE,
)

def _desk_spec(name: str, task: str):
    """Shared desk configuration: (desk, brief, tool_names, force_tool).

    Used by both the LangChain tool wrappers (delegate_tools) and the
    live-streaming entry point (run_desk_streaming) so they can't drift.
    """
    if name == "delegate_scout":
        return ("scout", SCOUT_BRIEF,
                 ["resolve_entity", "search_nba", "get_player_intel", "get_raptor_history",
                  "get_impact_estimate",
                  "get_on_off", "get_wowy", "get_four_factors",
                  "get_last_x", "get_percentiles", "get_shot_zones",
                  "get_shot_compare", "get_trend", "get_comps", "get_clutch",
                  "get_playoff_intel", "get_matchup_splits",
                  "get_regression_check", "get_streaks", "get_head_to_head",
                  "search_game_logs", "get_advanced", "run_python", "text_to_sql"],
                None)
    if name == "delegate_team":
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
        return ("team", TEAM_BRIEF,
                ["resolve_entity", "search_nba", "get_team_hub", "get_games_on_date",
                 "get_boxscore", "get_lineups", "get_lineup_stats", "get_wowy", "get_injuries", "get_preview",
                 "get_matchup_preview",
                 "get_game_prediction",
                 "get_scout_pack", "get_rotation_check", "get_cap_ledger",
                 "get_team_splits", "get_injury_impact", "run_python",
                 "text_to_sql"],
                force)
    if name == "delegate_league":
        force = None
        if _re.search(r"playoff|champion|finals|\bring\b|title",
                       task, _re.IGNORECASE):
            force = "get_playoffs"
        elif (not _SHOT_ZONE_RX.search(task)
              and _re.search(
                  r"which\s+(players|teams)|what\s+(players|teams)|"
                  r"top\s+\d+|\bunder\s+\d+|\bover\s+\d+|\bage\b|"
                  r"\baverag\w*\b|\bat least\b|"
                  r"leads?\s+the\s+league|who\s+leads\b",
                  task, _re.IGNORECASE)):
            force = ("text_to_sql", {"question": task.replace(
                " Answer via text_to_sql (you own that tool).", "")})
        return ("league", LEAGUE_BRIEF,
                ["get_standings", "get_leaders", "get_injuries", "get_rapm",
                 "get_impact_estimate",
                 "get_playoffs", "get_playoff_intel", "get_ratings", "get_clutch", "get_elo",
                 "get_elo_standings",
                 "get_playoff_sim", "get_game_prediction", "get_contract_value", "get_draft_board",
                 "get_draft_model", "get_risers", "get_streaks", "get_head_to_head",
                 "get_trade_check",
                 "get_trade_value",
                 "get_award_race",
                 "get_team_shot_zones",
                 "get_warehouse_freshness",
                 "run_python", "text_to_sql"],
                force)
    raise ValueError(f"unknown desk: {name}")


async def run_desk_streaming(name: str, task: str, provider: ProviderName,
                             model: str, on_token=None) -> dict[str, Any]:
    """Direct desk entry point with live token streaming.

    Same result contract as the LangChain delegate tools, but LLM text
    chunks are forwarded to on_token (async callable) the moment they're
    generated instead of going silent for seconds.
    """
    desk, brief, tool_names, force = _desk_spec(name, task)
    return await _run_desk(desk, brief, task, provider, model, tool_names,
                           force_tool=force, on_token=on_token)


def delegate_tools(provider: ProviderName, model: str) -> list:
    @tool("delegate_scout")
    async def delegate_scout(task: str) -> dict[str, Any]:
        """Hand player research to the scout. One player per call."""
        return await run_desk_streaming("delegate_scout", task, provider, model)

    @tool("delegate_team")
    async def delegate_team(task: str) -> dict[str, Any]:
        """Hand team research to the team desk. One team per call."""
        return await run_desk_streaming("delegate_team", task, provider, model)

    @tool("delegate_league")
    async def delegate_league(task: str) -> dict[str, Any]:
        """Hand leaguewide questions to the league desk."""
        return await run_desk_streaming("delegate_league", task, provider, model)

    return [delegate_scout, delegate_team, delegate_league]
