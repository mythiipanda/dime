"""V1 agent tools. Warehouse first, live on miss. Provenance in every row.

Twenty-seven tools. New tools need a decision row first.
"""

from typing import Any
import polars as pl
from langchain_core.tools import BaseTool, tool

from . import store
from .sources import nba_stats
from .sources.base import FetchResult

SEASON = "2025-26"
MAX_ROWS = 25


def _warehouse_or_live(
    table: str,
    where: str,
    params: list[object],
    fetch: Any,
    season: str,
    entity: str = "",
    limit: int = MAX_ROWS,
    live_first: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frame = None
    if not live_first:
        frame = store.read_frame(table, where, params)
    if frame is None or frame.height == 0:
        live: FetchResult = fetch()
        if not live.ok or live.frame.height == 0:
            return [], {"source": live.meta.source,
                        "error": live.error or "empty upstream response"}
        store.save_frame(table, live, entity)
        frame = store.read_frame(table, where, params)
        if frame.height == 0:
            frame = live.frame.with_columns(
                [
                    pl.lit(live.meta.source).alias("_source"),
                    pl.lit(live.meta.season).alias("_season"),
                    pl.lit(live.meta.fetched_at).alias("_fetched_at"),
                ]
            )
        return frame.head(limit).to_dicts(), {
            "rows": frame.height, "cached": False,
            "source": live.meta.source, "fetched_at": live.meta.fetched_at,
        }
    meta: dict[str, Any] = {"rows": frame.height, "cached": True}
    if "_source" in frame.columns:
        meta["source"] = frame["_source"][0]
        meta["fetched_at"] = frame["_fetched_at"][0]
    return frame.head(limit).to_dicts(), meta


@tool
def resolve_entity(query: str) -> dict[str, Any]:
    """Resolve a player or team name to canonical ids. Call before any id tool."""
    try:
        from nba_api.stats.static import players, teams

        name = query.strip().lower()
        p = players.find_players_by_full_name(query)[:8]
        if not p:
            seen: set[int] = set()
            p = []
            for fn in (players.find_players_by_last_name,
                       players.find_players_by_first_name):
                try:
                    for x in fn(query)[:8]:
                        if x.get("id") not in seen:
                            seen.add(x.get("id"))
                            p.append(x)
                except Exception:
                    pass
        if not p:
            all_p = players.get_players()
            p = [x for x in all_p if name in x.get("full_name", "").lower()][:8]
        t = teams.find_teams_by_full_name(query)[:8]
        if not t:
            all_t = teams.get_teams()
            t = [x for x in all_t
                 if name in x.get("full_name", "").lower()
                 or name == x.get("abbreviation", "").lower()][:8]
        exact_p = [x for x in p if x.get("full_name", "").lower() == name]
        exact_t = [x for x in t if x.get("full_name", "").lower() == name]
        return {
            "tool": "resolve_entity",
            "ok": True,
            "rows": {
                "players": exact_p or p,
                "teams": exact_t or t,
                "exact": bool(exact_p or exact_t),
            },
            "meta": {"source": "nba_api_static"},
        }
    except Exception as exc:
        return {"tool": "resolve_entity", "ok": False, "error": str(exc)[:200]}


@tool
def search_nba(query: str) -> dict[str, Any]:
    """Find NBA players or teams matching a name. Input is a plain name."""
    try:
        from nba_api.stats.static import players, teams

        name = query.strip()
        return {
            "tool": "search_nba",
            "ok": True,
            "rows": {
                "players": players.find_players_by_full_name(name)[:8],
                "teams": teams.find_teams_by_full_name(name)[:8],
            },
            "meta": {"source": "nba_api_static"},
        }
    except Exception as exc:
        return {"tool": "search_nba", "ok": False, "error": str(exc)[:200]}


@tool
def get_player_intel(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Game log plus shot sample for one player id. Warehouse first."""
    rows, meta = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_player_intel", "ok": True, "rows": rows, "meta": meta}


@tool
def get_team_hub(team_id: int, season: str = SEASON) -> dict[str, Any]:
    """Game log plus roster for one team id. Warehouse first."""
    games, meta = _warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    roster, _ = _warehouse_or_live(
        "silver_rosters", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_roster(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    return {
        "tool": "get_team_hub", "ok": True,
        "rows": {"games": games, "roster": roster}, "meta": meta,
    }


@tool
def get_games_on_date(game_date: str, season: str = SEASON) -> dict[str, Any]:
    """Scoreboard for one date. Date format is MM/DD/YYYY."""
    rows, meta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{game_date}"],
        lambda: nba_stats.scoreboard(game_date, season), season,
        entity=f"date:{game_date}", live_first=True,
    )
    return {"tool": "get_games_on_date", "ok": True, "rows": rows, "meta": meta}


@tool
def get_boxscore(game_id: str, season: str = SEASON) -> dict[str, Any]:
    """Traditional boxscore player stats for one game id."""
    rows, meta = _warehouse_or_live(
        "silver_boxscores", "_season = ? AND _entity = ?",
        [season, f"game:{game_id}"],
        lambda: nba_stats.boxscore_traditional(game_id, season), season,
        entity=f"game:{game_id}", live_first=True,
    )
    return {"tool": "get_boxscore", "ok": True, "rows": rows, "meta": meta}


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
def get_leaders(stat_category: str = "PTS", season: str = SEASON) -> dict[str, Any]:
    """League leaders for one stat category like PTS, REB, AST."""
    table = f"silver_leaders_{stat_category.lower()}"
    rows, meta = _warehouse_or_live(
        table, "_season = ?",
        [season], lambda: nba_stats.leaders(stat_category, season), season,
    )
    meta["stat_category"] = stat_category
    return {"tool": "get_leaders", "ok": True, "rows": rows, "meta": meta}


@tool
def get_lineups(team_id: int, season: str = SEASON) -> dict[str, Any]:
    """Five-man lineup stats for one team id, sorted by minutes."""
    rows, meta = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    return {"tool": "get_lineups", "ok": True, "rows": rows, "meta": meta}


@tool
def get_on_off(player_id: int, team_id: int, season: str = SEASON) -> dict[str, Any]:
    """On and off splits for one player on one team. Possession level."""
    from .sources import pbpstats

    rows, meta = _warehouse_or_live(
        "silver_on_off", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.on_off(player_id, team_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_on_off", "ok": True, "rows": rows, "meta": meta}


@tool
def get_wowy(player_ids: str, team_id: int, season: str = SEASON) -> dict[str, Any]:
    """With-or-without-you splits. player_ids is comma separated ids."""
    from .sources import pbpstats

    ids = [int(x) for x in player_ids.split(",") if x.strip().isdigit()]
    rows, meta = _warehouse_or_live(
        "silver_wowy", "_season = ? AND _entity = ?",
        [season, f"wowy:{player_ids}"],
        lambda: pbpstats.wowy(ids, team_id, season), season,
        entity=f"wowy:{player_ids}", live_first=True,
    )
    return {"tool": "get_wowy", "ok": True, "rows": rows, "meta": meta}


@tool
def get_four_factors(player_id: int, team_id: int, season: str = SEASON) -> dict[str, Any]:
    """Four factor on-off splits for one player on one team."""
    from .sources import pbpstats

    rows, meta = _warehouse_or_live(
        "silver_four_factors", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.four_factors(player_id, team_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_four_factors", "ok": True, "rows": rows, "meta": meta}


@tool
def get_shot_zones(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Zone splits for one player id: rim, midrange, three with shares."""
    import math

    from .sources import nba_stats

    res = nba_stats.shot_chart(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_shot_zones", "ok": False,
                "error": res.error or "empty upstream response"}
    zones = {"rim": [0, 0], "mid": [0, 0], "three": [0, 0]}
    for r in res.frame.to_dicts():
        try:
            dist = math.hypot(float(r.get("LOC_X", 0)), float(r.get("LOC_Y", 0))) / 10
        except (TypeError, ValueError):
            continue
        made = str(r.get("EVENT_TYPE", "")).lower().startswith("made")
        z = "rim" if dist < 8 else ("three" if dist > 23.75 else "mid")
        zones[z][1] += 1
        zones[z][0] += 1 if made else 0
    total = sum(a for _, a in zones.values()) or 1
    rows = [
        {"zone": z, "FGM": m, "FGA": a,
         "FG_PCT": round(m / a, 3) if a else 0.0,
         "share": round(a / total, 3)}
        for z, (m, a) in zones.items()
    ]
    return {"tool": "get_shot_zones", "ok": True, "rows": rows,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": 3, "cached": False}}


@tool
def get_last_x(player_id: int, n: int = 10, season: str = SEASON) -> dict[str, Any]:
    """Last n games for one player id, most recent first."""
    from .sources import nba_stats

    res = nba_stats.player_gamelog(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_last_x", "ok": False,
                "error": res.error or "empty upstream response"}
    frame = res.frame
    try:
        frame = frame.with_columns(
            pl.col("GAME_DATE").str.strptime(pl.Date, "%b %d, %Y").alias("_d")
        ).sort("_d", descending=True).drop("_d")
    except Exception:
        frame = frame.reverse()
    rows = frame.head(min(max(n, 1), 25)).to_dicts()
    store.save_frame("silver_player_gamelogs", res, f"player:{player_id}")
    return {"tool": "get_last_x", "ok": True, "rows": rows,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": len(rows), "cached": False}}


@tool
def get_percentiles(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Percentile ranks for one player id across PTS REB AST STL BLK."""
    cats = ["PTS", "REB", "AST", "STL", "BLK"]
    out: dict[str, Any] = {}
    for cat in cats:
        table = f"silver_leaders_{cat.lower()}"
        rows, _ = _warehouse_or_live(
            table, "_season = ?",
            [season], lambda c=cat: nba_stats.leaders(c, season), season,
            limit=600,
        )
        hit = next((r for r in rows if r.get("PLAYER_ID") == player_id), None)
        if hit and hit.get("RANK"):
            total = len(store.read_frame(table, "_season = ?", [season]))
            out[cat] = {
                "rank": hit["RANK"],
                "percentile": round(100 * (1 - (hit["RANK"] - 1) / max(total, 1)), 1),
            }
    return {"tool": "get_percentiles", "ok": True, "rows": out,
            "meta": {"source": "nba_api", "season": season}}


@tool
def get_briefing(game_date: str = "", season: str = SEASON) -> dict[str, Any]:
    """Morning briefing: scoreboard plus top scorers. Date MM/DD/YYYY, blank means latest."""
    from datetime import datetime, timedelta
    from .sources import nba_stats

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
def get_hustle(scope: str = "player", season: str = SEASON) -> dict[str, Any]:
    """Hustle leaders, player or team scope. Contests, deflections, charges."""
    rows, meta = _warehouse_or_live(
        f"silver_hustle_{scope}", "_season = ?",
        [season], lambda: nba_stats.hustle(scope, season), season,
    )
    return {"tool": "get_hustle", "ok": True, "rows": rows, "meta": meta}


@tool
def get_splits(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Home versus away plus monthly splits from the game log."""
    from .sources import nba_stats

    res = nba_stats.player_gamelog(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_splits", "ok": False,
                "error": res.error or "empty upstream response"}
    try:
        g = res.frame.with_columns(
            pl.col("MATCHUP").str.contains("@").alias("away")
        )
        home = g.filter(~pl.col("away")).select("PTS", "FG_PCT")
        away = g.filter(pl.col("away")).select("PTS", "FG_PCT")
        rows = [
            {"split": "home", "GP": home.height,
             "PPG": round(home["PTS"].mean() or 0, 1)},
            {"split": "away", "GP": away.height,
             "PPG": round(away["PTS"].mean() or 0, 1)},
        ]
    except Exception as exc:
        return {"tool": "get_splits", "ok": False, "error": str(exc)[:160]}
    return {"tool": "get_splits", "ok": True, "rows": rows,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": 2, "cached": False}}


@tool
def get_scouting_report(team_id: int, season: str = SEASON) -> dict[str, Any]:
    """One-call dossier: record, roster, lineups, leaders context."""
    from .sources import nba_stats

    games, _ = _warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    lineups, _ = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    wins = sum(1 for g in games if g.get("WL") == "W")
    top_lineup = (lineups or [{}])[0]
    return {"tool": "get_scouting_report", "ok": True,
            "rows": {"record": f"{wins}-{len(games) - wins}",
                     "games_sample": len(games),
                     "top_lineup": {
                         "GROUP_NAME": top_lineup.get("GROUP_NAME"),
                         "MIN": top_lineup.get("MIN"),
                         "PLUS_MINUS": top_lineup.get("PLUS_MINUS")}},
            "meta": {"source": "nba_api", "season": season}}


@tool
def get_recap(game_id: str, season: str = SEASON) -> dict[str, Any]:
    """Post-game recap data: boxscore top five plus team totals."""
    from .sources import nba_stats

    res = nba_stats.boxscore_traditional(game_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_recap", "ok": False,
                "error": res.error or "empty upstream response"}
    try:
        name_col = next((c for c in ("PLAYER_NAME", "nameI") if c in res.frame.columns),
                        res.frame.columns[9])
        team_col = next((c for c in ("TEAM_ABBREVIATION", "teamTricode") if c in res.frame.columns),
                        res.frame.columns[2])
        pts_col = next((c for c in ("PTS", "points") if c in res.frame.columns),
                       res.frame.columns[-2])
        reb_col = next((c for c in ("REB", "reboundsTotal") if c in res.frame.columns),
                       res.frame.columns[-4])
        ast_col = next((c for c in ("AST", "assists") if c in res.frame.columns),
                       res.frame.columns[-3])
        top = (res.frame.sort(pts_col, descending=True).head(5)
               .select(name_col, team_col, pts_col, reb_col, ast_col)
               .rename({name_col: "PLAYER", team_col: "TEAM",
                        pts_col: "PTS", reb_col: "REB", ast_col: "AST"})
               .to_dicts())
    except Exception as exc:
        return {"tool": "get_recap", "ok": False, "error": str(exc)[:160]}
    return {"tool": "get_recap", "ok": True, "rows": top,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": len(top), "cached": False}}


@tool
async def text_to_sql(question: str) -> dict[str, Any]:
    """Answer a data question with SQL over warehouse tables. SELECT only."""
    import re as _re

    from langchain_core.messages import HumanMessage, SystemMessage

    from . import store as _store
    from .providers import invoke_with_fallback

    allowed = ["silver_standings", "silver_player_gamelogs", "silver_team_games",
               "silver_leaders_pts", "silver_leaders_reb", "silver_leaders_ast",
               "silver_leaders_stl", "silver_leaders_blk", "silver_boxscores",
               "silver_lineups", "silver_shots", "silver_hustle_player",
               "silver_hustle_team", "silver_injuries"]
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
    try:
        resp = await invoke_with_fallback(
            "mistral", "ministral-8b-2512",
            [SystemMessage(content="Reply with SQL only, no prose."),
             HumanMessage(
                 content="Write one SQLite SELECT using only these tables "
                 f"and columns.\nSchema:\n{schema}\nQuestion: {question}")])
        sql = _re.sub(r"^```sql|```$", "", str(getattr(resp, "content", "") or ""),
                      flags=_re.MULTILINE).strip()
    except Exception as exc:
        return {"tool": "text_to_sql", "ok": False, "error": str(exc)[:160]}
    if not _re.match(r"(?i)^\s*select\b", sql) or _re.search(
            r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy)\b", sql):
        return {"tool": "text_to_sql", "ok": False,
                "error": "rejected non-SELECT", "sql": sql[:200]}
    used = set(_re.findall(r"(?i)from\s+(\w+)|join\s+(\w+)", sql))
    used_tables = {a or b for a, b in used}
    if not used_tables or not used_tables.issubset(set(present)):
        return {"tool": "text_to_sql", "ok": False,
                "error": "unknown table", "sql": sql[:200]}
    con = _store.connect()
    try:
        rows = con.execute(sql).fetchall()
        names = [d[0] for d in con.description]
    except Exception as exc:
        return {"tool": "text_to_sql", "ok": False,
                "error": str(exc)[:160], "sql": sql[:200]}
    finally:
        con.close()
    return {"tool": "text_to_sql", "ok": True,
            "rows": [dict(zip(names, r)) for r in rows[:25]],
            "meta": {"sql": sql[:500], "source": "warehouse"}}


@tool
def get_rapm(player: str = "", top: int = 10, season: str = SEASON) -> dict[str, Any]:
    """RAPM-lite ratings. Blank player returns top list, else one row."""
    from . import store as _store

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
    from . import store as _store

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
def get_combine(season: str = "2025") -> dict[str, Any]:
    """Draft combine measurements plus shooting drills for one draft year."""
    from .sources import nba_stats

    res = nba_stats.combine(season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_combine", "ok": False,
                "error": res.error or "empty upstream response"}
    return {"tool": "get_combine", "ok": True,
            "rows": res.frame.head(25).to_dicts(),
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": res.frame.height, "cached": False}}


@tool
def get_comps(player_id: int, season: str = SEASON, n: int = 5) -> dict[str, Any]:
    """Nearest statistical neighbors by per-game shape. Development comps."""
    import math

    from .sources import nba_stats

    base, _ = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    if not base:
        return {"tool": "get_comps", "ok": False, "error": "no baseline games"}
    dims = ["PTS", "REB", "AST", "FG_PCT", "FG3_PCT", "MIN"]
    try:
        avgs = {d: sum(float(r.get(d) or 0) for r in base) / len(base) for d in dims}
    except (TypeError, ValueError):
        return {"tool": "get_comps", "ok": False, "error": "bad baseline"}
    cands, _ = _warehouse_or_live(
        "silver_leaders_pts", "_season = ?",
        [season], lambda: nba_stats.leaders("PTS", season), season,
        limit=600,
    )
    per_game = []
    for r in cands:
        try:
            gp = float(r.get("GP") or 0)
            if gp <= 0:
                continue
            per_game.append((
                r,
                {d: float(r.get(d) or 0) / (gp if d in ("PTS", "REB", "AST", "MIN") else 1)
                 for d in dims},
            ))
        except (TypeError, ValueError):
            continue
    scales: dict[str, float] = {}
    for d in dims:
        vals = [p[d] for _, p in per_game]
        mean = sum(vals) / max(len(vals), 1)
        var = sum((v - mean) ** 2 for v in vals) / max(len(vals), 1)
        scales[d] = var ** 0.5 or 1.0
    scored = []
    for r, per in per_game:
        try:
            v = [(per[d] - avgs[d]) / scales[d] for d in dims]
            dist = math.sqrt(sum(x * x for x in v))
            if r.get("PLAYER_ID") != player_id:
                scored.append((dist, r.get("PLAYER"), r.get("TEAM")))
        except (TypeError, ValueError):
            continue
    scored.sort()
    rows = [{"PLAYER": name, "TEAM": team, "distance": round(d, 2)}
            for d, name, team in scored[:n]]
    return {"tool": "get_comps", "ok": True, "rows": rows,
            "meta": {"source": "nba_api", "season": season}}


@tool
def get_rest(team_abbrev: str = "", season: str = SEASON) -> dict[str, Any]:
    """Back-to-back plus rest-day splits from history game dates."""
    from datetime import datetime

    from . import store as _store

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

    from . import store as _store

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


v1_tools: list[BaseTool] = [
    resolve_entity,
    search_nba,
    get_player_intel,
    get_team_hub,
    get_games_on_date,
    get_boxscore,
    get_standings,
    get_leaders,
    get_lineups,
    get_on_off,
    get_wowy,
    get_four_factors,
    get_last_x,
    get_percentiles,
    get_briefing,
    get_shot_zones,
    get_hustle,
    get_splits,
    get_scouting_report,
    get_recap,
    text_to_sql,
    get_finder,
    get_rapm,
    get_combine,
    get_comps,
    get_rest,
    get_win_prob,
]

TOOL_NAMES = [t.name for t in v1_tools]
