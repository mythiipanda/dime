from datetime import datetime
from typing import Any, Literal

from langchain_core.tools import tool

from .._core import clamp_scope, clamp_season, team_error_message
from ..prediction import (
    RATINGS_LIVE,
    RATINGS_STORED,
    RatingsSource,
    ratings_unavailable,
    season_team_ratings,
)
from ..rating_metrics import RANKING_DIRECTIONS, TEAM_RATING_METRICS
from ._helpers import _owned_connection, _pkg

_RequestedMetric = Literal.__getitem__(tuple(["", *TEAM_RATING_METRICS]))
_RankingDirection = Literal.__getitem__(tuple(["", *RANKING_DIRECTIONS]))

_RATINGS_KEEP = [
    "TEAM_ID", "TEAM_NAME", "GP", "W", "L",
    "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
    "TS_PCT", "TM_TOV_PCT",
    "OFF_RATING_RANK", "DEF_RATING_RANK", "NET_RATING_RANK",
    "TS_PCT_RANK", "TM_TOV_PCT_RANK",
]


def _rating_board_row(card: dict[str, Any], team_id: int,
                      teams_by_id: dict[int, dict[str, Any]]) -> dict[str, Any]:
    team = teams_by_id.get(team_id, {})
    return {
        "TEAM_ID": team_id,
        "TEAM_NAME": str(team.get("full_name") or ""),
        "TEAM": str(team.get("abbreviation") or ""),
        "GP": card["gp"], "W": card["w"], "L": card["l"],
        "OFF_RATING": round(card["off"], 1),
        "DEF_RATING": round(card["def"], 1),
        "NET_RATING": round(card["net"], 1),
        "PACE": round(card["pace"], 2),
    }


def _ratings_live_read(season: str, live_on_static_miss: bool):
    pkg = _pkg()
    return pkg._warehouse_or_live(
        "silver_team_ratings", "_season = ?",
        [season], lambda: pkg.nba_stats.team_ratings(season), season,
        limit=30, live_on_static_miss=live_on_static_miss,
    )


def _ratings_offline_rows(season: str, teams_by_id: dict):
    pkg = _pkg()
    con = pkg.store.connect(read_only=True)
    try:
        ratings, offline = season_team_ratings(con, season)
    finally:
        con.close()
    if offline is None:
        return [], None, {}
    rows = [_rating_board_row(card, tid, teams_by_id)
            for tid, card in ratings.items()]
    rows.sort(key=lambda row: row["NET_RATING"], reverse=True)
    official = offline.kind == RATINGS_STORED
    return rows, offline, {"source": offline.declared, "season": season,
                           "rows": len(rows),
                           "method": "official" if official else "derived",
                           "method_kind": "official" if official else "derived",
                           **pkg.store.warehouse_identity()}


def _ratings_stored_meta(meta: dict) -> None:
    meta.setdefault("method", "official")
    meta.setdefault("method_kind", "official")


def _ratings_leader_answer(leader: dict, metric: str, direction: str,
                           season: str) -> str:
    raw = float(leader[metric])
    label = TEAM_RATING_METRICS[metric]["label"]
    value = (f"{raw:.3f}"
             if TEAM_RATING_METRICS[metric]["format"] == "decimal3"
             else f"{raw:g}")
    return (f"{leader.get('TEAM_NAME') or leader.get('TEAM')} had the "
            f"{'lowest' if direction == 'asc' else 'highest'} "
            f"{label} in {season}: {value}.")


def _ratings_rank(slim: list[dict[str, Any]], metric: str, direction: str,
                  meta: dict) -> list[dict[str, Any]]:
    present = [r for r in slim if r.get(metric) is not None]
    present.sort(key=lambda r: float(r[metric]),
                 reverse=direction == "desc")
    meta.update({"requested_metric": metric,
                 "stat_category": metric,
                 "ranking_direction": direction,
                 "claim_value_field": metric,
                 "claim_entity_field": "TEAM_NAME"})
    return present


def _ratings_team_scope(slim: list[dict[str, Any]], team: str,
                        meta: dict) -> list[dict[str, Any]]:
    want = str(team).strip().lower()
    return [r for r in slim if (
        want == str(r.get("TEAM") or "").lower()
        or want in str(r.get("TEAM_NAME") or "").lower()
        or str(r.get("TEAM_NAME") or "").lower() in want)]


def _ratings_team_answer(row: dict, season: str) -> str:
    return (f"{row.get('TEAM_NAME') or row.get('TEAM')} ratings, {season}: "
            f"{row.get('OFF_RATING')} offense, {row.get('DEF_RATING')} "
            f"defense, {row.get('NET_RATING'):+g} net, and "
            f"{row.get('PACE')} pace. Record: {row.get('W')}-{row.get('L')}.")


def _ratings_available_seasons() -> list[str]:
    try:
        try:
            from shared.coverage import parse_season_start, table_seasons
        except ImportError:
            from v2.adapters.coverage import parse_season_start, table_seasons
        return sorted(
            found for found in table_seasons("silver_team_ratings")
            if parse_season_start(found) is not None)
    except Exception:
        return []


_METRIC_ALIASES = {
    "OFF": "OFF_RATING", "OFFENSE": "OFF_RATING", "OFFENSIVE": "OFF_RATING",
    "ORTG": "OFF_RATING", "DEF": "DEF_RATING", "DEFENSE": "DEF_RATING",
    "DEFENSIVE": "DEF_RATING", "DRTG": "DEF_RATING", "NET": "NET_RATING",
    "NRTG": "NET_RATING", "NETRTG": "NET_RATING", "NET_RATING": "NET_RATING",
    "PACE": "PACE", "TS": "TS_PCT", "TS%": "TS_PCT", "TS_PCT": "TS_PCT",
    "TRUE_SHOOTING": "TS_PCT", "TOV": "TM_TOV_PCT", "TOV_PCT": "TM_TOV_PCT",
    "TM_TOV": "TM_TOV_PCT", "OFF_RATING": "OFF_RATING",
    "DEF_RATING": "DEF_RATING",
}

_DIRECTION_ALIASES = {
    "desc": "desc", "descending": "desc", "high": "desc", "highest": "desc",
    "top": "desc", "best": "desc", "max": "desc",
    "asc": "asc", "ascending": "asc", "low": "asc", "lowest": "asc",
    "bottom": "asc", "worst": "asc", "min": "asc",
}


@tool(description='Team ratings, optionally bound to one requested ranked metric.\n\nWhen ``requested_metric`` and ``ranking_direction`` are set, rows are\nordered by that metric field and the payload owns the leader claim.\n``team`` narrows a direct team-ratings question.')
def get_ratings(
    season: str | None = None,
    team: str = "",
    requested_metric: str = "",
    ranking_direction: str = "",
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season, "silver_team_ratings")
    from nba_api.stats.static import teams as _teams

    teams_by_id = {int(t["id"]): t for t in _teams.get_teams()}
    abbrev = {tid: str(t.get("abbreviation") or "")
              for tid, t in teams_by_id.items()}
    rows, meta = _ratings_live_read(season, False)
    source: RatingsSource | None = None
    if rows:
        _ratings_stored_meta(meta)
        source = RatingsSource(RATINGS_STORED, "silver_team_ratings")
    else:
        rows, offline, offline_meta = _ratings_offline_rows(season, teams_by_id)
        if offline is not None:
            source = offline
            meta = offline_meta
    if source is None and pkg.season_static(season or ""):
        rows, meta = _ratings_live_read(season, True)
        if rows:
            source = RatingsSource(RATINGS_LIVE,
                                   str(meta.get("source") or "live"))
    meta["ratings_provenance"] = source.kind if source else ""
    meta["ratings_source"] = source.table if source else ""
    slim = []
    for r in rows:
        d = {k: r.get(k) for k in _RATINGS_KEEP if k in r}
        d["TEAM"] = abbrev.get(r.get("TEAM_ID"), str(r.get("TEAM_NAME") or ""))
        slim.append(d)
    metric = str(requested_metric or "").strip().upper()
    metric = _METRIC_ALIASES.get(metric, metric)
    direction = _DIRECTION_ALIASES.get(
        str(ranking_direction or "").strip().lower(),
        str(ranking_direction or "").strip().lower())
    if metric:
        if metric not in TEAM_RATING_METRICS:
            return {"tool": "get_ratings", "ok": False,
                    "error": (f"unsupported requested_metric: "
                              f"{requested_metric!r}; valid: "
                              f"{sorted(TEAM_RATING_METRICS)} (aliases like "
                              f"'net', 'off', 'def', 'ts', 'tov' accepted)")}
        if direction not in RANKING_DIRECTIONS:
            return {"tool": "get_ratings", "ok": False,
                    "error": "ranking_direction must be 'asc' or 'desc'"}
        slim = _ratings_rank(slim, metric, direction, meta)
        if slim:
            meta["deterministic_answer"] = _ratings_leader_answer(
                slim[0], metric, direction, season)
    if team:
        slim = _ratings_team_scope(slim, team, meta)
        meta["team"] = team
        if slim and not metric:
            meta["deterministic_answer"] = _ratings_team_answer(slim[0], season)
    if not slim and season:
        available = _ratings_available_seasons()
        if season not in available:
            ask = ratings_unavailable(season, available)
            return {"tool": "get_ratings", "ok": False, "rows": [],
                    "error": ask,
                    "meta": {**meta, "deterministic_answer": ask}}
    return {"tool": "get_ratings", "ok": True, "rows": slim, "meta": meta}


@tool(description='Qualified player on-court offensive or defensive rating leaderboard.\n\nThese are lineup results while the player was on court, not an individual\ndefensive-value metric. A hard 500-total-minute floor is ALWAYS enforced:\nthe caller cannot undercut it, so garbage-time players can never top the\nboard (a 0-minute floor once crowned a 53.3 on-court DEF_RATING from\n~15 total minutes as the "best defensive player").')
def get_player_ratings(
    season: str | None = None, metric: str = "offense", limit: int = 10,
    min_minutes: int = 1000,
) -> dict[str, Any]:
    pkg = _pkg()
    season = clamp_season(pkg.resolve_season(season))
    metric = "defense" if str(metric).casefold().startswith("def") else "offense"
    limit = max(1, min(int(limit), 50))
    min_minutes = max(500, min(int(min_minutes), 4000))
    column = "DEF_RATING" if metric == "defense" else "OFF_RATING"
    direction = "ASC" if metric == "defense" else "DESC"
    con = pkg.store.connect(read_only=True)
    try:
        raw = con.execute(
            f"SELECT PLAYER_NAME, TEAM_ABBREVIATION, GP, MIN, {column} "
            "FROM silver_advanced WHERE _season = ? AND MIN >= ? "
            f"ORDER BY {column} {direction}, MIN DESC LIMIT ?",
            [season, min_minutes, limit],
        ).fetchall()
    finally:
        con.close()
    rows = [
        {"RANK": rank, "PLAYER": row[0], "TEAM": row[1], "GP": row[2],
         "MPG": (row[3] / row[2]) if row[2] else 0, "MINUTES": round(row[3]), column: row[4]}
        for rank, row in enumerate(raw, 1)
    ]
    return {
        "tool": "get_player_ratings", "ok": True, "rows": rows,
        "meta": {
            "source": "warehouse:silver_advanced", "season": season,
            "metric": metric, "qualification": f"{min_minutes:,}+ total minutes",
            "coverage": (
                "On-court team rating while each player played. This does not "
                "isolate individual offensive or defensive value."
            ),
        },
    }


@tool(description='Team offensive, defensive, and net ratings from playoff game logs.')
def get_playoff_team_ratings(
    season: str | None = None, limit: int = 30,
) -> dict[str, Any]:
    pkg = _pkg()
    season = clamp_season(pkg.resolve_season(season))
    limit = max(1, min(int(limit), 30))
    con = pkg.store.connect(read_only=True)
    source_as_of = None
    try:
        raw = con.execute(
            """
            WITH games AS (
              SELECT TEAM_ID, TEAM_NAME, GAME_ID, PTS,
                     FGA + 0.44 * FTA - OREB + TOV AS poss
              FROM silver_playoffs WHERE _season = ?
            ), paired AS (
              SELECT a.TEAM_ID, a.TEAM_NAME, a.GAME_ID, a.PTS, a.poss,
                     b.PTS AS opp_pts, b.poss AS opp_poss
              FROM games a JOIN games b
                ON a.GAME_ID = b.GAME_ID AND a.TEAM_ID <> b.TEAM_ID
            )
            SELECT TEAM_NAME, count(*),
                   round(100 * sum(PTS) / nullif(sum(poss), 0), 1) AS off_rating,
                   round(100 * sum(opp_pts) / nullif(sum(opp_poss), 0), 1) AS def_rating,
                   round(100 * sum(PTS) / nullif(sum(poss), 0)
                       - 100 * sum(opp_pts) / nullif(sum(opp_poss), 0), 1) AS net_rating
            FROM paired GROUP BY TEAM_ID, TEAM_NAME
            ORDER BY net_rating DESC LIMIT ?
            """,
            [season, limit],
        ).fetchall()
        source_as_of = con.execute(
            "SELECT MAX(_fetched_at) FROM silver_playoffs WHERE _season = ?",
            [season],
        ).fetchone()[0]
    finally:
        con.close()
    rows = [
        {"RANK": rank, "TEAM_NAME": row[0], "GP": row[1],
         "OFF_RATING": row[2], "DEF_RATING": row[3], "NET_RATING": row[4]}
        for rank, row in enumerate(raw, 1)
    ]
    return {
        "tool": "get_playoff_team_ratings", "ok": True, "rows": rows,
        "meta": {
            "source": "warehouse:silver_playoffs", "season": season,
            "as_of": str(source_as_of) if source_as_of else None,
            "method": "NBA box-score estimated possessions",
            "method_kind": "estimate",
            "coverage": "Completed playoff games only.",
            "qualification": "All playoff teams; estimated possessions use the NBA box-score formula.",
        },
    }


_TEAM_FOUR_FACTORS_SQL = """
WITH games AS (
    SELECT Team_ID, Game_ID, _season,
           FGM, FG3M, FGA, FTA, TOV, OREB, DREB,
           MIN, PTS, WL,
           split_part(MATCHUP, ' ', 1) AS TEAM
    FROM silver_team_games
    WHERE _season = ?
),
paired AS (
    SELECT g.*, o.DREB AS OPP_DREB, o.FGM AS OPP_FGM,
           o.FG3M AS OPP_FG3M, o.FGA AS OPP_FGA, o.FTA AS OPP_FTA,
           o.TOV AS OPP_TOV, o.OREB AS OPP_OREB
    FROM games g
    JOIN games o ON o.Game_ID = g.Game_ID AND o.Team_ID <> g.Team_ID
)
SELECT TEAM, Team_ID, _season, COUNT(*) AS GP,
       SUM(CASE WHEN WL = 'W' THEN 1 ELSE 0 END) AS W,
       ROUND((SUM(FGM) + 0.5 * SUM(FG3M)) / NULLIF(SUM(FGA), 0), 4) AS EFG_PCT,
       ROUND(SUM(TOV) / NULLIF(SUM(FGA) + 0.44 * SUM(FTA) + SUM(TOV), 0), 4) AS TOV_PCT,
       ROUND(SUM(OREB) / NULLIF(SUM(OREB) + SUM(OPP_DREB), 0), 4) AS ORB_PCT,
       ROUND(SUM(FTA) / NULLIF(SUM(FGA), 0), 4) AS FT_RATE,
       ROUND((SUM(OPP_FGM) + 0.5 * SUM(OPP_FG3M)) / NULLIF(SUM(OPP_FGA), 0), 4) AS OPP_EFG_PCT,
       ROUND(SUM(OPP_TOV) / NULLIF(SUM(OPP_FGA) + 0.44 * SUM(OPP_FTA) + SUM(OPP_TOV), 0), 4) AS OPP_TOV_PCT,
       ROUND(SUM(DREB) / NULLIF(SUM(DREB) + SUM(OPP_OREB), 0), 4) AS DRB_PCT,
       ROUND(SUM(OPP_FTA) / NULLIF(SUM(OPP_FGA), 0), 4) AS OPP_FT_RATE
FROM paired
GROUP BY TEAM, Team_ID, _season
ORDER BY EFG_PCT DESC
"""

_TEAM_FOUR_FACTOR_COLS = (
    "TEAM", "GP", "W", "EFG_PCT", "TOV_PCT", "ORB_PCT", "FT_RATE",
    "OPP_EFG_PCT", "OPP_TOV_PCT", "DRB_PCT", "OPP_FT_RATE")


@tool(description='Team four factors (eFG%, TOV%, ORB%, FT rate, plus defensive\nmirrors), computed offline from warehouse team game rows. Use for\n"why are the Thunder good", "team identity", or any four-factors\nask. Pass a team name/abbrev to scope to one team; empty returns\nthe full 30-team board.')
def get_team_four_factors(team: str = "", season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        _con = pkg.store.connect()
        try:
            tables = {r[0] for r in _con.execute("SHOW TABLES").fetchall()}
        finally:
            _con.close()
    except Exception as exc:
        return {"tool": "get_team_four_factors", "ok": False,
                "rows": [], "meta": {},
                "error": f"warehouse read failed: {str(exc)[:120]}"}
    derived = "silver_four_factors_team" not in tables
    if derived and "silver_team_games" not in tables:
        return {"tool": "get_team_four_factors", "ok": False,
                "rows": [], "meta": {"season": season},
                "error": "warehouse table missing: "
                         "silver_four_factors_team and "
                         "silver_team_games"}
    team_q = (team or "").strip()
    team_abbr = ""
    if team_q:
        from nba_api.stats.static import teams as _static
        match = None
        for t in _static.get_teams():
            if team_q.lower() in (t["full_name"].lower(),
                                  t["abbreviation"].lower(),
                                  t["nickname"].lower()):
                match = t
                break
        if match is None:
            return {"tool": "get_team_four_factors", "ok": False,
                    "rows": [], "meta": {"season": season},
                    "error": team_error_message(team_q)}
        team_abbr = match["abbreviation"]
    requested_season = season
    season_fallback = None
    try:
        src_table = ("silver_team_games" if derived
                     else "silver_four_factors_team")
        probe = pkg.store.connect(read_only=True)
        try:
            has_rows = probe.execute(
                f"SELECT 1 FROM {src_table} WHERE _season = ? LIMIT 1",
                [season]).fetchone()
            if not has_rows:
                latest = probe.execute(
                    f"SELECT MAX(_season) FROM {src_table} "
                    "WHERE _season <= ?", [season]).fetchone()
                latest = str(latest[0] or "") if latest else ""
                if latest and latest != season:
                    season_fallback = latest
                    season = latest
        finally:
            probe.close()
    except Exception:
        season_fallback = None
    try:
        if derived:
            raw = pkg.store._read_df(_TEAM_FOUR_FACTORS_SQL, [season])
            rows = [{k: r.get(k) for k in _TEAM_FOUR_FACTOR_COLS}
                    for r in raw]
            if team_abbr:
                rows = [r for r in rows if r.get("TEAM") == team_abbr]
        else:
            where, params = "_season = ?", [season]
            if team_abbr:
                where += " AND TEAM = ?"
                params.append(team_abbr)
            rows = pkg.store._read_df(
                f"SELECT TEAM, GP, W, EFG_PCT, TOV_PCT, ORB_PCT, FT_RATE, "
                f"OPP_EFG_PCT, OPP_TOV_PCT, DRB_PCT, OPP_FT_RATE "
                f"FROM silver_four_factors_team WHERE {where} "
                f"ORDER BY EFG_PCT DESC", params)
    except Exception as exc:
        return {"tool": "get_team_four_factors", "ok": False,
                "rows": [], "meta": {"season": season},
                "error": f"warehouse read failed: {str(exc)[:120]}"}
    if not rows:
        return {"tool": "get_team_four_factors", "ok": False,
                "rows": [], "meta": {"season": season},
                "error": f"no four-factors rows for {season}"}
    meta = {"season": season,
            "source": "warehouse:silver_team_games" if derived else "warehouse",
            "derived_from": "silver_team_games" if derived else None,
            "rows": len(rows),
            "note": "computed offline from silver_team_games box "
                    "scores; eFG% = (FGM + 0.5*FG3M)/FGA, TOV% per "
                    "possession estimate, ORB% vs opponent DREB, "
                    "FTr = FTA/FGA. Quote figures verbatim.",
            **({"requested_season": requested_season,
                "season_fallback": season_fallback}
               if season_fallback else {})}
    if team_q and rows:
        r0 = rows[0]
        meta["leader_line"] = (
            f"{r0['TEAM']} four factors {season}: eFG% {r0['EFG_PCT']}, "
            f"TOV% {r0['TOV_PCT']}, ORB% {r0['ORB_PCT']}, "
            f"FT rate {r0['FT_RATE']} (defense: opp eFG% "
            f"{r0['OPP_EFG_PCT']}, DRB% {r0['DRB_PCT']})")
    return {"tool": "get_team_four_factors", "ok": True, "rows": rows,
            "meta": meta}


@tool(description='Hustle leaders, player or team scope. Contests, deflections, charges.')
def get_hustle(scope: str = "player", season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    scope = clamp_scope(scope)
    rows, meta = pkg._warehouse_or_live(
        f"silver_hustle_{scope}", "_season = ?",
        [season], lambda: pkg.nba_stats.hustle(scope, season), season,
    )
    return {"tool": "get_hustle", "ok": True, "rows": rows, "meta": meta}


@tool(description='RAPM-lite ratings. Blank player returns top list, else one row.')
def get_rapm(player: str = "", top: int = 10, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    con = pkg.store.connect()
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
    out = [{"player_id": r[0], "name": r[1],
            "rapm": round(float(r[2] or 0), 2), "possessions": r[3]}
           for r in rows]
    return {"tool": "get_rapm", "ok": True, "rows": out,
            "meta": {"source": "rapm-lite (estimate)", "season": season,
                     "qualification": "players under 500 possessions "
                                      "excluded; estimates shrink "
                                      "toward the prior"}}


_IMPACT_SOURCES = (
    ("silver_impact", "PLAYER_NAME", "BPM", "bpm", "MP"),
    ("silver_rapm", "name", "rapm", "rapm_lite", "possessions"),
    ("silver_rapm_prior", "name", "rapm", "rapm_lite", "possessions"),
    ("silver_raptor_player", "PLAYER_NAME", "RAPTOR_TOTAL", "raptor_total", "MP"),
)


@tool(description='Player impact and league rank for a season across all-in-one '
      'plus-minus metrics the warehouse covers: published BPM '
      '(basketball-reference advanced), rapm-lite estimates, and '
      'FiveThirtyEight RAPTOR for older seasons. One row per metric covering '
      'the season; rank is 1..N by value within that season\'s player pool. '
      'Player required; season optional. Warehouse only; each row cites its '
      'source.')
def get_impact_rank(player: str = "", season: str | None = None) -> dict[str, Any]:
    from ...contracts import normalize_name
    pkg = _pkg()
    season = pkg.resolve_season(season)
    target = normalize_name(player or "")
    if not target:
        return {"tool": "get_impact_rank", "ok": False,
                "error": "player needed"}
    rows: list[dict[str, Any]] = []
    coverage: set[str] = set()
    with _owned_connection(None, read_only=True) as con:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table, name_col, val_col, metric, qual_col in _IMPACT_SOURCES:
            if table not in tables:
                continue
            for (found_season,) in con.execute(
                    f"SELECT DISTINCT _season FROM {table}").fetchall():
                if found_season:
                    coverage.add(str(found_season))
            board = [(str(n), float(v), q) for n, v, q in con.execute(
                f"""SELECT {name_col}, {val_col}, {qual_col} FROM {table}
                WHERE _season = ? AND {val_col} IS NOT NULL""",
                [season]).fetchall() if n]
            if not board:
                continue
            sources = [str(s[0]) for s in con.execute(
                f"SELECT DISTINCT _source FROM {table} WHERE _season = ?",
                [season]).fetchall()]
            board.sort(key=lambda r: r[1], reverse=True)
            order = {n: i + 1 for i, (n, _, _) in enumerate(board)}
            norm_map = {normalize_name(n): n for n, _, _ in board}
            hit = norm_map.get(target)
            if hit is None:
                like = [n for n, _, _ in board
                        if target in normalize_name(n)]
                if like:
                    hit = min(like, key=lambda n: order[n])
            if hit is None:
                continue
            value, qualifier = next(
                (v, q) for n, v, q in board if n == hit)
            rows.append({
                "player": hit, "season": season, "metric": metric,
                "value": round(value, 2), "rank": order[hit],
                "players": len(board),
                "qualifier": int(qualifier) if qualifier is not None else None,
                "source": "; ".join(sources)})
    if not rows:
        if not coverage:
            return {"tool": "get_impact_rank", "ok": False,
                    "error": "no impact tables loaded"}
        if season not in coverage:
            return {"tool": "get_impact_rank", "ok": False,
                    "error": f"no impact data for {season}; "
                             f"coverage: {', '.join(sorted(coverage))}"}
        return {"tool": "get_impact_rank", "ok": False,
                "error": f"unknown player for {season}: {player}"}
    return {"tool": "get_impact_rank", "ok": True, "rows": rows,
            "meta": {"season": season, "player": rows[0]["player"],
                     "metrics": [r["metric"] for r in rows],
                     "coverage": sorted(coverage)}}


@tool(description='Back-to-back plus rest-day splits from history game dates.')
def get_rest(team_abbrev: str = "", season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    con = pkg.store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_rest", "ok": False, "error": "history empty"}
        q = """SELECT team_abbreviation, game_date, wl FROM silver_hist_gamelogs
               WHERE _season = ?"""
        cols = {r[1] for r in
                con.execute("PRAGMA table_info(silver_hist_gamelogs)").fetchall()}
        if "season_type" in cols:
            q += " AND season_type = 'regular-season'"
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
    buckets = {
        "zero_days": {"wins": 0, "losses": 0},
        "one_day": {"wins": 0, "losses": 0},
        "two_plus_days": {"wins": 0, "losses": 0},
    }
    prev = None
    for t, d, w in parsed:
        if prev and prev[0] == t:
            gap = (d - prev[1]).days
            bucket = ("zero_days" if gap <= 1 else
                      "one_day" if gap == 2 else "two_plus_days")
            outcome = "wins" if w == "W" else "losses"
            buckets[bucket][outcome] += 1
        prev = (t, d)
    for values in buckets.values():
        games = values["wins"] + values["losses"]
        values["games"] = games
        values["win_pct"] = (round(values["wins"] / games, 3)
                             if games else None)
    _rmeta: dict[str, Any] = {"source": "warehouse", "season": season}
    if pkg.season_static(season):
        _rmeta["offseason"] = True
        _rmeta["note"] = (f"{season} is complete; these are final "
                          "splits. No NBA games until preseason, so no "
                          "upcoming back-to-backs exist right now.")
    return {"tool": "get_rest", "ok": True,
            "rows": {
                "rest_buckets": buckets,
                "back_to_back": (f"{buckets['zero_days']['wins']}-"
                                 f"{buckets['zero_days']['losses']}"),
                "three_plus_rest": (f"{buckets['two_plus_days']['wins']}-"
                                    f"{buckets['two_plus_days']['losses']}"),
            },
            "meta": {**_rmeta, "qualification": (
                "Rest days before each game: zero, one, or two-plus; the first "
                "game for each team has no prior-game baseline and is excluded."),
                "coverage": f"{len(parsed)} dated team-games in the selected scope."}}


@tool(description='Risers and fallers: last-N win pct vs season win pct, warehouse only.')
def get_risers(season: str | None = None, weeks: int = 4) -> dict[str, Any]:
    pkg = _pkg()
    season = str(pkg.resolve_season(season) or "").strip() or pkg.resolve_season(None)
    try:
        weeks = max(1, min(int(weeks or 4), 8))
    except (TypeError, ValueError):
        weeks = 4
    n = max(5, min(round(weeks * 2.5), 15))
    con = pkg.store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_risers", "ok": False, "error": "history empty"}
        cols = {r[1] for r in
                con.execute("PRAGMA table_info(silver_hist_gamelogs)").fetchall()}
        q = """SELECT team_abbreviation, game_date, wl FROM silver_hist_gamelogs
               WHERE _season = ?"""
        if "season_type" in cols:
            q += " AND season_type = 'regular-season'"
        rows = con.execute(q + " ORDER BY team_abbreviation, game_date",
                           [season]).fetchall()
    finally:
        con.close()
    if not rows:
        return {"tool": "get_risers", "ok": False,
                "error": f"no games for {season}"}
    offseason = pkg.season_static(season)
    by_team: dict[str, list] = {}
    for t, _, w in rows:
        if t:
            by_team.setdefault(t, []).append(w)
    table = []
    for t, ws in by_team.items():
        w_all = sum(1 for w in ws if w == "W")
        last = ws[-n:]
        w_last = sum(1 for w in last if w == "W")
        sp = w_all / len(ws)
        lp = w_last / len(last)
        table.append({"TEAM": t, "LAST10": f"{w_last}-{len(last) - w_last}",
                      "LAST10_PCT": round(lp, 3), "SEASON_PCT": round(sp, 3),
                      "DELTA": round(lp - sp, 3)})
    table.sort(key=lambda d: d["DELTA"], reverse=True)
    meta = {"source": "warehouse", "season": season,
            "window": n, "weeks": weeks}
    if offseason:
        meta["offseason"] = True
        meta["note"] = (f"{season} is complete; these are end-of-season "
                        f"form windows, not current risers. No NBA games "
                        f"until preseason.")
    return {"tool": "get_risers", "ok": True,
            "rows": {"risers": table[:5], "fallers": table[-5:][::-1]},
            "meta": meta}


@tool(description="Player risers and fallers: last-N games scoring/efficiency vs the\nplayer's own season average, warehouse only. Use this for\nplayer-level 'who is rising/falling/hot' asks; get_risers is the\nTEAM version (win-rate windows).")
def get_player_risers(season: str | None = None, n: int = 10) -> dict[str, Any]:
    pkg = _pkg()
    season = str(pkg.resolve_season(season) or "").strip() or pkg.resolve_season(None)
    try:
        n = max(5, min(int(n or 10), 15))
    except (TypeError, ValueError):
        n = 10
    con = pkg.store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_player_gamelogs" not in tables:
            return {"tool": "get_player_risers", "ok": False,
                    "error": "player gamelogs empty"}
        rows = con.execute(
            """SELECT g._entity, g.GAME_DATE, g.PTS, g.FG_PCT, g.FG3_PCT
               FROM silver_player_gamelogs g
               WHERE g._season = ?
               ORDER BY g._entity,
                        strptime(g.GAME_DATE, '%b %d, %Y')""",
            [season]).fetchall()
        names = {}
        try:
            for pid, pname in con.execute(
                    "SELECT PLAYER_ID, PLAYER FROM silver_player_season "
                    "WHERE _season = ?", [season]).fetchall():
                names[f"player:{pid}"] = pname
        except Exception:
            pass
        teams = {}
        try:
            for pid, team in con.execute(
                    "SELECT PLAYER_ID, TEAM FROM silver_player_season "
                    "WHERE _season = ?", [season]).fetchall():
                teams[f"player:{pid}"] = team
        except Exception:
            pass
    finally:
        con.close()
    if not rows:
        return {"tool": "get_player_risers", "ok": False,
                "error": f"no player games for {season}"}
    by_player: dict[str, list] = {}
    for ent, _d, pts, fg, fg3 in rows:
        if pts is None:
            continue
        by_player.setdefault(ent, []).append((pts, fg, fg3))
    table = []
    for ent, games in by_player.items():
        if len(games) < 25:
            continue
        season_pts = sum(g[0] for g in games) / len(games)
        last = games[-n:]
        last_pts = sum(g[0] for g in last) / len(last)
        fg_season = [g[1] for g in games if g[1] is not None]
        fg_last = [g[1] for g in last if g[1] is not None]
        table.append({
            "PLAYER": names.get(ent, ent.replace("player:", "id ")),
            "TEAM": teams.get(ent, ""),
            "GP": len(games),
            "SEASON_PPG": round(season_pts, 1),
            f"LAST{n}_PPG": round(last_pts, 1),
            "PPG_DELTA": round(last_pts - season_pts, 1),
            "SEASON_FG_PCT": round(sum(fg_season) / len(fg_season), 3)
                if fg_season else None,
            f"LAST{n}_FG_PCT": round(sum(fg_last) / len(fg_last), 3)
                if fg_last else None,
        })
    table.sort(key=lambda d: d["PPG_DELTA"], reverse=True)
    meta = {"source": "warehouse", "season": season, "window": n,
            "definition": "last-N scoring vs own season average, min 25 GP"}
    if pkg.season_static(season):
        meta["offseason"] = True
        meta["note"] = (f"{season} is complete; these are end-of-season "
                        f"form windows, not current risers. No NBA games "
                        f"until preseason.")
    return {"tool": "get_player_risers", "ok": True,
            "rows": {"risers": table[:8], "fallers": table[-8:][::-1]},
            "meta": meta}
