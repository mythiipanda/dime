"""Five nodes. Typed state. Tool budget plus dedupe plus parallel exec.

Event dicts stream out in the frontend contract: node_update,
thought_stream, message, final_answer, suggestions, graph_end, error.
"""

import asyncio
import json
import re
import time
import unicodedata
from collections.abc import AsyncGenerator
from typing import Any, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage

from .providers import (
    accumulate_tool_calls,
    astream_with_fallback,
    get_llm,
    invoke_with_fallback,
    resolve_model_id,
)
from .skills import catalog as skills_catalog
from .subagents import delegate_tools, run_desk_streaming, _SHOT_ZONE_RX
from .tools import v1_tools

ANALYST_SYSTEM = (
    "You are Dime, an NBA data analyst assistant. "
    "Answer ONLY from the tool results you receive. "
    "Every number you state must appear in the evidence. "
    "Never invent streaks, averages, or ranks. "
    "Never list months, dates, or specifics absent from evidence. "
    "Round every number to 1 decimal max. Write percentages with a "
    "percent sign, never as raw decimals. Never print raw field names "
    "like ts_pct or efg_pct. "
    "Name the tool output you used. Say when data is missing. "
    "When a tool reports an error naming unknown players or missing data, "
    "say so plainly instead of claiming nothing came back. "
    "Never mention tool names, table names, SQL, or phrases like "
    "'no table to show' or 'no evidence'. Restate any error as one "
    "plain analyst sentence with names, never ids. "
    "Derive per-game numbers when totals and games are both present, "
    "showing the division. "
    "Keep answers short and specific with numbers. "
    "For player comparisons: one markdown table with 8 or more metric rows "
    "covering scoring, rebounds, assists, shooting splits, efficiency, "
    "usage, impact, and team record, "
    "then 2 to 4 takeaways each naming who leads and by how much, "
    "then one verdict per dimension covering scoring, efficiency, shot "
    "diet, clutch, impact, and team context, then one overall verdict. "
    "Name each side's team and record when present. "
    "State one number per fact, never ranges. "
    "Only cite all-in-one metrics present in evidence: RAPM-lite, on-off "
    "net, RAPTOR history. Label RAPM-lite and RAPTOR as estimates. "
    "Never invent PER, BPM, EPM, WS, VORP, or LEBRON. Say EPM is unavailable. "
    "State the season the data covers in the first line of every answer. "
    "Never name tools, tables, or query languages."
)

PLANNER_SYSTEM = (
    "You are the retrieval supervisor. Your tools: resolve_entity, "
    "get_compare, get_comps, get_preview, get_matchup_preview, get_briefing, "
    "get_trade_value, get_matchup_splits, get_regression_check, "
    "get_award_race, delegate_scout, "
    "delegate_team, delegate_league, run_python. Workers behind the delegates own "
    "every granular dataset, including text_to_sql. "
    "For players most statistically like X (comps, similar players), call "
    "get_comps directly — never improvise similarity from SQL. "
    "For who wins a trade, trade value, fair value, or trade grades, call "
    "get_trade_value directly. "
    "For performance splits (vs defense tiers, home/away, rest days), call "
    "get_matchup_splits directly. "
    "For is-it-real / sustainability / regression questions, call "
    "get_regression_check directly. "
    "For award races (MVP, DPOY, ROY, 6MOY, MIP), call get_award_race "
    "directly. "
    "For narrative game previews (form, star matchups, injuries, x-factors, "
    "why-watch), call get_matchup_preview; for score predictions use "
    "get_preview. "
    "For custom math, statistical calculations, regression, or ad-hoc queries "
    "over warehouse tables, call run_python. "
    "For filtered or ranked player lists (top-N, under an age, above "
    "stat thresholds, draft queries), call delegate_league and tell it "
    "to answer via text_to_sql. "
    "For supporting-cast questions, call run_python averaging teammate PPG "
    "from silver_leaders_pts excluding the star, joined with NET_RATING "
    "from silver_team_ratings. "
    "Delegate multi-part work (comparisons, previews, roundups) to one delegate per entity. "
    "Pass the user's question to the delegate unchanged as the task. "
    "For cross-season history delegate to the right desk and tell it to use text_to_sql. "
    "For historical draft or all-time RAPTOR player impact, query silver_hist_draft "
    "or silver_raptor_player via text_to_sql. Prefer text_to_sql over run_python "
    "for single-fact warehouse lookups; use run_python only for math. "
    "For single-season leaders, standings, injuries, playoffs, ratings, "
    "clutch, ELO, or title odds, call delegate_league. "
    "For two-player compares call get_compare first, then one "
    "delegate_scout per player for shot diet, clutch, and advanced depth. "
    "If the question asks how players did in the playoffs, call "
    "get_playoff_intel per player first. "
    "Synthesize dimension by dimension with a verdict per dimension."
    "For two-team previews call get_preview once and nothing else. "
    "If the question names a venue or home team (in, at, hosting, "
    "homestand), pass it as home_abbrev. "
    "After a composite call, make no further tool calls this turn. "
    "Resolve calls alone never answer a question. "
    "Always follow identity results with data calls in the next round. "
    "Resolve every name with resolve_entity first when the task lacks an explicit id. "
    "Never expand a nickname yourself. Pass names to tools verbatim. "
    "Id params also accept names directly and resolve internally. "
    "Use returned ids verbatim. Never invent or recall ids from memory. "
    "Never ask the user for clarification. Always call tools, using "
    "carried thread entities when the question has pronouns. "
    "Plan the SMALLEST set of calls that answers the question. "
    "Prefer one call, except comparisons, previews, and roundups, which "
    "need one call per dimension. "
    "Never repeat a call with the same args. "
    "Batch independent calls together. "
    "Call search_nba first when you lack an id. "
    "The current season is 2025-26. Pass season 2025-26 always, "
    "unless the user names a different season explicitly."
    "\n\nAnalyst skills. Match the question to one skill and follow it:\n"
    + skills_catalog()
)

MAX_TOOL_ROUNDS = 3
MAX_TOOL_CALLS = 8
DEEP_TOOL_ROUNDS = 5
DEEP_TOOL_CALLS = 12

# Patterns that trigger deep investigation mode: multi-entity comparisons,
# open-ended research questions, and explicit depth requests.
DEEP_TRIGGERS = [
    r"\bdeep dive\b", r"\binvestigat\w*\b", r"\bcomprehensive\b",
    r"\bthorough\b", r"\bcompare\b.*\b(and|vs|versus)\b.*\b(and|vs|versus)\b",
    r"\bbreak down\b", r"\bfull (report|analysis|breakdown)\b",
    r"\bwhy\b.*\b(and|also)\b.*\bhow\b",
    r"\ball\b.*\b(teams|players)\b",
    r"\brank\b.*\b(top|best)\b.*\b\d+\b",
]

TOOL_LABELS = {
    "resolve_entity": "Identifying players and teams",
    "search_nba": "Searching league coverage",
    "get_compare": "Comparing players",
    "delegate_scout": "Scouting players",
    "delegate_team": "Scouting teams",
    "delegate_league": "Scanning league data",
    "run_python": "Crunching numbers",
    "text_to_sql": "Querying the warehouse",
    "get_playoff_intel": "Pulling playoff logs",
    "get_trade_check": "Checking trade math",
    "get_trade_value": "Grading trade value",
    "get_award_race": "Ranking award races",
    "get_matchup_preview": "Previewing the matchup",
    "get_game_prediction": "Simulating the matchup",
    "get_briefing": "Briefing the slate",
    "get_lineup_stats": "Rating lineups",
    "get_streaks": "Finding streaks",
    "get_head_to_head": "Checking head-to-head history",
    "get_team_shot_zones": "Mapping shot zones",
    "get_warehouse_freshness": "Checking warehouse freshness",
    "get_elo_standings": "Computing ELO ratings",
    "get_impact_estimate": "Estimating impact",
}


def tool_label(name: str) -> str:
    if not name:
        return "Checking data"
    if name in TOOL_LABELS:
        return TOOL_LABELS[name]
    return name.replace("_", " ").strip().title() or "Checking data"


def _tool_names_from_calls_made(calls_made: list[str]) -> list[str]:
    names: list[str] = []
    for key in calls_made or []:
        name = key.partition(":")[0].strip()
        if name and name not in names:
            names.append(name)
    return names


def _friendly_progress(names: list[str]) -> str:
    labels: list[str] = []
    for name in names or []:
        label = tool_label(name)
        if label not in labels:
            labels.append(label)
    if not labels:
        return "Reviewing evidence"
    return " and ".join(sorted(labels))


def _args_summary(name: str, args: dict[str, Any] | None) -> str:
    args = args or {}
    if (name or "").startswith("delegate_"):
        task = str(args.get("task", ""))
        return task[:140] if task else name
    if name in ("run_python", "text_to_sql"):
        return "Warehouse query"
    try:
        parts = [f"{k}={v}" for k, v in args.items()]
        return ", ".join(parts)[:140] or name
    except Exception:
        return name


def _result_rows(result: dict[str, Any]) -> int:
    rows = result.get("rows", None)
    if isinstance(rows, list):
        return len(rows)
    if isinstance(rows, dict):
        total = 0
        for value in rows.values():
            if isinstance(value, list):
                total += len(value)
            elif value:
                total += 1
        return total
    tables = result.get("tables")
    if isinstance(tables, list):
        total = 0
        for table in tables:
            if isinstance(table, dict):
                total += _result_rows(table)
            elif isinstance(table, list):
                total += len(table)
            elif table:
                total += 1
        return total
    if rows is None:
        return 0
    return 1 if rows else 0


def _result_status(result: dict[str, Any]) -> str:
    if result.get("ok") is False:
        return "fail"
    if result.get("error"):
        return "fail"
    return "ok"

_LEAGUE_RX = re.compile(
    r"playoff|champion|finals|leader|standing|injur|clutch|\brating\b|"
    r"elo|title odds|streak|versus|power rank|net rating|"
    r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b", re.IGNORECASE)
_COMPARE_RX = re.compile(
    r"\bvs\.?\b|\bversus\b|\bcompare\b", re.IGNORECASE)
_LIST_RX = re.compile(
    r"which\s+(players|teams)|what\s+(players|teams)|top\s+\d+|"
    r"\bunder\s+\d+|\bover\s+\d+|\bage\b|"
    r"\baverag\w*\b|\bat least\b|"
    r"leads?\s+the\s+league|who\s+leads\b", re.IGNORECASE)
_COMPS_RX = re.compile(
    r"\bmost\s+like\b|\bplays?\s+like\b|\bstatistically\s+similar\b|"
    r"\bsimilar\s+players?\b|\bclosest\s+comps?\b|"
    r"\bcomparable\s+players?\b|\bplayer\s+comps?\b",
    re.IGNORECASE)
_PREDICT_RX = re.compile(
    r"who\s+(wins|will\s+win|is\s+going\s+to\s+win)|"
    r"who\s+do\s+you\s+(have|like)|"
    r"\bwin\s+prob\w*\b|"
    r"\bprojected\s+(total|score)\b|"
    r"\bpre[\s-]?game\s+(monte\s*carlo|prediction|estimate)|"
    r"\bmonte\s*carlo\b|"
    r"\bpredict(?:s|ed|ing)?\s+(?:the\s+)?(?:score|winner|game|matchup)\b|"
    r"\bchances?\s+of\s+winning\b|"
    r"\bfavor\w*\b",
    re.IGNORECASE)
# Live in-game probability and season-title questions are not pre-game
# predictions: they belong to get_win_prob / the league desk.
_PREDICT_LIVE_RX = re.compile(r"\blive\b|\bin[\s-]*game\b", re.IGNORECASE)
_PREDICT_TITLE_RX = re.compile(
    r"championship|\btitle\b|\bfinals\b|\bring\b", re.IGNORECASE)
# Unambiguous impact-estimate phrasing: an estimate/impact pairing
# within one clause ("estimate X's impact", "his estimated per-100
# impact"), or "how good has/is [player]". RAPTOR/WAR/peak/career-arc
# phrasing is deliberately NOT here: the raptor fast-path claims those.
_IMPACT_RX = re.compile(
    r"\bestimat\w+.{0,48}\bimpact\b|\bimpact\b.{0,48}\bestimat\w+|"
    r"\bhow\s+good\s+(?:has|is|was)\b",
    re.IGNORECASE)
_BRIEFING_RX = re.compile(r"\bbriefing\b", re.IGNORECASE)
_BRIEFING_CONTEXT_RX = re.compile(
    r"20\d\d[-/]\d{1,2}[-/]\d{1,2}|\bslate\b|\bmorning\b|"
    r"\btoday\b|\byesterday\b|\btomorrow\b",
    re.IGNORECASE)

_entity_cache: dict[str, Any] | None = None


def _entity_lists() -> tuple[list[dict], list[dict]]:
    global _entity_cache
    if _entity_cache is None:
        from nba_api.stats.static import players, teams

        _entity_cache = {"players": players.get_players(),
                         "teams": teams.get_teams()}
    return _entity_cache["players"], _entity_cache["teams"]


def _detect_entities(question: str) -> tuple[list[str], list[str]]:
    import unicodedata as _ud

    from .tools._core import NICKNAMES

    def _norm(s: str) -> str:
        return "".join(c for c in _ud.normalize("NFKD", s or "")
                       if not _ud.combining(c)).lower()

    q = question.lower()
    for nick, full in NICKNAMES.items():
        if re.search(r"\b" + re.escape(nick) + r"\b", q):
            q += " " + full.lower()
    nq = _norm(q)
    players, teams = _entity_lists()
    found_p = [p["full_name"] for p in players
               if p.get("full_name", "") and _norm(p["full_name"]) in nq]
    found_t = []
    race_words = re.search(
        r"magic number|standings|playoff race|\bseed\b|tanking|lottery",
        q)
    for t in teams:
        full = t.get("full_name", "")
        nick = full.split()[-1].lower() if full else ""
        city = (t.get("city") or "").lower()
        if (full.lower() in q
                or (nick and not race_words
                    and re.search(r"\b" + re.escape(nick) + r"\b", q))
                or (city and not race_words
                    and re.search(r"\b" + re.escape(city) + r"\b", q))
                or re.search(r"\b" + re.escape(t.get("abbreviation", "")) + r"\b",
                             question, re.IGNORECASE)):
            found_t.append(full)
    return found_p, found_t


def _expand_nicknames(question: str) -> str:
    from .tools._core import NICKNAMES

    out = question
    lowered = out.lower()
    for nick in sorted(NICKNAMES, key=len, reverse=True):
        full = NICKNAMES[nick]
        if full.lower() in lowered:
            continue
        out = re.sub(r"\b" + re.escape(nick) + r"\b", full, out,
                     flags=re.IGNORECASE)
        lowered = out.lower()
    return out


def _direct_named_teams(question: str, found_t: list[str]) -> list[str]:
    """Teams named outright in the question text.

    _detect_entities expands nicknames before matching, so a city word
    in the expansion can pull in a same-city rival the user never named
    ("Lakers" -> "Los Angeles" -> Clippers). The prediction fast-path
    needs exactly the two teams the user asked about, so re-match
    against the raw question.
    """
    from nba_api.stats.static import teams as _static_teams

    abbr_of = {t["full_name"]: t["abbreviation"]
               for t in _static_teams.get_teams()}
    q = question or ""
    out = []
    for full in found_t:
        nick = full.split()[-1].lower()
        abbr = (abbr_of.get(full) or "").lower()
        if (full.lower() in q.lower()
                or re.search(r"\b" + re.escape(nick) + r"\b", q,
                             re.IGNORECASE)
                or (abbr and re.search(r"\b" + re.escape(abbr) + r"\b",
                                       q, re.IGNORECASE))):
            out.append(full)
    return out


def _player_team_abbr(pid: int, season: str) -> str:
    """Current team abbrev for a player from warehouse gamelog MATCHUP."""
    import time as _time

    from . import store

    for _ in range(3):
        try:
            con = store.connect()
            try:
                rows = con.execute(
                    "SELECT MATCHUP FROM silver_player_gamelogs"
                    " WHERE _season = ? AND _entity = ? LIMIT 40",
                    [season, f"player:{pid}"],
                ).fetchall()
            finally:
                con.close()
            from collections import Counter as _Counter

            c = _Counter(str(r[0] or "").split(" ")[0] for r in rows)
            c.pop("", None)
            if c:
                return c.most_common(1)[0][0]
            return ""
        except Exception:
            _time.sleep(0.2)
    return ""


def _trade_sides(question: str, found_p: list[str], found_t: list[str],
                 season: str) -> dict[str, str] | None:
    """Deterministic trade sides: players grouped by current team abbrev."""
    from nba_api.stats.static import teams as _static

    from .tools._core import coerce_player_id

    def _fold(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                       if not unicodedata.combining(c)).lower()

    raw_q = _fold(question)
    named = []
    for p in found_p:
        low = _fold(p)
        last = low.split()[-1]
        if low in raw_q or re.search(r"\b" + re.escape(last) + r"\b", raw_q):
            named.append(p)
    found_p = named
    q = question.lower()
    abbr_of = {t["full_name"]: t["abbreviation"] for t in _static.get_teams()}
    nick_of = {t["full_name"].split()[-1].lower(): t["abbreviation"]
               for t in _static.get_teams()}
    order: list[str] = []

    def _abbr(full: str) -> str:
        if full in abbr_of:
            return abbr_of[full]
        return nick_of.get(full.split()[-1].lower(), "")

    mentioned = [a for a in (_abbr(f) for f in found_t) if a]
    by_team: dict[str, list[str]] = {}
    for p in found_p:
        try:
            pid = coerce_player_id(p)
        except Exception:
            continue
        ab = _player_team_abbr(pid, season) if pid else ""
        if not ab:
            continue
        by_team.setdefault(ab, []).append(p)
    for a in mentioned:
        by_team.setdefault(a, [])
        if a not in order:
            order.append(a)
    for a in by_team:
        if a not in order:
            order.append(a)
    if len(order) < 2:
        return None
    side_a, side_b = order[0], order[1]
    players_a = by_team.get(side_a, [])
    players_b = by_team.get(side_b, [])
    if not players_a or not players_b:
        rest = [p for p in found_p
                if p not in players_a and p not in players_b]
        for i, p in enumerate(rest):
            (players_a if i % 2 == 0 else players_b).append(p)
    if not players_a or not players_b:
        return None
    return {"team_a": side_a, "players_a": ", ".join(players_a),
            "team_b": side_b, "players_b": ", ".join(players_b)}


def _triage_plan_text(question: str, found_p: list[str],
                        found_t: list[str], has_history: bool) -> str:
    names = (found_p or []) + (found_t or [])
    prefix = f"Found {', '.join(names[:3])} — " if names else ""
    q = question or ""
    is_trade = bool(re.search(r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b|\bdeal\b",
                              q, re.IGNORECASE))
    is_cast = bool(re.search(
        r"supporting cast|\bcast\b|teammates?|rotation depth|"
        r"around (him|her|them)|better team\b|deeper team\b",
        q, re.IGNORECASE))
    is_raptor = bool(found_p and re.search(
        r"\braptor\b|\bwar\b|peak|all-time|all time|greatest season|"
        r"best season|career (arc|trajectory|history|impact)|"
        r"\btrajectory\b|\barc\b|over time|aging|development curve",
        q, re.IGNORECASE))
    is_compare = bool(_COMPARE_RX.search(q))
    if is_trade:
        return prefix + "checking trade math in the warehouse."
    if len(found_t) == 1 and re.search(
            r"last \d+ seasons|each of the last|past \d+ seasons|"
            r"across the last|last three seasons", q, re.IGNORECASE):
        return prefix + "pulling recent seasons from the warehouse."
    if found_p and is_cast:
        return prefix + "comparing supporting casts in the warehouse."
    if is_raptor:
        return prefix + "pulling RAPTOR history from the warehouse."
    if (_LIST_RX.search(q) and not is_trade and not is_cast
            and not is_compare and not is_raptor):
        return prefix + "asking the league desk to scan the warehouse."
    if has_history and ((not found_p) or (not found_t)):
        return prefix + "using thread context to seed scout and team desks."
    if found_p and not found_t:
        return prefix + "asking the scout desk to pull advanced metrics."
    if found_t and not found_p:
        return prefix + "asking the team desk to pull record and ratings."
    if _LEAGUE_RX.search(q):
        return prefix + "asking the league desk to scan the warehouse."
    return prefix + "planning warehouse lookups."


def _delegate_result_summary(out: dict[str, Any]) -> str | None:
    try:
        s = out.get("summary")
        return str(s)[:200] if s else None
    except Exception:
        return None


async def _stream_planner(tooled, messages: list,
                         holder: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
    """Stream the supervisor planner's raw tokens live as thought_token events.

    The planner is tool-bound: text chunks stream immediately while
    tool_call_chunks accumulate. The final tool-call list lands in
    holder["calls"]. Falls back to blocking ainvoke if streaming fails.
    """
    tc_chunks: list[dict] = []
    try:
        async for chunk in tooled.astream(messages):
            t = getattr(chunk, "content", "") or ""
            if t:
                yield _event("thought_token", {"node": "data_retrieval",
                                               "text": str(t)})
            for tc in getattr(chunk, "tool_call_chunks", None) or []:
                tc_chunks.append(dict(tc) if isinstance(tc, dict) else tc)
        holder["calls"] = accumulate_tool_calls(tc_chunks)
    except Exception:
        resp = await tooled.ainvoke(messages)
        t = getattr(resp, "content", "") or ""
        if t:
            yield _event("thought_token", {"node": "data_retrieval",
                                           "text": str(t)})
        holder["calls"] = getattr(resp, "tool_calls", None) or []


def _spawn(coro, *, name=None):
    """Schedule a coroutine as a background asyncio.Task.

    asyncio.create_task() only accepts coroutines. Passing the Future
    returned by asyncio.gather() raises "TypeError: a coroutine was
    expected, got <_GatheringFuture pending>". Every spawn site in this
    module goes through this helper so a Future can never leak into
    create_task again.
    """
    if not asyncio.iscoroutine(coro):
        raise TypeError(
            "_spawn() requires a coroutine, got "
            f"{type(coro).__name__}; wrap asyncio.gather(...) in an "
            "'async def' or await the Future directly")
    return asyncio.create_task(coro, name=name)


async def _run_delegate_live(name: str, task: str, primary: str, model: str,
                             holder: dict[str, Any],
                             node: str = "data_retrieval") -> AsyncGenerator[dict[str, Any], None]:
    """Run a delegate desk, yielding thought_token SSE events live as the
    desk's LLM generates text. The desk's final result dict is stored in
    holder["result"] when the generator is exhausted.

    Uses a queue + background task so tokens flow the moment they're
    generated instead of going silent for the seconds the desk works.
    """
    q: asyncio.Queue = asyncio.Queue()
    desk = name.replace("delegate_", "")

    async def _on_tok(t: str) -> None:
        await q.put(t)

    async def _runner() -> None:
        try:
            holder["result"] = await run_desk_streaming(
                name, task, primary, model, on_token=_on_tok)  # type: ignore[arg-type]
        except Exception as exc:
            holder["result"] = {"tool": name, "ok": False,
                                "error": str(exc)[:200]}
        finally:
            await q.put(None)

    runner = _spawn(_runner(), name="delegate-live")
    while True:
        tok = await q.get()
        if tok is None:
            break
        yield _event("thought_token", {"node": node, "text": tok,
                                       "agent": desk})
    await runner


def _trace_replay_events(out: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        trace = out.get("tool_trace") or []
    except Exception:
        return []
    if not isinstance(trace, list):
        return []
    agent = ""
    try:
        agent = str(out.get("agent") or "")
    except Exception:
        agent = ""
    events: list[dict[str, Any]] = []
    for te in trace:
        if not isinstance(te, dict):
            continue
        tname = str(te.get("name") or "")
        if not tname:
            continue
        tlabel = str(te.get("label") or tool_label(tname))
        tagent = str(te.get("agent") or agent or
                     tname.replace("delegate_", ""))
        events.append(_event("tool_call", {
            "node": "data_retrieval", "name": tname,
            "label": tlabel, "agent": tagent,
        }))
        tstatus = te.get("status") or "ok"
        terr = None
        try:
            if tstatus != "ok" and te.get("error"):
                terr = str(te.get("error"))[:160]
        except Exception:
            terr = None
        rdata: dict[str, Any] = {
            "node": "data_retrieval", "name": tname,
            "label": tlabel, "status": tstatus,
            "rows": te.get("rows", 0), "ms": te.get("ms", 0),
            "agent": tagent,
        }
        tsql = te.get("sql")
        if isinstance(tsql, str) and tsql.strip():
            rdata["sql"] = tsql.strip()
        if terr:
            rdata["error"] = terr
        events.append(_event("tool_result", rdata))
    return events


def _done_thought(label: str, out: dict[str, Any], ms: int) -> str:
    try:
        rows = _result_rows(out)
    except Exception:
        rows = 0
    ok = _result_status(out) == "ok"
    tail = f"{rows} row{'s' if rows != 1 else ''} in {ms}ms" if ok else "failed"
    return f"{label} — {tail}."


def _tool_result_payload(node: str, name: str, out: dict[str, Any], ms: int,
                         summary: str | None = None) -> dict[str, Any]:
    """Build the SSE tool_result payload for one tool execution.

    Lifts the executed SQL off the tool output (top-level ``sql``, falling
    back to ``meta.sql``) so the UI can show the exact query behind a number.
    """
    status = _result_status(out)
    payload: dict[str, Any] = {
        "node": node, "name": name, "label": tool_label(name),
        "status": status, "rows": _result_rows(out), "ms": ms,
    }
    if summary:
        payload["summary"] = summary
    try:
        sql = out.get("sql")
        if not sql and isinstance(out.get("meta"), dict):
            sql = out["meta"].get("sql")
        sql = str(sql or "").strip()
    except Exception:
        sql = ""
    if sql:
        payload["sql"] = sql
    if status != "ok":
        try:
            payload["error"] = str(out.get("error"))[:160]
        except Exception:
            payload["error"] = "failed"
    return payload


async def _triage_tool(name: str, args: dict[str, Any], state: dict,
                       holder: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
    """Run one v1 tool from triage, emitting tool_call/tool_result/thought_stream.

    Appends the result to state and stashes it in holder["out"]. Every
    status is grounded in the real tool result; nothing is canned.
    """
    from .tools import v1_tools

    fn = next((t for t in v1_tools if t.name == name), None)
    label = tool_label(name)
    t0 = time.time()
    yield _event("tool_call", {
        "node": "data_retrieval", "name": name, "label": label,
        "summary": _args_summary(name, args),
    })
    try:
        out = await fn.ainvoke(args) if fn is not None else {
            "tool": name, "ok": False, "error": "unknown tool"}
    except Exception as exc:
        out = {"tool": name, "ok": False, "error": str(exc)[:160]}
    if not isinstance(out, dict):
        out = {"tool": name, "rows": out}
    ms = int((time.time() - t0) * 1000)
    rd = _tool_result_payload("data_retrieval", name, out, ms)
    yield _event("tool_result", rd)
    yield _event("thought_stream", {
        "node": "data_retrieval",
        "text": _done_thought(label, out, ms),
    })
    state["tool_results"].append(out)
    state["calls_made"].append(name + ":" + json.dumps(args, sort_keys=True))
    holder["out"] = out


async def _triage_terminal(question: str,
                           state: dict) -> AsyncGenerator[dict[str, Any], None]:
    """End retrieval after a decisive triage hit.

    Marks planner rounds exhausted so run_chat skips the supervisor loop,
    and closes the data_retrieval window run_chat opened. Call only when
    the evidence already answers the question; the planner fallback stays
    for anything uncertain.
    """
    state["round"] = (DEEP_TOOL_ROUNDS if _is_deep_question(question)
                      else MAX_TOOL_ROUNDS)
    yield _event("node_update", {"node": "data_retrieval", "status": "complete"})


async def _triage_seed(question: str, primary: str, model: str,
                       state: dict) -> AsyncGenerator[dict[str, Any], None]:
    found_p, found_t = _detect_entities(question)
    yield _event("thought_stream", {
        "node": "data_retrieval",
        "text": _triage_plan_text(question, found_p, found_t, bool(state.get("history"))),
    })
    is_compare = bool(_COMPARE_RX.search(question))
    is_trade = bool(re.search(r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b|\bdeal\b",
                              question, re.IGNORECASE))
    is_cast = bool(re.search(
        r"supporting cast|\bcast\b|teammates?|rotation depth|"
        r"around (him|her|them)|better team\b|deeper team\b",
        question, re.IGNORECASE))
    is_predict = (
        len(found_t) >= 2
        and _PREDICT_RX.search(question)
        and not is_trade
        and not is_cast
        and not _PREDICT_LIVE_RX.search(question)
        and not _PREDICT_TITLE_RX.search(question)
        and not state.get("history")
    )
    if is_predict:
        # Pre-game prediction phrasing ("who wins", "win probability",
        # "projected total"): get_game_prediction owns the Monte Carlo.
        # The supervisor's toolset exposes get_preview ("Side-by-side
        # preview of two teams") but not get_game_prediction, so without
        # this the routing detours to get_preview and the desk briefs'
        # IF/THEN lines never get a vote. Only on clean single-turn
        # questions; anything uncertain falls through to the planner.
        _named = _direct_named_teams(question, found_t)
        if len(_named) == 2:
            _ph: dict[str, Any] = {}
            async for _e in _triage_tool(
                    "get_game_prediction",
                    {"a": _named[0], "b": _named[1]}, state, _ph):
                yield _e
            _pout = _ph.get("out") or {}
            if _result_status(_pout) == "ok":
                # _triage_tool appended the raw tool dict. analytics_agent
                # only treats tool_results entries with a non-empty "rows"
                # key as evidence, so wrap it the same way other triage
                # paths do; otherwise the turn falls into the canned
                # no-data branch and the LLM never runs.
                if state["tool_results"] and state["tool_results"][-1] is _pout:
                    state["tool_results"][-1] = {
                        "tool": "get_game_prediction", "rows": [_pout]}
                async for _e in _triage_terminal(question, state):
                    yield _e
            return
    if ((len(found_p) >= 2 or len(found_t) >= 2 or is_compare)
            and not (is_trade and not is_compare)
            and not (is_cast and not is_compare)):
        return
    if is_trade:
        season = "2025-26"
        m = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if m:
            season = f"{m.group(1)}-{m.group(2)}"
        sides = _trade_sides(question, found_p, found_t, season)
        if sides:
            from .tools import v1_tools

            fn = next((t for t in v1_tools if t.name == "get_trade_check"),
                      None)
            if fn is not None:
                _tname = "get_trade_check"
                _tlabel = tool_label(_tname)
                _t0 = time.time()
                yield _event("tool_call", {
                    "node": "data_retrieval", "name": _tname,
                    "label": _tlabel,
                    "summary": _args_summary(_tname, sides),
                })
                try:
                    out = await fn.ainvoke(sides)
                except Exception as exc:
                    out = {"tool": "get_trade_check", "ok": False,
                           "error": str(exc)[:160]}
                if not isinstance(out, dict):
                    out = {"tool": "get_trade_check", "rows": out}
                _ms = int((time.time() - _t0) * 1000)
                _rd: dict[str, Any] = _tool_result_payload(
                    "data_retrieval", _tname, out, _ms)
                yield _event("tool_result", _rd)
                yield _event("thought_stream", {
                    "node": "data_retrieval",
                    "text": _done_thought(_tlabel, out, _ms),
                })
                state["tool_results"].append(out)
                state["calls_made"].append("get_trade_check:" + json.dumps(
                    sides, sort_keys=True))
                return
    if len(found_t) == 1 and re.search(
            r"last \d+ seasons|each of the last|past \d+ seasons|"
            r"across the last|last three seasons",
            question, re.IGNORECASE):
        from nba_api.stats.static import teams as _static_teams

        full = found_t[0]
        nick = full.split()[-1] if full else ""
        code = (
            "rows = con.execute(\"SELECT _season, WINS, LOSSES "
            "FROM silver_standings WHERE TeamName IN ('"
            + nick.replace("'", "") + "', '" + full.replace("'", "")
            + "') ORDER BY _season DESC LIMIT 5\").fetchall()\n"
            "for _s, _w, _l in rows:\n"
            "    print(f\"{_s}: {_w} wins, {_l} losses (regular season)\")\n"
            "out = [{\"season\": _s, \"wins\": _w, \"losses\": _l} "
            "for _s, _w, _l in rows]"
        )
        _tp_args = {"code": code}
        _t0 = time.time()
        yield _event("tool_call", {
            "node": "data_retrieval", "name": "run_python",
            "label": tool_label("run_python"),
            "summary": _args_summary("run_python", _tp_args),
        })
        try:
            from .tools import v1_tools as _vt

            fn = next((t for t in _vt if t.name == "run_python"), None)
            out = await fn.ainvoke({"code": code}) if fn is not None else {
                "tool": "run_python", "ok": False, "error": "no python tool"}
        except Exception as exc:
            out = {"tool": "run_python", "ok": False, "error": str(exc)[:160]}
        if not isinstance(out, dict):
            out = {"tool": "run_python", "rows": out}
        _ms = int((time.time() - _t0) * 1000)
        _rd = _tool_result_payload("data_retrieval", "run_python", out, _ms)
        yield _event("tool_result", _rd)
        yield _event("thought_stream", {
            "node": "data_retrieval",
            "text": _done_thought(tool_label("run_python"), out, _ms),
        })
        state["tool_results"].append(out)
        state["calls_made"].append("run_python:" + json.dumps(
            {"code": code[:120]}, sort_keys=True))
        return
    if len(found_p) >= 1 and re.search(
            r"supporting cast|\bcast\b|teammates?|rotation depth|"
            r"around (him|her|them)|help (does|do|has|have)\b|"
            r"better team\b|deeper team\b",
            question, re.IGNORECASE):
        from .tools._core import coerce_player_id as _cp2

        sides = []
        for p in found_p[:2]:
            try:
                _pid = _cp2(p)
                _ab = _player_team_abbr(_pid, "2025-26") if _pid else ""
            except Exception:
                _pid, _ab = 0, ""
            if _ab:
                sides.append((p, _ab))
        if sides:
            from nba_api.stats.static import teams as _st

            lines = ["print('Supporting cast comparison, 2025-26 regular season')"]
            for p, ab in sides:
                last = p.split()[-1].replace("'", "")
                safe = "".join(
                    c for c in unicodedata.normalize("NFKD", p)
                    if not unicodedata.combining(c)).replace("'", "")
                lines.append(f"print('{safe} plays for {ab} this season')")
                full = next((t["full_name"] for t in _st.get_teams()
                             if t["abbreviation"] == ab), ab)
                nick = full.split()[-1].replace("'", "")
                lines.append(
                    f"_t_{ab} = con.execute(\"SELECT TEAM_NAME, NET_RATING FROM "
                    f"silver_team_ratings WHERE _season='2025-26' AND "
                    f"(TEAM_NAME = '{nick}' OR TEAM_NAME = '{full}') "
                    f"LIMIT 1\").fetchall()")
                lines.append(
                    f"_mates_{ab} = con.execute(\"SELECT PLAYER, PTS, GP FROM "
                    f"silver_leaders_pts WHERE _season='2025-26' AND TEAM='{ab}' "
                    f"AND UPPER(PLAYER) NOT LIKE '%{last.upper()}%' "
                    f"ORDER BY PTS DESC LIMIT 4\").fetchall()")
                lines.append(
                    f"_adv_{ab} = con.execute(\"SELECT PLAYER_NAME, TS_PCT, "
                    f"NET_RATING FROM silver_advanced WHERE _season='2025-26' "
                    f"AND TEAM_ABBREVIATION='{ab}'\").fetchall()")
                lines.append(
                    f"_admap_{ab} = {{str(r[0]): (r[1], r[2]) "
                    f"for r in _adv_{ab}}}")
                lines.append(
                    f"print('{safe} ({ab}) team net: ' + str(_t_{ab}))")
                lines.append(
                    f"print('{ab} supporting mates (excluding {safe}):')")
                lines.append(
                    f"for m in _mates_{ab}:\n"
                    f"    _nm = str(m[0]).encode('ascii', 'ignore').decode()\n"
                    f"    _ppg = m[1]/max(m[2], 1)\n"
                    f"    _pair = _admap_{ab}.get(m[0], (None, None))\n"
                    f"    _ts = _pair[0]\n"
                    f"    _nr = _pair[1]\n"
                    f"    _tss = f'{{_ts*100:.1f}}%' if _ts is not None else 'n/a'\n"
                    f"    _nrs = f'{{_nr:+.1f}}' if _nr is not None else 'n/a'\n"
                    f"    print(f'  {{_nm}}: {{_ppg:.1f}} ppg, TS {{_tss}} net {{_nrs}}')")
                lines.append(
                    f"_best_{ab} = max([m[1]/max(m[2],1) for m in _mates_{ab}] "
                    f"+ [0])")
                lines.append(
                    f"print('Top {ab} supporting scorer ({safe} excluded): ' "
                    f"+ str(round(_best_{ab}, 1)) + ' ppg')")
                lines.append(
                    f"_tslist_{ab} = [_admap_{ab}.get(m[0], "
                    f"(None, None))[0] for m in _mates_{ab}]")
                lines.append(
                    f"_tsvals_{ab} = [v for v in _tslist_{ab} "
                    f"if v is not None]")
                lines.append(
                    f"print('{ab} cast-average TS%: ' + "
                    f"(f'{{sum(_tsvals_{ab})/len(_tsvals_{ab})*100:.1f}}%' "
                    f"if _tsvals_{ab} else 'n/a'))")
        if sides:
            lines.append("out = 'cast table printed'")
            code = "\n".join(lines)
            _cast_args = {"code": code}
            _t0 = time.time()
            yield _event("tool_call", {
                "node": "data_retrieval", "name": "run_python",
                "label": tool_label("run_python"),
                "summary": _args_summary("run_python", _cast_args),
            })
            try:
                from .tools import v1_tools as _vt2

                fn2 = next((t for t in _vt2 if t.name == "run_python"), None)
                out = await fn2.ainvoke({"code": code}) if fn2 is not None else {
                    "tool": "run_python", "ok": False, "error": "no python tool"}
            except Exception as exc:
                out = {"tool": "run_python", "ok": False,
                       "error": str(exc)[:160]}
            if not isinstance(out, dict):
                out = {"tool": "run_python", "rows": out}
            _ms = int((time.time() - _t0) * 1000)
            _rd = _tool_result_payload("data_retrieval", "run_python", out, _ms)
            yield _event("tool_result", _rd)
            yield _event("thought_stream", {
                "node": "data_retrieval",
                "text": _done_thought(tool_label("run_python"), out, _ms),
            })
            state["tool_results"].append(out)
            state["calls_made"].append("run_python:" + json.dumps(
                {"code": code[:120]}, sort_keys=True))
            return
    if found_p and re.search(
            r"\braptor\b|\bwar\b|peak|all-time|all time|greatest season|"
            r"best season|career (arc|trajectory|history|impact)|"
            r"\btrajectory\b|\barc\b|over time|aging|development curve",
            question, re.IGNORECASE):
        try:
            from .tools import v1_tools as _vt3

            fn3 = next((t for t in _vt3 if t.name == "get_raptor_history"),
                       None)
            for p in found_p[:2]:
                _rh_args = {"player": p}
                _t0 = time.time()
                yield _event("tool_call", {
                    "node": "data_retrieval", "name": "get_raptor_history",
                    "label": tool_label("get_raptor_history"),
                    "summary": _args_summary("get_raptor_history", _rh_args),
                })
                try:
                    out = await fn3.ainvoke({"player": p}) if fn3 is not None else {
                        "tool": "get_raptor_history", "ok": False,
                        "error": "no raptor tool"}
                except Exception as exc:
                    out = {"tool": "get_raptor_history", "ok": False,
                           "error": str(exc)[:160]}
                if not isinstance(out, dict):
                    out = {"tool": "get_raptor_history", "rows": out}
                _ms = int((time.time() - _t0) * 1000)
                _rd = _tool_result_payload(
                    "data_retrieval", "get_raptor_history", out, _ms)
                yield _event("tool_result", _rd)
                yield _event("thought_stream", {
                    "node": "data_retrieval",
                    "text": _done_thought(
                        tool_label("get_raptor_history"), out, _ms),
                })
                state["tool_results"].append(out)
                state["calls_made"].append("get_raptor_history:" + json.dumps(
                    {"player": p}, sort_keys=True))
            return
        except Exception:
            pass
    is_impact = bool(
        found_p and _IMPACT_RX.search(question)
        and not is_compare and not is_trade and not is_cast
        and not state.get("history"))
    if is_impact:
        # Unambiguous impact-estimate phrasing ("estimate X's impact",
        # "how good has [player] been"): get_impact_estimate answers it
        # directly. Without this the question detours to delegate_scout,
        # whose brief only routes impact to get_raptor_history, and the
        # desk improvises impact numbers from raw net ratings.
        # RAPTOR/WAR/peak/career phrasing is claimed by the raptor
        # fast-path above and never reaches this block. Only on clean
        # single-turn questions; anything uncertain falls through to the
        # planner.
        _ih: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_impact_estimate", {"player": found_p[0]}, state, _ih):
            yield _e
        _iout = _ih.get("out") or {}
        if _result_status(_iout) == "ok":
            # _triage_tool appended the raw tool dict. analytics_agent
            # only treats tool_results entries with a non-empty "rows"
            # key as evidence, so wrap it the same way the prediction
            # fast-path does; otherwise the turn falls into the canned
            # no-data branch and the LLM never runs.
            if state["tool_results"] and state["tool_results"][-1] is _iout:
                state["tool_results"][-1] = {
                    "tool": "get_impact_estimate", "rows": [_iout]}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    is_comps = bool(found_p and _COMPS_RX.search(question))
    if is_comps and not is_trade and not is_cast and not is_compare:
        # "players like X" phrasing: get_comps answers directly. Routing
        # through delegate_league first wastes a desk plus planner rounds
        # improvising similarity from SQL.
        _decisive = True
        for p in found_p[:2]:
            _ch: dict[str, Any] = {}
            async for _e in _triage_tool(
                    "get_comps", {"player_id": p}, state, _ch):
                yield _e
            _cout = _ch.get("out") or {}
            if _result_status(_cout) != "ok" or not _result_rows(_cout):
                _decisive = False
        if _decisive:
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    if (_BRIEFING_RX.search(question) and _BRIEFING_CONTEXT_RX.search(question)
            and not is_trade and not is_cast and not is_compare):
        # Slate/morning briefing: get_briefing owns the scoreboard. A date
        # in the question pins the day; otherwise the tool defaults to
        # yesterday.
        _bm = re.search(r"(20\d\d)[-/](\d{1,2})[-/](\d{1,2})", question)
        _bdate = ""
        if _bm:
            _bdate = (f"{int(_bm.group(2)):02d}/"
                      f"{int(_bm.group(3)):02d}/{_bm.group(1)}")
        _bh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_briefing", {"game_date": _bdate}, state, _bh):
            yield _e
        _bout = _bh.get("out") or {}
        _brows = _bout.get("rows") if isinstance(_bout, dict) else None
        _bgames = _brows.get("games") if isinstance(_brows, dict) else None
        if _result_status(_bout) == "ok" and _bgames:
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    delegates = {t.name: t for t in delegate_tools(primary, model)}  # type: ignore[arg-type]
    is_raptor = bool(found_p and re.search(
        r"\braptor\b|\bwar\b|peak|all-time|all time|greatest season|"
        r"best season|career (arc|trajectory|history|impact)|"
        r"\btrajectory\b|\barc\b|over time|aging|development curve",
        question, re.IGNORECASE))
    if (_LIST_RX.search(question) and not is_trade and not is_cast
            and not is_compare and not is_raptor
            and not _SHOT_ZONE_RX.search(question)
            and "delegate_league" in delegates):
        task = (question + " Answer via text_to_sql (you own that tool).")
        _dl_args = {"task": task}
        _t0 = time.time()
        yield _event("tool_call", {
            "node": "data_retrieval", "name": "delegate_league",
            "label": tool_label("delegate_league"),
            "summary": _args_summary("delegate_league", _dl_args),
        })
        try:
            _holder: dict[str, Any] = {}
            async for _e in _run_delegate_live(
                    "delegate_league", task, primary, model, _holder):
                yield _e
            out = _holder.get("result") or {"tool": "delegate_league",
                                            "ok": False, "error": "no result"}
        except Exception as exc:
            out = {"tool": "delegate_league", "ok": False,
                   "error": str(exc)[:160]}
        if not isinstance(out, dict):
            out = {"tool": "delegate_league", "rows": out}
        _ms = int((time.time() - _t0) * 1000)
        _rd = _tool_result_payload(
            "data_retrieval", "delegate_league", out, _ms,
            summary=_delegate_result_summary(out),
        )
        yield _event("tool_result", _rd)
        for _te in _trace_replay_events(out):
            yield _te
        yield _event("thought_stream", {
            "node": "data_retrieval",
            "text": _done_thought(
                tool_label("delegate_league"), out, _ms),
        })
        state["tool_results"].append(out)
        state["calls_made"].append("delegate_league:" + json.dumps(
            {"task": task}, sort_keys=True))
        if (_result_status(out) == "ok" and not state.get("history")
                and not _is_deep_question(question)):
            # Desk answered a list question decisively. The planner's
            # follow-up round adds nothing here, and with thread history
            # it would inject carry context the desk never saw, so only
            # skip on a clean single-turn hit.
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    if (not found_p or not found_t) and state.get("history"):
        carry_p, carry_t = [], []
        for t in state["history"][-6:]:
            p, q = _detect_entities((t.get("text") or ""))
            carry_p.extend(p)
            carry_t.extend(q)
        hist_p = sorted(set(carry_p))
        hist_t = sorted(set(carry_t))
        if (not found_p and hist_p) or (not found_t and hist_t):
            seed_p = list(found_p[:2]) if found_p else hist_p[:2]
            seed_t = list(found_t[:1]) if found_t else hist_t[:1]
            seeds: list[tuple[str, str]] = []
            for p in seed_p:
                team_hint = ""
                try:
                    from .tools._core import coerce_player_id as _cp

                    _pid = _cp(p)
                    if _pid:
                        _ab = _player_team_abbr(_pid, "2025-26")
                        if _ab:
                            team_hint = f" Warehouse lists {p} on {_ab}."
                except Exception:
                    pass
                seeds.append(("delegate_scout",
                              f"Player focus: {p}.{team_hint} Report advanced "
                              f"metrics via get_advanced, plus form, shot diet, "
                              f"and clutch. Original question: {question}"))
            for t in seed_t:
                seeds.append(("delegate_team",
                              f"Team focus: {t}. Report record, splits, and "
                              f"rating context. Original question: {question}"))
            for name, task in seeds[:3]:
                if name not in delegates:
                    continue
                _s_args = {"task": task}
                _t0 = time.time()
                yield _event("tool_call", {
                    "node": "data_retrieval", "name": name,
                    "label": tool_label(name),
                    "summary": _args_summary(name, _s_args),
                })
                try:
                    _holder2: dict[str, Any] = {}
                    async for _e2 in _run_delegate_live(
                            name, task, primary, model, _holder2):
                        yield _e2
                    out = _holder2.get("result") or {"tool": name,
                                                     "ok": False,
                                                     "error": "no result"}
                except Exception as exc:
                    out = {"tool": name, "ok": False, "error": str(exc)[:160]}
                if not isinstance(out, dict):
                    out = {"tool": name, "rows": out}
                _ms = int((time.time() - _t0) * 1000)
                _rd = _tool_result_payload(
                    "data_retrieval", name, out, _ms,
                    summary=_delegate_result_summary(out),
                )
                yield _event("tool_result", _rd)
                for _te in _trace_replay_events(out):
                    yield _te
                state["tool_results"].append(out)
                state["calls_made"].append(name + ":" + json.dumps(
                    {"task": task}, sort_keys=True))
            if seeds:
                return
    pick = None
    if is_trade:
        pick = "delegate_league"
    elif found_p and not found_t:
        pick = "delegate_scout"
    elif found_t and not found_p:
        pick = "delegate_team"
    elif _LEAGUE_RX.search(question):
        pick = "delegate_league"
    elif re.search(r"draft|prospect|rookie|combine", question, re.IGNORECASE):
        pick = "delegate_league"
    if pick is None or pick not in delegates:
        return
    _p_args = {"task": question}
    _t0 = time.time()
    yield _event("tool_call", {
        "node": "data_retrieval", "name": pick,
        "label": tool_label(pick),
        "summary": _args_summary(pick, _p_args),
    })
    try:
        _holder3: dict[str, Any] = {}
        async for _e3 in _run_delegate_live(
                pick, question, primary, model, _holder3):
            yield _e3
        out = _holder3.get("result") or {"tool": pick, "ok": False,
                                         "error": "no result"}
    except Exception as exc:
        out = {"tool": pick, "ok": False, "error": str(exc)[:160]}
    if not isinstance(out, dict):
        out = {"tool": pick, "rows": out}
    _ms = int((time.time() - _t0) * 1000)
    _rd = _tool_result_payload(
        "data_retrieval", pick, out, _ms,
        summary=_delegate_result_summary(out),
    )
    yield _event("tool_result", _rd)
    for _te in _trace_replay_events(out):
        yield _te
    yield _event("thought_stream", {
        "node": "data_retrieval",
        "text": _done_thought(tool_label(pick), out, _ms),
    })
    state["tool_results"].append(out)
    state["calls_made"].append(pick + ":" + json.dumps({"task": question},
                                                       sort_keys=True))


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
    "delegate_scout", "delegate_team", "delegate_league", "run_python",
    "get_playoff_intel", "get_comps", "get_trade_value",
    "get_matchup_splits", "get_regression_check", "get_award_race",
    "get_matchup_preview",
})


def _is_deep_question(question: str) -> bool:
    """Detect questions that need deep investigation mode."""
    q = (question or "").lower()
    for pat in DEEP_TRIGGERS:
        if re.search(pat, q):
            return True
    # 3+ entities also triggers deep mode
    try:
        qp, qt = _detect_entities(question)
        if len(qp) + len(qt) >= 3:
            return True
    except Exception:
        pass
    return False


def _supervisor_tools(state: DimeState) -> list:
    return [t for t in _all_tools(state) if t.name in SUPERVISOR_TOOL_NAMES]


_DISPLAY_TITLES = {
    "run_python": "Warehouse query",
    "text_to_sql": "Warehouse query",
    "get_compare": "Player comparison",
    "get_leaders": "League leaders",
    "get_lineups": "Lineups",
    "get_shot_zones": "Shot zones",
    "get_matchup_splits": "Matchup splits",
    "get_regression_check": "Regression check",
    "get_comps": "Comps",
    "get_award_race": "Award race",
    "get_trade_value": "Trade value",
    "get_matchup_preview": "Matchup preview",
}


def _display_title(name: str, meta: dict[str, Any] | None = None) -> str:
    base = _DISPLAY_TITLES.get(name or "")
    if base is None:
        if (name or "").startswith("delegate_"):
            base = "Analyst research"
        elif (name or "").startswith("get_"):
            base = name[4:].replace("_", " ").strip().title() or "Dataset"
        elif name:
            base = tool_label(name)
        else:
            base = "Dataset"
    cat = ""
    try:
        cat = str((meta or {}).get("stat_category") or "").strip()
    except Exception:
        cat = ""
    return f"{base} · {cat}" if cat else base


def _with_title(rec: dict[str, Any]) -> dict[str, Any]:
    out = dict(rec)
    try:
        meta = out.get("meta") if isinstance(out.get("meta"), dict) else None
        out["title"] = _display_title(str(out.get("tool", "")), meta)
    except Exception:
        out["title"] = "Dataset"
    return out


def _flatten_tables(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _sanitize(rec: dict[str, Any]) -> dict[str, Any] | None:
        tool = rec.get("tool")
        if tool in ("resolve_entity", "search_nba"):
            return None
        out = dict(rec)
        out.pop("tool", None)
        if tool in _DISPLAY_TITLES:
            try:
                meta = out.get("meta") if isinstance(out.get("meta"), dict) else None
                out["title"] = _display_title(str(tool or ""), meta)
            except Exception:
                out["title"] = _DISPLAY_TITLES.get(str(tool), "Dataset")
        else:
            out.pop("title", None)
        meta = out.get("meta")
        if isinstance(meta, dict):
            out["meta"] = {k: v for k, v in meta.items()
                           if k not in ("sql", "query")}
        return out

    flat: list[dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        nested = r.get("tables")
        if isinstance(nested, list) and r.get("agent"):
            for t in nested:
                if isinstance(t, dict):
                    clean = _sanitize(_with_title(t))
                    if clean is not None:
                        flat.append(clean)
        else:
            clean = _sanitize(_with_title(r))
            if clean is not None:
                flat.append(clean)
    return flat


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?(?:-\d+)?%?", text)


def _event(kind: str, payload: Any) -> dict[str, Any]:
    if kind == "tool_result" and isinstance(payload, dict) and payload.get("error"):
        payload = {**payload, "error": _sanitize_error(str(payload["error"]))}
    return {"type": kind, "data": payload}


_ABS_PATH_RX = re.compile(r"(?<![\w:/])(?:/[\w.\-]+)+")
_PID_RX = re.compile(r"\bpid\b\s*[:=]?\s*\d+", re.IGNORECASE)


def _sanitize_error(msg: str) -> str:
    msg = _PID_RX.sub("pid", msg)
    return _ABS_PATH_RX.sub(lambda m: m.group(0).rsplit("/", 1)[-1], msg)


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
    carry: list[str] = []
    qp, qt = _detect_entities(state["question"])
    team_facts = []
    if qp or qt:
        try:
            from .tools._core import coerce_player_id as _cp

            for p in qp[:4]:
                _pid = _cp(p)
                _ab = _player_team_abbr(_pid, "2025-26") if _pid else ""
                if _ab:
                    team_facts.append(f"{p} plays for {_ab}")
        except Exception:
            pass
    if team_facts:
        prior += ("\nWarehouse team facts, trust these over memory: "
                  + "; ".join(team_facts) + ".")
    if state["history"]:
        turns = state["history"][-6:]
        prior += "\nConversation so far:\n" + "\n".join(
            f"{t['role']}: {t['text'][:600]}" for t in turns
        )
        carry_p, carry_t = [], []
        for t in turns:
            p, q = _detect_entities(t["text"] or "")
            carry_p.extend(p)
            carry_t.extend(q)
        carry = sorted(set(carry_p) | set(carry_t))[:6]
        if carry:
            prior += ("\nEntities mentioned earlier this thread: "
                      + ", ".join(carry) + ". Resolve pronouns like his, "
                      "her, their, and both to these entities. Never ask "
                      "which players the user means when entities exist.")
    if state["tool_results"]:
        prior += "\nPrior tool results this turn: " + str(state["tool_results"])[:4000]
    max_calls = DEEP_TOOL_CALLS if _is_deep_question(state["question"]) else MAX_TOOL_CALLS
    budget_left = max_calls - len(state["calls_made"])
    if budget_left <= 0:
        yield _event("thought_stream", {"node": "data_retrieval",
                                        "text": "Tool budget spent. Answering from evidence."})
        state["round"] = DEEP_TOOL_ROUNDS if _is_deep_question(state["question"]) else MAX_TOOL_ROUNDS
        yield _event("node_update", {"node": "data_retrieval", "status": "complete"})
        return
    try:
        question_for_planner = state["question"]
        if carry and not _detect_entities(question_for_planner)[0] \
                and not _detect_entities(question_for_planner)[1]:
            question_for_planner = (
                f"About {', '.join(carry)}: {question_for_planner}")
        _pholder: dict[str, Any] = {}
        async for _pe in _stream_planner(
                tooled,
                [SystemMessage(content=PLANNER_SYSTEM + prior),
                 HumanMessage(content=question_for_planner)],
                _pholder):
            yield _pe
        calls = _pholder.get("calls", [])
    except Exception as exc:
        yield _event("error", {"node": "data_retrieval", "message": str(exc)[:200]})
        return
    fresh = []
    for call in calls:
        key = _call_key(call.get("name", ""), call.get("args", {}) or {})
        if key in state["calls_made"]:
            continue
        state["calls_made"].append(key)
        fresh.append(call)
        _deep = _is_deep_question(state["question"])
        _max = DEEP_TOOL_CALLS if _deep else MAX_TOOL_CALLS
        if len(state["calls_made"]) >= _max:
            break
    if not fresh:
        made_names = _tool_names_from_calls_made(state["calls_made"])
        if made_names:
            yield _event("thought_stream", {"node": "data_retrieval",
                                            "text": _friendly_progress(made_names)})
        made = {k.partition(":")[0] for k in state["calls_made"]}
        if made <= {"resolve_entity", "search_nba"}:
            state["tool_results"].append(
                {"tool": "supervisor_note", "rows": [],
                 "note": "Identity is resolved. Call a delegate or data "
                         "tool now. No more identity calls."})
            state["_pending_calls"] = []  # type: ignore[typeddict-unknown-key]
        else:
            _deep2 = _is_deep_question(state["question"])
            state["round"] = DEEP_TOOL_ROUNDS if _deep2 else MAX_TOOL_ROUNDS
    else:
        state["_pending_calls"] = fresh  # type: ignore[typeddict-unknown-key]
        names = sorted({c.get("name", "") for c in fresh})
        yield _event("thought_stream", {"node": "data_retrieval",
                                        "text": _friendly_progress(names)})
    yield _event("node_update", {"node": "data_retrieval", "status": "complete"})


async def actual_tool_node(state: DimeState) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "tools", "status": "running"})
    by_name = {t.name: t for t in _supervisor_tools(state)}
    pending = state.pop("_pending_calls", [])  # type: ignore[typeddict-unknown-key]
    elapsed: dict[int, int] = {}

    async def _run(call: dict[str, Any]) -> dict[str, Any]:
        t0 = time.time()
        name = call.get("name", "")
        args = call.get("args", {}) or {}
        fn = by_name.get(name)
        if fn is None:
            elapsed[id(call)] = int((time.time() - t0) * 1000)
            await _tok_q.put(None)
            return {"tool": name, "ok": False, "error": "unknown tool"}
        if isinstance(args, dict) and "season" in args:
            from .tools._core import clamp_season

            args = {**args, "season": clamp_season(args.get("season"))}
        try:
            if name.startswith("delegate_"):
                # Stream the desk's raw tokens live while it works.
                async def _on_tok(t: str) -> None:
                    await _tok_q.put((name, t))

                out = await run_desk_streaming(
                    name, args.get("task", "") if isinstance(args, dict) else "",
                    state["primary"], state["model"],  # type: ignore[arg-type]
                    on_token=_on_tok)
            else:
                out = await fn.ainvoke(args)
            elapsed[id(call)] = int((time.time() - t0) * 1000)
            await _tok_q.put(None)
            return out if isinstance(out, dict) else {"tool": name, "rows": out}
        except Exception as exc:
            elapsed[id(call)] = int((time.time() - t0) * 1000)
            await _tok_q.put(None)
            return {"tool": name, "ok": False, "error": str(exc)[:200]}

    for call in pending:
        name = call.get("name", "") if isinstance(call, dict) else ""
        args = call.get("args", {}) or {} if isinstance(call, dict) else {}
        yield _event("tool_call", {
            "node": "tools", "name": name,
            "label": tool_label(name),
            "summary": _args_summary(name, args),
        })
    _tok_q: asyncio.Queue = asyncio.Queue()
    async def _gather_all():
        return await asyncio.gather(*(_run(c) for c in pending))

    _gather = _spawn(_gather_all(), name="tool-gather")
    # Drain live desk tokens while the tools run; each _run posts one
    # None sentinel when it finishes.
    _remaining = len(pending)
    while _remaining > 0:
        _item = await _tok_q.get()
        if _item is None:
            _remaining -= 1
            continue
        _tname, _ttext = _item
        yield _event("thought_token", {
            "node": "tools", "text": _ttext,
            "agent": _tname.replace("delegate_", ""),
        })
    results = await _gather
    for call, result in zip(pending, results):
        state["tool_results"].append(result)
        name = call.get("name", "") if isinstance(call, dict) else ""
        if not name and isinstance(result, dict):
            name = str(result.get("tool", ""))
        res = result if isinstance(result, dict) else {}
        rdata = _tool_result_payload(
            "tools", name, res, elapsed.get(id(call), 0))
        yield _event("tool_result", rdata)
        for _te in _trace_replay_events(res if isinstance(res, dict) else {}):
            _td = dict(_te.get("data", {}) or {})
            _td["node"] = "tools"
            yield {"type": _te.get("type", "tool_call"), "data": _td}
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


async def _suggest_llm(
    question: str,
    results: list[dict[str, Any]],
    calls_made: list[str],
    llm: Any,
) -> list[str]:
    """Evidence-grounded follow-up suggestions via LLM.

    Falls back to hardcoded _suggest on any failure. The LLM sees a
    compact summary of what data came back, so suggestions reference
    actual players, teams, and stats — not generic templates.
    """
    try:
        # Compact evidence: tool names + first few row keys/values
        evidence: list[str] = []
        for r in results[:6]:
            if not isinstance(r, dict):
                continue
            tool = r.get("tool", "?")
            rows = r.get("rows", [])
            if isinstance(rows, dict):
                rows = [rows]
            if not isinstance(rows, list):
                rows = []
            sample = []
            for row in rows[:3]:
                if isinstance(row, dict):
                    keys = [k for k in row.keys() if not k.startswith("_")][:4]
                    sample.append({k: row[k] for k in keys})
            evidence.append(f"{tool}: {json.dumps(sample)[:400]}")
        evidence_str = "\n".join(evidence) or "no data returned"

        prompt = (
            "You suggest follow-up questions for an NBA analytics chatbot. "
            "Based on the user's question and the data retrieved, suggest exactly 3 "
            "specific follow-up questions the user would likely want to ask next. "
            "Reference actual player/team names and stats from the data. "
            "Keep each suggestion under 12 words. "
            "Return ONLY a JSON array of 3 strings, no other text.\n\n"
            f"User question: {question}\n\n"
            f"Data retrieved:\n{evidence_str}"
        )
        resp = await llm.ainvoke([
            SystemMessage(content="You suggest follow-up questions. Return only JSON."),
            HumanMessage(content=prompt),
        ])
        text = resp.content if hasattr(resp, "content") else str(resp)
        # Extract JSON array
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError("no JSON array in response")
        suggestions = json.loads(match.group(0))
        if not isinstance(suggestions, list):
            raise ValueError("not a list")
        out = [str(s).strip() for s in suggestions if str(s).strip()][:3]
        if len(out) < 3:
            raise ValueError("fewer than 3 suggestions")
        return out
    except Exception:
        return _suggest(question, results, calls_made)


def _sanitize_evidence(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _label(name: str) -> str:
        n = (name or "").lower()
        if n == "run_python" or "python" in n:
            return "computed"
        if n.startswith("delegate_") or n in ("resolve_entity", "search_nba"):
            return "league data"
        return "warehouse table"

    def _clean(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if k == "tool":
                    out["source_kind"] = _label(str(v) if v is not None else "")
                    continue
                if k == "calls_made":
                    continue
                if k == "meta" and isinstance(v, dict):
                    blob = json.dumps(v, default=str).lower()
                    if "sql" in blob:
                        continue
                if isinstance(v, str) and k.lower() in ("sql", "query"):
                    continue
                out[k] = _clean(v)
            return out
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return obj

    cleaned = _clean(results)
    return cleaned if isinstance(cleaned, list) else []


def _collect_seasons(results: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "_season" and isinstance(v, str) and v:
                    found.append(v)
                else:
                    _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)

    _walk(results)
    seen: list[str] = []
    for s in found:
        if s not in seen:
            seen.append(s)
    return sorted(seen)


def _clean_error_text(text: str) -> str:
    s = text or ""
    s = re.sub(r"\b(get_\w+|delegate_\w+|resolve_entity|search_nba|run_python|text_to_sql)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bsilver_\w+\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"(?is)\bselect\b.*?(;|$)", " ", s)
    s = re.sub(r"\bSQL\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d{5,}\b", " ", s)
    s = re.sub(r"\b\d{3,4}\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .;:,")
    s = re.sub(r"\s+\b(id|on|in|at|for|with|from|and|or)$", "", s, flags=re.IGNORECASE).strip(" .;:,")
    return s


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
        and r.get("tool", "") not in ("resolve_entity", "search_nba")
    ]
    if not evidenced:
        raw_errs = [str(r.get("error", ""))
                    for r in state["tool_results"]
                    if isinstance(r, dict) and r.get("error")][:3]
        cleaned = [_clean_error_text(e) for e in raw_errs]
        cleaned = [c for c in cleaned if c and len(c) >= 12][:1]
        seasons = _collect_seasons(state["tool_results"])
        try:
            _qp, _qt = _detect_entities(state.get("question", "") or "")
            subject = (_qp + _qt)[:1]
            subject = subject[0] if subject else "NBA"
        except Exception:
            subject = "NBA"
        m = re.search(r"(20\d\d-\d\d)", state.get("question", "") or "")
        season_q = m.group(1) if m else (seasons[-1] if seasons else "")
        if season_q:
            base = f"No {subject} data found for {season_q}"
        else:
            base = f"No {subject} data found"
        if seasons and seasons != [season_q]:
            base += f"; warehouse covers {', '.join(seasons)}"
        elif seasons and len(seasons) > 1:
            base += f"; warehouse covers {', '.join(seasons)}"
        if cleaned:
            base += f"; {cleaned[0]}"
        state["analysis"] = base + "."
        yield _event(
            "custom_data", {"node": "analytics", "tables": _flatten_tables(state["tool_results"])}
        )
        yield _event("node_update", {"node": "analytics", "status": "complete"})
        return
    evidence = str(_sanitize_evidence(state["tool_results"]))[:12000]
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
    try:
        llm = get_llm(state["primary"], state["model"])  # type: ignore[arg-type]
    except Exception:
        llm = None
    if llm:
        state["suggestions"] = await _suggest_llm(
            state["question"], state["tool_results"], state["calls_made"], llm
        )
    else:
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
    question = _expand_nicknames(question or "")
    state = DimeState(
        question=question, primary=primary, model=model, round=0,
        tool_results=[], calls_made=[], history=history or [],
        analysis="", suggestions=[],
    )
    async for e in entry_node(state):
        yield e
    yield _event("node_update", {"node": "data_retrieval", "status": "running"})
    async for e in _triage_seed(question, primary, model, state):
        yield e
    deep = _is_deep_question(question)
    max_rounds = DEEP_TOOL_ROUNDS if deep else MAX_TOOL_ROUNDS
    if deep:
        yield _event("thought_stream", {
            "node": "entry",
            "text": "Deep investigation mode: expanded tool budget.",
        })
    while state["round"] < max_rounds:
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
