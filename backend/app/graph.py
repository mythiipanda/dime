"""Five nodes. Typed state. Tool budget plus dedupe plus parallel exec.

Event dicts stream out in the frontend contract: node_update,
thought_stream, message, final_answer, suggestions, graph_end, error.
"""

import asyncio
import json
import re
import unicodedata
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
    "For ranking questions, narrate the full order including the middle, "
    "not just the top and bottom; the table carries every row. "
    "Only cite all-in-one metrics present in evidence: RAPM-lite, on-off "
    "net, RAPTOR history. Label RAPM-lite and RAPTOR as estimates. "
    "Never invent PER, BPM, EPM, WS, VORP, or LEBRON. Say EPM is unavailable. "
    "State the season the data covers in the first line of every answer. "
    "Never name tools, tables, or query languages."
)

PLANNER_SYSTEM = (
    "You are the retrieval supervisor. Your tools: resolve_entity, "
    "get_compare, get_preview, get_briefing, delegate_scout, "
    "delegate_team, delegate_league, run_python. Workers behind the delegates own "
    "every granular dataset, including text_to_sql. "
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
    "clutch, ELO, title odds, today games, briefings, hustle boards, "
    "or deep standings splits, call delegate_league. "
    "For two-player compares call get_compare first, then one "
    "delegate_scout per player for shot diet, clutch, and advanced depth. "
    "If the question asks which metric is right, whether metrics agree, "
    "or names EPM, LEBRON, DARKO, DRIP, or RAPTOR for two players, "
    "call compare_metrics first and never invent those metrics. "
    "If the question asks to debate, settle an argument, or make a "
    "shareable card for two players, call get_debate_card. "
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
    return "Checking " + " and ".join(sorted(labels))


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
    r"\bvs\.?\b(?!\s+top[-\s]?\d)|\bversus\b(?!\s+top[-\s]?\d)|\bcompare\b",
    re.IGNORECASE)
_LIST_RX = re.compile(
    r"which\s+(players|teams)|what\s+(players|teams)|top\s+\d+|"
    r"\bunder\s+\d+|\bover\s+\d+|\bage\b|"
    r"\baverag\w*\b|\bat least\b|"
    r"leads?\s+the\s+league|who\s+leads\b", re.IGNORECASE)

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

    raw_q = question.lower()
    named = []
    for p in found_p:
        low = p.lower()
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


async def _triage_seed(question: str, primary: str, model: str,
                       state: dict) -> None:
    found_p, found_t = _detect_entities(question)
    if state.get("history") and re.search(
            r"\b(him|her|them|they|his|hers|theirs|it|that team|that player)\b",
            question, re.IGNORECASE):
        for t in state["history"][-6:]:
            hp, ht = _detect_entities(t.get("text") or "")
            for p in hp:
                if p not in found_p and len(found_p) < 3:
                    found_p.append(p)
            for tm in ht:
                if tm not in found_t and len(found_t) < 2:
                    found_t.append(tm)
    is_compare = bool(_COMPARE_RX.search(question))
    is_trade = bool(re.search(r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b|\bdeal\b",
                              question, re.IGNORECASE))
    is_cast = bool(re.search(
        r"supporting cast|\bcast\b|teammates?|rotation depth|"
        r"around (him|her|them)|better team\b|deeper team\b",
        question, re.IGNORECASE))
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
                try:
                    out = await fn.ainvoke(sides)
                except Exception as exc:
                    out = {"tool": "get_trade_check", "ok": False,
                           "error": str(exc)[:160]}
                state["tool_results"].append(
                    out if isinstance(out, dict) else {"tool": "get_trade_check",
                                                      "rows": out})
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
        try:
            from .tools import v1_tools as _vt

            fn = next((t for t in _vt if t.name == "run_python"), None)
            out = await fn.ainvoke({"code": code}) if fn is not None else {
                "tool": "run_python", "ok": False, "error": "no python tool"}
        except Exception as exc:
            out = {"tool": "run_python", "ok": False, "error": str(exc)[:160]}
        state["tool_results"].append(
            out if isinstance(out, dict) else {"tool": "run_python",
                                              "rows": out})
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
            try:
                from .tools import v1_tools as _vt2

                fn2 = next((t for t in _vt2 if t.name == "run_python"), None)
                out = await fn2.ainvoke({"code": code}) if fn2 is not None else {
                    "tool": "run_python", "ok": False, "error": "no python tool"}
            except Exception as exc:
                out = {"tool": "run_python", "ok": False,
                       "error": str(exc)[:160]}
            state["tool_results"].append(
                out if isinstance(out, dict) else {"tool": "run_python",
                                                  "rows": out})
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
                try:
                    out = await fn3.ainvoke({"player": p}) if fn3 is not None else {
                        "tool": "get_raptor_history", "ok": False,
                        "error": "no raptor tool"}
                except Exception as exc:
                    out = {"tool": "get_raptor_history", "ok": False,
                           "error": str(exc)[:160]}
                state["tool_results"].append(
                    out if isinstance(out, dict) else {"tool": "get_raptor_history",
                                                      "rows": out})
                state["calls_made"].append("get_raptor_history:" + json.dumps(
                    {"player": p}, sort_keys=True))
            return
        except Exception:
            pass
    delegates = {t.name: t for t in delegate_tools(primary, model)}  # type: ignore[arg-type]
    is_raptor = bool(found_p and re.search(
        r"\braptor\b|\bwar\b|peak|all-time|all time|greatest season|"
        r"best season|career (arc|trajectory|history|impact)|"
        r"\btrajectory\b|\barc\b|over time|aging|development curve",
        question, re.IGNORECASE))
    if (_LIST_RX.search(question) and not is_trade and not is_cast
            and not is_compare and not is_raptor
            and "delegate_league" in delegates):
        task = (question + " Answer via text_to_sql (you own that tool).")
        try:
            out = await delegates["delegate_league"].ainvoke({"task": task})
        except Exception as exc:
            out = {"tool": "delegate_league", "ok": False,
                   "error": str(exc)[:160]}
        state["tool_results"].append(
            out if isinstance(out, dict) else {"tool": "delegate_league",
                                               "rows": out})
        state["calls_made"].append("delegate_league:" + json.dumps(
            {"task": task}, sort_keys=True))
        return
    if (found_p and not is_trade and not is_cast
            and not is_compare and not is_raptor
            and re.search(
                r"\bsplit|versus top|vs top|against top|last \d+|"
                r"home\b|away\b|monthly|defense\b",
                question, re.IGNORECASE)
            and "delegate_scout" in delegates):
        task = (question + " Use get_splits (it carries vs-top-10-defense"
                " and vs-rest rows) for matchup context.")
        try:
            out = await delegates["delegate_scout"].ainvoke({"task": task})
        except Exception as exc:
            out = {"tool": "delegate_scout", "ok": False,
                   "error": str(exc)[:160]}
        state["tool_results"].append(
            out if isinstance(out, dict) else {"tool": "delegate_scout",
                                               "rows": out})
        state["calls_made"].append("delegate_scout:" + json.dumps(
            {"task": task}, sort_keys=True))
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
                try:
                    out = await delegates[name].ainvoke({"task": task})
                except Exception as exc:
                    out = {"tool": name, "ok": False, "error": str(exc)[:160]}
                state["tool_results"].append(
                    out if isinstance(out, dict) else {"tool": name, "rows": out})
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
    try:
        out = await delegates[pick].ainvoke({"task": question})
    except Exception as exc:
        out = {"tool": pick, "ok": False, "error": str(exc)[:160]}
    state["tool_results"].append(
        out if isinstance(out, dict) else {"tool": pick, "rows": out})
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
    "resolve_entity", "get_compare", "compare_metrics", "get_debate_card", "get_preview", "get_briefing",
    "delegate_scout", "delegate_team", "delegate_league", "run_python",
    "get_playoff_intel",
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
    "compare_metrics": "Metric adjudication",
    "get_debate_card": "Debate card",
    "get_leaders": "League leaders",
    "get_lineups": "Lineups",
    "get_shot_zones": "Shot zones",
}

_KIND_FOR_TOOL = {
    "run_python": "python",
    "text_to_sql": "warehouse",
    "get_compare": "compare",
    "compare_metrics": "compare",
    "get_preview": "compare",
    "get_debate_card": "debate",
    "get_wowy": "wowy",
    "get_shot_zones": "shots",
    "get_shot_compare": "shots",
    "get_leaders": "leaders",
    "get_lineups": "lineups",
    "get_raptor_history": "raptor",
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
        out["kind"] = _KIND_FOR_TOOL.get(str(tool or ""), "dataset")
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
        resp = await tooled.ainvoke(
            [SystemMessage(content=PLANNER_SYSTEM + prior), HumanMessage(content=question_for_planner)]
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
        for call in fresh:
            yield _event("message", {"node": "data_retrieval",
                                     "label": tool_label(call.get("name", "")),
                                     "status": "started"})
        state["_pending_calls"] = fresh  # type: ignore[typeddict-unknown-key]
        names = sorted({c.get("name", "") for c in fresh})
        yield _event("thought_stream", {"node": "data_retrieval",
                                        "text": _friendly_progress(names)})
    yield _event("node_update", {"node": "data_retrieval", "status": "complete"})


async def actual_tool_node(state: DimeState) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "tools", "status": "running"})
    by_name = {t.name: t for t in _supervisor_tools(state)}
    pending = state.pop("_pending_calls", [])  # type: ignore[typeddict-unknown-key]

    async def _run(call: dict[str, Any]) -> dict[str, Any]:
        name = call.get("name", "")
        args = call.get("args", {}) or {}
        fn = by_name.get(name)
        if fn is None:
            return {"tool": name, "ok": False, "error": "unknown tool"}
        if isinstance(args, dict) and "season" in args:
            from .tools._core import clamp_season

            args = {**args, "season": clamp_season(args.get("season"))}
        try:
            out = await fn.ainvoke(args)
            return out if isinstance(out, dict) else {"tool": name, "rows": out}
        except Exception as exc:
            return {"tool": name, "ok": False, "error": str(exc)[:200]}

    results = await asyncio.gather(*(_run(c) for c in pending))
    for call, result in zip(pending, results):
        state["tool_results"].append(result)
        name = call.get("name", "") if isinstance(call, dict) else ""
        if not name and isinstance(result, dict):
            name = str(result.get("tool", ""))
        yield _event("message", {"node": "tools",
                                 "label": tool_label(name),
                                 "status": _result_status(result if isinstance(result, dict) else {}),
                                 "rows": _result_rows(result if isinstance(result, dict) else {})})
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
    await _triage_seed(question, primary, model, state)
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
