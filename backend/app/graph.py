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
from typing import Any, NotRequired, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage

from .providers import (
    accumulate_tool_calls,
    astream_with_fallback,
    get_llm,
    invoke_with_fallback,
    resolve_model_id,
)
from .skills import catalog as skills_catalog, load_skill as skills_load_skill
from .subagents import delegate_tools, run_desk_streaming, _SHOT_ZONE_RX, _HISTORICAL_RX
from .tools import v1_tools
from .tools._core import tool_label

ANALYST_SYSTEM = (
    "You are Dime, an NBA data analyst assistant. "
    "Answer ONLY from the tool results you receive. "
    "Every number you state must appear in the evidence. "
    "Never invent streaks, averages, or ranks. "
    "Never list months, dates, or specifics absent from evidence. "
    "Round every number to 1 decimal max - except small-scale "
    "ratings (RAPM, net/off/def rating under 10), which keep 2 "
    "decimals so close values never read as ties. Write percentages with a "
    "percent sign, never as raw decimals. Never print raw field names "
    "like ts_pct or efg_pct. "
    "Name the tool output you used. Say when data is missing. "
    "When a tool reports an error naming unknown players or missing data, "
    "say so plainly instead of claiming nothing came back. "
    "Never mention tool names, table names, SQL, agents, desks, or "
    "phrases like 'per the team agent', 'no table to show', or "
    "'no evidence'. Restate any error as one plain analyst sentence "
    "with names, never ids. "
    "Never mix FG% and eFG%: label each metric you cite, and for zone "
    "accuracy prefer eFG% when present. Never write a comparison that "
    "contradicts the evidence numbers; the larger share leads. "
    "Missing zone data is written as N/A and excluded from takeaways, "
    "never rendered as 0.0% and never argued from. "
    "Derive per-game numbers when totals and games are both present, "
    "showing the division. "
    "Keep answers short and specific with numbers. "
    "Use one Takeaways block and one Verdict block at most; never "
    "repeat a heading or restate the same numbers in two sections. "
    "The Verdict is the decisive takeaway - one sentence judging what "
    "the evidence DOES show, never a report of missing or unavailable "
    "data; absence notes belong in the body, never in the verdict "
    "(the UI renders the verdict as the headline). "
    "Use a numbered list only when the user asked for a ranking. "
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
    "For three-point zones (corner, above the break) quote 3P% (the fg "
    "fields), never the 1.5x eFG; use eFG only for two-point zones. "
    "When shot-zone or shot-compare evidence is present, never claim "
    "shot charts or visual courts are unavailable; the evidence card "
    "renders the court. "
    "State the season the data covers in the first line of every answer; "
    "write it exactly like 'This data covers the 2025-26 season.' and "
    "never duplicate the word season. "
    "Never name tools, tables, or query languages. "
    "If the evidence carries an assumption note about which player a "
    "loose name matched (e.g. James -> LeBron), state the assumption "
    "in one clause (QA #59). "
    "If the user states a personal preference (favorite team, favorite "
    "player), acknowledge it for THIS conversation only - say 'I'll "
    "remember that during this conversation', never 'I have noted' or "
    "anything implying it persists across sessions; nothing carries "
    "between sessions (F51). "
)

_PLANNER_PREFIX = (
    "You are the retrieval supervisor. Your tools: resolve_entity, "
    "get_compare, get_comps, get_preview, get_matchup_preview, get_briefing, "
    "get_trade_value, get_matchup_splits, get_regression_check, "
    "get_award_race, delegate_scout, "
    "delegate_team, delegate_league, run_python. Workers behind the delegates own "
    "every granular dataset, including text_to_sql. "
    "For players most statistically like X (comps, similar players), call "
    "get_comps directly — never improvise similarity from SQL. "
    "For who wins a trade, trade value, fair value, or trade grades, call "
    "get_trade_value directly — it resolves player names itself, so skip "
    "resolve_entity for trade questions. "
    "For is-this-trade-legal, salary matching, cap rules, apron, or "
    "trade exceptions, call get_trade_check directly, never "
    "get_trade_value. "
    "For a team's record when a named player plays or sits, call "
    "delegate_team and tell it to use search_game_logs with the player "
    "and no filters, reporting rows.record verbatim; never answer from "
    "text_to_sql over gamelogs. "
    "For performance splits (vs defense tiers, home/away, rest days), call "
    "get_matchup_splits directly. "
    "For team-vs-team record, season series, meetings, or 'how did X do "
    "against Y' questions, call get_season_series directly - never "
    "run_python or text_to_sql for team-vs-team (free SQL has answered "
    "about the wrong teams). "
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
    "For top-N team comparisons across several stats (top 3 scoring teams "
    "with wins, best defenses by rating and record), call get_team_compare "
    "- it joins the deduped team-totals board with standings records in "
    "one deterministic payload. Never text_to_sql anonymous aggregates "
    "(they ship nameless tables). "
    "For supporting-cast questions, call run_python averaging teammate PPG "
    "from silver_leaders_pts excluding the star, joined with NET_RATING "
    "from silver_team_ratings. "
    "Delegate multi-part work (comparisons, previews, roundups) to one delegate per entity. "
    "Pass the user's question to the delegate unchanged as the task. "
    "For cross-season history delegate to the right desk and tell it to use text_to_sql. "
    "For historical draft or all-time RAPTOR player impact, query silver_hist_draft "
    "or silver_raptor_player via text_to_sql. Prefer text_to_sql over run_python "
    "for single-fact warehouse lookups; use run_python only for math. "
    "For schedule, fixtures, upcoming games, back-to-backs, or rest-day "
    "questions, call delegate_league and tell it to use silver_schedule "
    "via text_to_sql or get_games_on_date; in the offseason (June to "
    "October) the honest answer is that no games are scheduled until "
    "preseason - never substitute a streak or standings table. "
    "For rookie questions (ROY, best rookies, rookies averaging X), "
    "rookies are the current draft class: delegate_league and tell it "
    "to use get_rookie_leaders with the stat and threshold. Never "
    "answer rookie questions from silver_hist_player_seasons, never "
    "use age as a rookie proxy, and never route them to text_to_sql "
    "(F46: a 'rookies 20+ ppg' query listed Edwards/LaMelo/Wemby from "
    "2023-24 - the right answer was Cooper Flagg). "
    "For Finals or playoff-series questions naming two teams, "
    "delegate_league and keep BOTH team names in the task verbatim "
    "so the desk calls get_season_series on the pair - a dropped "
    "team name turns it into an aggregate playoff lookup that "
    "cannot see the series (F49). "
    "For single-season leaders, standings, injuries, playoffs, ratings, "
    "clutch, ELO, title odds, today games, briefings, hustle boards, "
    "or deep standings splits, call delegate_league. "
    "For player risers/fallers (who is rising, falling, hot lately), "
    "call get_player_risers; get_risers is the TEAM win-rate version. "
    "ELO means the 1500-scale rating from get_elo_standings; never "
    "report NET_RATING as ELO. For title/playoff odds call "
    "get_playoff_sim. "
    "For one player's season averages (ppg, rpg, apg, per-game asks, "
    "how many X per game, what does X average), call "
    "get_season_averages first - never delegate_league or text_to_sql "
    "for a single player's season line. "
    "For two-player compares call get_compare first, then one "
    "delegate_scout per player for shot diet, clutch, and advanced depth. "
    "For shot charts, shot zones, shot diet, or shooting-location "
    "questions about players, call delegate_scout once per player and "
    "tell it to use get_shot_zones (single player) or get_shot_compare "
    "(two players); never delegate_team or delegate_league for these. "
    "In a thread, 'their shot charts' means the carried players from "
    "the prior turn - resolve them from thread context, not teams. "
    "If the question asks which metric is right, whether metrics agree, "
    "or names EPM, LEBRON, DARKO, DRIP, or RAPTOR for two players, "
    "call compare_metrics first and never invent those metrics. "
    "If the question asks to debate, settle an argument, or make a "
    "shareable card for two players, call get_debate_card. "
    "If the question asks how players did in the playoffs, call "
    "get_playoff_intel per player first. "
    "Synthesize dimension by dimension with a verdict per dimension. "
    "In two-player compare answers, state each player's headline line "
    "(per-game points, rebounds, assists, and an efficiency figure) "
    "from the payload before the takeaways - never present a margin "
    "or percentage gap without the underlying numbers. Every takeaway "
    "that cites a lead or a gap must name both figures, like "
    "'66.5% vs 61.6% TS', never 'leads by 4.9 percentage points' alone. "
    "The same rule holds everywhere: any sentence citing a limit, gap, "
    "or comparison must carry the figures from the payload - never an "
    "empty slot like 'sends out $ but can only take in $'."
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
    "unless the user names a different season explicitly. "
    "Season-boundary rule: it is the 2026 offseason. 'This season', "
    "'current season', and 'last season' all mean 2025-26 (the most "
    "recently completed season) until 2026-27 tips off in late October "
    "2026. Do not map 'last season' to 2024-25 during the offseason."
    "\n\nAnalyst skills. Match the question to one skill and follow it:\n"
)


SKILL_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("compare_players", ("compare", "comparing", "comparison", "versus",
                         " vs ", " vs.", "better than", "who is better",
                         "which is better", "rank them", "head-to-head",
                         "head to head")),
    ("form_check", ("slump", "hot streak", "cold streak", "recent form",
                    "last 10", "last ten", "heating up", "in form",
                    "out of form")),
    ("game_preview", ("preview", "matchup", "tonight",
                      "projected score", "projected total")),
    ("impact_check", ("impact", "on-off", "on/off", "carrying",
                      "how good has", "how good is", "career arc",
                      "raptor", "lebron", "estimated per-100",
                      "per-100 impact")),
    ("lineup_wowy", ("wowy", "plays well together", "play well together",
                     "best lineup", "lineup")),
    ("morning_briefing", ("briefing", "recap", "last night", "standouts")),
    ("shot_profile", ("shot chart", "shot zones", "shot profile", "shooting",
                      "shot diet", "zones", "corner three", "true shooting")),
    ("standings_read", ("standings", "playoff race", "clinch", "magic number",
                        "lottery", "tanking", "seed")),
    ("leaders_read", ("scoring title", "leads the league", "who leads",
                      "league leaders", "leaders", "leading scorer",
                      "points leader", "leads in")),
    ("record_when_plays", ("record when", "when he plays", "when she plays",
                           "when they play", "when plays", "record with",
                           "record without", "with and without", "when sits",
                           "when he sits", "sits", "without him", "without her",
                           "with him")),
    ("historical_leaders", ("each season", "every season", "all-time",
                            "all time", "single-season", "single season",
                            "career leaders", "season leaders",
                            "multi-season", "per season", "by season",
                            "decade", "best single", "greatest season")),
]

MAX_SKILLS_PER_TURN = 2


def match_skills(question: str,
                 limit: int = MAX_SKILLS_PER_TURN) -> list[str]:
    q = (question or "").lower()
    matched: list[str] = []
    for name, keywords in SKILL_KEYWORDS:
        if any(kw in q for kw in keywords):
            matched.append(name)
            if len(matched) >= limit:
                break
    return matched


def build_planner_prompt(question: str) -> str:
    prompt = _PLANNER_PREFIX + skills_catalog()
    for name in match_skills(question):
        try:
            body = skills_load_skill(name) or ""
        except Exception:
            body = ""
        if body.strip():
            prompt += "\n\n" + body.strip()
    return prompt


PLANNER_SYSTEM = (
    _PLANNER_PREFIX
    + skills_catalog()
)

MAX_TOOL_ROUNDS = 3

# Watchdog (v2 step 3, Tony's "some of these don't even finish"): a
# stuck turn must end honestly, never hang. Per-call timeouts feed the
# circuit breaker; the turn budget forces the coverage-named honest
# end (_COMPUTE_FALLBACK); heartbeats at the SSE layer already ping.
TOOL_CALL_TIMEOUT_S = 25.0
DESK_CALL_TIMEOUT_S = 75.0
TURN_WARN_S = 40.0
TURN_BUDGET_S = 90.0
DEEP_TURN_BUDGET_S = 180.0
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
        # Game-log results nest the actual game rows under "matches"
        # alongside metadata keys (player, filters, totals); count the
        # games, not the keys ("7 rows" for 1 game otherwise).
        matches = rows.get("matches")
        if isinstance(matches, list):
            return len(matches)
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
    r"elo|title odds|streak|versus|power rank|net rating|comeback|"
    r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b", re.IGNORECASE)
_COMPARE_RX = re.compile(
    r"\bvs\.?\b(?!\s+top[-\s]?\d)|\bversus\b(?!\s+top[-\s]?\d)|\bcompare\b",
    re.IGNORECASE)
# Trade-value phrasing that get_trade_value answers on its own: the planner
# used to spend two LLM rounds (resolve_entity, then the value call) before
# calling it, but the tool resolves names itself.
_TRADE_VALUE_RX = re.compile(
    r"who wins|win(?:s|ner|ning)?\b[^.?!]{0,25}\btrades?\b|trade value|"
    r"fair value|grade[sd]? (?:this|that|the) trade|"
    r"value of (?:this|that|the) trade|production value vs salary|"
    r"who (?:got|gets) the better (?:deal|end)", re.IGNORECASE)
# Compound trade questions the value fast-path must NOT swallow: legality,
# cap math, or picks need the planner (or the get_trade_check path).
_TRADE_VALUE_NO_RX = re.compile(
    r"\blegal\b|salary cap|under the cap|\bapron\b|luxury tax|"
    r"salary match|trade exception|\bcba\b|"
    r"\bpicks?\b|\bfrp\b|\bsrp\b|first[\s-]?round pick|second[\s-]?round pick",
    re.IGNORECASE)
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
_MATCHUP_SPLITS_RX = re.compile(
    r"\bmatchup\s+splits?\b|\bteam\s+splits?\b|"
    r"\bsplits?\b.{0,24}\b(?:vs\.?|versus)\b|"
    r"\b(?:vs\.?|versus)\b.{0,24}\bsplits?\b",
    re.IGNORECASE)
# Game-log questions are answerable straight from the warehouse:
# "game logs", "40-point games", "triple-doubles", "scored 50 points".
# The planner free-forms these through text_to_sql and hits
# unknown-table/column errors on silver_player_gamelogs (caught red in
# the demo recording), so the triage fast-path routes them to
# search_game_logs, which owns the per-player log filter pipeline.
# Best-game phrasing ("best game", "career high", "season high", "most
# points") is a game-log question answered with the max-points game from
# the warehouse logs. Kept as its own regex because "career high" trips
# _GAMELOG_NO_RX's "career" guard, which is meant for career averages,
# not single-game highs.
_GAMELOG_BEST_RX = re.compile(
    r"\bbest game\b|\bcareer[\s-]*high\b|\bseason[\s-]*high\b|"
    r"\bmost points\b",
    re.IGNORECASE)
_GAMELOG_RX = re.compile(
    r"\bgame[\s-]*logs?\b|"
    r"\btriple[\s-]*doubles?\b|\bdouble[\s-]*doubles?\b|"
    + _GAMELOG_BEST_RX.pattern + r"|"
    r"\b\d{2}\s*[-–—\s]?\s*(?:points?|pts?)\b|"  # "40-point games" / "40 point games" / "40pt games"
    r"\b\d{1,2}\s*[-–—]\s*rebounds?\b|"       # "15-rebound games"
    r"\b\d{1,2}\s*[-–—]\s*assists?\b|"        # "12-assist games"
    r"(?:scored|had|dropped|posted|recorded)\s+\d{2}\s*(?:\+|or more)?"
    r"\s*(?:points?|pts?)\b|"                 # "scored 50 points"
    r"\bgames?\b.{0,16}\b(?:vs\.?|versus|against)\b|"  # "games vs the Lakers"
    r"\b(?:vs\.?|versus|against)\b.{0,90}\bgames?\b",  # "against the Wizards... list every game"
    re.IGNORECASE)
# Season averages and career-history phrasing are NOT game-log
# questions: the tool only covers 2025-26 warehouse logs.
_GAMELOG_NO_RX = re.compile(
    r"\baverag\w*|\bavg\b|\bppg\b|\bper game\b|"
    r"\bcareer\b|\ball[\s-]*time\b|\blast season\b",
    re.IGNORECASE)
# Single-player season-average asks ("how many assists per game does
# Jokic average") are not game-log questions and not league questions:
# route them to get_season_averages. Career/all-time/last-season stay
# with the planner (season resolution lives there).
_SEASON_AVG_RX = re.compile(
    r"\baverag\w*|\bavg\b|\bper game\b|\b[prs]pg\b|\bapg\b|"
    r"\bbpg\b|\bspg\b|\bmpg\b|"
    # QA #61/64: season-form performance asks ("how is James playing
    # this season?") must answer from the 60-game season line, not an
    # 8-game gamelog sample narrated as the season.
    r"\bhow (?:is|has|'s)\b.{0,40}\bplay(?:ing|ed)\b|"
    r"\bhow['’]?s\b.{0,30}\bthis season\b",
    re.IGNORECASE)
_SEASON_LINE_RX = re.compile(
    r"\bseason (?:average|averages|avg|line|numbers|stats?|"
    r"performance)\b", re.IGNORECASE)
_SEASON_AVG_NO_RX = re.compile(
    r"\bcareer\b|\ball[\s-]*time\b|\blast season\b|"
    r"\blast \d+ games?\b|\blately\b|\brecent(?:ly)?\b",
    re.IGNORECASE)
# League-wide leader questions have no named player, so the
# player-scoped fast-path can't fire ("who had the most 50-point games
# this season"). The planner free-forms these into text_to_sql and
# improvises, so route them to search_game_logs with league_wide=True.
# Conservative: requires a who/which + most + stat-games phrasing; the
# multi-player compare ("who had more 40-point games, X or Y?") names
# players and is excluded by the no-named-player gate in _triage_seed.
_LEAGUE_LEADERS_RX = re.compile(
    r"\b(?:who|which(?:\s+player)?)\b.{0,40}\bmost\b.{0,80}?"
    r"(?:\b\d{2}\s*[-–—]?\s*points?\s+games?\b|"
    r"\btriple[\s-]*doubles?\b|"
    r"\bdouble[\s-]*doubles?\b|"
    r"\b\d{1,2}\s*[-–—]?\s*rebounds?\s+games?\b|"
    r"\b\d{1,2}\s*[-–—]?\s*assists?\s+games?\b)",
    re.IGNORECASE)
# Existence phrasing of the same league-wide ask ("did anyone score 60
# points this season?", "was there a 60-point game this season?") also
# has no named player, so it needs the same league-wide fast-path
# instead of the planner. Conservative: requires a two-digit points
# number with points/game wording, or a scoring verb + two-digit
# number ("has anyone dropped 50 this season?"). Player-scoped asks
# name a player and stay on the player path via the no-named-player
# gate in _triage_seed.
_LEAGUE_EXISTENCE_RX = re.compile(
    r"(?:\b(?:did|has|have)\b.{0,40}?\banyone\b.{0,60}?"
    r"(?:\b\d{2}\s*[-–—\s]?\s*(?:points?|pts?)\b|"
    r"(?:scored|dropped|posted|recorded)\s+\d{2}\b)|"
    r"\b(?:was|were|is|are)\b.{0,20}?\bthere\b.{0,40}?"
    r"\b\d{2}\s*[-–—\s]?\s*(?:points?|pts?)\s+games?\b|"
    r"\bany\b.{0,10}?\b\d{2}\s*[-–—\s]?\s*(?:points?|pts?)"
    r"\s+games?\b)",
    re.IGNORECASE)
# Team-population phrasing ("which team had the most 50-point games
# this season?") matches _LEAGUE_LEADERS_RX (which + most +
# stat-games) but must not answer per-player: it needs the team_wide
# mode of search_game_logs. Same stat alternation as _LEAGUE_LEADERS_RX.
# Player-scoped asks name a player and stay on the player path via the
# no-named-player gate in _triage_seed.
_LEAGUE_TEAM_RX = re.compile(
    r"\b(?:which|what)\b.{0,40}\bteams?\b.{0,80}?"
    r"(?:\b\d{2}\s*[-–—]?\s*points?\s+games?\b|"
    r"\btriple[\s-]*doubles?\b|"
    r"\bdouble[\s-]*doubles?\b|"
    r"\b\d{1,2}\s*[-–—]?\s*rebounds?\s+games?\b|"
    r"\b\d{1,2}\s*[-–—]?\s*assists?\s+games?\b)",
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
    # Surname-only references ("a Brunson for Wembanyama trade"): full-name
    # matching never fires, and downstream pins that need found_p miss the
    # lane entirely (2026-09-13 probe: a legality ask fell to the planner,
    # which answered value instead). Add a player when their surname is
    # capitalized in the original question and UNIQUE among ACTIVE players
    # (the all-time pool shares surnames like Brunson with retired
    # players). Shared surnames stay for resolve_entity; the case gate
    # keeps lowercase common words ("love", "ball") from becoming players.
    _suffixes = {"jr.", "sr.", "ii", "iii", "iv"}
    from nba_api.stats.static import players as _static_players
    _by_surname: dict[str, list] = {}
    for ap in _static_players.get_active_players():
        fn = ap.get("full_name", "")
        if not fn:
            continue
        toks = [t for t in fn.split() if t.lower() not in _suffixes]
        if not toks:
            continue
        _by_surname.setdefault(_norm(toks[-1]), []).append((toks[-1], fn))
    for sur, entries in _by_surname.items():
        if len(entries) != 1:
            continue
        disp, fn = entries[0]
        if len(sur) < 3 or fn in found_p:
            continue
        for _m in re.finditer(r"\b" + re.escape(disp) + r"\b", question):
            # First-name position guard: "Cooper Flagg" must not detect
            # Sharife Cooper. A surname used as a surname is followed by
            # a lowercase or punctuated token, not another Capitalized
            # name token.
            _rest = question[_m.end():].lstrip()
            if _rest[:1].isupper():
                continue
            # Hyphenated-surname fragment guard: the "Alexander" in
            # "Gilgeous-Alexander" is not a mention of Trey Alexander.
            # It added a phantom second player to carry scans and
            # flaked the F67 T3 playoff pin (battery run8/run12,
            # 2026-09-13).
            if _m.start() > 0 and question[_m.start() - 1] == "-":
                continue
            found_p.append(fn)
            break
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
                # F68/F69: abbreviations match case-SENSITIVELY -
                # case-insensitive matching read the word "was" as WAS
                # (Washington Wizards) and silently derailed carry
                # chains ("Who was their best player?" -> Wizards
                # thought line + wrong-team pull). Real abbreviations
                # arrive uppercase; lowercase intent is caught by the
                # city/nickname branches.
                or re.search(r"\b" + re.escape(t.get("abbreviation", "")) + r"\b",
                             question)):
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


def _detect_carry_players(text: str) -> list[str]:
    """Carry-time player detection for history turns: full entity
    detection first, then distinctive surname-only mentions ("What is
    Brunson averaging?"). The pronoun gate upstream already
    established a referent, and coerce_player_id raises on
    multi-active namesakes (QA #59), so a resolved surname is
    unambiguous enough to carry."""
    found, _ = _detect_entities(text)
    if found:
        return found
    from nba_api.stats.static import players as _static_players
    out: list[str] = []
    for _m in re.finditer(r"\b[A-Z][a-z]{3,}\b", text):
        tok = _m.group(0)
        # Hyphenated-surname fragment: "Alexander" inside
        # "Gilgeous-Alexander" is not a surname mention - it carried
        # Trey Alexander alongside SGA, broke the one-carried-player
        # gate, and flaked the F67 T3 playoff pin (battery run8/run12,
        # 2026-09-13). A real second mention of a hyphenated player
        # still resolves through full detection above.
        if _m.start() > 0 and text[_m.start() - 1] == "-":
            continue
        # Unique ACTIVE player with this exact surname ("Brunson" ->
        # Jalen; Rick is inactive). Ties and namesakes carry nothing -
        # same conservatism as the question-time loose-name rule.
        try:
            exact = [x for x in
                     _static_players.find_players_by_last_name(tok)
                     if x.get("is_active")
                     and x.get("full_name", "").split()[-1].lower()
                     == tok.lower()]
        except Exception:
            continue
        if len(exact) == 1:
            nm = str(exact[0].get("full_name") or "")
            if nm and nm not in out:
                out.append(nm)
        if len(out) >= 3:
            break
    return out


def _direct_named_players(question: str, found_p: list[str]) -> list[str]:
    """Players named outright in the raw question text.

    _detect_entities expands nicknames before matching, so a nickname
    can surface a player the user never meant (e.g. a stray "Bron").
    The game-log fast-path needs exactly the player asked about, so
    re-match full names (or known nicknames) against the raw question,
    mirroring what _direct_named_teams does for teams.
    """
    from .tools._core import NICKNAMES

    def _norm(s: str) -> str:
        import unicodedata as _ud

        return "".join(c for c in _ud.normalize("NFKD", s or "")
                       if not _ud.combining(c)).lower()

    rev: dict[str, list[str]] = {}
    for nick, full in NICKNAMES.items():
        rev.setdefault(_norm(full), []).append(nick)
    q = _norm(question)
    out = []
    for full in found_p:
        nfull = _norm(full)
        if nfull in q:
            out.append(full)
            continue
        for nick in rev.get(nfull, []):
            if re.search(r"\b" + re.escape(nick) + r"\b", q):
                out.append(full)
                break
    return out


def _gamelog_args(question: str, player: str | None,
                  teams: list[str]) -> dict[str, Any]:
    """Parse search_game_logs args from a triage-claimed question.

    Conservative: only set what the regexes can see; everything else
    keeps the tool default. Opponent prefers the re-matched team entity
    over raw text extraction. player None means league-wide mode: the
    caller sets league_wide=True.
    """
    from .tools.gamelog import MONTH_NAMES

    args: dict[str, Any] = {}
    if player is not None:
        args["player"] = player
    q = question or ""
    if _GAMELOG_BEST_RX.search(q):
        # "best game" / "career high" / "season high" / "most points":
        # answer with the single max-points game, not a filtered list.
        args["best_game"] = True
    # F57: "under 20 points" is a CEILING, not a floor - mapping it to
    # min_points inverted the filter (returned every 20+ game, then the
    # narrative honestly reported the wrong set as empty). Detect
    # under/at-most qualifiers before the floor regexes see the digits.
    _mu = (re.search(r"\b(?:under|below|fewer\s+than|less\s+than)"
                     r"\s+(\d{1,3})\s*[-–—\s]?\s*(?:points?|pts?)\b",
                     q, re.IGNORECASE)
           or re.search(r"(?:scored|dropped|posted|recorded)\s+"
                        r"(?:under|below|fewer\s+than|less\s+than)"
                        r"\s+(\d{1,3})\b", q, re.IGNORECASE))
    _ma = re.search(r"\b(?:no\s+more\s+than|at\s+most|not\s+more\s+than)"
                    r"\s+(\d{1,3})\s*[-–—\s]?\s*(?:points?|pts?)\b",
                    q, re.IGNORECASE)
    if _mu:
        args["max_points"] = int(_mu.group(1))
    elif _ma:
        # "no more than 20" includes 20: exclusive ceiling N+1.
        args["max_points"] = int(_ma.group(1)) + 1
    else:
        m = (re.search(r"\b(\d{2})\s*[-–—\s]?\s*(?:points?|pts?)\b", q,
                       re.IGNORECASE)
             or re.search(r"(?:scored|had|dropped|posted|recorded)\s+(\d{2})"
                          r"\s*(?:\+|or more)?\s*(?:points?|pts?)\b", q,
                          re.IGNORECASE)
             # Bare "dropped 50" / "scored 60" (existence phrasing like "has
             # anyone dropped 50 this season?"). "had" is excluded: "had 12
             # rebounds" is a rebound ask, not a points floor.
             or re.search(r"(?:scored|dropped|posted|recorded)\s+(\d{2})\b",
                          q, re.IGNORECASE))
        if m:
            args["min_points"] = int(m.group(1))
    for _cap, _key in (("rebounds?", "max_rebounds"),
                       ("assists?", "max_assists")):
        _mu2 = re.search(r"\b(?:under|below|fewer\s+than|less\s+than)"
                         r"\s+(\d{1,2})\s*" + _cap + r"\b",
                         q, re.IGNORECASE)
        if _mu2:
            args[_key] = int(_mu2.group(1))
    if "max_rebounds" not in args:
        m = (re.search(r"\b(\d{1,2})\s*[-–—]\s*rebounds?\b", q, re.IGNORECASE)
             or re.search(r"(?:with|had|posted|grabbed)\s+(\d{1,2})\+?"
                          r"\s*rebounds?\b", q, re.IGNORECASE))
        if m:
            args["min_rebounds"] = int(m.group(1))
    if "max_assists" not in args:
        m = (re.search(r"\b(\d{1,2})\s*[-–—]\s*assists?\b", q, re.IGNORECASE)
             or re.search(r"(?:with|had|posted|dished)\s+(\d{1,2})\+?"
                          r"\s*assists?\b", q, re.IGNORECASE))
        if m:
            args["min_assists"] = int(m.group(1))
    if re.search(r"\btriple[\s-]*doubles?\b", q, re.IGNORECASE):
        args["triple_double"] = True
    elif re.search(r"\bdouble[\s-]*doubles?\b", q, re.IGNORECASE):
        args["double_double"] = True
    if teams and re.search(r"\bvs\.?|\bversus\b|\bagainst\b", q,
                           re.IGNORECASE):
        args["opponent"] = teams[0]
    else:
        m = re.search(
            r"(?:\bvs\.?|\bversus\b|\bagainst\b)\s+(?:the\s+)?"
            r"([A-Za-z][A-Za-z.'&-]*(?:\s+[A-Za-z][A-Za-z.'&-]*)*)",
            q, re.IGNORECASE)
        if m:
            toks = m.group(1).split()
            stop = {"this", "last", "next", "season", "year", "games",
                    "game", "at", "in", "on", "his", "her", "their",
                    "a", "an", "the"}
            while toks and toks[-1].lower() in stop:
                toks.pop()
            if toks:
                args["opponent"] = " ".join(toks[:3])
    for name in MONTH_NAMES:
        if re.search(r"\b" + name + r"\b", q, re.IGNORECASE):
            args["month"] = name
            break
    if re.search(r"\bat home\b|\bhome games?\b", q, re.IGNORECASE):
        args["home_away"] = "home"
    elif re.search(r"\bon the road\b|\baway games?\b", q, re.IGNORECASE):
        args["home_away"] = "away"
    if re.search(r"\bplayoffs?\b|\bpostseason\b", q, re.IGNORECASE):
        args["playoffs"] = True
    return args


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


def _money_m(v: object) -> str:
    try:
        return f"${float(v) / 1_000_000:.1f}M"
    except (TypeError, ValueError):
        return "an unknown amount"


def _trade_verdict_text(rows: dict[str, Any]) -> str:
    """Deterministic trade verdict from the get_trade_check payload.

    QA 2026-09-13: the LLM verdict inverted the constraint ("SAS cannot
    receive enough") while its own takeaways stated it correctly - the
    classic whack-a-mole the v67 law bans. On the pinned trade lane the
    answer ships payload-built text: side A sends rows.team_a.out and
    receives rows.team_b.out, capped at rows.team_a.allowed_in (and the
    mirror for B), so the receiving limit and the outgoing salary can
    never be swapped by compose variance.
    """
    a = rows.get("team_a") or {}
    b = rows.get("team_b") or {}
    ta = str(a.get("team") or "Team A")
    tb = str(b.get("team") or "Team B")
    pa = ", ".join(str(p) for p in a.get("players") or []) or "unnamed players"
    pb = ", ".join(str(p) for p in b.get("players") or []) or "unnamed players"
    out_a, out_b = _money_m(a.get("out")), _money_m(b.get("out"))
    allow_a = _money_m(a.get("allowed_in"))
    allow_b = _money_m(b.get("allowed_in"))
    rule_a = str(a.get("match_rule") or "salary matching")
    rule_b = str(b.get("match_rule") or "salary matching")
    lines: list[str] = []
    if rows.get("legal"):
        lines.append("Legal under the simplified 2023 CBA "
                     "salary-matching rules.")
    else:
        lines.append("Not legal as constructed.")
    def _f(v: object) -> float | None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    legal = bool(rows.get("legal"))
    for team, send, recv, allow, rule, inc, cap in (
            (ta, out_a, out_b, allow_a, rule_a,
             _f(b.get("out")), _f(a.get("allowed_in"))),
            (tb, out_b, out_a, allow_b, rule_b,
             _f(a.get("out")), _f(b.get("allowed_in")))):
        ok = (inc <= cap) if (inc is not None and cap is not None) else legal
        line = (f"{team} sends out {send} and takes back {recv}; "
                f"{team} can receive at most {allow} under the {rule} "
                "rule")
        if ok:
            line += " - within the limit."
        elif inc is not None and cap is not None:
            line += (f" - ${(inc - cap) / 1_000_000:.1f}M over, "
                     "so the trade fails here.")
        else:
            line += " - over the limit, so the trade fails here."
        lines.append(line)
    for issue in rows.get("issues") or []:
        s = str(issue)
        if "takes back too much" not in s:
            lines.append(s[0].upper() + s[1:] + ".")
    corr = rows.get("attribution_corrections") or []
    if corr:
        lines.append("Roster corrections applied: "
                     + "; ".join(str(c) for c in corr) + ".")
    sal_date = str(rows.get("salary_date") or "").strip()[:10]
    disc = ("Estimate only with simplified rules - cash, trade "
            "exceptions, taxpayer midlevel, frozen picks, Stepien, "
            "base-year, trade kickers and sign-and-trades are not "
            "modeled.")
    if sal_date:
        disc = f"Salary figures as of {sal_date}. " + disc
    lines.append(disc)
    return "\n".join(lines)


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
        # QA #70: "the Luka trade" names the player by FIRST name only.
        # Keep any distinctive (4+ char) name token, first or last -
        # ambiguity is handled downstream by coerce_player_id.
        if (low in raw_q
                or re.search(r"\b" + re.escape(last) + r"\b", raw_q)
                or any(re.search(r"\b" + re.escape(tok) + r"\b", raw_q)
                       for tok in low.split() if len(tok) >= 4)):
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
    resolved: list[tuple[str, int]] = []
    for p in found_p:
        try:
            pid = coerce_player_id(p)
        except Exception:
            continue
        if pid:
            resolved.append((p, pid))
    team_of: dict[int, str] = {}
    if resolved:
        import time as _time

        from collections import Counter as _Counter

        from . import store

        entities = [f"player:{pid}" for _, pid in resolved]
        placeholders = ", ".join(["?"] * len(entities))
        batched: dict[int, str] = {}
        batched_ok = False
        for _ in range(3):
            try:
                con = store.connect()
                try:
                    rows = con.execute(
                        "SELECT _entity, MATCHUP FROM (SELECT _entity, MATCHUP,"
                        " ROW_NUMBER() OVER (PARTITION BY _entity) AS _rn"
                        " FROM silver_player_gamelogs"
                        " WHERE _season = ? AND _entity IN (" + placeholders + "))"
                        " WHERE _rn <= 40",
                        [season, *entities],
                    ).fetchall()
                finally:
                    con.close()
                per: dict[str, list] = {}
                for ent, matchup in rows:
                    per.setdefault(ent, []).append(matchup)
                for _, pid in resolved:
                    c = _Counter(str(m or "").split(" ")[0]
                                 for m in per.get(f"player:{pid}", []))
                    c.pop("", None)
                    if c:
                        batched[pid] = c.most_common(1)[0][0]
                batched_ok = True
                break
            except Exception:
                _time.sleep(0.2)
        if batched_ok:
            team_of = batched
        else:
            for p, pid in resolved:
                ab = _player_team_abbr(pid, season) if pid else ""
                if ab:
                    team_of[pid] = ab
    for p, pid in resolved:
        ab = team_of.get(pid, "")
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
    # QA #70: a side with no named players is NOT a bail - the tool
    # turns it into the fast informative refusal ("past trade's other
    # side is not in this dataset"). Bail only when neither side has
    # players at all.
    if not players_a and not players_b:
        return None
    return {"team_a": side_a, "players_a": ", ".join(players_a),
            "team_b": side_b, "players_b": ", ".join(players_b)}


def _triage_plan_text(question: str, found_p: list[str],
                        found_t: list[str], has_history: bool) -> str:
    names = (found_p or []) + (found_t or [])
    prefix = f"Found {', '.join(names[:3])} — " if names else ""
    q = question or ""
    is_trade = bool(re.search(r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b|\bdeal\b|\blegal(?:ity)?\b",
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
        # F43: desk reasoning tokens streamed raw into the expanded
        # progress UI ("I need to query the warehouse...", sandbox
        # errors with '!' markers). Progress now comes only from
        # labeled tool_call events; drain the queue, emit nothing raw.
        continue
    await runner
    # NOTE: without a yield this compiles as a coroutine and every
    # 'async for' caller dies with "requires an object with aiter
    # method, got coroutine" - the exact text that leaked as a final
    # answer in F46's blowout probe. Emit one sanitized desk-done
    # status instead of the raw token stream.
    _res = holder.get("result") or {}
    _ok = not (isinstance(_res, dict) and _res.get("ok") is False)
    yield _event("thought_stream", {
        "node": node,
        "text": (f"{desk.title()} desk finished." if _ok
                 else f"{desk.title()} desk hit a snag; checking the rest of the evidence."),
    })


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
                terr = _user_safe_tool_error(tname, str(te.get("error")))
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
        # F43/F44: this field streams live into the progress UI, which
        # rendered raw SQL errors ('ambiguous reference to column
        # TEAM_ID ... LINE 42'). The model still sees the full error in
        # state; the stream gets a sanitized line.
        try:
            payload["error"] = _user_safe_tool_error(
                name, str(out.get("error") or ""))
        except Exception:
            payload["error"] = "failed"
    return payload


def _user_safe_tool_error(name: str, err: str) -> str:
    """One sanitized clause for streamed tool errors. Never SQL, never
    column names, never sandbox internals."""
    if not err:
        return "failed"
    low = err.lower()
    if "disabled for this run" in low:
        return "skipped after repeated failures"
    if "unknown player" in low:
        base = _clean_error_text(err)
        return (base[:120] or "player not found")
    base = _clean_error_text(err)
    if not base or len(base) < 12 or "column" in low or "select" in low:
        return "that data pull did not complete"
    return base[:120]


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
    _orig_p, _orig_t = list(found_p), list(found_t)
    if state.get("history") and re.search(
            r"\b(him|her|them|they|his|hers|their|theirs|it|he|she|"
            r"that team|that player)\b",
            question, re.IGNORECASE):
        # Player carry prefers the SUBJECT of prior asks (user turns);
        # answer mentions follow only when no ask named anyone - the
        # F64 flake: a playoff-avg answer that happened to name a
        # second player broke the one-carried-player pin gate 1/3 of
        # the time. Team carry keeps the all-turns recency scan (the
        # F67 "their best player" chain resolves the team FROM the
        # answer - "best record?" names no team in the ask).
        _hist = state["history"][-6:]
        _user_turns = [t for t in _hist if t.get("role") == "human"]
        for t in _user_turns:
            for p in _detect_carry_players(t.get("text") or ""):
                if p not in found_p and len(found_p) < 3:
                    found_p.append(p)
        if not found_p:
            # F67-chain flake (battery run8/run12, 2026-09-13): the asks
            # named nobody ("best record?" / "their best player?"), so
            # the user-turn scan found no referent for "he" and the old
            # `_user_turns or _hist` fell through only when NO user
            # turns existed - the answer that DID name the player (the
            # T2 pin's SGA) was ignored and the T3 playoff pin wobbled
            # to planner variance.
            # Answer mentions are the fallback when user turns name no
            # one; when a user turn DID name someone (the F64 case),
            # this never runs and the one-carried-player gate holds.
            for t in reversed(_hist):
                for p in _detect_carry_players(t.get("text") or ""):
                    if p not in found_p and len(found_p) < 3:
                        found_p.append(p)
        for t in _hist:
            for tm in _detect_entities(t.get("text") or "")[1]:
                if tm not in found_t and len(found_t) < 2:
                    found_t.append(tm)
        # S4: surface carry to the client so the UI can say "picking up
        # from earlier" instead of pretending the pronoun was explicit.
        _carried_p = [p for p in found_p if p not in _orig_p]
        _carried_t = [t for t in found_t if t not in _orig_t]
        if _carried_p or _carried_t:
            state["carry_note"] = {"players": _carried_p,
                                   "teams": _carried_t}
    yield _event("thought_stream", {
        "node": "data_retrieval",
        "text": _triage_plan_text(question, found_p, found_t, bool(state.get("history"))),
    })
    is_compare = bool(_COMPARE_RX.search(question))
    is_trade = bool(re.search(r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b|\bdeal\b|\blegal(?:ity)?\b",
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
    _named = _direct_named_teams(question, found_t)
    is_matchup_splits = (
        len(_named) == 2
        and _MATCHUP_SPLITS_RX.search(question)
        and not is_trade
        and not is_cast
        and not _PREDICT_LIVE_RX.search(question)
        and not state.get("history")
    )
    if is_matchup_splits:
        # B2: planner-owned matchup-splits ask looped 5 rounds (188s turn)
        # retrying a failing tool; answer straight from warehouse splits.
        _decisive = True
        for t in _named[:2]:
            _mh: dict[str, Any] = {}
            async for _e in _triage_tool(
                    "get_team_splits", {"team": t}, state, _mh):
                yield _e
            _mout = _mh.get("out") or {}
            if _result_status(_mout) != "ok" or not _result_rows(_mout):
                _decisive = False
        if _decisive:
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    _named_p = _direct_named_players(question, found_p)
    is_gamelog = (
        len(_named_p) == 1
        and _GAMELOG_RX.search(question)
        # "career high" trips _GAMELOG_NO_RX's "career" guard, which is
        # meant for career averages, not single-game highs.
        and (_GAMELOG_BEST_RX.search(question)
             or not _GAMELOG_NO_RX.search(question))
        and not is_trade
        and not is_cast
        and not _PREDICT_LIVE_RX.search(question)
        and not state.get("history")
    )
    if is_gamelog:
        # Demo bug: the planner free-formed a game-log question into
        # text_to_sql, hit "unknown table or column" on
        # silver_player_gamelogs, and streamed the red error row.
        # search_game_logs owns the per-player log pipeline, so answer
        # straight from the warehouse. Only on clean single-turn
        # questions with exactly one named player; anything uncertain
        # (no clear player, multi-player, averages/career phrasing)
        # falls through to the planner.
        _gh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "search_game_logs",
                _gamelog_args(question, _named_p[0], _named), state, _gh):
            yield _e
        _gout = _gh.get("out") or {}
        if _result_status(_gout) == "ok":
            # _triage_tool appended the raw tool dict. analytics_agent
            # only treats tool_results entries with a non-empty "rows"
            # key as evidence, so wrap it the same way the prediction
            # fast-path does; otherwise the turn falls into the canned
            # no-data branch and the LLM never runs.
            if state["tool_results"] and state["tool_results"][-1] is _gout:
                state["tool_results"][-1] = {
                    "tool": "search_game_logs", "rows": [_gout]}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    # QA #67 route pins - the planner is non-deterministic, so known
    # phrasing classes get deterministic routes BEFORE it runs.
    # (a) truly-unanswerable known gaps (contract types, bench splits):
    # never run tools; inject the named-gap message as the sole error
    # so the no-evidence branch ships it verbatim.
    # QA #72 (F58): memory/preference statements are not data asks.
    # Pin a deterministic session-scoped acknowledgment BEFORE the
    # planner - unrouted, "favorite team is the Lakers" hit the team
    # desk, the resolver matched both Los Angeles teams, and the final
    # answer shipped "No Los Angeles Clippers data found."
    _mem_pin = _memory_ack(question)
    if _mem_pin:
        state["tool_results"].append(
            {"tool": "memory_note", "ok": False, "error": _mem_pin})
        async for _e in _triage_terminal(question, state):
            yield _e
        return
    # F66: multi-metric "top N teams" compares ("compare the top 3
    # scoring teams: total points, per-game average, and how many games
    # each won") escaped every pin, fanned out through delegate_league,
    # and shipped a NAMELESS table with empty cells and invented
    # numbers. Deterministic lane: get_team_compare joins the deduped
    # team-totals board with standings records; compose ships
    # meta.deterministic_answer verbatim. Guards: a named player or
    # named teams keep their own routes; single-stat totals asks keep
    # the team-totals pin below.
    _dc_top = re.search(r"\btop\s*(\d+)\b", question, re.IGNORECASE)
    _dc_stat = re.search(
        r"\b(scoring|points?|rebounding|rebounds?|assists?|steals?|"
        r"blocks?)\b", question, re.IGNORECASE)
    _dc_metrics = sum(
        bool(re.search(p, question, re.IGNORECASE)) for p in (
            r"\btotals?\b", r"per[\s-]*game|\baverages?\b|\bavg\b",
            r"\bwins?\b|\bwon\b|\brecord\b"))
    if (_dc_top and _dc_stat and _dc_metrics >= 2
            and not found_p and not found_t
            and re.search(r"\bteams?\b", question, re.IGNORECASE)):
        _dc_stat_map = {
            "scoring": "PTS", "point": "PTS", "points": "PTS",
            "rebounding": "REB", "rebound": "REB", "rebounds": "REB",
            "assist": "AST", "assists": "AST",
            "steal": "STL", "steals": "STL",
            "block": "BLK", "blocks": "BLK"}
        _dcseason = "2025-26"
        _dsm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _dsm:
            _dcseason = f"{_dsm.group(1)}-{_dsm.group(2)}"
        _dch: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_team_compare",
                {"stat_category": _dc_stat_map.get(
                     _dc_stat.group(1).lower(), "PTS"),
                 "top": int(_dc_top.group(1)), "season": _dcseason},
                state, _dch):
            yield _e
        _dcout = _dch.get("out") or {}
        if _result_status(_dcout) == "ok":
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    # F69 (2026-09-13 prod QA, Tony): "in your view who are the top 15
    # players in the league" was planner-routed to a STEALS leaderboard
    # presented as an overall ranking. Overall top-N player asks (no
    # single-stat keyword) pin to get_player_rankings: RAPM-lite for
    # current coverage, FiveThirtyEight WAR for 2014-15..2021-22, an
    # honest coverage note elsewhere. The deterministic answer names the
    # metric basis (v67 law: "in your view" still answers from the
    # payload). Burn-down: stat-qualified top-N asks keep get_leaders;
    # team top-N keeps the F66 pin above.
    _rk_m = re.search(
        r"\btop\s*(\d+)\s+(?:best\s+)?players?\b|"
        r"\bbest\s+(\d+)\s+players?\b|"
        r"\btop\s+players?\s+in\s+the\s+(?:league|nba)\b|"
        r"\bbest\s+players?\s+in\s+the\s+(?:league|nba)\b",
        question, re.IGNORECASE)
    if (_rk_m and not found_p and not found_t
            and not re.search(
                r"\bscor\w*|\bpoints?\b|\brebounds?\w*\b|"
                r"\bassists?\b|\bsteals?\b|\bblocks?\b|"
                r"\bthrees?\b|\b3-?pt|\bshoot\w*\b|"
                r"\bdefen[cs]\w*\b|\brookie|\bclutch\b|"
                r"\bhustle\b|\bdunk\w*\b",
                question, re.IGNORECASE)
            and not is_trade and not is_cast):
        _rk_n = int(next((g for g in _rk_m.groups() if g), "15"))
        _rkseason = "2025-26"
        _rkm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _rkm:
            _rkseason = f"{_rkm.group(1)}-{_rkm.group(2)}"
        _rkh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_player_rankings", {"n": _rk_n, "season": _rkseason},
                state, _rkh):
            yield _e
        _rkout = _rkh.get("out") or {}
        if _result_status(_rkout) == "ok" and _rkout.get("rows"):
            _rkmetric = (_rkout.get("meta") or {}).get("metric")
            if _rkmetric == "rapm_lite":
                _rkbasis = ("Ranked by RAPM-lite (regularized "
                            "plus-minus), the impact metric in the "
                            "warehouse; 2,000-possession minimum")
                _rkrows_txt = "\n".join(
                    f"{r['rank']}. {r['player']} (RAPM {r['rapm']})"
                    for r in _rkout["rows"])
            else:
                _rkbasis = ("Ranked by FiveThirtyEight WAR "
                            "(RAPTOR vintage)")
                _rkrows_txt = "\n".join(
                    f"{r['rank']}. {r['player']} "
                    f"({r['war']} WAR, {r['raptor']} RAPTOR)"
                    for r in _rkout["rows"])
            _rkdet = (f"Top {len(_rkout['rows'])} players, "
                      f"{_rkseason} season. {_rkbasis}:\n"
                      + _rkrows_txt)
            _rkout.setdefault("meta", {})["deterministic_answer"] = _rkdet
            if state["tool_results"] and state["tool_results"][-1] is _rkout:
                state["tool_results"][-1] = {
                    "tool": "get_player_rankings",
                    "rows": _rkout["rows"], "meta": _rkout["meta"]}
            async for _e in _triage_terminal(question, state):
                yield _e
        else:
            # Uncovered season: ship the honest coverage note from the
            # tool error instead of the generic refusal.
            _rkerr = (_rkout.get("error") or
                      "No overall impact metric covers that season.")
            state["analysis"] = str(_rkerr)
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    # Tony live find (11:54 AM): team-TOTAL counting-stat asks ("which
    # team leads in total assists this season?") dead-ended honestly -
    # get_leaders is player-level and the league desk said team totals
    # are "not explicitly reported". They are one aggregation away:
    # pin straight to get_team_leaders (game logs summed by team).
    # Guards: no named player, no "player" word - player-leader
    # phrasings keep their routes.
    _tt_m = re.search(
        r"\bteam(?:s|\b).{0,45}?\b(?:total|most|leads?|best|highest|top)\b"
        r".{0,30}?\b(assists?|rebounds?|points?|steals?|blocks?)\b|"
        r"\b(assists?|rebounds?|points?|steals?|blocks?)\b.{0,20}?"
        r"\bby team\b", question, re.IGNORECASE)
    if (_tt_m and not found_p
            and not re.search(r"\bplayers?\b", question, re.IGNORECASE)
            # single-game asks ("most 50-point games") belong to the
            # gamelog team-wide fast path, not season totals
            and not re.search(r"\bgames?\b|\d+\s*-?\s*pts?\b|"
                              r"\d+-point", question, re.IGNORECASE)):
        _tt_word = (_tt_m.group(1) or _tt_m.group(2) or "").lower()
        _tt_stat = {"assist": "AST", "assists": "AST",
                    "rebound": "REB", "rebounds": "REB",
                    "point": "PTS", "points": "PTS",
                    "steal": "STL", "steals": "STL",
                    "block": "BLK", "blocks": "BLK"}.get(_tt_word, "AST")
        _tseason = "2025-26"
        _tsm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _tsm:
            _tseason = f"{_tsm.group(1)}-{_tsm.group(2)}"
        _tth: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_team_leaders",
                {"stat_category": _tt_stat, "season": _tseason},
                state, _tth):
            yield _e
        _tt_out = _tth.get("out") or {}
        if _result_status(_tt_out) == "ok":
            # No rows=[payload] wrap: rows are already the leaderboard
            # list (get_risers/QA #23 convention).
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    # QA #74 (F60): "Who won the 2026 Finals?" - the marquee phrasing -
    # dead-ended to the generic fallback under planner variance (8s/2
    # tools) while the long phrasing worked. The playoffs payload
    # carries the finals block deterministically; pin it. Guards: no
    # MVP (award known-gap owns that), no future/prediction phrasing,
    # no named player, clean single-turn only.
    # F63: a Finals series ask ("who did X beat", "series score") is the
    # same deterministic lane even mid-thread - allow history then.
    _fin_series_ask = bool(
        re.search(r"\bfinals\b", question, re.IGNORECASE)
        and re.search(r"\bseries (?:score|result)\b|\bwho did\b[^?]*\bbeat\b|"
                      r"\bgame[- ]by[- ]game\b|\bwalk (?:me )?through\b|"
                      r"\beach game\b|\bevery game\b",
                      question, re.IGNORECASE))
    if (((re.search(r"\bfinals\b", question, re.IGNORECASE)
          and re.search(r"\bwho (?:won|wins|took)\b|\bwinner\b|"
                        r"\bwho did\b[^?]*\bbeat\b|"
                        r"\bchampions?(?:ship)?\s+(?:winner|result)|"
                        r"\bgame[- ]by[- ]game\b|\bwalk (?:me )?through\b|"
                        r"\beach game\b|\bevery game\b|"
                        r"\bchampions?\b", question, re.IGNORECASE))
         or (re.search(r"\bchampions?\b|\btitle\b", question, re.IGNORECASE)
             and re.search(r"\b20\d\d\b|\bnba\b|\bthis (?:year|season)\b",
                           question, re.IGNORECASE)
             and re.search(r"\bwho\b|\bwinner\b|\bchampions?\b",
                           question, re.IGNORECASE)))
            and not re.search(r"\bmvp\b|\bwill\b|\bgoing to\b|\bodds\b|"
                              r"\bpredict", question, re.IGNORECASE)
            and not found_p
            and (not state.get("history") or _fin_series_ask)):
        _fseason = "2025-26"
        _fm = re.search(r"\b(20\d\d)\b", question)
        if _fm:
            _fy = int(_fm.group(1))
            _fseason = f"{_fy - 1}-{str(_fy)[2:]}"
        _fh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_playoffs", {"season": _fseason}, state, _fh):
            yield _e
        _fout = _fh.get("out") or {}
        if _result_status(_fout) == "ok":
            _meta = dict(_fout.get("meta") or {})
            # Game-by-game / walkthrough asks ship deterministic (v67
            # law): the LLM given this payload answered with only the
            # headline, and mid-thread it once claimed no Finals data
            # existed at all. Build the listing from the payload.
            if re.search(r"\bgame[- ]by[- ]game\b|\bwalk (?:me )?through\b|"
                         r"\beach game\b|\bevery game\b",
                         question, re.IGNORECASE):
                _fin = ((_fout.get("rows") or {}).get("finals")
                        if isinstance(_fout.get("rows"), dict) else None) or {}
                _games = sorted(_fin.get("games") or [],
                                key=lambda g: str(g.get("date") or ""))
                if _games:
                    from datetime import datetime as _dt2

                    _lines = [f"Finals series: {_fin.get('series_score')}."]
                    for _i, _g in enumerate(_games, 1):
                        try:
                            _gd = _dt2.strptime(str(_g.get("date")),
                                                "%Y-%m-%d").strftime("%b %-d")
                        except (TypeError, ValueError):
                            _gd = str(_g.get("date") or "")
                        _line = f"Game {_i} ({_gd}): "
                        if _g.get("scoreline"):
                            _line += str(_g["scoreline"]) + " - "
                        else:
                            _line += str(_g.get("matchup") or "") + " - "
                        _line += f"{_g.get('winner')} won"
                        if _g.get("home"):
                            _line += (f" at home" if _g.get("home")
                                      == _g.get("winner")
                                      else f" on the road at {_g['home']}")
                        _lines.append(_line + ".")
                    _note = _fin.get("finals_mvp_note")
                    if _note:
                        _lines.append(str(_note))
                    _meta["deterministic_answer"] = "\n".join(
                        "- " + ln if ln.startswith("Game ") else ln
                        for ln in _lines)
            if state["tool_results"] and state["tool_results"][-1] is _fout:
                state["tool_results"][-1] = {
                    "tool": "get_playoffs", "rows": [_fout],
                    "meta": _meta}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    # Contract-value asks ("most overpaid", "best value contracts").
    # Sweep3: this lane ran a 15-tool, 65s planner fan-out and composed
    # empty slots ("His salary of exceeds a predicted value of by a
    # residual of ."). Pin it: one get_contract_value call and a
    # deterministic board built from the payload (v67 law: LLM-composed
    # numerals are untrusted on pinned lanes).
    # Burn-down: belongs in a generic ranking-board pin framework.
    if (re.search(r"\boverpaid\b|\bunderpaid\b|\bbest value\b|"
                  r"\bworst value\b|\bvalue contracts?\b|"
                  r"\bbiggest bargains?\b", question, re.IGNORECASE)
            and not found_p
            and not re.search(r"\btrade\b|\btrad(e|ing)\b",
                              question, re.IGNORECASE)):
        _over = not re.search(r"\bunderpaid\b|\bbest value\b|"
                              r"\bbargain", question, re.IGNORECASE)
        _vargs: dict[str, Any] = {"season": "2025-26"}
        if found_t:
            _vargs["team"] = found_t[0]
        _vh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_contract_value", _vargs, state, _vh):
            yield _e
        _vout = _vh.get("out") or {}
        if _result_status(_vout) == "ok":
            _vrows = _vout.get("rows") or []
            _vmeta = _vout.get("meta") or {}
            _board = _vrows[:5] if _over else _vrows[10:15]
            if _board:
                def _m(v: object) -> str:
                    try:
                        return f"${float(v) / 1e6:.1f}M"
                    except (TypeError, ValueError):
                        return "?"
                _scope = _vmeta.get("team_scope")
                _title = ("Most overpaid" if _over
                          else "Best value (most underpaid)")
                _title += " contracts"
                if _scope:
                    _title += f" on {_scope}"
                _lines = [
                    f"{_title} - {_vmeta.get('salary_season', '2026-27')} "
                    f"salary vs production-predicted value:"]
                for _f in _board:
                    _res = _f.get("RESIDUAL") or 0
                    _lines.append(
                        f"- {_f.get('PLAYER')} ({_f.get('TEAM')}): "
                        f"{_m(_f.get('SALARY'))} salary vs "
                        f"{_m(_f.get('PREDICTED'))} predicted - "
                        f"{_m(abs(_res))} "
                        f"{'over' if _res > 0 else 'under'}.")
                _lines.append(
                    "Residual = salary minus an OLS-predicted value from "
                    "per-game production (PTS + 1.2*REB + 1.5*AST + 2*STL "
                    f"+ 2*BLK - 1.5*TOV) across "
                    f"{_vmeta.get('n_qualified', '?')} qualified players "
                    f"({_vmeta.get('min_gp', 20)}+ GP).")
                _vmeta = {**_vmeta,
                          "deterministic_answer": "\n".join(_lines)}
            if state["tool_results"] and state["tool_results"][-1] is _vout:
                state["tool_results"][-1] = {
                    "tool": "get_contract_value", "rows": _vrows,
                    "meta": _vmeta}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    # Player-vs-player head-to-head asks ("head to head between X and
    # Y"). Sweep3: this lane ran 11 tools / 92.5s and its LLM answer
    # once declared "no shared court time" while the teams had met.
    # Pin it: one get_compare call, deterministic answer from the
    # payload (season lines + actual meetings from the pair block).
    # Burn-down: DONE (2026-09-13) - widened from h2h-only to every
    # two-player compare after the LLM-composed efficiency compare
    # flaked under battery load (dropped a TS figure). One get_compare
    # call, deterministic answer from the payload; the scout-desk
    # enrichment from the former fast-path is traded for numerals that
    # cannot drift.
    # F68 (2026-09-13 prod QA): comparative FOLLOW-UPS carry no compare
    # keyword at all - "who has a better true shooting percentage
    # between them?" resolved both players via carry and still fell to
    # the planner, which flaked to the no-data refusal with an empty
    # supervisor note. When exactly two players are in scope (named or
    # carried), comparative adjectives are a compare ask.
    _two_player_comparative = bool(re.search(
        r"\bbetter\b|\bworse\b|\bhigher\b|\blower\b|\bbest\b|"
        r"\bstronger\b|\bmore efficient\b|\befficient\b",
        question, re.IGNORECASE)) and len(found_p) == 2
    if ((re.search(r"\bhead[- ]to[- ]head\b|\bh2h\b|\bcompare\b|"
                   r"\bvs\.?\b|\bversus\b", question, re.IGNORECASE)
         or _two_player_comparative)
            and len(found_p) == 2
            and not re.search(r"\bimpact\b|\brapm\b|on.off",
                              question, re.IGNORECASE)
            # Trade-value asks name two players and say "vs" but belong
            # to the get_trade_value fast-path (test_trade_latency).
            and not re.search(
                r"\btrad(e|es|ed|ing)\b|sign-and-trade|\bswap\b|"
                r"\bdeal\b", question, re.IGNORECASE)):
        _hh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_compare",
                {"a": found_p[0], "b": found_p[1], "season": "2025-26"},
                state, _hh):
            yield _e
        _hout = _hh.get("out") or {}
        if _result_status(_hout) == "ok":
            _hr = _hout.get("rows") or {}
            _a, _b = _hr.get("a") or {}, _hr.get("b") or {}
            _pair = _hr.get("pair") or {}

            def _pc(v: object) -> str:
                try:
                    return f"{float(v) * 100:.1f}%"
                except (TypeError, ValueError):
                    return "?"
            _lines = []
            for _p in (_a, _b):
                if _p.get("name"):
                    _lines.append(
                        f"- {_p['name']} ({_p.get('team', '?')}): "
                        f"{_p.get('ppg', '?')} pts, {_p.get('rpg', '?')} reb, "
                        f"{_p.get('apg', '?')} ast on {_pc(_p.get('ts_pct'))} "
                        f"TS over {_p.get('gp', '?')} games.")
            _meet = _pair.get("h2h_meetings") or []
            if _meet:
                _aw = sum(1 for m in _meet
                          if str(m.get("a_wl") or "").upper() == "W")
                _lines.append(
                    f"They shared the floor {len(_meet)} time(s) this "
                    f"season; {_a.get('name', 'player A')}'s team went "
                    f"{_aw}-{len(_meet) - _aw} in those games:")
                for _m in sorted(_meet, key=lambda g: str(g.get("date") or "")):
                    _lines.append(
                        f"- {_m.get('date')}: {_a.get('name', 'A')} "
                        f"{_m.get('a_pts', '?')} pts, {_b.get('name', 'B')} "
                        f"{_m.get('b_pts', '?')} pts "
                        f"({'W' if str(_m.get('a_wl') or '').upper() == 'W' else 'L'} "
                        f"for {_a.get('name', 'A')}).")
            elif _pair.get("note"):
                _lines.append(str(_pair["note"]))
            try:
                _tsa, _tsb = float(_a.get("ts_pct")), float(_b.get("ts_pct"))
                _ppa, _ppb = float(_a.get("ppg")), float(_b.get("ppg"))
                _eff = _a if _tsa >= _tsb else _b
                _vol = _a if _ppa >= _ppb else _b
                _lines.append(
                    f"Verdict: {_eff.get('name')} holds the efficiency edge "
                    f"({_pc(max(_tsa, _tsb))} vs {_pc(min(_tsa, _tsb))} TS); "
                    f"{_vol.get('name')} leads scoring volume "
                    f"({max(_ppa, _ppb):.1f} vs {min(_ppa, _ppb):.1f} ppg).")
            except (TypeError, ValueError):
                pass
            _hmeta = dict(_hout.get("meta") or {})
            _hmeta["deterministic_answer"] = "\n".join(_lines)
            if state["tool_results"] and state["tool_results"][-1] is _hout:
                state["tool_results"][-1] = {
                    "tool": "get_compare", "rows": [_hout],
                    "meta": _hmeta}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    # Clutch-scorer leaderboard asks ("best clutch scorers this
    # season"). Sweep3: this lane spent 16.8s on a delegate fan-out
    # for a board the warehouse already serves. Pin it: one get_clutch
    # call and a deterministic board built from the payload (v67 law:
    # LLM-composed numerals are untrusted on pinned lanes).
    # Burn-down: merge into a generic ranking-board pin framework with
    # the contract-value and standings boards.
    if (re.search(r"\bclutch\b", question, re.IGNORECASE)
            and re.search(r"\b(best|top|leaders?|scorers?|rank)\b",
                          question, re.IGNORECASE)
            and not found_p and not found_t
            and not re.search(r"\bteams?\b", question, re.IGNORECASE)):
        _cl: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_clutch", {"scope": "player", "season": "2025-26"},
                state, _cl):
            yield _e
        _clout = _cl.get("out") or {}
        if _result_status(_clout) == "ok":
            _crows = _clout.get("rows") or []
            _cmeta = dict(_clout.get("meta") or {})
            if _crows:
                _lines = [
                    "Clutch scoring leaders - final 5 minutes, margin "
                    "within 5 (2025-26):"]
                for _f in _crows[:5]:
                    try:
                        _fg = f"{float(_f.get('FG_PCT')) * 100:.1f}%"
                    except (TypeError, ValueError):
                        _fg = "?"
                    _pm = _f.get("PLUS_MINUS")
                    try:
                        _pmi = int(_pm)
                        _pms = f"+{_pmi}" if _pmi >= 0 else str(_pmi)
                    except (TypeError, ValueError):
                        _pms = "?"
                    _lines.append(
                        f"- {_f.get('PLAYER_NAME')}: {_f.get('PTS')} pts "
                        f"over {_f.get('GP')} clutch games on {_fg} FG "
                        f"(plus-minus {_pms}).")
                _cmeta["deterministic_answer"] = "\n".join(_lines)
            if state["tool_results"] and state["tool_results"][-1] is _clout:
                state["tool_results"][-1] = {
                    "tool": "get_clutch", "rows": _crows, "meta": _cmeta}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    _GAP_PIN_RX = re.compile(
        r"\btwo[\s-]*way\b|\b10[\s-]*day\b|\bg[\s-]?league\b|"
        r"\bcontract (?:types?|status|kinds?)\b|"
        r"\bbench (?:scoring|points|production|minutes|unit)|"
        r"second unit|starters? vs\b", re.IGNORECASE)
    _gap_pin = _gap_note(question)
    if _gap_pin and _GAP_PIN_RX.search(question):
        state["tool_results"].append(
            {"tool": "known_gap", "ok": False, "error": _gap_pin})
        async for _e in _triage_terminal(question, state):
            yield _e
        return
    # (b) comeback / blown-lead phrasings: straight to
    # get_standings_deep (behind/ahead-at-half proxy board) - free-SQL
    # routes here produced raw ids, wrong seasons, and wrong reasons.
    if (re.search(r"\bcomeback|\bblown lead", question, re.IGNORECASE)
            and not _named_p):
        _cseason = "2025-26"
        _cm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _cm:
            _cseason = f"{_cm.group(1)}-{_cm.group(2)}"
        _ch: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_standings_deep",
                {"season": _cseason, "top": 5}, state, _ch):
            yield _e
        _cout = _ch.get("out") or {}
        if _result_status(_cout) == "ok":
            if state["tool_results"] and state["tool_results"][-1] is _cout:
                # QA #68: the pin must carry ONLY the comeback board -
                # the full deep payload let the frontend render the
                # clutch grid next to a comeback narrative, orphaned
                # from any label.
                _crows = _cout.get("rows")
                _cb = (_crows.get("comeback_kings")
                       if isinstance(_crows, dict) else None) or []
                state["tool_results"][-1] = {
                    "tool": "get_standings_deep",
                    "rows": _cb,
                    "meta": {
                        "source": "warehouse", "season": _cseason,
                        "stat_category": "record when trailing at "
                                         "halftime (comeback proxy)",
                        "note": "behind-at-halftime record is the "
                                "comeback proxy; play-by-play margin "
                                "data is not in the dataset. Name the "
                                "WINS (count) leader as the answer; "
                                "winning percentage is secondary."}}
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    is_season_avg = (
        len(_named_p) == 1
        and _SEASON_AVG_RX.search(question)
        and not _SEASON_AVG_NO_RX.search(question)
        and not is_compare
        and not is_trade
        and not is_cast
        and not _PREDICT_LIVE_RX.search(question)
    )
    if is_season_avg:
        # Single-stat asks used to fall through to the planner, which
        # sent them to delegate_league -> text_to_sql and dead-ended on
        # a null (F26). The season line is seeded for every rostered
        # player, so answer straight from the warehouse. No history
        # gate: follow-up chips restate the player and stat.
        _sseason = "2025-26"
        _sm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _sm:
            _sseason = f"{_sm.group(1)}-{_sm.group(2)}"
        _sh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_season_averages",
                {"player_id": _named_p[0], "season": _sseason},
                state, _sh):
            yield _e
        _sout = _sh.get("out") or {}
        if _result_status(_sout) == "ok":
            if state["tool_results"] and state["tool_results"][-1] is _sout:
                state["tool_results"][-1] = {
                    "tool": "get_season_averages", "rows": [_sout]}
            async for _e in _triage_terminal(question, state):
                yield _e
            return
        # Unknown player or missing line: fall through to the planner.
    # F64: cross-turn "compare that to his season average" - the name
    # arrives by pronoun carry, so the direct-name pin above never
    # fires, and the planner free-styles a run_python average over a
    # PARTIAL game-log window (live, 5:17 PM: Brunson "28 PPG across
    # 13 complete games" labeled as his season average while the full
    # season line exists). One player carried from history + an
    # explicit season-line ask routes to get_season_averages; the
    # ledger/history supplies the "that" side. Playoff-average asks
    # stay with the playoff lanes; career/last-N stay out via
    # _SEASON_AVG_NO_RX.
    if (not is_season_avg
            and len(found_p) == 1
            and state.get("history")
            and _SEASON_LINE_RX.search(question)
            and not _SEASON_AVG_NO_RX.search(question)
            and not re.search(r"\bplayoffs?\b", question, re.IGNORECASE)
            and not is_trade and not is_cast):
        _cseason = "2025-26"
        _cm2 = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _cm2:
            _cseason = f"{_cm2.group(1)}-{_cm2.group(2)}"
        _ch2: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_season_averages",
                {"player_id": found_p[0], "season": _cseason},
                state, _ch2):
            yield _e
        _cout2 = _ch2.get("out") or {}
        if _result_status(_cout2) == "ok":
            if state["tool_results"] and state["tool_results"][-1] is _cout2:
                state["tool_results"][-1] = {
                    "tool": "get_season_averages", "rows": [_cout2]}
            async for _e in _triage_terminal(question, state):
                yield _e
            return
        # Unknown player or missing line: fall through to the planner.
    # F63: cross-turn playoff/Finals carry - "How did he do in the
    # playoffs?" names nobody, so player-level lanes never fire and the
    # planner settles for TEAM-level tables (live, 6:22 PM: injuries +
    # team game logs, honest dead-end 0/3). One player carried from
    # history + an explicit playoff/Finals ask pins that player's
    # playoff game log. Named-player playoff asks keep their own lanes.
    if (not _named_p
            and len(found_p) == 1
            and state.get("history")
            and re.search(r"\bplayoffs?\b|\bpostseason\b|\bfinals\b",
                          question, re.IGNORECASE)
            and not is_trade and not is_cast and not is_compare):
        _pseason = "2025-26"
        _pm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _pm:
            _pseason = f"{_pm.group(1)}-{_pm.group(2)}"
        _ph: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_playoff_intel",
                {"player_id": found_p[0], "season": _pseason},
                state, _ph):
            yield _e
        _pout = _ph.get("out") or {}
        if _result_status(_pout) == "ok":
            async for _e in _triage_terminal(question, state):
                yield _e
            return
        # Unknown player / no playoff log: fall through to the planner.
    # F62: cross-turn specific-game stat follow-up - "How many points
    # did he score in that game?" carries the player AND the game
    # from history; unpinned, the planner dumps the whole playoff log
    # grouped by month and asks for a date (prod f62, 2/2). One
    # carried player + "that/this game" + a Finals game number (from
    # the question itself or the most recent history turn that set
    # one) resolves the exact game row from the warehouse and answers
    # from the payload (v67 law: deterministic on pinned lanes).
    # Burn-down: Finals game-N only; regular-season or undated "that
    # game" references stay with the planner.
    if (not _named_p
            and len(found_p) == 1
            and state.get("history")
            and re.search(r"\b(?:that|this) game\b", question,
                          re.IGNORECASE)
            and re.search(r"\bhow many\b|\bwhat did\b|\bwhat'd\b|"
                          r"\bhow'd\b|\bhow did\b", question,
                          re.IGNORECASE)
            and not is_trade and not is_cast and not is_compare):
        _gnum = 0
        _gm2 = re.search(r"\bgame\s+(\d+)\b", question, re.IGNORECASE)
        if _gm2 and re.search(r"\bfinals\b", question, re.IGNORECASE):
            _gnum = int(_gm2.group(1))
        else:
            for _ht in reversed(state["history"][-6:]):
                _htx = str(_ht.get("text") or "")
                _hm = re.search(r"\bgame\s+(\d+)\b", _htx,
                                re.IGNORECASE)
                if _hm and re.search(r"\bfinals\b", _htx,
                                     re.IGNORECASE):
                    _gnum = int(_hm.group(1))
                    break
        if _gnum:
            try:
                from .tools._core import coerce_player_id as _gcp
                _gpid = _gcp(found_p[0])
            except Exception:
                _gpid = None
            if _gpid:
                import time as _gtime

                from . import store as _gstore
                _grow: dict[str, Any] | None = None
                for _try in range(3):
                    try:
                        _gcon = _gstore.connect()
                        try:
                            _gfd = [r[0] for r in _gcon.execute(
                                "SELECT DISTINCT GAME_DATE FROM "
                                "silver_playoffs WHERE _season = ? AND "
                                "substr(CAST(GAME_ID AS VARCHAR), 8, 1) "
                                "= '4'", ["2025-26"]).fetchall()]
                            from datetime import datetime as _gdt
                            _gdates = [
                                _d.strftime("%b %-d, %Y") for _d in
                                sorted(_gdt.strptime(str(_x), "%Y-%m-%d")
                                       for _x in _gfd)]
                            if _gdates and _gnum <= len(_gdates):
                                _r = _gcon.execute(
                                    "SELECT GAME_DATE, MATCHUP, PTS, "
                                    "REB, AST, MIN FROM "
                                    "silver_playoff_gamelogs WHERE "
                                    "_season = ? AND _entity = ? AND "
                                    "GAME_DATE = ?",
                                    ["2025-26", f"player:{_gpid}",
                                     _gdates[_gnum - 1]]).fetchone()
                                if _r:
                                    _grow = dict(zip(
                                        ["GAME_DATE", "MATCHUP", "PTS",
                                         "REB", "AST", "MIN"], _r))
                        finally:
                            _gcon.close()
                        break
                    except Exception:
                        _gtime.sleep(0.2)
                if _grow:
                    from .tools.splits import _resolve_name as _grname
                    _gdisp = _grname(_gpid, str(found_p[0]))
                    _gstat = "PTS"
                    if re.search(r"\brebounds?\b", question,
                                 re.IGNORECASE):
                        _gstat = "REB"
                    elif re.search(r"\bassists?\b", question,
                                   re.IGNORECASE):
                        _gstat = "AST"
                    _gval = _grow.get(_gstat)
                    if _gval is not None:
                        _gnoun = {"PTS": "points", "REB": "rebounds",
                                  "AST": "assists"}[_gstat]
                        _gverb = {"PTS": "scored", "REB": "grabbed",
                                  "AST": "dished"}[_gstat]
                        _gres = {
                            "tool": "pin_game_stat_followup",
                            "ok": True,
                            "rows": [_grow],
                            "meta": {
                                "source": "warehouse",
                                "season": "2025-26",
                                "deterministic_answer": (
                                    f"{_gdisp} {_gverb} {int(_gval)} "
                                    f"{_gnoun} in Game {_gnum} of the "
                                    f"2026 Finals "
                                    f"({_grow['GAME_DATE']}, "
                                    f"{_grow['MATCHUP']}).")}}
                        yield _event("tool_call", {
                            "node": "data_retrieval",
                            "name": "pin_game_stat_followup",
                            "label": tool_label(
                                "pin_game_stat_followup"),
                            "summary": f"{_gdisp} Finals game "
                                       f"{_gnum} log, 2025-26"})
                        yield _event("tool_result",
                                     _tool_result_payload(
                                         "data_retrieval",
                                         "pin_game_stat_followup",
                                         _gres, 0))
                        yield _event("thought_stream", {
                            "node": "data_retrieval",
                            "text": f"Reading {_gdisp}'s Finals game "
                                    f"{_gnum} line from the warehouse."})
                        state["tool_results"].append(_gres)
                        state["calls_made"].append(
                            "pin_game_stat_followup")
                        async for _e in _triage_terminal(question, state):
                            yield _e
                        return
    # F61: "all-time record for most points by a team in one game" went
    # to delegate_league + freeform text_to_sql and shipped a different
    # number each run (144 off playoff rows vs 157 off regular rows)
    # with no coverage window named. Deterministic lane:
    # silver_hist_gamelogs is the team game-log table (2009-10 through
    # current); answer from the payload verbatim with the span named
    # (v67 law).
    # Burn-down: team single-game SCORING record only - player records
    # keep the gamelog best-game pin, other team stat records
    # (rebounds/assists) stay with the planner until they flake.
    if (re.search(r"\bmost points\b|\bscoring record\b|"
                  r"\bhighest[\s-]*scor", question, re.IGNORECASE)
            and re.search(r"\bteam\b", question, re.IGNORECASE)
            and re.search(r"\bin (?:one|a|1) game\b|"
                          r"\bsingle[\s-]*game\b", question,
                          re.IGNORECASE)
            and not found_p
            and not is_compare and not is_trade and not is_cast):
        import time as _rtime

        from . import store as _rstore
        _rrows: list[dict[str, Any]] = []
        for _try in range(3):
            try:
                _rcon = _rstore.connect()
                try:
                    _rcur = _rcon.execute(
                        "SELECT team_name, pts, game_date, _season, "
                        "matchup FROM silver_hist_gamelogs "
                        "ORDER BY pts DESC LIMIT 5")
                    _rcols = [d[0] for d in _rcon.description]
                    _rrows = [dict(zip(_rcols, r))
                              for r in _rcur.fetchall()]
                finally:
                    _rcon.close()
                break
            except Exception:
                _rtime.sleep(0.2)
        if _rrows:
            from .tools._core import SEASON as _RCUR
            from .tools._core import HIST_SEASON_START as _RHIST
            _rtop = _rrows[0]
            _rnxt = "; ".join(
                f"{r['team_name']} {r['pts']} ({r['game_date']})"
                for r in _rrows[1:4])
            _rdet = (
                f"This data covers the {_RHIST} through {_RCUR} "
                f"seasons.\n"
                f"The highest-scoring team game in coverage: "
                f"{_rtop['team_name']} scored {_rtop['pts']} points "
                f"({_rtop['matchup']}, {_rtop['game_date']}, "
                f"{_rtop['_season']} season).")
            if _rnxt:
                _rdet += f" Next: {_rnxt}."
            _rdet += (" Team games before 2009-10 are outside "
                      "coverage.")
            _rres = {
                "tool": "pin_team_scoring_record", "ok": True,
                "rows": _rrows,
                "meta": {"source": "warehouse",
                         "span": f"{_RHIST}..{_RCUR}",
                         "deterministic_answer": _rdet}}
            yield _event("tool_call", {
                "node": "data_retrieval",
                "name": "pin_team_scoring_record",
                "label": tool_label("pin_team_scoring_record"),
                "summary": "team single-game scoring record, all "
                           "coverage seasons"})
            yield _event("tool_result", _tool_result_payload(
                "data_retrieval", "pin_team_scoring_record", _rres, 0))
            yield _event("thought_stream", {
                "node": "data_retrieval",
                "text": "Reading the team single-game scoring record "
                        "from the warehouse."})
            state["tool_results"].append(_rres)
            state["calls_made"].append("pin_team_scoring_record")
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    # Four-factors team asks: verified live (2026-09-13) that the
    # planner free-formed "Thunder four factors" through text_to_sql /
    # run_python and shipped WRONG figures (12.4% TOV vs 10.8% real,
    # "FT rate not available" while it sits in the table). Pin the lane
    # to get_team_four_factors (silver_four_factors_team, computed
    # offline from team game rows) with a deterministic answer (v67
    # law). Player four-factors keep get_four_factors (found_p guard).
    # Burn-down: team-scope only; player on/off four-factors and
    # four-factors inside broader compares stay with the planner.
    # QA hammer P2 (2026-09-13 v79 retest): "compare OKC and Detroit by
    # four factors" carries "compare", so the old gate skipped the lane
    # and routed to PREVIEW filler. Two-team four-factors compares run
    # one call per team and ship a deterministic side-by-side.
    if (re.search(r"\bfour[\s-]*factors?\b", question, re.IGNORECASE)
            and not found_p
            and not is_trade and not is_cast):
        from .tools._core import SEASON as _FFCUR

        def _ffpct(v: object) -> str:
            # QA hammer P3: table values are raw fractions (0.5613);
            # prose must render percents (56.1%) like the check-lines.
            try:
                return f"{float(v) * 100:.1f}%"
            except (TypeError, ValueError):
                return "?"

        def _ffrate(v: object) -> str:
            try:
                return f"{float(v):.3f}"
            except (TypeError, ValueError):
                return "?"

        if len(found_t) >= 2:
            _cmprows: list[dict[str, Any]] = []
            for _t in found_t[:2]:
                _ch: dict[str, Any] = {}
                async for _e in _triage_tool(
                        "get_team_four_factors", {"team": _t}, state, _ch):
                    yield _e
                _co = _ch.get("out") or {}
                if _result_status(_co) == "ok" and _co.get("rows"):
                    _cmprows.extend(_co["rows"])
            if len(_cmprows) >= 2:
                _ca, _cb = _cmprows[0], _cmprows[1]
                _clines = [
                    f"This data covers the {_FFCUR} season.",
                    f"{_ca['TEAM']} vs {_cb['TEAM']} four factors:",
                    (f"- eFG%: {_ca['TEAM']} {_ffpct(_ca['EFG_PCT'])} vs "
                     f"{_cb['TEAM']} {_ffpct(_cb['EFG_PCT'])}"),
                    (f"- TOV%: {_ca['TEAM']} {_ffpct(_ca['TOV_PCT'])} vs "
                     f"{_cb['TEAM']} {_ffpct(_cb['TOV_PCT'])}"),
                    (f"- ORB%: {_ca['TEAM']} {_ffpct(_ca['ORB_PCT'])} vs "
                     f"{_cb['TEAM']} {_ffpct(_cb['ORB_PCT'])}"),
                    (f"- FT rate: {_ca['TEAM']} {_ffrate(_ca['FT_RATE'])} "
                     f"vs {_cb['TEAM']} {_ffrate(_cb['FT_RATE'])}"),
                ]
                try:
                    _ea = float(_ca["EFG_PCT"]) - float(_ca["TOV_PCT"])
                    _eb = float(_cb["EFG_PCT"]) - float(_cb["TOV_PCT"])
                    _cw = _ca["TEAM"] if _ea >= _eb else _cb["TEAM"]
                    _clines.append(
                        f"Verdict: {_cw} holds the shooting/turnover "
                        f"edge.")
                except (TypeError, ValueError, KeyError):
                    pass
                _cmeta = {"source": "warehouse",
                          "deterministic_answer": "\n".join(_clines)}
                state["tool_results"].append({
                    "tool": "get_team_four_factors",
                    "rows": _cmprows, "meta": _cmeta})
                state["calls_made"].append("get_team_four_factors")
                async for _e in _triage_terminal(question, state):
                    yield _e
            return
        _ffh: dict[str, Any] = {}
        _ffargs: dict[str, Any] = {}
        if found_t:
            _ffargs["team"] = found_t[0]
        async for _e in _triage_tool(
                "get_team_four_factors", _ffargs, state, _ffh):
            yield _e
        _ffout = _ffh.get("out") or {}
        if _result_status(_ffout) == "ok" and _ffout.get("rows"):
            _frows = _ffout["rows"]
            if len(_frows) == 1:
                _r0 = _frows[0]
                _ffdet = (
                    f"This data covers the {_FFCUR} season.\n"
                    f"{_r0['TEAM']} four factors: eFG% "
                    f"{_ffpct(_r0['EFG_PCT'])}, "
                    f"TOV% {_ffpct(_r0['TOV_PCT'])}, "
                    f"ORB% {_ffpct(_r0['ORB_PCT'])}, "
                    f"FT rate {_ffrate(_r0['FT_RATE'])}. Defense: "
                    f"opponent eFG% {_ffpct(_r0['OPP_EFG_PCT'])}, "
                    f"forced TOV% {_ffpct(_r0['OPP_TOV_PCT'])}, "
                    f"DRB% {_ffpct(_r0['DRB_PCT'])}, "
                    f"opponent FT rate {_ffrate(_r0['OPP_FT_RATE'])}. "
                    f"Computed from {_r0['GP']} team game rows "
                    f"(record {_r0['W']}-{_r0['GP'] - _r0['W']}).")
            else:
                _ffdet = (
                    f"This data covers the {_FFCUR} season.\n"
                    "League four-factors board (offense): "
                    + "; ".join(
                        f"{r['TEAM']} eFG% {_ffpct(r['EFG_PCT'])}, "
                        f"TOV% {_ffpct(r['TOV_PCT'])}"
                        for r in _frows[:5]) + ".")
            _ffout.setdefault("meta", {})["deterministic_answer"] = _ffdet
            if state["tool_results"] and \
                    state["tool_results"][-1] is _ffout:
                state["tool_results"][-1] = {
                    "tool": "get_team_four_factors",
                    "rows": _frows, "meta": _ffout["meta"]}
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    # Record-when-plays: "What is Denver's record when Jokic plays?"
    # has a planner recipe (delegate_team -> search_game_logs, report
    # rows.record verbatim) but sampling skips it ~50% of the time
    # (test_record_when_jokic_plays flakes identically on the deployed
    # base - unpinned lane variance, not a regression). One resolvable
    # player + a record-when-plays ask pins search_game_logs with no
    # filters and answers from rows.record verbatim (v67 law).
    # Burn-down: "plays" only - "sits"/"without" complements stay
    # with the planner.
    if (re.search(r"\brecord\b", question, re.IGNORECASE)
            and re.search(r"\bwhen\b", question, re.IGNORECASE)
            and re.search(r"\bplays?\b|\bplaying\b|\bon the floor\b|"
                          r"\bin the lineup\b", question, re.IGNORECASE)
            and not re.search(r"\bsits?\b|\bsitting\b|\bsat\b|"
                              r"\bwithout\b|\bmissing\b|\bmiss(?:es|ed)?\b|"
                              r"\bis out\b|\bwas out\b", question,
                              re.IGNORECASE)
            and len(found_p) == 1
            and not is_trade and not is_cast and not is_compare):
        _rwseason = "2025-26"
        _rwm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _rwm:
            _rwseason = f"{_rwm.group(1)}-{_rwm.group(2)}"
        _rwpo = bool(re.search(r"\bplayoffs?\b|\bpostseason\b|"
                               r"\bfinals\b", question, re.IGNORECASE))
        _rwh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "search_game_logs",
                {"player": found_p[0], "season": _rwseason,
                 "playoffs": _rwpo, "limit": 100},
                state, _rwh):
            yield _e
        _rwout = _rwh.get("out") or {}
        if _result_status(_rwout) == "ok":
            _rwrows = _rwout.get("rows") or {}
            _rwrec = _rwrows.get("record") or {}
            _rwg = _rwrec.get("games")
            if _rwg:
                _rwpname = str(_rwrows.get("player") or found_p[0])
                _rwabbr = str(_rwrows.get("player_team") or "")
                try:
                    from .tools.headtohead import _team_abbr as _rwta
                    _rwfull = _rwta(_rwabbr)[1] if _rwabbr else ""
                except Exception:
                    _rwfull = _rwabbr
                _rwscope = ("playoff " if _rwpo else "")
                _rwout["meta"] = dict(_rwout.get("meta") or {})
                _rwout["meta"]["deterministic_answer"] = (
                    f"The {_rwfull} went {_rwrec.get('w')}-"
                    f"{_rwrec.get('l')} in the {_rwg} {_rwscope}games "
                    f"{_rwpname} played"
                    + ("" if _rwpo else " this season")
                    + f" ({_rwseason}).")
                async for _e in _triage_terminal(question, state):
                    yield _e
            return
        # Unknown player / no games: fall through to the planner.
    # F67: "their best player" carry - the planner resolved "their" to
    # team-scoring TOTALS and gave up (live, 6:22 PM chain retest),
    # though the control ask with the team named outright works. One
    # team resolved (named or carried) + a best-player ask reads the
    # team's top scorers straight from the leaders table. Carried
    # players from history do not block the pin: the question names
    # nobody (capital guard), so a carried player is context, not
    # the ask.
    # Resolve "their" deterministically: a team named in the question
    # wins; otherwise the textually FIRST team of the MOST RECENT
    # history turn that mentions one - and only when the question
    # actually carries a pronoun/reference, so a league-wide ask
    # ("best player in the league") never inherits a team. Battery
    # run 2 flake (local, 8:59 PM): T1's standings answer also named
    # the Spurs, so "exactly one carried team" silently failed 1/3
    # of the time and the turn fell to the planner. Pronoun reference
    # is recency, not uniqueness.
    def _first_team_in(text: str) -> str | None:
        cands = _detect_entities(text)[1]
        if not cands:
            return None
        low = text.lower()
        def _pos(full: str) -> int:
            spots = [low.find(full.lower()),
                     low.find(full.split()[-1].lower())]
            spots = [s for s in spots if s >= 0]
            return min(spots) if spots else len(low)
        return min(cands, key=_pos)
    # F67: "best record this season?" - the highest-traffic standings
    # ask - ran through delegate_league planner variance and sometimes
    # shipped an answer with no team name at all (battery F67[2]),
    # which then broke the next turn's "their" carry. Pin it: top
    # standings row, answer text built from payload fields (v67 law:
    # deterministic on pinned lanes). Burn-down: standings-record class.
    if (re.search(r"\bbest record\b|\btop record\b", question,
                  re.IGNORECASE)
            and not found_p and not _named_p
            and not is_trade and not is_cast and not is_compare):
        _sh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "get_standings", {"season": "2025-26"}, state, _sh):
            yield _e
        _sout = _sh.get("out") or {}
        if _result_status(_sout) == "ok":
            _srows = _sout.get("rows") or []
            _top = _srows[0] if _srows and isinstance(_srows[0], dict) else {}
            _steam = str(_top.get("team") or "").strip()
            _srec = str(_top.get("Record") or "").strip()
            try:
                _spct = f"{float(_top.get('WinPCT')):.3f}".lstrip("0")
            except (TypeError, ValueError):
                _spct = ""
            if _steam and _srec:
                _sout["meta"] = dict(_sout.get("meta") or {})
                _sout["meta"]["deterministic_answer"] = (
                    f"The {_steam} had the best record in the "
                    f"2025-26 season at {_srec}"
                    + (f" ({_spct})" if _spct else "") + ".")
                async for _e in _triage_terminal(question, state):
                    yield _e
            return
    _bteam = _first_team_in(question)
    if not _bteam and state.get("history") and re.search(
            r"\b(their|theirs|them|they|that team|this team|it)\b",
            question, re.IGNORECASE):
        for _ht in reversed(state["history"][-6:]):
            _bteam = _first_team_in(_ht.get("text") or "")
            if _bteam:
                break
    if (_bteam
            and not _named_p
            and re.search(r"\bbest players?\b|\bstar players?\b|"
                          r"\btop players?\b", question, re.IGNORECASE)
            # a mid-sentence capitalized token is a name the static
            # list did not catch ("Is Brunson their best player?") -
            # leave those to the planner. Finals/NBA/Playoffs are
            # keywords, not names (QA: "their best player in the
            # Finals?" escaped the pin on the capital F).
            and not re.search(
                r"(?<!^)\b[A-Z][a-z]{2,}\b",
                __import__("functools").reduce(
                    lambda _q, _w: re.sub(rf"\b{re.escape(_w)}\b", "",
                                          _q, flags=re.IGNORECASE),
                    [_w for _ft in found_t for _w in str(_ft).split()],
                    re.sub(r"\b(?:Finals?|NBA|Playoffs?)\b", "",
                           question)))
            and not is_trade and not is_cast and not is_compare):
        try:
            from .tools.gamelog import _team_abbr as _tabbr
            _babbr, _bfull = _tabbr(_bteam)
        except Exception:
            _babbr, _bfull = "", _bteam
        _brows: list[dict[str, Any]] = []
        _bfinals = bool(re.search(r"\bfinals\b", question, re.IGNORECASE))
        if _babbr:
            import time as _btime

            from . import store as _bstore
            for _try in range(3):
                try:
                    _bcon = _bstore.connect()
                    try:
                        if _bfinals:
                            # Finals-phrased ask: answer from the actual
                            # Finals game logs (round 4 dates), not the
                            # season leader table (QA F63 team-carry gap:
                            # "Spurs' best player in the Finals").
                            _fd = [r[0] for r in _bcon.execute(
                                "SELECT DISTINCT GAME_DATE FROM "
                                "silver_playoffs WHERE _season = ? AND "
                                "substr(CAST(GAME_ID AS VARCHAR), 8, 1) "
                                "= '4'", ["2025-26"]).fetchall()]
                            if _fd:
                                # gamelogs store 'Jun 13, 2026', not ISO
                                from datetime import datetime as _bdt
                                _fd = [_bdt.strptime(str(_d), "%Y-%m-%d")
                                       .strftime("%b %-d, %Y")
                                       for _d in _fd]
                                _ph = ",".join("?" * len(_fd))
                                for _e, _gp, _pts, _ppg in _bcon.execute(
                                        "SELECT _entity, COUNT(*), "
                                        "SUM(PTS), ROUND(AVG(PTS), 1) "
                                        "FROM silver_playoff_gamelogs "
                                        "WHERE _season = ? AND "
                                        "MATCHUP LIKE ? AND GAME_DATE "
                                        f"IN ({_ph}) GROUP BY 1 "
                                        "ORDER BY 3 DESC LIMIT 3",
                                        ["2025-26", _babbr + " %",
                                         *sorted(_fd)]).fetchall():
                                    _pid = str(_e).replace("player:", "")
                                    _nm = _bcon.execute(
                                        "SELECT DISTINCT PLAYER FROM "
                                        "silver_leaders_pts WHERE "
                                        "CAST(PLAYER_ID AS VARCHAR) = ?",
                                        [_pid]).fetchone()
                                    _brows.append({
                                        "PLAYER": _nm[0] if _nm else _pid,
                                        "GP": _gp, "PTS": _pts,
                                        "PPG": _ppg})
                        if not _brows:
                            _cur = _bcon.execute(
                                "SELECT PLAYER, GP, PTS, "
                                "ROUND(PTS * 1.0 / NULLIF(GP, 0), 1) AS PPG "
                                "FROM silver_leaders_pts "
                                "WHERE TEAM = ? AND _season = ? AND GP >= 20 "
                                "ORDER BY PTS * 1.0 / NULLIF(GP, 0) DESC "
                                "LIMIT 3", [_babbr, "2025-26"])
                            _bcols = [d[0] for d in _bcon.description]
                            _brows = [dict(zip(_bcols, r))
                                      for r in _cur.fetchall()]
                    finally:
                        _bcon.close()
                    break
                except Exception:
                    _btime.sleep(0.2)
        if _brows:
            _bmeta: dict[str, Any] = {
                "source": "warehouse", "season": "2025-26",
                "note": (f"top {_bfull} scorers by per-game "
                         "points (20+ games); 'best player' "
                         "read as the team's leading scorers")}
            if _bfinals:
                _btop = _brows[0]
                _bmeta["note"] = (
                    f"top {_bfull} scorers in the Finals series, "
                    "from the Finals game logs")
                _bmeta["deterministic_answer"] = (
                    f"{_btop['PLAYER']} was the {_bfull}' leading "
                    f"Finals scorer at {_btop['PPG']} points per game "
                    f"over {_btop['GP']} games "
                    f"({int(_btop['PTS'])} total).")
            _bres = {
                "tool": "pin_team_best_player", "ok": True,
                "rows": _brows,
                "meta": _bmeta}
            yield _event("tool_call", {
                "node": "data_retrieval",
                "name": "pin_team_best_player",
                "label": tool_label("pin_team_best_player"),
                "summary": f"{_bfull} scoring leaders, 2025-26"})
            yield _event("tool_result", _tool_result_payload(
                "data_retrieval", "pin_team_best_player", _bres, 0))
            yield _event("thought_stream", {
                "node": "data_retrieval",
                "text": f"Reading {_bfull} scoring leaders from the "
                        "warehouse."})
            state["tool_results"].append(_bres)
            state["calls_made"].append("pin_team_best_player")
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    if re.search(r"\bris(?:ers?|ing)\b|\bfall(?:ers?|ing)\b",
                 question, re.IGNORECASE) and not found_p and not is_trade:
        # Player-level risers used to fall to the planner, which burned
        # 12 tool calls / 177s and still surfaced TEAM win rates
        # (QA F12 retest). One hop, warehouse only.
        _team_intent = found_t or re.search(
            r"\bteams?\b|\bfranchise", question, re.IGNORECASE)
        _rtool = ("get_risers" if _team_intent
                  else "get_player_risers")
        _rh2: dict[str, Any] = {}
        async for _e in _triage_tool(
                _rtool, {"season": "2025-26"}, state, _rh2):
            yield _e
        _rout = _rh2.get("out") or {}
        if _result_status(_rout) == "ok":
            # No rows=[payload] wrap: the dataset table renders the raw
            # payload as one giant JSON row (QA #23). Unwrapped, asTable
            # finds the risers/fallers arrays like team get_risers (F12).
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    if re.search(r"back-to-backs?|back to backs?|\bb2b\b|rest days?|"
                 r"days? of rest|rest advantage", question, re.IGNORECASE) \
            and not is_trade and not is_cast:
        # QA F17: back-to-back asks fell to the planner, which substituted
        # an irrelevant win-streak table. Route to the rest splits tool;
        # its offseason note makes "no games until preseason" explicit.
        _rest_args: dict[str, Any] = {"season": "2025-26"}
        if found_t:
            from .tools._core import coerce_team_id as _ctid
            from nba_api.stats.static import teams as _tteams
            try:
                _tid = _ctid(found_t[0])
                _rest_args["team_abbrev"] = {
                    t["id"]: t["abbreviation"]
                    for t in _tteams.get_teams()}.get(_tid, "")
            except Exception:
                pass
        _rh4: dict[str, Any] = {}
        async for _e in _triage_tool("get_rest", _rest_args, state, _rh4):
            yield _e
        if _result_status(_rh4.get("out") or {}) == "ok":
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    _elo_ask = bool(re.search(r"\belo\b", question, re.IGNORECASE))
    _odds_ask = bool(re.search(
        r"playoff odds|title odds|championship odds|odds to win|"
        r"title chances|playoff chances|win the (title|championship|finals)",
        question, re.IGNORECASE))
    if (_elo_ask or _odds_ask) and not is_trade and not is_cast:
        # QA F10: the league desk used to improvise ELO from NET_RATING
        # ("OKC ELO 11.1") and hand out raw 1.0 odds. Route to the real
        # tools: get_elo_standings (1500-scale ELO) and get_playoff_sim
        # (actual results while the season is complete).
        _any_ok = False
        if _odds_ask:
            _oh: dict[str, Any] = {}
            async for _e in _triage_tool(
                    "get_playoff_sim", {"season": "2025-26"}, state, _oh):
                yield _e
            _any_ok = _any_ok or _result_status(_oh.get("out") or {}) == "ok"
        if _elo_ask:
            _eargs: dict[str, Any] = {"season": "2025-26"}
            if found_t:
                _eargs["opponent"] = found_t[0]
            _eh: dict[str, Any] = {}
            async for _e in _triage_tool(
                    "get_elo_standings", _eargs, state, _eh):
                yield _e
            _any_ok = _any_ok or _result_status(_eh.get("out") or {}) == "ok"
        if _any_ok:
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    _is_shot = bool(re.search(
        r"shot ?charts?|shot zones?|shot diet|shot profile|"
        r"shooting (?:splits?|profile|locations?|map)|zone diet|"
        r"where (?:does|do|did)\b.{0,40}\bshoot",
        question, re.IGNORECASE))
    if _is_shot and found_p and not is_trade and not is_cast:
        # Shot-chart asks used to burn ~22 planner tool calls / 67s on a
        # compare thread (QA F3/#19 latency). One hop, warehouse-first.
        _stool = "get_shot_compare" if len(found_p) >= 2 else "get_shot_zones"
        _sargs = ({"a": found_p[0], "b": found_p[1], "season": "2025-26"}
                  if len(found_p) >= 2
                  else {"player_id": found_p[0], "season": "2025-26"})
        _sh3: dict[str, Any] = {}
        async for _e in _triage_tool(_stool, _sargs, state, _sh3):
            yield _e
        _sout = _sh3.get("out") or {}
        if _result_status(_sout) == "ok":
            # Same QA #23 wrap leak as the risers path; pass through raw.
            async for _e in _triage_terminal(question, state):
                yield _e
            return
    is_league_team = (
        not _named_p
        and _LEAGUE_TEAM_RX.search(question)
        and not _GAMELOG_NO_RX.search(question)
        and not is_trade
        and not is_cast
        and not _PREDICT_LIVE_RX.search(question)
        and not state.get("history")
    )
    if is_league_team:
        # "which team had the most 50-point games this season" also
        # matches _LEAGUE_LEADERS_RX, so this runs first: answering it
        # per-player would silently group by the wrong population.
        # team_wide groups matched games by the player's own team that
        # night instead. Same clean single-turn guards as below.
        _targs = _gamelog_args(question, None, _named)
        _targs["team_wide"] = True
        _th: dict[str, Any] = {}
        async for _e in _triage_tool(
                "search_game_logs", _targs, state, _th):
            yield _e
        _tout = _th.get("out") or {}
        if _result_status(_tout) == "ok":
            # Wrap like the player fast-path: analytics only treats
            # entries with a non-empty "rows" key as evidence.
            if state["tool_results"] and state["tool_results"][-1] is _tout:
                state["tool_results"][-1] = {
                    "tool": "search_game_logs", "rows": [_tout]}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    is_league_leaders = (
        not _named_p
        and (_LEAGUE_LEADERS_RX.search(question)
             or _LEAGUE_EXISTENCE_RX.search(question))
        and not _GAMELOG_NO_RX.search(question)
        and not is_trade
        and not is_cast
        and not _PREDICT_LIVE_RX.search(question)
        and not state.get("history")
    )
    if is_league_leaders:
        # Ticket B: "who had the most 50-point games this season" names
        # no player, so the player-scoped fast-path can't fire and the
        # planner improvises SQL. Answer from the warehouse instead via
        # the league-wide mode of search_game_logs. Only on clean
        # single-turn questions with no named player; anything
        # uncertain falls through to the planner.
        _largs = _gamelog_args(question, None, _named)
        _largs["league_wide"] = True
        _lh: dict[str, Any] = {}
        async for _e in _triage_tool(
                "search_game_logs", _largs, state, _lh):
            yield _e
        _lout = _lh.get("out") or {}
        if _result_status(_lout) == "ok":
            # Wrap like the player fast-path: analytics only treats
            # entries with a non-empty "rows" key as evidence.
            if state["tool_results"] and state["tool_results"][-1] is _lout:
                state["tool_results"][-1] = {
                    "tool": "search_game_logs", "rows": [_lout]}
            async for _e in _triage_terminal(question, state):
                yield _e
        return
    if (is_trade
            # QA #70: QA retests inside existing threads. The history
            # gate exists for context-dependent follow-ups ("who wins
            # it?") - a self-contained question naming a team or
            # player must pin regardless of thread history.
            and (not state.get("history") or found_t or found_p)
            and _TRADE_VALUE_RX.search(question)
            and not _TRADE_VALUE_NO_RX.search(question)
            # F56: "Did the Mavericks win the Luka trade?" names ONE
            # team + the player - _trade_sides resolves the player's
            # team into the second side. Requiring two named teams
            # let one-sided phrasings escape to the planner, which
            # answered a two-sided question from one roster.
            # Exactly 2 named teams, or 1 team + named player(s) whose
            # own team becomes the second side. Three-team trades
            # (3 named teams) stay with the planner.
            and (len(found_t) == 2
                 or (len(found_t) == 1 and found_p))):
        # B3: "who wins this trade on value" used to go through two planner
        # LLM rounds (resolve_entity, then the value call) before reaching
        # get_trade_value, which resolves names itself. Parse sides
        # deterministically and answer straight from the warehouse.
        # Exactly two teams only: three-team trades fall to the planner.
        _vseason = "2025-26"
        _vm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _vm:
            _vseason = f"{_vm.group(1)}-{_vm.group(2)}"
        _vsides = _trade_sides(question, found_p, found_t, _vseason)
        if _vsides:
            _vh: dict[str, Any] = {}
            async for _e in _triage_tool(
                    "get_trade_value", _vsides, state, _vh):
                yield _e
            _vout = _vh.get("out") or {}
            if _result_status(_vout) == "ok":
                # Wrap like the prediction/gamelog fast-paths: analytics
                # only treats entries with a non-empty "rows" as evidence.
                if state["tool_results"] and state["tool_results"][-1] is _vout:
                    state["tool_results"][-1] = {
                        "tool": "get_trade_value", "rows": [_vout]}
                async for _e in _triage_terminal(question, state):
                    yield _e
                return
            # QA #70: the F47 both-sides refusal is terminal - the
            # planner's resolve_entity self-correction cannot fill a
            # side the question never named, and the extra 5+ tools
            # (60-100s) only re-arrive at the same answer. Ship the
            # refusal via the no-evidence compose branch.
            if _vout.get("terminal"):
                async for _e in _triage_terminal(question, state):
                    yield _e
                return
            # Unknown players or missing data: fall through to the planner
            # so it can self-correct with resolve_entity. The tool's hints
            # are already in state["tool_results"].
    is_compare_fast = (
        is_compare
        and 2 <= len(_named_p) <= 3
        # _detect_entities caps at 3 players, so a 4-way ask would
        # silently drop one - the same wrong-shape answer QA flagged on
        # the 2-of-3 debate card. Three or more "vs" separators means
        # the question names more players than the pin can serve.
        and len(re.findall(r"\bvs\.?\b", question)) < 3
        and not is_trade
        and not is_cast
        and not re.search(r"\bimpact\b", question, re.IGNORECASE)
        # Chips and follow-ups name both players again; the history gate
        # used to push those to the LLM planner, which could answer with
        # zero tools and no data.
    )
    if is_compare_fast:
        # Two-player compare turns burned 4 planner LLM rounds (10.3s)
        # on deterministic routing: get_compare, then one scout per
        # player. The tool resolves names itself, so answer straight
        # from the warehouse. QA #71: a 3-player compare fanned out
        # through the planner (29 tools / 30s) - run the three pairwise
        # get_compare calls deterministically instead. 4+ player asks
        # fall to the planner.
        _cseason = "2025-26"
        _cm = re.search(r"(20\d\d)\s*-\s*(\d\d)", question)
        if _cm:
            _cseason = f"{_cm.group(1)}-{_cm.group(2)}"
        from itertools import combinations as _combinations
        _cok = True
        for _ca, _cb in _combinations(_named_p[:3], 2):
            _chh: dict[str, Any] = {}
            async for _e in _triage_tool(
                    "get_compare",
                    {"a": _ca, "b": _cb, "season": _cseason},
                    state, _chh):
                yield _e
            if _result_status(_chh.get("out") or {}) != "ok":
                _cok = False
                break
        if _cok:
            for _cp in _named_p[:3]:
                _ctask = (f"Player focus: {_cp}. "
                          f"Original question: {question}")
                _cargs = {"task": _ctask}
                yield _event("tool_call", {
                    "node": "data_retrieval", "name": "delegate_scout",
                    "label": tool_label("delegate_scout"),
                    "summary": _args_summary("delegate_scout", _cargs),
                })
                _ct0 = time.time()
                try:
                    _cholder: dict[str, Any] = {}
                    async for _ce in _run_delegate_live(
                            "delegate_scout", _ctask, primary, model,
                            _cholder):
                        yield _ce
                    _cout2 = _cholder.get("result") or {
                        "tool": "delegate_scout", "ok": False,
                        "error": "no result"}
                except Exception as exc:
                    _cout2 = {"tool": "delegate_scout", "ok": False,
                              "error": str(exc)[:160]}
                if not isinstance(_cout2, dict):
                    _cout2 = {"tool": "delegate_scout", "rows": _cout2}
                _cms = int((time.time() - _ct0) * 1000)
                yield _event("tool_result", _tool_result_payload(
                    "data_retrieval", "delegate_scout", _cout2, _cms,
                    summary=_delegate_result_summary(_cout2)))
                for _cte in _trace_replay_events(_cout2):
                    yield _cte
                state["tool_results"].append(_cout2)
                state["calls_made"].append("delegate_scout:" + json.dumps(
                    _cargs, sort_keys=True))
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
                if out.get("ok") and isinstance(out.get("rows"), dict):
                    # Compose inverted this verdict once already; ship
                    # the payload-built text (v67 law).
                    out.setdefault("meta", {})["deterministic_answer"] = (
                        _trade_verdict_text(out["rows"]))
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
        _cast_rows: list[dict[str, Any]] = []
        _cast_notes: list[str] = []
        if sides:
            # Structured rows, not print-only text: the evidence card and
            # the narrative both get real player names sorted by PPG
            # (QA F34 follow-up: no more "Mate 1/2/3/4" placeholders).
            from . import store as _store3

            try:
                _con3 = _store3.connect()
                try:
                    for p, ab in sides:
                        last = p.split()[-1]
                        try:
                            mates = _con3.execute(
                                "SELECT PLAYER, PTS, GP FROM "
                                "silver_leaders_pts WHERE _season='2025-26' "
                                "AND TEAM=? AND UPPER(PLAYER) NOT LIKE ? "
                                "ORDER BY PTS DESC LIMIT 4",
                                [ab, "%" + last.upper() + "%"]).fetchall()
                        except Exception:
                            mates = []
                        try:
                            adv = {str(r[0]): (r[1], r[2])
                                   for r in _con3.execute(
                                       "SELECT PLAYER_NAME, TS_PCT, "
                                       "NET_RATING FROM silver_advanced "
                                       "WHERE _season='2025-26' AND "
                                       "TEAM_ABBREVIATION=?",
                                       [ab]).fetchall()}
                        except Exception:
                            adv = {}
                        if not mates:
                            _cast_notes.append(
                                f"{p}: cast data unavailable right now")
                            continue
                        for m in mates:
                            ppg = (m[1] or 0) / max(m[2] or 0, 1)
                            pair = adv.get(str(m[0]), (None, None))
                            _cast_rows.append({
                                "SIDE": p, "PLAYER": str(m[0]),
                                "TEAM": ab, "GP": int(m[2] or 0),
                                "PPG": round(ppg, 1),
                                "TS_PCT": (round(pair[0] * 100, 1)
                                           if pair[0] is not None else None),
                                "NET_RATING": (round(pair[1], 1)
                                               if pair[1] is not None
                                               else None),
                            })
                finally:
                    _con3.close()
            except Exception:
                _cast_rows = []
                _cast_notes = ["cast data unavailable right now"]
        if sides:
            if _cast_rows:
                _cmeta: dict[str, Any] = {"source": "warehouse",
                                          "season": "2025-26",
                                          "note": "supporting cast, "
                                                  "star excluded, "
                                                  "sorted by PPG"}
                if _cast_notes:
                    _cmeta["unavailable"] = "; ".join(_cast_notes)
                out = {"tool": "run_python", "ok": True,
                       "rows": _cast_rows, "meta": _cmeta}
            else:
                out = {"tool": "run_python", "ok": False,
                       "error": "cast data unavailable right now"}
            _cast_args = {"code": "structured supporting-cast query"}
            _t0 = time.time()
            yield _event("tool_call", {
                "node": "data_retrieval", "name": "run_python",
                "label": tool_label("run_python"),
                "summary": _args_summary("run_python", _cast_args),
            })
            _ms = int((time.time() - _t0) * 1000)
            _rd = _tool_result_payload("data_retrieval", "run_python", out, _ms)
            yield _event("tool_result", _rd)
            yield _event("thought_stream", {
                "node": "data_retrieval",
                "text": _done_thought(tool_label("run_python"), out, _ms),
            })
            state["tool_results"].append(out)
            state["calls_made"].append("run_python:" + json.dumps(
                {"code": "cast"}, sort_keys=True))
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
    _sm = re.search(r"(\d+)[- ]point", question, re.IGNORECASE)
    if (_sm and not is_trade and not is_cast
            and not is_compare and not is_raptor
            and re.search(r"streak|longest|consecutive", question,
                          re.IGNORECASE)):
        _thresh = max(1, min(int(_sm.group(1)), 60))
        _code = (
            "rows = con.execute(\"WITH g AS (SELECT Player_ID, PTS, "
            "TRY_STRPTIME(GAME_DATE, '%b %d, %Y') AS d "
            "FROM silver_player_gamelogs WHERE _season = '2025-26'), "
            "s AS (SELECT Player_ID, d, PTS, ROW_NUMBER() OVER "
            "(PARTITION BY Player_ID ORDER BY d) - ROW_NUMBER() OVER "
            f"(PARTITION BY Player_ID, (PTS >= {_thresh})::INT ORDER BY d) "
            "AS grp FROM g WHERE d IS NOT NULL), "
            "agg AS (SELECT Player_ID, COUNT(*) AS streak FROM s WHERE PTS >= "
            f"{_thresh} GROUP BY Player_ID, grp) "
            "SELECT MAX(l.PLAYER), MAX(a.streak) FROM agg a LEFT JOIN "
            "(SELECT DISTINCT PLAYER, PLAYER_ID FROM silver_leaders_pts) l "
            "ON CAST(l.PLAYER_ID AS VARCHAR) = CAST(a.Player_ID AS VARCHAR) "
            "GROUP BY a.Player_ID "
            "ORDER BY MAX(a.streak) DESC LIMIT 5\").fetchall()\n"
            "[print(f'{r[0]}: {r[1]} games') for r in rows]\n"
            "out = rows"
        )
        try:
            from .tools import v1_tools as _vtsq

            _fn = next((t for t in _vtsq if t.name == "run_python"), None)
            out = await _fn.ainvoke({"code": _code}) if _fn is not None else {
                "tool": "run_python", "ok": False, "error": "no python tool"}
        except Exception as exc:
            out = {"tool": "run_python", "ok": False,
                   "error": str(exc)[:160]}
        state["tool_results"].append(
            out if isinstance(out, dict) else {"tool": "run_python",
                                              "rows": out})
        state["calls_made"].append("run_python:" + json.dumps(
            {"code": _code[:120]}, sort_keys=True))
        return
    if (_LIST_RX.search(question) and not is_trade and not is_cast
            and not is_compare and not is_raptor
            and not _SHOT_ZONE_RX.search(question)
            and not _HISTORICAL_RX.search(question)
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
    if (found_p and not is_trade and not is_cast
            and not is_compare and not is_raptor
            and re.search(
                r"overpaid|underpaid|contract value|good value|worth (it|his|her|the)|"
                r"salary vs production|value (for|of the)|worth the (money|contract)",
                question, re.IGNORECASE)):
        try:
            from .tools import v1_tools as _vtcv

            fncv = next((t for t in _vtcv if t.name == "get_contract_value"),
                        None)
            out = await fncv.ainvoke(
                {"player": found_p[0]}) if fncv is not None else {
                "tool": "get_contract_value", "ok": False,
                "error": "no contract tool"}
        except Exception as exc:
            out = {"tool": "get_contract_value", "ok": False,
                   "error": str(exc)[:160]}
        state["tool_results"].append(
            out if isinstance(out, dict) else {"tool": "get_contract_value",
                                              "rows": out})
        state["calls_made"].append("get_contract_value:" + json.dumps(
            {"player": found_p[0]}, sort_keys=True))
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
    elif re.search(r"injur|healthy|available|\bstatus\b", question,
                   re.IGNORECASE):
        # F45: scout-only routes cannot see the injury report or the
        # playoff inactive listings; league owns both.
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
    # Turn-level caches, reset per turn in run_chat.
    # desk_cache: (desk, entity) -> first desk result, shared across rounds.
    desk_cache: NotRequired[dict[str, dict[str, Any]]]
    # ledger: thread evidence facts (v2 step 2), loaded from store per
    # turn; extraction at ship time emits a ledger_facts event.
    ledger: NotRequired[list[str]]
    # entity_cache: normalized query -> resolve_entity result.
    entity_cache: NotRequired[dict[str, dict[str, Any]]]


def _call_key(name: str, args: dict[str, Any]) -> str:
    return name + ":" + json.dumps(args, sort_keys=True, default=str)


def _desk_dedupe_key(name: str, args: dict[str, Any]) -> tuple | None:
    """Turn-scoped dedupe key for a delegate desk: (desk, entities).

    Returns None when no player/team entity is detectable in the desk
    task, in which case the call is not dedupable (e.g. league-wide
    scans whose tasks legitimately differ each round).
    """
    try:
        task = args.get("task", "") if isinstance(args, dict) else ""
        qp, qt = _detect_entities(str(task or ""))
        ents = tuple(sorted(
            {p.strip().casefold() for p in qp}
            | {t.strip().casefold() for t in qt}))
    except Exception:
        return None
    return (name, ents) if ents else None


def _all_tools(state: DimeState) -> list:
    return list(v1_tools) + delegate_tools(state["primary"], state["model"])  # type: ignore[arg-type]


# B2: text_to_sql failed x5 across 5 planner rounds (188s turn); cut a tool after 2 straight fails.
_CIRCUIT_BREAKER_STRIKES = 2


def _circuit_broken_tools(state: dict[str, Any]) -> set[str]:
    try:
        streaks: dict[str, int] = {}
        for entry in state.get("tool_results") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("tool")
            if not name:
                continue
            try:
                failed = _result_status(entry) != "ok"
            except Exception:
                continue
            if failed:
                streaks[name] = streaks.get(name, 0) + 1
            else:
                streaks[name] = 0
        return {n for n, s in streaks.items() if s >= _CIRCUIT_BREAKER_STRIKES}
    except Exception:
        return set()


SUPERVISOR_TOOL_NAMES = frozenset({
    "resolve_entity", "get_compare", "compare_metrics", "get_debate_card", "get_preview", "get_briefing",
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
    broken = _circuit_broken_tools(state)
    return [t for t in _all_tools(state) if t.name in SUPERVISOR_TOOL_NAMES and t.name not in broken]


_DISPLAY_TITLES = {
    "run_python": "Warehouse query",
    "text_to_sql": "Warehouse query",
    "get_compare": "Player comparison",
    "compare_metrics": "Metric adjudication",
    "get_debate_card": "Debate card",
    "get_leaders": "League leaders",
    "get_team_compare": "Team compare",
    "get_team_four_factors": "Four factors",
    "get_team_leaders": "Team totals",
    "get_lineups": "Lineups",
    "get_shot_zones": "Shot zones",
    "get_matchup_splits": "Matchup splits",
    "get_regression_check": "Regression check",
    "get_comps": "Comps",
    "get_award_race": "Award race",
    "get_trade_value": "Trade value",
    "get_matchup_preview": "Matchup preview",
    "get_standings_deep": "Standings deep cuts",
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
    "get_team_compare": "leaders",
    "get_team_four_factors": "leaders",
    "get_team_leaders": "leaders",
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
        # QA F37: several fast paths wrap the whole tool payload as
        # rows=[payload]; the table then renders one row whose columns
        # are tool/ok/rows/meta with raw JSON blobs (risers #23, season
        # averages #37). Unwrap centrally so EVERY tool-result table is
        # safe, not just the paths patched one by one.
        rows = out.get("rows")
        if (isinstance(rows, list) and len(rows) == 1
                and isinstance(rows[0], dict)
                and "rows" in rows[0]
                and ("ok" in rows[0] or "tool" in rows[0])):
            inner = rows[0]
            out["rows"] = inner.get("rows")
            inner_meta = inner.get("meta")
            if isinstance(inner_meta, dict):
                meta = out.get("meta") if isinstance(out.get("meta"), dict) else {}
                out["meta"] = {**inner_meta, **meta}
        # QA #66: rows keyed ONLY by an id get a readable name first -
        # otherwise the id strip below leaves the model with "one
        # player" and no name to cite.
        try:
            from .tools._core import attach_names as _attach_names
            out["rows"] = _attach_names(out.get("rows"))
        except Exception:
            pass
        # QA #62: raw ids are plumbing, never user-facing table
        # columns. Frontend references no *_id field (verified by
        # grep), so strip them centrally at the emit point.
        _rows = out.get("rows")
        if isinstance(_rows, list):
            out["rows"] = [
                {k: v for k, v in r.items()
                 if not (k == "id" or k.endswith("_id"))}
                if isinstance(r, dict) else r
                for r in _rows
            ]
        out["kind"] = _KIND_FOR_TOOL.get(str(tool or ""), "dataset")
        # Every table keeps the title _with_title computed - dropping
        # non-curated titles here left pin-lane payloads (playoff
        # intel, standings, season averages) untitled, and the card
        # header fell back to a bare "DATASET" (QA S2 polish nit).
        if tool in _DISPLAY_TITLES:
            try:
                meta = out.get("meta") if isinstance(out.get("meta"), dict) else None
                out["title"] = _display_title(str(tool or ""), meta)
            except Exception:
                out["title"] = _DISPLAY_TITLES.get(str(tool), "Dataset")
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
    if state.get("ledger"):
        prior += ("\nEstablished facts from earlier in this "
                  "conversation (verified from tool data - trust them, "
                  "never contradict them, and do not re-fetch what they "
                  "already answer): " + " | ".join(
                      state["ledger"][-_LEDGER_MAX:]) + ".")
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
                [SystemMessage(content=build_planner_prompt(question_for_planner) + prior),
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
            desk_cache = state.setdefault("desk_cache", {})
            entity_cache = state.setdefault("entity_cache", {})
            if name.startswith("delegate_"):
                dkey = _desk_dedupe_key(
                    name, args if isinstance(args, dict) else {})
                if dkey is not None and dkey in desk_cache:
                    elapsed[id(call)] = 0
                    await _tok_q.put(None)
                    return {**desk_cache[dkey], "deduped": True}
                # Stream the desk's raw tokens live while it works.
                async def _on_tok(t: str) -> None:
                    await _tok_q.put((name, t))

                out = await asyncio.wait_for(
                    run_desk_streaming(
                        name,
                        args.get("task", "") if isinstance(args, dict) else "",
                        state["primary"], state["model"],  # type: ignore[arg-type]
                        on_token=_on_tok),
                    timeout=DESK_CALL_TIMEOUT_S)
                if (isinstance(out, dict) and dkey is not None
                        and _result_status(out) == "ok"):
                    desk_cache[dkey] = out
            elif name == "resolve_entity":
                qnorm = (str(args.get("query", "") or "").strip().casefold()
                         if isinstance(args, dict) else "")
                if qnorm in entity_cache:
                    elapsed[id(call)] = 0
                    await _tok_q.put(None)
                    return {**entity_cache[qnorm], "deduped": True}
                out = await asyncio.wait_for(fn.ainvoke(args),
                                             timeout=TOOL_CALL_TIMEOUT_S)
                if isinstance(out, dict) and _result_status(out) == "ok":
                    entity_cache[qnorm] = out
            else:
                out = await asyncio.wait_for(fn.ainvoke(args),
                                             timeout=TOOL_CALL_TIMEOUT_S)
            elapsed[id(call)] = int((time.time() - t0) * 1000)
            await _tok_q.put(None)
            return out if isinstance(out, dict) else {"tool": name, "rows": out}
        except TimeoutError:
            elapsed[id(call)] = int((time.time() - t0) * 1000)
            await _tok_q.put(None)
            return {"tool": name, "ok": False,
                    "error": f"timed out after {int(time.time() - t0)}s"}
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
        if res.get("deduped"):
            continue  # deduped reuse: no second trace replay in the UI
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
    s = re.sub(r"Client error '\d{3}[^']*' for url\s*'[^']*'\.?", " ", s)
    # content-free sandbox/schema failures are not an "informative
    # refusal" - strip them so the honest fallback fires instead
    s = re.sub(r"unknown table or column\.?[^\n]*", " ", s,
               flags=re.IGNORECASE)
    s = re.sub(r"Valid tables:[^\n]*", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"For more information check:[^\n]*", " ", s)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"\bsilver_\w+\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"(?is)\bselect\b.*?(;|$)", " ", s)
    s = re.sub(r"\bSQL\b", " ", s, flags=re.IGNORECASE)
    # QA #32: stripping 3-4 digit runs ate YEARS ("2025-26" -> "-26").
    # Only long runs (raw ids like 1629029) get scrubbed here.
    s = re.sub(r"\b\d{5,}\b", " ", s)
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
    # F45: a delegate whose answer is a NOTE (injury miss / playoff
    # inactive listing) carries it in a real summary with zero rows.
    # That is evidence; without this the compose collapses it to
    # "No <player> data found" over a correct desk answer.
    _delegate_ok = any(
        isinstance(r, dict) and r.get("agent") and r.get("ok")
        and isinstance(r.get("summary"), str)
        and len(r["summary"].strip()) >= 40
        for r in state["tool_results"]
    )
    if not evidenced and not _delegate_ok:
        # F63-T3 class: fresh evidence failed, but the thread ledger
        # holds payload-extracted facts from earlier turns. "No New
        # York Knicks data found" shipped live while the ledger knew
        # 'NBA Finals result: NYK 4 - 1 SAS'. The ledger is
        # provenance-valid; answer from it instead of false no-data.
        _led = [f for f in (state.get("ledger") or []) if isinstance(f, str)]
        if _led:
            from .tools._core import SEASON as _CUR_SEASON
            state["analysis"] = (
                f"This data covers the {_CUR_SEASON} season.\n"
                "From earlier in this conversation: "
                + "; ".join(_led[-_LEDGER_MAX:]) + ".")
            yield _event(
                "custom_data",
                {"node": "analytics",
                 "tables": _flatten_tables(state["tool_results"])})
            yield _event("node_update",
                         {"node": "analytics", "status": "complete"})
            return
        raw_errs = [str(r.get("error", ""))
                    for r in state["tool_results"]
                    if isinstance(r, dict) and r.get("error")][:3]
        cleaned = [_clean_error_text(e) for e in raw_errs]
        cleaned = [c for c in cleaned if c and len(c) >= 12]
        # Prefer informative refusals (F47 'side has no assets', F33
        # inactive notes, coverage sentences) over generic query
        # failures - the first error in the list is often the SQL
        # dead-end, not the answer-shaped one.
        def _rank(e: str) -> int:
            low = e.lower()
            if any(k in low for k in (
                    "not in this dataset", "no assets", "was listed "
                    "inactive", "unknown player", "no playoff games",
                    "no 20", "covers ", "not seeded", "same team")):
                return 0
            if "did not succeed" in low or "did not complete" in low:
                return 2
            return 1
        cleaned = sorted(cleaned, key=_rank)[:1]
        seasons = _collect_seasons(state["tool_results"])
        try:
            _qp, _qt = _detect_entities(state.get("question", "") or "")
            subject = (_qp + _qt)[:1]
            subject = subject[0] if subject else "NBA"
        except Exception:
            subject = "NBA"
        m = re.search(r"(20\d\d-\d\d)", state.get("question", "") or "")
        season_q = m.group(1) if m else (seasons[-1] if seasons else "")
        if cleaned:
            # QA #32: lead with the specific tool error ("LeBron James
            # is on PHI per salary data"), not the overclaiming
            # "No <player> data found" - data often EXISTS elsewhere.
            base = cleaned[0][0].upper() + cleaned[0][1:]
            if seasons:
                base += f" Warehouse coverage: {', '.join(seasons)}"
        else:
            if season_q:
                base = f"No {subject} data found for {season_q}"
            else:
                base = f"No {subject} data found"
            if seasons:
                base += f"; warehouse covers {', '.join(seasons)}"
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
                    content=(
                        f"Question: {state['question']}"
                        + (("\nEstablished facts from earlier in this "
                            "conversation (verified from tool data - trust "
                            "them, never contradict them, and use them "
                            "when this turn's evidence is thin): "
                            + " | ".join(state["ledger"][-_LEDGER_MAX:])
                            + ".") if state.get("ledger") else "")
                        + f"\nEvidence: {evidence}"
                    )
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


_DEV_TEXT_RX = re.compile(
    r"Traceback \(most recent call last\)[^\n]*|"
    r"line \d+, in <module>|"
    r"name '[A-Za-z_][\w.]*' is not defined|"
    r"\b[A-Za-z]*(?:Error|Exception|Warning): [^\n]*|"
    r"File \"[^\n]*\", line \d+|"
    # F53: httpx client errors (403/404/5xx with the external URL) are
    # tool internals, never an answer
    r"Client error '\d{3}[^']*' for url[^\n]*|"
    r"[Uu]nknown table or column\.?[^\n]*|"
    r"Valid tables:[^\n]*|"
    r"For more information check:[^\n]*|"
    r"https?://developer\.mozilla\.org[^\n]*|"
    # F43: run_python sandbox rejections must never BE the answer
    r"That code pattern is unavailable[^\n]*|"
    r"[^\n]*already preloaded[^\n]*|"
    r"imports/IO/writes[^\n]*|"
    r"[^\n]*con\.execute\([^\n]*|"
    r"[^\n]*rows\s*=\s*con\.[^\n]*",
    re.IGNORECASE)


# F61/verify-v0: the honest compute-failure end. Names coverage instead
# of admitting infra or blaming the user. Single source - the scrub's
# canned replacements and the presentation gap detection both key on it.
_COMPUTE_FALLBACK = ("That one didn't come back from the dataset just "
                     "now. It covers 2025-26 player and team stats, "
                     "game logs, standings, playoffs and the Finals.")




def _renumber_lists(text: str) -> str:
    """Renumber each contiguous ordered-list block from 1.

    Scrub rules can delete a list item ("Takeaways\\n2. ..." after
    item 1 was stripped as plumbing narration). Markdown renders the
    literal numbers, so renumber every contiguous block sequentially.
    """
    out: list[str] = []
    n = 0
    for line in text.split("\n"):
        m = re.match(r"^(\s*)\d+([.)]\s+)(.*)$", line)
        if m:
            n += 1
            out.append(f"{m.group(1)}{n}{m.group(2)}{m.group(3)}")
        else:
            if line.strip():
                n = 0
            out.append(line)
    return "\n".join(out)




def _scrub_final_text(text: str) -> str:
    """Exception text is for logs, never for the narrative (QA F34).

    A synthesis pass that quotes a raw NameError or Traceback makes the
    product look broken; swap the fragment for an honest plain-English
    admission instead."""
    if not text:
        return text
    # F61 shape ("I could not compute that from the dataset - the
    # warehouse query for it did not run. Try a narrower ask."): infra
    # admission + user-blaming. Rewrite before any other rule touches
    # it; also kill a standalone "Try a narrower ask" sentence.
    text = re.sub(
        r"I could not compute that from the dataset[^.!?\n]*[.!?]"
        r"\s*(?:Try a narrower ask[^.!?\n]*[.!?]?\s*)?",
        _COMPUTE_FALLBACK + " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:^|\s)Try a narrower ask[^.!?\n]*[.!?]?\s*",
                  " ", text, flags=re.IGNORECASE)
    # F43: an answer that IS a tool/sandbox error must not ship. When
    # internal-error patterns cover most of the text, replace the whole
    # thing with one honest sentence.
    _hits = _DEV_TEXT_RX.findall(text)
    _covered = sum(len(h) for h in _hits)
    if _hits and _covered >= 0.6 * len(text):
        return _COMPUTE_FALLBACK
    cleaned = _DEV_TEXT_RX.sub("that data pull did not complete", text)
    # P3/F66-chain: "Based on the get_X tool output" / display-name
    # variants ("Based on the Get Standings output") are orchestration,
    # never prose. Must run BEFORE the QA #60/#61 sentence drops, which
    # otherwise nuke the whole sentence for containing "tool".
    cleaned = re.sub(
        r"[Bb]ased on the [Gg]et[_ ][A-Za-z]+(?: tool)? output,?", "",
        cleaned)
    # QA #60: the model sometimes NARRATES a tool error in prose
    # ("A query for the award returned an error stating 'Finals MVP'
    # is not a valid award key"). Internal plumbing is never the
    # user's business - strip the whole sentence, not the fragment.
    cleaned = re.sub(
        r"[^.!?\n]*\b(?:returned an error|error stating|"
        r"not a valid [A-Za-z' ]*? key)\b[^.!?\n]*[.!?]",
        " ", cleaned)
    # QA #61: stop chasing phrasings - ANY sentence that talks about
    # tools or errors is plumbing narration and never ships. (The
    # honest whole-answer fallback returns before this pass, so its
    # own wording is unaffected.)
    cleaned = re.sub(
        r"[^.!?\n]*\b(?:tools?|errors?|unknown tables?|"
        r"warehouse quer\w*)\b[^.!?\n]*[.!?]", " ", cleaned)
    # "Based on scout summary and league data" - same class as
    # "per the scout summary".
    def _strip_based_prefix(m: "re.Match[str]") -> str:
        # Sentence-start removal must not leave a lowercase opener
        # ("Based on the available league data, the highest..." lost
        # its capital). Mid-sentence removals stay lowercase.
        pre = m.string[: m.start()].rstrip()
        rest = m.string[m.end():]
        if (not pre or pre.endswith((".", "!", "?", "\n"))) and rest:
            return ""  # capitalization handled by the post-pass below
        return ""
    cleaned = re.sub(
        r"[Bb]ased on (?:the )?(?:(?:available|current|latest|full) )*"
        r"(?:scout|league|team|\w+ desk) (?:summary|data),?",
        "", cleaned)
    cleaned = cleaned.lstrip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    # Field-name parrots: the model quotes evidence keys ("ambiguity
    # note") and summary wording ("scout summary") as prose.
    cleaned = re.sub(r"\bambiguity[_ ]note\b", "note", cleaned,
                     flags=re.IGNORECASE)
    # QA #76: this used to rewrite to "the data", colliding into
    # "Data provided by the data and split records".
    cleaned = re.sub(r"\b(?:the )?(?:scout|league|team) summary\b",
                     "the dataset", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwarehouse tables?\b", "the dataset", cleaned,
                     flags=re.IGNORECASE)
    # QA #75 nit: "per the warehouse output" leaks the same internal
    # term in a softer form. v67: "Based on warehouse data, ..." leaked
    # live (v66 smoke) - widen the prefix class and capitalize the
    # replacement when the phrase opened the sentence.
    def _wh_repl(m: "re.Match[str]") -> str:
        pre = m.string[: m.start()].rstrip()
        if not pre or pre.endswith((".", "!", "?", "\n")):
            return "From the dataset"
        return "from the dataset"

    cleaned = re.sub(
        r"\b(?:per|from|in|via|[Bb]ased on|[Aa]ccording to) (?:the )?"
        r"warehouse (?:outputs?|data|tables?)\b",
        _wh_repl, cleaned)
    cleaned = re.sub(r"\bwarehouse output\b", "the dataset", cleaned,
                     flags=re.IGNORECASE)
    # v77 QA nit: "according to the output" leaks the same infra term
    # without the "warehouse" prefix - same rewrite class.
    cleaned = re.sub(
        r"\b(?:[Pp]er|[Ff]rom|[Vv]ia|[Bb]ased on|[Aa]ccording to) "
        r"(?:the )?outputs?\b",
        _wh_repl, cleaned)
    # 2026-09-13 sweep: "output" as the SUBJECT of a sentence is the
    # same leak class - "The output confirms he holds the top rank."
    # Drop the whole sentence (the fact it confirms is already in the
    # answer); "the statistical estimate output reports X" keeps the
    # fact via the narrower "estimate output" -> "estimate" rewrite.
    cleaned = re.sub(r"\bestimate output\b", "estimate", cleaned,
                     flags=re.IGNORECASE)
    # 2026-09-13 sweep2: "I used the provided game logs and summary to
    # show ..." - first-person tool narration, never prose.
    cleaned = re.sub(
        r"[^.!?\n]*\bI used the (?:provided )?[A-Za-z ]*?"
        r"(?:logs?|summary|output|data|stats?|table)\b[^.!?\n]*[.!?]",
        " ", cleaned)
    # "league leaders output lists" - "output" as a source noun; the
    # subject-verb drop above only covers "The output ...".
    cleaned = re.sub(r"\b(league leaders|leaders|league) output\b",
                     r"\1 table", cleaned)
    cleaned = re.sub(
        r"[^.!?\n]*\b[Tt]he output (?:confirms?|shows?|indicates?|"
        r"reports?|states?)\b[^.!?\n]*[.!?]", " ", cleaned)
    # v77 QA nit: "using the basketball-reference the dataset" - the
    # warehouse-output rewrite fires AFTER a source name, leaving
    # "<source> the dataset". Collapse to "<source> dataset".
    cleaned = re.sub(r"\b(basketball-reference|nba api) the dataset\b",
                     r"\1 dataset", cleaned, flags=re.IGNORECASE)

    # F51: memory-persistence claims ("Noted your favorite team!",
    # "I'll remember that") imply cross-session memory that does not
    # exist (F22 shelved). Session-scoped phrasing survives; anything
    # else is rewritten to it. Analytical "as noted" is untouched.
    def _memory_scope(m: "re.Match[str]") -> str:
        sent = m.group(0)
        if re.search(r"this (?:conversation|chat|session)", sent,
                     re.IGNORECASE):
            return sent
        return ("I'll keep that in mind during this conversation - "
                "nothing carries over between sessions.")
    cleaned = re.sub(
        r"[^.!?\n]*\b(?:i(?:'ve| have) noted|noted (?:that )?you(?:r)?\b|"
        r"i(?:'ll| will) remember|i won't forget|"
        r"i(?:'ve| have) saved|"
        r"i(?:'ll| will) keep (?:that|this|it) in mind)\b[^.!?\n]*[.!?]",
        _memory_scope, cleaned, flags=re.IGNORECASE)
    # v67 live collision: "per the NBA API league data" hit the
    # league-data rule below and shipped "per the NBA API the dataset".
    cleaned = re.sub(r"\b(?:the )?NBA API league data\b", "the dataset",
                     cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bleague data\b", "the dataset", cleaned,
                     flags=re.IGNORECASE)
    # scrub collisions: "the data data", "the dataset and the dataset"
    cleaned = re.sub(r"\b[Tt]he data data\b", "the data", cleaned)
    # 2026-09-13 probe: "the dataset data shows:" - the league-data
    # rewrite landing after "the dataset" rewrite. Same collision class.
    cleaned = re.sub(r"\b[Tt]he dataset data\b", "the data", cleaned)
    # Same probe: "Analysis based on ``." - an empty tool-name citation
    # left when the model backticks a blank. Drop the line outright.
    cleaned = re.sub(r"(?m)^[ \t]*\*?Analysis based on `[^`]*`\.?\*?[ \t]*$\n?",
                     "", cleaned)
    cleaned = re.sub(r"\bthe the\b", "the", cleaned,
                     flags=re.IGNORECASE)
    # 2026-09-13 sweep: "10.7 assists per game ." - stray space before
    # terminal punctuation, an LLM typo class that reads sloppy.
    cleaned = re.sub(r" +([.,;:!?])(?=\s|$)", r"\1", cleaned)
    # Sweep2: "points, efficiency, and efficiency" - the LLM repeated
    # the final list item. Collapse "X, and X" -> "and X"... kept
    # simple: drop the earlier duplicate and its comma.
    cleaned = re.sub(r"\b(\w{4,}), and \1\b", r"and \1", cleaned)
    # 2026-09-13 gauntlet: "**Takeaways:**\n\n**Verdict:**" - a section
    # header whose items were all stripped (or never written) ships as
    # an empty section. Drop header lines with no list items or prose
    # before the next header.
    cleaned = re.sub(
        r"(?m)^[ \t]*\*\*[^*\n]+\*\*:?[ \t]*\n"
        r"(?=[ \t]*\n?[ \t]*\*\*|\s*$)",
        "", cleaned)
    cleaned = re.sub(r"\bcomeback_kings\b", "comeback wins", cleaned,
                     flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthe dataset(?:,? and|,)? the dataset\b",
                     "the dataset", cleaned, flags=re.IGNORECASE)
    # 2026-09-13 compose probe: the "the dataset" rewrites above turn a
    # "Source: league agent summary" attribution line into "Source:
    # league agent the dataset" - an internal agent name + broken
    # grammar. Source lines that name an agent or the dataset are
    # orchestration leaks, never provenance; drop the whole line.
    cleaned = re.sub(
        r"(?m)^[ \t]*\*{0,2}Source:\*{0,2}[^\n]*\b(?:agent|dataset)\b[^\n]*$",
        "", cleaned)
    # Sweep3: trailing empty list items ("3." with no text) after the
    # model ran out of content.
    cleaned = re.sub(r"(?m)^[ \t]*(?:\d+\.|[-*])[ \t]*$\n?", "", cleaned)
    # Same probe: "And the dataset, Shai ... played" - a dangling
    # vocative left when a prefix rule fired mid-sentence. "And the
    # dataset," can never open a grammatical sentence; strip it.
    cleaned = re.sub(r"(?m)(^|[.!?] )[Aa]nd the dataset, ", r"\1",
                     cleaned)
    # Same probe: a rewrite landed "the dataset" inside a markdown
    # header ("### Player Comparison (the dataset)"). Headers are
    # titles, not prose - drop the parenthetical there only.
    cleaned = re.sub(r"(?m)^(#{1,6} [^\n]*?)\s*\(the dataset\)\s*$",
                     r"\1", cleaned)
    # Raw ids are plumbing (QA #65: "Their unique identifier is
    # 1610612760"). Kill id-narration sentences, then lone long runs.
    cleaned = re.sub(
        r"[^.!?\n]*\b(?:unique identifier|does not include the "
        r"(?:team |player )?name)\b[^.!?\n]*[.!?]", " ", cleaned)
    cleaned = re.sub(r"\b\d{5,}\b", " ", cleaned)
    # QA #61c: integer-valued stats carry decimal noise ("32.0
    # minutes", "15.0 games"). Strip trailing .0 everywhere.
    cleaned = re.sub(r"\b(\d+)\.0\b", r"\1", cleaned)
    # QA #61b: renumber numbered-list runs sequentially from 1 - the
    # model emits "2. 3. 4." after an unnumbered first item. Line-start
    # runs of 2+ are real list syntax; inline runs need 3+ markers so a
    # stat sentence chain ("scored 5. Next game 6.") is never touched.
    def _renum_lines(m: "re.Match[str]") -> str:
        n = 0
        out = []
        for ln in m.group(0).split("\n"):
            mm = re.match(r"^(\s*)\d+\.\s", ln)
            if mm:
                n += 1
                ln = f"{mm.group(1)}{n}. " + ln[mm.end():]
            out.append(ln)
        return "\n".join(out)
    cleaned = re.sub(r"(?:^\s*\d+\. [^\n]*(?:\n\s*\d+\. [^\n]*)+)",
                     _renum_lines, cleaned, flags=re.MULTILINE)
    _marks = list(re.finditer(r"(?<![\d.])(\d{1,2})\. (?=[A-Z])",
                              cleaned))
    _runs: list[list["re.Match[str]"]] = []
    _cur: list["re.Match[str]"] = []
    for m in _marks:
        if _cur and int(m.group(1)) == int(_cur[-1].group(1)) + 1:
            _cur.append(m)
        else:
            if len(_cur) >= 3:
                _runs.append(_cur)
            _cur = [m]
    if len(_cur) >= 3:
        _runs.append(_cur)
    for _run in reversed(_runs):
        for _i, m in enumerate(reversed(_run)):
            cleaned = (cleaned[:m.start(1)]
                       + str(len(_run) - _i) + cleaned[m.end(1):])
    # QA nit batch (Sep 12 overnight chain): internal arithmetic
    # narration never ships. "Dividing 2143 by 64 gives 33.5 points
    # per game." keeps the value and drops the scratch work;
    # "(509 \u00f7 19)" and "130/5 = 26 PPG" lose the long division.
    cleaned = re.sub(
        r"[Dd]ividing \d[\d,]*(?:\.\d+)? by \d[\d,]*(?:\.\d+)? "
        r"gives ", "", cleaned)
    cleaned = re.sub(
        r"\(\s*\d[\d,]*(?:\.\d+)?\s*[\u00f7/]\s*\d[\d,]*"
        r"(?:\.\d+)?\s*\)", "", cleaned)
    cleaned = re.sub(
        r"\b\d[\d,]*(?:\.\d+)?\s*/\s*\d[\d,]*(?:\.\d+)?"
        r"\s*=\s*", "", cleaned)
    # "a 48 and 30 record" -> "a 48-30 record" (HOU-with-KD chain).
    cleaned = re.sub(r"\b(\d{1,3}) and (\d{1,3}) record\b",
                     r"\1-\2 record", cleaned)
    # "the LAL franchise" - abbreviations are table shorthand, never
    # prose (T7 ambiguity answer shipped it live).
    try:
        from nba_api.stats.static import teams as _static_teams
        _abbr_map = {t["abbreviation"]: t["full_name"]
                     for t in _static_teams.get_teams()}
    except Exception:
        _abbr_map = {}
    if _abbr_map:
        def _franchise(m: "re.Match[str]") -> str:
            return (f"the {_abbr_map.get(m.group(1), m.group(1))} "
                    f"franchise")
        cleaned = re.sub(r"\bthe ([A-Z]{3}) franchise\b",
                         _franchise, cleaned)
    # Scrub-collision leftover: "Data provided by the data and split
    # records" (league-agent rewrite landed next to "provided by").
    cleaned = re.sub(r"\bprovided by the data\b",
                     "provided by the dataset", cleaned,
                     flags=re.IGNORECASE)
    # Strip-induced fragment: "And playoff logs, Jalen ..." - the
    # based-on strip ate the sentence head and left a dangling And.
    cleaned = re.sub(r"(^|[.!?]\s+)And (?=(?:playoff |game )?logs\b)",
                     r"\1From the ", cleaned)
    # Sentence-start capitalization after lead-in strips ("Based on
    # scout summary, the team" -> "The team"), keeping stat acronyms.
    _KEEP_LOWER = {"efg", "ts", "usg", "ast", "stl", "blk", "tov",
                   "fg", "ft", "3p", "3pm", "rapm", "epm"}
    def _cap(m: "re.Match[str]") -> str:
        word = m.group(2)
        if word.lower().rstrip("%") in _KEEP_LOWER:
            return m.group(0)
        return m.group(1) + word[0].upper() + word[1:]
    cleaned = re.sub(r"(^|[.!?]\s+)([a-z][a-zA-Z%]*)", _cap, cleaned)
    # P3: tool names and desk identities are orchestration, never prose
    # ("Based on the get_injuries tool output", "the league agent").
    cleaned = re.sub(r"\bthe get_\w+ tool\b", "the data", cleaned)
    cleaned = re.sub(r"\bget_\w+\b", "", cleaned)
    cleaned = re.sub(r"\bfrom the (league|scout|team) (agent|desk)\b",
                     "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[Pp]er the (league|scout|team|\w+ desk) summary,?",
                     "", cleaned)
    cleaned = re.sub(r"\bthe (league|scout|team) (agent|desk)\b",
                     "the data", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bseason([.,]?) season\b", r"season\1", cleaned)
    cleaned = re.sub(r"\bper game([.,]?)\s+per game\b", r"per game\1",
                     cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    # The season-first-line guard fires once; when two evidence streams
    # each pulled it in, the sentence lands twice. Keep the first.
    _sfx = re.compile(
        r"(This data covers the \d{4}-\d{2} season\.)", re.IGNORECASE)
    _seen = False
    def _dedupe_season(m: "re.Match[str]") -> str:
        nonlocal _seen
        if _seen:
            return ""
        _seen = True
        return m.group(1)
    cleaned = _sfx.sub(_dedupe_season, cleaned)
    # Whole-paragraph / long-sentence repeats: two evidence streams can
    # each yield the same analysis block (seen live: the full Derik
    # Queen verdict twice). Paragraph keys diverge once the season line
    # is stripped from the second copy, so dedupe long sentences too.
    paras = cleaned.split("\n\n")
    if len(paras) > 1:
        seen_paras: set[str] = set()
        kept: list[str] = []
        for para in paras:
            key = re.sub(r"\s+", " ", para).strip().lower()
            if len(key) >= 80 and key in seen_paras:
                continue
            seen_paras.add(key)
            kept.append(para)
        cleaned = "\n\n".join(kept)
    # Split on horizontal whitespace only - eating the newline after a
    # list item ("1. First.\n2. Second") flattens lists into prose.
    sentences = re.split(r"(?<=[.!?])[ \t]+", cleaned)
    if len(sentences) > 1:
        seen_s: set[str] = set()
        kept_s: list[str] = []
        for s in sentences:
            key = re.sub(r"\s+", " ", s).strip().lower()
            if len(key) >= 60 and key in seen_s:
                continue
            seen_s.add(key)
            kept_s.append(s)
        cleaned = " ".join(kept_s)
        cleaned = re.sub(r" \n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # QA #46 structural net: an answer that reads like an error and
    # carries no data claim at all is replaced wholesale - pattern
    # lists alone kept missing new exception phrasings ('async for'
    # requires..., 'no such column ...').
    _errish = re.search(
        r"error|exception|unavailable|requires an object|traceback|"
        r"did not succeed|not defined|no such column|failed after|"
        r"coroutine|aiter", cleaned, re.IGNORECASE)
    if _errish and not re.search(r"\d", cleaned):
        return _COMPUTE_FALLBACK
    return cleaned.strip()


_LEDGER_MAX = 20


def _extract_ledger_facts(state: dict) -> list[str]:
    """Thread evidence ledger (v2 step 2): facts extracted from tool
    PAYLOADS at ship time - never from LLM text (v67 lesson). Persisted
    per-thread so follow-ups resolve evidence, not just entities
    (F62/F63: the thread produced Brunson's Game 5 line and the NYK-SAS
    Finals matchup, then later turns claimed the dataset lacked them).
    """
    facts: list[str] = []
    for tr in state.get("tool_results") or []:
        if not isinstance(tr, dict) or _result_status(tr) != "ok":
            continue
        # Pins wrap payloads as {"tool": t, "rows": [raw_tool_dict]};
        # the planner path stores the raw dict directly. Unify.
        _r = tr.get("rows")
        if (isinstance(_r, list) and len(_r) == 1
                and isinstance(_r[0], dict) and "rows" in _r[0]):
            tr = _r[0]
        try:
            tname = tr.get("tool")
            rows = tr.get("rows")
            if tname == "get_playoffs" and isinstance(rows, dict):
                fin = rows.get("finals") or {}
                score = fin.get("series_score")
                if score:
                    facts.append(f"NBA Finals result: {score}")
                champ = rows.get("champion")
                rec = rows.get("champion_record") or {}
                if champ:
                    line = f"NBA champion: {champ}"
                    if rec.get("w") is not None:
                        line += f" ({rec['w']}-{rec['l']} playoffs)"
                    facts.append(line)
            elif tname == "get_team_leaders":
                ll = (tr.get("meta") or {}).get("leader_line")
                if ll:
                    facts.append(ll[0].upper() + ll[1:])
            elif tname == "get_team_compare":
                da = (tr.get("meta") or {}).get("deterministic_answer")
                if da:
                    facts.append(da[0].upper() + da[1:])
            elif tname == "get_standings" and isinstance(rows, list):
                # QA F67: "Which team had the best record?" answered OKC
                # 64-18, but the ledger carried nothing, so the next
                # turn ("their best player") resolved to a false
                # absence. Persist the best-record team as trusted
                # evidence for pronoun carry. LeagueRank 1 row wins;
                # fall back to max WINS.
                best = None
                for r in rows:
                    if isinstance(r, dict) and r.get("LeagueRank") == 1.0:
                        best = r
                        break
                if best is None:
                    def _w(row: dict) -> float:
                        try:
                            return float(row.get("WINS"))
                        except (TypeError, ValueError):
                            return -1.0
                    cands = [r for r in rows if isinstance(r, dict)]
                    best = max(cands, key=_w, default=None)
                    if best is not None and _w(best) < 0:
                        best = None
                if best is not None and best.get("team"):
                    line = f"Best record: {best['team']}"
                    rec = best.get("Record")
                    if rec:
                        line += f" ({rec})"
                    if best.get("abbrev"):
                        line += f" [{best['abbrev']}]"
                    facts.append(line)
            elif tname == "search_game_logs" and isinstance(rows, dict):
                matches = rows.get("matches") or []
                player = rows.get("player")
                # single-game context only: exactly one match, or an
                # explicit game-number/date filter narrowed it
                filt = str(rows.get("filters") or "")
                if (player and matches and (len(matches) == 1 or re.search(
                        r"game \d", filt, re.IGNORECASE))):
                    m0 = matches[0]
                    def _i(v: object) -> int:
                        try:
                            return int(float(v))  # type: ignore[arg-type]
                        except (TypeError, ValueError):
                            return 0
                    facts.append(
                        f"{player} on {m0.get('date')} "
                        f"({m0.get('matchup')}): {_i(m0.get('pts'))} pts, "
                        f"{_i(m0.get('reb'))} reb, {_i(m0.get('ast'))} ast")
        except Exception:
            continue
    out: list[str] = []
    for f in facts:
        if f and f not in out:
            out.append(f)
    return out[:_LEDGER_MAX]


def _verify_draft_numerals(state: dict, text: str) -> list[str]:
    """Verify node v0: numeral provenance (telemetry only).

    Every number in the shipped answer must trace to this turn's tool
    payloads or the season line - the v67 lesson generalized (LLM-
    composed numerals are untrusted). Violations land on
    state['_verify'] for the eval harness/reviewer; the re-route that
    acts on them ships with the full verify node.
    """
    import json as _json

    def _norm(n: str) -> str:
        return n[:-2] if n.endswith(".0") else n

    if not state.get("tool_results") and not state.get("ledger"):
        state["_verify"] = {"numeral_violations": []}
        return []
    try:
        raw = _json.dumps(state.get("tool_results") or [])
        raw += _json.dumps(state.get("ledger") or [])
        allowed = {_norm(n) for n in re.findall(r"\d+(?:\.\d+)?", raw)}
        try:
            from .tools._core import SEASON as _S
            allowed |= set(re.findall(r"\d+", _S))
        except Exception:
            allowed |= {"2025", "26"}
        violations: list[str] = []
        for n in re.findall(r"\d+(?:\.\d+)?", text or ""):
            if _norm(n) not in allowed and n not in violations:
                violations.append(n)
        state["_verify"] = {"numeral_violations": violations}
        return violations
    except Exception:
        return []

# QA #65 known-gap taxonomy: what the dataset provably does NOT have.
# When an answer comes back content-thin, the honest fallback names
# the specific gap (bench-scoring style) instead of shipping
# boilerplate or inventing a wrong reason.
_KNOWN_GAPS: list[tuple["re.Pattern[str]", str]] = [
    (re.compile(r"\btwo[\s-]*way\b|\b10[\s-]*day\b|\bg[\s-]?league\b|"
                r"\bcontract (?:types?|status|kinds?)\b", re.IGNORECASE),
     "The dataset does not track contract types (two-way, 10-day, "
     "G League), so players cannot be filtered by contract status. "
     "It does track minutes and stats for every rostered player."),
    (re.compile(r"\bbench (?:scoring|points|production|minutes|unit)|"
                r"second unit|starters? vs\b", re.IGNORECASE),
     "The dataset does not split bench vs starter production. "
     "It does track per-player stats for everyone, starters included."),
    (re.compile(r"\bplay[\s-]*by[\s-]*play|in[\s-]*game (?:margin|flow|comeback)|"
                r"(?:largest|biggest) (?:deficit|lead|comeback|run)|"
                r"quarter[\s-]*by[\s-]*quarter", re.IGNORECASE),
     "The dataset has no play-by-play, so in-game margin flow "
     "(deficits, runs, quarter splits) cannot be computed. Comeback "
     "numbers use behind-at-halftime records as the proxy."),
    (re.compile(r"\bwho won\b.{0,25}\b(?:mvp|dpoy|roy|6moy|mip)\b|"
                r"\baward (?:winners?|results?|outcomes?)\b", re.IGNORECASE),
     "The dataset does not record award outcomes. It can rank "
     "candidates by a statistical formula instead."),
]


def _gap_note(question: str) -> str | None:
    q = question or ""
    for rx, msg in _KNOWN_GAPS:
        if rx.search(q):
            return msg
    return None


# QA #72 (F58): memory/preference statements ("My favorite team is the
# Lakers. Remember that.") are NOT data asks. Unpinned, the planner
# routed them to the team desk, the resolver mapped "Lakers" to BOTH
# Los Angeles teams, and presentation shipped "No Los Angeles Clippers
# data found." - wrong team, false no-data claim, no acknowledgment.
_MEMORY_STATEMENT_RX = re.compile(
    r"\bfavou?rite\s+(?:team|player)\b", re.IGNORECASE)
_MEMORY_DATA_ASK_RX = re.compile(
    r"\bwho\b|\bwhat\b|\bwhich\b|\bhow (?:many|much|does|did|is|are)\b|"
    r"\bwins?\b|\bloss(?:es)?\b|\bpoints?\b|\bstats?\b|\brecord\b|"
    r"\bscores?d?\b|\bcompare\b|\bvs\.?\b|\baverages?d?\b|\bleaders?\b|"
    r"\bbest\b|\bworst\b|\brank|\bodds\b|\btrades?\b|\binjur|"
    r"\blineups?\b|\bcontracts?\b|\bsalary\b|\bplayoffs?\b|\bfinals\b|"
    r"\bmvp\b|\bchampionship|\btitles?\b|\brookie|\bstreak\b|"
    r"\broster\b|\bschedule\b|\bgames?\b", re.IGNORECASE)


def _memory_ack(question: str) -> str | None:
    """Session-scoped acknowledgment for preference/memory statements.

    Returns None when the statement carries an analytical ask - those
    fall through to the normal routes.
    """
    q = question or ""
    if not _MEMORY_STATEMENT_RX.search(q):
        return None
    if _MEMORY_DATA_ASK_RX.search(q):
        return None
    m = re.search(r"\bfavou?rite\s+(team|player)\s+is\s+(?:the\s+)?"
                  r"([^.,!?\n]+)", q, re.IGNORECASE)
    if m:
        entity = re.split(r"\s+(?:and|but|so)\s+", m.group(2).strip())[0]
        kind = m.group(1).lower()
        return (f"Got it - I've got {entity} down as your favorite {kind} "
                "for this conversation. Nothing carries over between "
                "sessions.")
    return ("Got it - I'll keep that in mind during this conversation. "
            "Nothing carries over between sessions.")



_ABSENCE_RX = re.compile(
    r"(?:is|are|was|were)?\s*(?:missing|unavailable|not available|"
    r"not in the|could not be found|no record)",
    re.IGNORECASE)


def _strip_false_absence(text: str, tool_results: list) -> str:
    """F65: 'Heat win total is missing from the standings' shipped live
    while get_standings' payload carried MIA 43-39 - the planner used a
    top-N cut and synthesis reported its evidence WINDOW as a warehouse
    gap. Deterministic guard: a sentence claiming absence about an
    entity whose data sits in this turn's payloads is false - drop the
    sentence, keep the rest. Conservative: only fires when the entity
    string literally appears in payload JSON.

    QA F65 (compare markdown): sentence reassembly must preserve the
    original newline structure. Splitting on newlines and rejoining
    with spaces flattened tables, headings and bullet lists into one
    line, so the UI rendered the markdown source literally.
    """
    import json as _json

    try:
        hay = _json.dumps(
            [r for r in tool_results or [] if isinstance(r, dict)],
            default=str).lower()
    except Exception:
        return text
    if not hay or hay == "[]":
        return text

    def _sweep(chunk: str) -> str:
        kept: list[str] = []
        for seg in re.split(r"(?<=[.!?])[ \t]+", chunk):
            if _ABSENCE_RX.search(seg):
                # entity = capitalized tokens (team/player names) in the
                # sentence; false only if one appears in the payload.
                ents = re.findall(r"[A-Z][a-z]{2,}", seg)
                if any(e.lower() in hay for e in ents):
                    continue  # false absence claim: drop
            kept.append(seg)
        return " ".join(s.strip() for s in kept if s.strip())

    # Newlines are structural (tables, headings, lists): sweep each
    # line separately and rejoin with the original separators.
    parts = re.split(r"(\n+)", text)
    out = "".join(part if part.startswith("\n") else _sweep(part)
                  for part in parts)
    return out or text


async def presentation_agent(state: DimeState) -> AsyncGenerator[dict[str, Any], None]:
    yield _event("node_update", {"node": "presentation", "status": "running"})
    text = state.get("analysis", "") or "No data came back. Try a player or team name."
    # QA #65 (F54): a content-thin answer - boilerplate season line and
    # nothing else - never ships. Name the known gap when the question
    # matches the taxonomy, else the honest generic fallback.
    _core = re.sub(r"This data covers the \d{4}-\d{2} season\.?", "",
                   text, flags=re.IGNORECASE)
    _words = re.findall(r"[A-Za-z]+", _core)
    if ((len(_words) < 5 and not re.search(r"\d", _core))
            or text.startswith("No data came back")):
        _gap = (_gap_note(state.get("question", "") or "")
                or _memory_ack(state.get("question", "") or ""))
        if _gap:
            text = _gap
        else:
            # f62 (2026-09-13 prod QA): the refusal declared "could not
            # find" while the turn's tool_results carried the correct
            # 19-row playoff log - prose contradicting its own attached
            # evidence. The refusal must look at the payloads first:
            # with rows attached, the honest message is a summary
            # failure, not an absence.
            _has_rows = False
            for _tr in state.get("tool_results") or []:
                if not isinstance(_tr, dict):
                    continue
                _r = _tr.get("rows")
                if isinstance(_r, list) and _r:
                    _has_rows = True
                elif isinstance(_r, dict) and any(
                        v for v in _r.values() if v):
                    _has_rows = True
            text = (("I pulled the relevant data but could not turn it "
                     "into a clean summary - the evidence panel below "
                     "has the full breakdown.")
                    if _has_rows else
                    ("I could not find that in the dataset. "
                     "It covers 2025-26 player and team stats, "
                     "game logs, standings, playoffs and the "
                     "Finals - try one of those."))
    _scrubbed = _scrub_final_text(text)
    _scrubbed = _strip_false_absence(_scrubbed,
                                 state.get("tool_results") or [])
    # F66: multi-metric team compare ships deterministic - the payload
    # built the sentence, the LLM narrative is ignored (v67 design
    # law: LLM-composed numerals are untrusted on pinned lanes).
    for _tr in state.get("tool_results") or []:
        if (isinstance(_tr, dict)
                and isinstance(_tr.get("meta"), dict)
                and _tr["meta"].get("deterministic_answer")):
            _det = str(_tr["meta"]["deterministic_answer"])
            try:
                if _tr.get("tool") not in ("get_trade_check",
                                           "pin_team_scoring_record",
                                           "get_team_four_factors"):
                    # Trade verdicts quote next-season salary-sheet
                    # figures with their own as-of date; the generic
                    # current-season header would misstate them. The
                    # team scoring-record pin carries its own
                    # historical-span coverage line; the four-factors
                    # pin writes its coverage line into the det.
                    from .tools._core import SEASON as _CUR_SEASON
                    _det = (f"This data covers the {_CUR_SEASON} season.\n"
                            + _det)
            except Exception:
                pass
            _scrubbed = _det
            break
    # v67 (v66 live smoke, 12:32 PM): team-totals answers paraphrased
    # away the leader's total - "scored the most total points with PTS
    # (122.1 per game)". meta.note already tells the LLM to cite
    # leader_line verbatim; it still drops the value under variance.
    # v67 repair-regex rounds then chased four degenerate with-clause
    # shapes ("with PTS (", "with PTS,", "with .", "with ,") and the
    # LLM kept inventing more. Whack-a-mole lost: when get_team_leaders
    # is the evidence, the answer ships deterministic - leader_line
    # plus runner-ups from rows, no LLM narrative at all.
    for _tr in state.get("tool_results") or []:
        if (isinstance(_tr, dict)
                and _tr.get("tool") == "get_team_leaders"
                and _tr.get("rows") and isinstance(_tr.get("meta"), dict)):
            _tm = _tr["meta"]
            _tstat = _tm.get("stat_category")
            _trows = _tr["rows"]
            if _tstat and _trows[0].get(_tstat) is not None \
                    and _tm.get("leader_line"):
                _ll = _tm["leader_line"]
                _ll = _ll[0].upper() + _ll[1:] + "."
                _stat_word = {"PTS": "points", "REB": "rebounds",
                              "AST": "assists", "STL": "steals",
                              "BLK": "blocks"}.get(_tstat, _tstat)
                _runners = "; ".join(
                    f"{r['TEAM']} {r[_tstat]} ({r['PER_GAME']} per game)"
                    for r in _trows[1:4]
                    if r.get(_tstat) is not None)
                _det = _ll
                if _runners:
                    _det += (f" Next in total {_stat_word}: "
                             f"{_runners}.")
                try:
                    from .tools._core import SEASON as _CUR_SEASON
                    _det = (f"This data covers the {_CUR_SEASON} "
                            f"season.\n" + _det)
                except Exception:
                    pass
                _scrubbed = _det
            break
    # QA #67 (F55): with no explicit season context in the question,
    # the season line must say the CURRENT season - a stray 2024-25
    # row in evidence must not relabel the answer.
    if not re.search(r"20\d\d-\d\d|last season|career|"
                     r"all[\s-]*time|histor", state.get("question", "")
                     or "", re.IGNORECASE):
        try:
            from .tools._core import SEASON as _CUR_SEASON
            _scrubbed = re.sub(
                r"This data covers the \d{4}-\d{2} season",
                f"This data covers the {_CUR_SEASON} season",
                _scrubbed, count=1)
            _scrubbed = re.sub(
                r"This data covers the 20\d\d season",
                f"This data covers the {_CUR_SEASON} season",
                _scrubbed, count=1)
        except Exception:
            pass
    # F61 residual: the coverage line must match the evidence span -
    # a deep hist answer from silver_hist_* shipped "This data covers
    # the 2022-23 season." over rows spanning many seasons. When the
    # evidence carries 2+ distinct seasons, rewrite the line to the
    # real min-through-max span.
    def _row_seasons(node: object, _out: set) -> None:
        stack = [node]
        while stack:
            it = stack.pop()
            if isinstance(it, list):
                stack.extend(it[:300])
            elif isinstance(it, dict):
                for k, v in it.items():
                    lk = str(k).lower()
                    if lk in ("_season", "season") and isinstance(v, str):
                        if re.fullmatch(r"20\d\d-\d\d", v.strip()):
                            _out.add(v.strip())
                    elif isinstance(v, (list, dict)):
                        stack.append(v)
    _ev_seasons: set = set()
    for _tr in state.get("tool_results") or []:
        if isinstance(_tr, dict):
            _row_seasons(_tr.get("rows"), _ev_seasons)
    if len(_ev_seasons) >= 2:
        _ys = sorted(int(s[:4]) for s in _ev_seasons)
        _span = (f"{_ys[0]}-{str(_ys[0] + 1)[2:]} through "
                 f"{_ys[-1]}-{str(_ys[-1] + 1)[2:]}")
        _scrubbed = re.sub(
            r"This data covers the 20\d\d-\d\d season\.",
            f"This data covers the {_span} seasons.", _scrubbed,
            count=1)
    # F61 coverage-window honesty: all-time/historical asks run over the
    # silver_hist_* span, but the compose prompt tells the model to
    # write the current-season line verbatim (and sometimes no line at
    # all). For a historical question with no explicit season, the line
    # must name the historical span; when the line is missing over
    # evidenced rows, prepend it.
    _qtxt = state.get("question", "") or ""
    _hist_q = re.search(
        r"all[\s-]*time|histor|record for|since (?:19|20)\d\d",
        _qtxt, re.IGNORECASE) and not re.search(r"20\d\d-\d\d", _qtxt)
    if _hist_q:
        try:
            from .tools._core import SEASON as _CUR_SEASON
            from .tools._core import HIST_SEASON_START as _HIST_START
            _hist_line = (f"This data covers the {_HIST_START} through "
                          f"{_CUR_SEASON} seasons.")
            _new, _n = re.subn(
                r"This data covers the 20\d\d-\d\d season\.",
                _hist_line, _scrubbed, count=1)
            _scrubbed = _new
            if _n == 0 and "This data covers" not in _scrubbed:
                _has_rows = any(
                    isinstance(r, dict) and r.get("rows")
                    for r in _flatten_tables(state["tool_results"]))
                if _has_rows:
                    # A model-written "season not specified" admission
                    # contradicts the span line - drop it (F61 bench run
                    # shipped exactly that over 144-pt playoff rows).
                    _scrubbed = re.sub(
                        r"The season is not specified in the "
                        r"evidence\.?\s*", "", _scrubbed,
                        flags=re.IGNORECASE)
                    _scrubbed = _hist_line + "\n" + _scrubbed
        except Exception:
            pass
    # A named known-gap beats any no-data outcome: the generic
    # compute-failure fallback AND model-worded admissions ("the query
    # did not succeed", "no data is available", "I cannot rank").
    # "Contract types are not tracked" informs; failure narration
    # only mystifies (QA #65 F54).
    _gap = (_gap_note(state.get("question", "") or "")
            or _memory_ack(state.get("question", "") or ""))
    # The override exists to rescue NO-DATA outcomes. When the answer is
    # evidence-backed, an honest gap sentence inside it ("margin flow is
    # not in the dataset") must NOT trigger a full replacement - that
    # nuked a correct 21-row comeback board on live (10:09 AM probe).
    _evidenced = any(
        isinstance(r, dict) and r.get("rows")
        for r in _flatten_tables(state["tool_results"]))
    _delegate_ok = any(
        isinstance(r, dict) and r.get("agent") and r.get("ok")
        and isinstance(r.get("summary"), str)
        and len(r["summary"].strip()) >= 40
        for r in state["tool_results"])
    if _gap and not _evidenced and not _delegate_ok and (
            _scrubbed.startswith(_COMPUTE_FALLBACK[:40])
            or re.search(
                r"did not succeed|no data is available|"
                r"i cannot|can't rank|not available|"
                r"is missing|could not be computed|"
                r"does not include", _scrubbed, re.IGNORECASE)):
        _scrubbed = _gap
    # F39: compose sometimes emits GFM pipe tables in the answer text.
    # Tables are evidence cards now (S2 design) - the LLM-composed table
    # is a duplicate with untrusted labels (it rendered team wins as a
    # "Points Per Game" row on the Luka/SGA compare). Strip pipe-table
    # blocks (2+ consecutive pipe rows) when real table artifacts exist
    # to cite; single stray pipe lines and prose stay.
    if _evidenced:
        _kept: list[str] = []
        _run: list[str] = []
        for _ln in _scrubbed.split("\n") + [""]:
            if re.match(r"^\s*\|.*\|\s*$", _ln):
                _run.append(_ln)
            else:
                if len(_run) < 2:
                    _kept.extend(_run)
                _run = []
                _kept.append(_ln)
        _stripped = re.sub(r"\n{3,}", "\n\n",
                           "\n".join(_kept)).strip()
        if _stripped:
            _scrubbed = _stripped
    # QA #66: the thin-net must also run POST-scrub - the sentence
    # strips can remove every sentence, and shipping an empty string
    # is worse than the boilerplate it replaced.
    _core2 = re.sub(r"This data covers the \d{4}-\d{2} season\.?", "",
                    _scrubbed, flags=re.IGNORECASE)
    _words2 = re.findall(r"[A-Za-z]+", _core2)
    if len(_words2) < 5 and not re.search(r"\d", _core2):
        _scrubbed = _gap or ("I could not find that in the dataset. "
                             "It covers 2025-26 player and team stats, "
                             "game logs, standings, playoffs and the "
                             "Finals - try one of those.")
    # Watchdog: a turn that blew its wall-clock budget with no usable
    # evidence ends with coverage named - never a hang, never the old
    # "try a narrower ask" (F61/v70).
    if state.get("_watchdog_tripped") and not _evidenced and not _delegate_ok:
        _scrubbed = _gap or _COMPUTE_FALLBACK
    _scrubbed = _renumber_lists(_scrubbed)
    _verify_draft_numerals(state, _scrubbed)
    _new_facts = _extract_ledger_facts(state)
    if _new_facts:
        yield _event("ledger_facts", {"facts": _new_facts})
    _fa: dict[str, Any] = {"text": _scrubbed}
    if state.get("carry_note"):
        _fa["carry"] = state["carry_note"]
    yield _event("final_answer", _fa)
    try:
        llm = get_llm(state["primary"], state["model"])  # type: ignore[arg-type]
    except Exception:
        llm = None
    _q = state["question"]
    _trs = state["tool_results"]
    _cm = state["calls_made"]

    async def _suggest_bg() -> list[str]:
        if llm is None:
            return _suggest(_q, _trs, _cm)
        return await _suggest_llm(_q, _trs, _cm, llm)

    state["_suggest_task"] = _spawn(_suggest_bg(), name="suggestions")  # type: ignore[typeddict-unknown-key]
    yield _event("node_update", {"node": "presentation", "status": "complete"})


async def _finish_suggestions(state: DimeState) -> list[str]:
    """Await the background suggestions task spawned by presentation_agent.

    Runs after graph_end so the LLM call never delays the answer
    stream. Falls back to the hardcoded _suggest on timeout or error.
    """
    task = state.pop("_suggest_task", None)  # type: ignore[typeddict-unknown-key]
    items: Any = None
    if task is not None:
        try:
            items = await asyncio.wait_for(task, timeout=20)
        except Exception:
            items = None
    if not isinstance(items, list) or not items:
        items = _suggest(state["question"], state["tool_results"],
                         state["calls_made"])
    return [str(i) for i in items][:3]


async def run_chat(
    question: str,
    model_id: str | None,
    history: list[dict[str, str]] | None = None,
    thread: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    if thread:
        try:
            from . import store as _store

            _store.compact_thread(thread)
        except Exception:
            pass
    primary, model = resolve_model_id(model_id)
    question = _expand_nicknames(question or "")
    state = DimeState(
        question=question, primary=primary, model=model, round=0,
        tool_results=[], calls_made=[], history=history or [],
        analysis="", suggestions=[],
        desk_cache={}, entity_cache={},
    )
    if thread:
        try:
            from . import store as _store2

            state["ledger"] = _store2.thread_facts(thread)
        except Exception:
            pass
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
    _turn_t0 = time.time()
    _turn_budget = DEEP_TURN_BUDGET_S if deep else TURN_BUDGET_S
    _warned = False
    while state["round"] < max_rounds:
        _el = time.time() - _turn_t0
        if not _warned and _el > TURN_WARN_S:
            _warned = True
            yield _event("thought_stream", {
                "node": "data_retrieval",
                "text": "Still working on it - pulling the last of the "
                        "data together.",
            })
        if _el > _turn_budget:
            state["_watchdog_tripped"] = True  # type: ignore[typeddict-unknown-key]
            yield _event("thought_stream", {
                "node": "data_retrieval",
                "text": "That took too long - wrapping up with what I "
                        "have.",
            })
            break
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
    state["suggestions"] = await _finish_suggestions(state)
    yield _event("suggestions", {"items": state["suggestions"]})
