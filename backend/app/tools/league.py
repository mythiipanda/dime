"""League desk. Standings, leaders, hustle, ratings, history, draft."""

from typing import Any
from langchain_core.tools import tool

from ..sources import nba_stats
from ._core import SEASON, clamp_stat, _warehouse_or_live


@tool
def get_injuries(team: str = "", season: str = SEASON) -> dict[str, Any]:
    """Injury report, optional team abbreviation filter."""
    from ..sources import espn

    rows, meta = _warehouse_or_live(
        "silver_injuries", "_season = ?",
        [season], lambda: espn.injuries(season), season,
    )
    if team:
        from nba_api.stats.static import teams as _teams

        want = team.strip().upper()
        full = next(
            (t["full_name"] for t in _teams.get_teams()
             if t["abbreviation"] == want or t["full_name"].upper() == want),
            want,
        )
        rows = [r for r in rows if full.lower() in str(r.get("display_name", "")).lower()]
    return {"tool": "get_injuries", "ok": True, "rows": rows, "meta": meta}


@tool
def get_standings(season: str = SEASON) -> dict[str, Any]:
    """League standings for one season like 2025-26."""
    rows, meta = _warehouse_or_live(
        "silver_standings", "_season = ?",
        [season], lambda: nba_stats.standings(season), season,
        limit=30,
    )
    return {"tool": "get_standings", "ok": True, "rows": rows, "meta": meta}


@tool
def get_playoffs(season: str = SEASON) -> dict[str, Any]:
    """Playoff wins per team plus champion for one season."""
    rows, meta = _warehouse_or_live(
        "silver_playoffs", "_season = ?",
        [season], lambda: nba_stats.playoff_results(season), season,
        limit=600,
    )
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    games = 0
    for r in rows:
        team = str(r.get("TEAM_ABBREVIATION") or "")
        if not team:
            continue
        games += 1
        if r.get("WL") == "W":
            wins[team] = wins.get(team, 0) + 1
        else:
            losses[team] = losses.get(team, 0) + 1
    table = sorted(
        ((t, w) for t, w in wins.items()), key=lambda x: x[1], reverse=True)
    champ = table[0][0] if table and table[0][1] >= 12 else ""
    return {"tool": "get_playoffs", "ok": True,
            "rows": {"champion": champ,
                     "champion_record":
                         {"w": wins.get(champ, 0), "l": losses.get(champ, 0)}
                         if champ else {},
                     "wins": [{"team": t, "w": w, "l": losses.get(t, 0)}
                              for t, w in table[:16]],
                     "games_total": games // 2},
            "meta": meta}


@tool
def get_leaders(stat_category: str = "PTS", season: str = SEASON) -> dict[str, Any]:
    """League leaders for one stat category like PTS, REB, AST."""
    stat_category = clamp_stat(stat_category)
    table = f"silver_leaders_{stat_category.lower()}"
    rows, meta = _warehouse_or_live(
        table, "_season = ?",
        [season], lambda: nba_stats.leaders(stat_category, season), season,
    )
    meta["stat_category"] = stat_category
    try:
        from .. import store as _store

        total = len(_store.read_frame(table, "_season = ?", [season]))
        for r in rows:
            rank = r.get("RANK") or 0
            if rank and total:
                r["PERCENTILE"] = round(100 * (1 - (rank - 1) / total), 1)
    except Exception:
        pass
    return {"tool": "get_leaders", "ok": True, "rows": rows, "meta": meta}


@tool
def get_hustle(scope: str = "player", season: str = SEASON) -> dict[str, Any]:
    """Hustle leaders, player or team scope. Contests, deflections, charges."""
    from ._core import clamp_scope

    scope = clamp_scope(scope)
    rows, meta = _warehouse_or_live(
        f"silver_hustle_{scope}", "_season = ?",
        [season], lambda: nba_stats.hustle(scope, season), season,
    )
    return {"tool": "get_hustle", "ok": True, "rows": rows, "meta": meta}


@tool
def get_rapm(player: str = "", top: int = 10, season: str = SEASON) -> dict[str, Any]:
    """RAPM-lite ratings. Blank player returns top list, else one row."""
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_rapm" not in tables:
            return {"tool": "get_rapm", "ok": False, "error": "rapm empty"}
        if player:
            rows = con.execute(
                """SELECT player_id, name, rapm, possessions FROM silver_rapm
                WHERE _season = ? AND LOWER(name) LIKE ?""",
                [season, f"%{player.lower()}%"],
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT player_id, name, rapm, possessions FROM silver_rapm
                WHERE _season = ? ORDER BY rapm DESC LIMIT ?""",
                [season, max(top, 1)],
            ).fetchall()
    finally:
        con.close()
    out = [{"player_id": r[0], "name": r[1], "rapm": r[2], "possessions": r[3]}
           for r in rows]
    return {"tool": "get_rapm", "ok": True, "rows": out,
            "meta": {"source": "rapm-lite", "season": season}}


@tool
def get_finder(
    mode: str = "streak", team_abbrev: str = "", opponent: str = "",
    season: str = SEASON, window: int = 5,
) -> dict[str, Any]:
    """Team finder across history seasons. Modes: streak, versus, span."""
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_finder", "ok": False, "error": "history empty"}
        q = """SELECT team_abbreviation, game_date, matchup, wl, pts
               FROM silver_hist_gamelogs WHERE _season = ?"""
        params: list[object] = [season]
        if team_abbrev:
            q += " AND team_abbreviation = ?"
            params.append(team_abbrev.upper())
        rows = con.execute(q + " ORDER BY game_date", params).fetchall()
    finally:
        con.close()
    if not rows:
        return {"tool": "get_finder", "ok": False, "error": "no games found"}
    if mode == "versus" and opponent:
        opp = opponent.upper()
        rel = [r for r in rows if opp in (r[2] or "")]
        w = sum(1 for r in rel if r[3] == "W")
        return {"tool": "get_finder", "ok": True,
                "rows": {"record": f"{w}-{len(rel) - w}", "games": len(rel)},
                "meta": {"source": "warehouse", "season": season}}
    if mode == "span":
        best = None
        for i in range(len(rows) - window + 1):
            chunk = rows[i:i + window]
            if len({c[0] for c in chunk}) > 1:
                continue
            total = sum(c[4] or 0 for c in chunk)
            if best is None or total > best[0]:
                best = (total, chunk[0][0], chunk[0][1], chunk[-1][1])
        if best is None:
            return {"tool": "get_finder", "ok": False, "error": "no span found"}
        return {"tool": "get_finder", "ok": True,
                "rows": {"team": best[1], "window": window, "points": best[0],
                         "from": best[2], "to": best[3]},
                "meta": {"source": "warehouse", "season": season}}
    best_w = best_l = cur_w = cur_l = 0
    for r in rows:
        if r[3] == "W":
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        best_w = max(best_w, cur_w)
        best_l = max(best_l, cur_l)
    return {"tool": "get_finder", "ok": True,
            "rows": {"longest_win_streak": best_w, "longest_loss_streak": best_l,
                     "games": len(rows)},
            "meta": {"source": "warehouse", "season": season}}


@tool
def get_rest(team_abbrev: str = "", season: str = SEASON) -> dict[str, Any]:
    """Back-to-back plus rest-day splits from history game dates."""
    from datetime import datetime

    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_rest", "ok": False, "error": "history empty"}
        q = """SELECT team_abbreviation, game_date, wl FROM silver_hist_gamelogs
               WHERE _season = ?"""
        params: list[object] = [season]
        if team_abbrev:
            q += " AND team_abbreviation = ?"
            params.append(team_abbrev.upper())
        rows = con.execute(q + " ORDER BY team_abbreviation, game_date",
                           params).fetchall()
    finally:
        con.close()
    try:
        parsed = [(t, datetime.strptime(d, "%Y-%m-%d").date(), w)
                  for t, d, w in rows if d]
    except (TypeError, ValueError):
        return {"tool": "get_rest", "ok": False, "error": "bad dates"}
    b2b_w = b2b_l = rest_w = rest_l = 0
    prev = None
    for t, d, w in parsed:
        if prev and prev[0] == t:
            gap = (d - prev[1]).days
            if gap <= 1:
                b2b_w += w == "W"
                b2b_l += w != "W"
            elif gap >= 3:
                rest_w += w == "W"
                rest_l += w != "W"
        prev = (t, d)
    return {"tool": "get_rest", "ok": True,
            "rows": {"back_to_back": f"{b2b_w}-{b2b_l}",
                     "three_plus_rest": f"{rest_w}-{rest_l}"},
            "meta": {"source": "warehouse", "season": season}}


@tool
def get_win_prob(team_a: str = "", team_b: str = "", season: str = SEASON) -> dict[str, Any]:
    """Elo-lite win probability between two abbreviations. Neutral court."""
    import math

    from .. import store as _store

    def rating(abbrev: str) -> float:
        con = _store.connect()
        try:
            rows = con.execute(
                """SELECT wl, pts FROM silver_hist_gamelogs
                WHERE _season = ? AND team_abbreviation = ?""",
                [season, abbrev.upper()],
            ).fetchall()
        finally:
            con.close()
        if not rows:
            return 1500.0
        w = sum(1 for result, _ in rows if result == "W")
        r = 1500 + (w / len(rows) - 0.5) * 200
        return r

    if not team_a or not team_b:
        return {"tool": "get_win_prob", "ok": False, "error": "two abbreviations needed"}
    ra, rb = rating(team_a), rating(team_b)
    pa = 1 / (1 + 10 ** ((rb - ra) / 400))
    return {"tool": "get_win_prob", "ok": True,
            "rows": {team_a.upper(): round(pa, 3), team_b.upper(): round(1 - pa, 3)},
            "meta": {"source": "warehouse", "season": season}}


CAP = {"cap": 165_000_000, "tax": 201_048_000,
       "apron1": 209_661_000, "apron2": 222_372_000}


def _payroll(team: str) -> tuple[int, list[dict]]:
    from .. import store as _store

    con = _store.connect()
    try:
        rows = con.execute(
            """SELECT player, salary FROM silver_cap_players
            WHERE team = ?""",
            [team.upper()],
        ).fetchall()
    finally:
        con.close()
    players = [{"player": r[0], "salary": r[1]} for r in rows]
    return sum(r[1] or 0 for r in rows), players


@tool
def get_cap_ledger(team: str = "") -> dict[str, Any]:
    """Payroll plus apron room for one abbreviation. 2026-27 thresholds."""
    if not team:
        return {"tool": "get_cap_ledger", "ok": False, "error": "abbreviation needed"}
    total, players = _payroll(team)
    return {"tool": "get_cap_ledger", "ok": True,
            "rows": {"team": team.upper(), "payroll": total,
                     "players": sorted(players, key=lambda p: p["salary"] or 0,
                                       reverse=True)[:15],
                     "room_under_apron2": CAP["apron2"] - total,
                     "over_tax": total > CAP["tax"]},
            "meta": {"source": "orojas119/nba-salary-cap", "season": "2026-27",
                     **{k: v for k, v in CAP.items()}}}


@tool
def get_trade_check(
    team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "",
) -> dict[str, Any]:
    """Trade legality check. Player names comma separated per side.

    Simplified 2023 CBA: 125 percent plus 250k matching for non-apron
    teams, 100 percent for second-apron teams, no aggregation above
    the second apron. Picks and exceptions stay out of v1.
    """
    import math as _math

    def salaries(team: str, names: str) -> tuple[int, list[str]]:
        total, roster = _payroll(team)
        want = [n.strip().lower() for n in names.split(",") if n.strip()]
        matched = []
        total_out = 0
        for w in want:
            hit = next((p for p in roster if w in p["player"].lower()), None)
            if hit:
                matched.append(hit["player"])
                total_out += hit["salary"] or 0
        return total_out, matched

    if not team_a or not team_b:
        return {"tool": "get_trade_check", "ok": False,
                "error": "two teams needed"}
    out_a, names_a = salaries(team_a, players_a)
    out_b, names_b = salaries(team_b, players_b)
    pay_a, _ = _payroll(team_a)
    pay_b, _ = _payroll(team_b)
    over2 = lambda p: p > CAP["apron2"]
    issues = []
    if over2(pay_a) and len(names_a) > 1:
        issues.append(f"{team_a.upper()} cannot aggregate above second apron")
    if over2(pay_b) and len(names_b) > 1:
        issues.append(f"{team_b.upper()} cannot aggregate above second apron")
    ok_a = out_b <= (out_a if over2(pay_a) else out_a * 1.25 + 250_000)
    ok_b = out_a <= (out_b if over2(pay_b) else out_b * 1.25 + 250_000)
    if not ok_a:
        issues.append(f"{team_a.upper()} takes back too much")
    if not ok_b:
        issues.append(f"{team_b.upper()} takes back too much")
    return {"tool": "get_trade_check", "ok": True,
            "rows": {"team_a": {"team": team_a.upper(), "out": out_a,
                                "players": names_a, "payroll": pay_a},
                     "team_b": {"team": team_b.upper(), "out": out_b,
                                "players": names_b, "payroll": pay_b},
                     "legal": not issues, "issues": issues},
            "meta": {"source": "orojas119/nba-salary-cap", "rules": "v1-simplified"}}


@tool
def get_combine(season: str = "2025") -> dict[str, Any]:
    """Draft combine measurements plus shooting drills for one draft year."""
    res = nba_stats.combine(season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_combine", "ok": False,
                "error": res.error or "empty upstream response"}
    return {"tool": "get_combine", "ok": True,
            "rows": res.frame.head(25).to_dicts(),
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": res.frame.height, "cached": False}}


@tool
def get_briefing(game_date: str = "", season: str = SEASON) -> dict[str, Any]:
    """Morning briefing: scoreboard plus top scorers. Date MM/DD/YYYY, blank means latest."""
    from datetime import datetime, timedelta

    day = game_date.strip()
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")
    games, gmeta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{day}"],
        lambda: nba_stats.scoreboard(day, season), season,
        entity=f"date:{day}", live_first=True,
    )
    leaders, _ = _warehouse_or_live(
        "silver_leaders_pts", "_season = ?",
        [season], lambda: nba_stats.leaders("PTS", season), season,
    )
    top = [
        {"PLAYER": r.get("PLAYER"), "TEAM": r.get("TEAM"), "PTS": r.get("PTS")}
        for r in leaders[:5]
    ]
    return {"tool": "get_briefing", "ok": True,
            "rows": {"date": day, "games": games, "top_scorers": top},
            "meta": gmeta}


@tool
async def text_to_sql(question: str) -> dict[str, Any]:
    """Answer a data question with SQL over warehouse tables. SELECT only."""
    import re as _re

    from langchain_core.messages import HumanMessage, SystemMessage

    from .. import store as _store
    from ..providers import invoke_with_fallback

    allowed = ["silver_standings", "silver_playoffs", "silver_player_gamelogs", "silver_team_games",
               "silver_leaders_pts", "silver_leaders_reb", "silver_leaders_ast",
               "silver_leaders_stl", "silver_leaders_blk", "silver_boxscores",
               "silver_lineups", "silver_shots", "silver_hustle_player",
               "silver_hustle_team", "silver_injuries", "silver_hist_gamelogs",
               "silver_hist_standings", "silver_hist_possessions",
               "silver_hist_shots", "silver_hist_lineups"]
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        present = [t for t in allowed if t in tables]
        cols: dict[str, list[str]] = {}
        for t in present:
            cols[t] = [r[1] for r in
                       con.execute(f"PRAGMA table_info({t})").fetchall()][:20]
    finally:
        con.close()
    if not present:
        return {"tool": "text_to_sql", "ok": False, "error": "warehouse empty"}
    schema = "\n".join(f"{t}: {', '.join(c)}" for t, c in cols.items())
    examples = (
        "\nExamples.\nQ: Thunder record this season?\n"
        "SQL: SELECT WINS, LOSSES FROM silver_standings "
        "WHERE TeamCity = 'Oklahoma City' AND _season = '2025-26'\n"
        "Q: OKC wins per season, last 3 seasons?\n"
        "SQL: SELECT _season, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins "
        "FROM silver_hist_gamelogs WHERE team_abbreviation = 'OKC' "
        "AND _season IN ('2025-26', '2024-25', '2023-24') GROUP BY _season"
    )
    feedback = ""
    for _ in range(3):
        try:
            resp = await invoke_with_fallback(
                "mistral", "ministral-8b-2512",
                [SystemMessage(content="Reply with SQL only, no prose."),
                 HumanMessage(
                     content="Write one SQLite SELECT using only these tables "
                     "and columns. Match column case exactly as listed.\n"
                     f"Schema:\n{schema}{examples}\nQuestion: {question}{feedback}")])
            sql = _re.sub(r"^```sql|```$", "", str(getattr(resp, "content", "") or ""),
                          flags=_re.MULTILINE).strip()
        except Exception as exc:
            return {"tool": "text_to_sql", "ok": False, "error": str(exc)[:160]}
        if not _re.match(r"(?i)^\s*select\b", sql) or _re.search(
                r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy)\b", sql):
            feedback = "\nPrevious reply was not a single SELECT. Reply with SQL only."
            continue
        used = set(_re.findall(r"(?i)from\s+(\w+)|join\s+(\w+)", sql))
        used_tables = {a or b for a, b in used}
        if not used_tables or not used_tables.issubset(set(present)):
            feedback = "\nPrevious reply used unknown tables. Use only listed tables."
            continue
        con = _store.connect()
        try:
            rows = con.execute(sql).fetchall()
            names = [d[0] for d in con.description]
        except Exception as exc:
            feedback = f"\nPrevious SQL failed: {str(exc)[:200]} Fix it."
            continue
        finally:
            con.close()
        if not rows:
            feedback = (
                "\nPrevious SQL ran but returned 0 rows. "
                "A literal value is probably wrong. Query again with "
                "different literals or look at the table first "
                "(SELECT DISTINCT col FROM table LIMIT 20)."
            )
            continue
        return {"tool": "text_to_sql", "ok": True,
                "rows": [dict(zip(names, r)) for r in rows[:25]],
                "meta": {"sql": sql[:500], "source": "warehouse"}}
    return {"tool": "text_to_sql", "ok": False,
            "error": "sql failed after retries" + feedback[-160:]}
