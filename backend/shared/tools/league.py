
import ast
import json
import re
import duckdb
from contextlib import contextmanager
from typing import Any, Literal
from langchain_core.tools import tool

from .. import store
from ..sources import nba_stats
from ._core import IN_SEASON_MONTHS as _IN_SEASON_MONTHS, TTL_LEADERS, TTL_SCOREBOARD_PAST, clamp_stat, _warehouse_or_live, is_past_game_date, is_scope_game, last_completed_season, resolve_season, season_static
from .leader_metrics import COUNTING_METRICS, per_game_column, per_game_value
from .rating_metrics import RANKING_DIRECTIONS, TEAM_RATING_METRICS

_RequestedMetric = Literal.__getitem__(tuple(["", *TEAM_RATING_METRICS]))
_RankingDirection = Literal.__getitem__(tuple(["", *RANKING_DIRECTIONS]))

def _injury_entries(raw: object) -> list:
    if not isinstance(raw, str):
        return []
    try:
        raw = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        try:
            raw = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            raw = []
    return raw if isinstance(raw, list) else []

def _injury_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        row = dict(row)
        if isinstance(row.get("injuries"), str):
            row["injuries"] = _injury_entries(row["injuries"])
        normalized.append(row)
    return normalized

def _injury_playoff_note(player: str, season: str | None) -> str | None:
    try:
        from ._core import coerce_player_id
        from .gamelog import playoff_inactive_note as _pin
        from .splits import _resolve_name as _rn

        pid = coerce_player_id(player)
        return _pin(pid, season, _rn(pid, str(player)))
    except Exception:
        return None

def _injury_player_rows(rows: list[dict[str, Any]],
                        player: str) -> list[dict[str, Any]]:
    low = str(player).strip().lower()
    return [
        r for r in rows
        if low in str(r.get("player") or r.get("name") or "").lower()
        or any(
            low in str((item.get("athlete") or {}).get("displayName", "")).lower()
            for item in (r.get("injuries") or [])
            if isinstance(item, dict)
        )
    ]

def _injury_team_rows(rows: list[dict[str, Any]],
                      team: str) -> list[dict[str, Any]]:
    from nba_api.stats.static import teams as _teams

    want = team.strip().upper()
    full = next(
        (t["full_name"] for t in _teams.get_teams()
         if t["abbreviation"] == want or t["full_name"].upper() == want),
        want,
    )
    return [r for r in rows
            if full.lower() in str(r.get("display_name", "")).lower()]

@tool(description="Injury report, optional team abbreviation or player filter.\n\nWith a player name, also joins playoff inactive listings so\n'is X injured?' surfaces 'inactive for the entire playoff run'\ninstead of a bare 'active' (F45).")
def get_injuries(team: str = "", player: str = "",
                 season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    from ..sources import espn

    rows, meta = _warehouse_or_live(
        "silver_injuries", "_season = ?",
        [season], lambda: espn.injuries(season), season,
    )
    rows = _injury_rows(rows)

    note = _injury_playoff_note(player, season) if player else None
    if player:
        rows = _injury_player_rows(rows, player)
    if team:
        rows = _injury_team_rows(rows, team)
    meta = dict(meta)
    if not rows and not player:

        meta["empty_meaning"] = "no listed rows at source vintage; availability unknown"
        meta["warning"] = (
            "empty team or league injury report does not establish universal availability"
        )
    out = {"tool": "get_injuries", "ok": True, "rows": rows, "meta": meta}
    if player and not rows:
        out["player_note"] = (
            f"{player} is NOT on the current injury report. Report that "
            "directly; an empty list for a named player is an answer, "
            "never 'no data'.")
    if note:
        out.setdefault("rows")
        out["inactive_note"] = note
    return out

_STANDINGS_HIST_MAP = {
    "team_id": "TeamID", "team_city": "TeamCity",
    "team_name": "TeamName", "conference": "Conference",
    "wins": "WINS", "losses": "LOSSES", "win_pct": "WinPCT",
    "record": "Record", "playoff_rank": "PlayoffRank",
    "league_rank": "LeagueRank", "l10": "L10", "home": "HOME",
    "road": "ROAD", "points_pg": "PointsPG",
    "opp_points_pg": "OppPointsPG", "diff_points_pg": "DiffPointsPG",
    "str_current_streak": "strCurrentStreak",
    "three_pts_or_less": "ThreePTSOrLess",
    "ahead_at_half": "AheadAtHalf", "behind_at_half": "BehindAtHalf",
    "oct": "Oct", "nov": "Nov", "dec": "Dec", "jan": "Jan",
    "feb": "Feb", "mar": "Mar", "apr": "Apr",
}

def _hist_standings_rows(season: str) -> list[dict[str, Any]]:
    season = resolve_season(season)
    try:
        from .. import store as _store
    except Exception:
        from shared import store as _store
    frame = _store.read_frame(
        "silver_hist_standings", "_season = ?", [season])
    if frame.height == 0:
        return []
    out: list[dict[str, Any]] = []
    for h in frame.to_dicts():
        row = {dst: h.get(src) for src, dst in _STANDINGS_HIST_MAP.items()
               if h.get(src) is not None}
        if row:
            out.append(row)
    out.sort(key=lambda r: -(r.get("WINS") or 0))
    return out

_STANDINGS_KEEP = ("TeamID", "team", "abbrev", "Conference", "WINS",
                   "LOSSES", "WinPCT", "Record", "PlayoffRank",
                   "LeagueRank", "L10", "HOME", "ROAD", "PointsPG",
                   "OppPointsPG", "DiffPointsPG", "CurrentStreak")

def _slim_standings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from nba_api.stats.static import teams as _static

    abbr_by_id = {t.get("id"): str(t.get("abbreviation") or "")
                  for t in _static.get_teams()}
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        tid = r.get("TeamID")
        full = f"{r.get('TeamCity') or ''} {r.get('TeamName') or ''}".strip()
        slim = {k: r.get(k) for k in _STANDINGS_KEEP
                if k in r and k not in ("team", "abbrev")}
        slim["team"] = full
        slim["abbrev"] = abbr_by_id.get(tid, "")
        out.append(slim)
    return out

@tool(description='League standings for one season like 2025-26.')
def get_standings(season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    rows, meta = _warehouse_or_live(
        "silver_standings", "_season = ?",
        [season], lambda: nba_stats.standings(season), season,
        limit=30,
    )
    if not rows:

        hist = _hist_standings_rows(str(season))
        if hist:
            return {"tool": "get_standings", "ok": True,
                    "rows": _slim_standings(hist),
                    "meta": {"source": "warehouse", "season": str(season),
                             "coverage": "historical_standings"}}
        return {"tool": "get_standings", "ok": False,
                "error": (f"No standings on file for {season}; standings "
                          f"cover 2009-10 through the current season.")}
    return {"tool": "get_standings", "ok": True,
            "rows": _slim_standings(rows), "meta": meta}

_STANDINGS_DEEP_COLUMNS = (
    'TeamCity, TeamName, WinPCT, '
    '"ThreePTSOrLess", "AheadAtHalf", "BehindAtHalf", '
    '"L10", "strCurrentStreak", '
    '"Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"')

_STANDINGS_DEEP_HIST_COLUMNS = (
    "team_city, team_name, win_pct, "
    "three_pts_or_less, ahead_at_half, behind_at_half, "
    "l10, str_current_streak, "
    "oct, nov, dec, jan, feb, mar, apr")

_MONTH_NAMES = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]

def _standings_split(rec: object) -> tuple[int, int] | None:
    try:
        w, loss = str(rec or "").strip().split("-")
        return int(w), int(loss)
    except (TypeError, ValueError):
        return None

def _standings_pct(w: int, loss: int) -> float:
    return round(w / (w + loss), 3) if w + loss else 0.0

def _standings_deep_query(con, season: str) -> list[tuple]:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_standings" in tables:
        rows = con.execute(
            f"SELECT {_STANDINGS_DEEP_COLUMNS} "
            "FROM silver_standings WHERE _season = ?", [season]).fetchall()
        if rows:
            return rows
    if "silver_hist_standings" in tables:
        return con.execute(
            f"SELECT {_STANDINGS_DEEP_HIST_COLUMNS} "
            "FROM silver_hist_standings WHERE _season = ?", [season]).fetchall()
    return []

def _standings_deep_teams(rows: list[tuple]) -> list[dict[str, Any]]:
    teams = []
    for city, name, winpct, clutch, ahead, behind, l10, streak, *months in rows:
        teams.append({
            "TEAM": f"{city or ''} {name or ''}".strip(),
            "SEASON_PCT": round(float(winpct or 0), 3),
            "clutch": _standings_split(clutch),
            "ahead": _standings_split(ahead),
            "behind": _standings_split(behind),
            "L10": l10,
            "STREAK": streak,
            "months": months,
        })
    return teams

def _halftime_board(teams: list[dict[str, Any]], key: str,
                    top: int, by_loss: bool) -> list[dict[str, Any]]:
    board = sorted(
        ({"TEAM": t["TEAM"], "W": t[key][0], "L": t[key][1],
          "PCT": _standings_pct(*t[key])}
         for t in teams if t[key]),
        key=lambda d: d["L"] if by_loss else (d["W"], d["PCT"]),
        reverse=True,
    )
    return board[:top]

def _standings_deep_months(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_month = []
    for i, month in enumerate(_MONTH_NAMES):
        entries = []
        for t in teams:
            parsed = _standings_split(t["months"][i])
            if parsed and parsed[0] + parsed[1] >= 3:
                entries.append((t["TEAM"], parsed[0], parsed[1],
                                _standings_pct(*parsed)))
        if not entries:
            continue
        best = max(entries, key=lambda e: (e[3], e[1]))
        worst = min(entries, key=lambda e: (e[3], -e[1]))
        by_month.append({"MONTH": month,
                         "BEST_TEAM": best[0],
                         "BEST_RECORD": f"{best[1]}-{best[2]}",
                         "BEST_PCT": best[3],
                         "WORST_TEAM": worst[0],
                         "WORST_RECORD": f"{worst[1]}-{worst[2]}",
                         "WORST_PCT": worst[3]})
    return by_month

def _standings_deep_momentum(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    momentum = []
    for t in teams:
        mar = _standings_split(t["months"][5])
        apr = _standings_split(t["months"][6])
        lw = (mar[0] if mar else 0) + (apr[0] if apr else 0)
        ll = (mar[1] if mar else 0) + (apr[1] if apr else 0)
        if lw + ll < 5:
            continue
        late = _standings_pct(lw, ll)
        momentum.append({"TEAM": t["TEAM"], "LATE": f"{lw}-{ll}",
                         "LATE_PCT": late, "SEASON_PCT": t["SEASON_PCT"],
                         "DELTA": round(late - t["SEASON_PCT"], 3),
                         "L10": t["L10"], "STREAK": t["STREAK"]})
    momentum.sort(key=lambda d: d["DELTA"], reverse=True)
    return momentum

def _standings_deep_comeback_leader(comeback: list[dict[str, Any]]) -> str:
    if not comeback:
        return ""
    return (f"{comeback[0]['TEAM']} lead with "
            f"{comeback[0]['W']} wins when trailing at halftime")

@tool(description='Standings deep cuts: clutch records, comeback kings, blown leads, monthly momentum.')
def get_standings_deep(season: str | None = None, top: int = 5) -> dict[str, Any]:
    from .. import store as _store

    season = str(resolve_season(season) or "").strip() or resolve_season(None)
    try:
        top = max(1, min(int(top or 5), 15))
    except (TypeError, ValueError):
        top = 5

    con = _store.connect()
    try:
        if "silver_standings" not in {
                r[0] for r in con.execute("SHOW TABLES").fetchall()}:
            return {"tool": "get_standings_deep", "ok": False,
                    "error": "standings empty"}
        rows = _standings_deep_query(con, season)
    finally:
        con.close()
    if not rows:
        return {"tool": "get_standings_deep", "ok": False,
                "error": f"no standings for {season}"}
    teams = _standings_deep_teams(rows)
    clutch_rank = sorted(
        ({"TEAM": t["TEAM"], "W": t["clutch"][0], "L": t["clutch"][1],
          "PCT": _standings_pct(*t["clutch"]),
          "RECORD": f"{t['clutch'][0]}-{t['clutch'][1]}"}
         for t in teams if t["clutch"]),
        key=lambda d: (d["PCT"], d["W"]), reverse=True,
    )
    comeback = _halftime_board(teams, "behind", top, False)
    blown = _halftime_board(teams, "ahead", top, True)
    momentum = _standings_deep_momentum(teams)
    return {"tool": "get_standings_deep", "ok": True,
            "rows": {"clutch": clutch_rank[:top],
                     "clutch_cold": clutch_rank[-top:][::-1],
                     "comeback_kings": comeback,
                     "blown_leads": blown,
                     "monthly": {"by_month": _standings_deep_months(teams),
                                 "surging": momentum[:top],
                                 "fading": momentum[-top:][::-1]}},
            "meta": {"source": "warehouse", "season": season, "top": top,
                     "teams": len(teams),

                     "comeback_leader": _standings_deep_comeback_leader(
                         comeback),
                     "note": "comeback_kings and blown_leads use "
                             "behind/ahead-at-halftime records as the "
                             "proxy. Play-by-play in-game margin data "
                             "(deficits, runs, quarter splits) is not "
                             "in the dataset - say that, never claim "
                             "game logs are missing."}}

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

_RATINGS_KEEP = ["TEAM_ID", "TEAM_NAME", "GP", "W", "L",
                 "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
                 "TS_PCT", "TM_TOV_PCT",
                 "OFF_RATING_RANK", "DEF_RATING_RANK", "NET_RATING_RANK",
                 "TS_PCT_RANK", "TM_TOV_PCT_RANK"]

def _ratings_live_read(season: str, live_on_static_miss: bool):
    return _warehouse_or_live(
        "silver_team_ratings", "_season = ?",
        [season], lambda: nba_stats.team_ratings(season), season,
        limit=30, live_on_static_miss=live_on_static_miss,
    )

def _ratings_offline_rows(season: str, teams_by_id: dict):
    from .prediction import RATINGS_STORED, season_team_ratings

    con = store.connect(read_only=True)
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
                           **store.warehouse_identity()}

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
        from v2.adapters.coverage import parse_season_start
        from v2.adapters.coverage import table_seasons
        return sorted(
            found for found in table_seasons("silver_team_ratings")
            if parse_season_start(found) is not None)
    except Exception:
        return []

@tool(description='Team ratings, optionally bound to one requested ranked metric.\n\nWhen ``requested_metric`` and ``ranking_direction`` are set, rows are\nordered by that metric field and the payload owns the leader claim.\n``team`` narrows a direct team-ratings question.')
def get_ratings(
    season: str | None = None,
    team: str = "",
    requested_metric: _RequestedMetric = "",
    ranking_direction: _RankingDirection = "",
) -> dict[str, Any]:
    season = resolve_season(season, "silver_team_ratings")
    from nba_api.stats.static import teams as _teams

    from .prediction import (
        RATINGS_LIVE,
        RATINGS_STORED,
        RatingsSource,
        ratings_unavailable,
    )

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
    if source is None and season_static(season or ""):
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
    direction = str(ranking_direction or "").strip().lower()
    if metric:
        if metric not in TEAM_RATING_METRICS:
            return {"tool": "get_ratings", "ok": False,
                    "error": f"unsupported requested_metric: {metric}"}
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
    season = resolve_season(season)
    from ._core import clamp_season

    season = clamp_season(season)
    metric = "defense" if str(metric).casefold().startswith("def") else "offense"
    limit = max(1, min(int(limit), 50))

    min_minutes = max(500, min(int(min_minutes), 4000))
    column = "DEF_RATING" if metric == "defense" else "OFF_RATING"
    direction = "ASC" if metric == "defense" else "DESC"
    con = store.connect(read_only=True)
    try:
        raw = con.execute(
            f"SELECT PLAYER_NAME, TEAM_ABBREVIATION, GP, MIN, {column} "
            "FROM silver_advanced WHERE _season = ? AND GP * MIN >= ? "
            f"ORDER BY {column} {direction}, GP * MIN DESC LIMIT ?",
            [season, min_minutes, limit],
        ).fetchall()
    finally:
        con.close()
    rows = [
        {"RANK": rank, "PLAYER": row[0], "TEAM": row[1], "GP": row[2],
         "MPG": row[3], "MINUTES": round(row[2] * row[3]), column: row[4]}
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
    season = resolve_season(season)
    from ._core import clamp_season

    season = clamp_season(season)
    limit = max(1, min(int(limit), 30))
    con = store.connect(read_only=True)
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

_CLUTCH_PBP_FIRST = 2021
_CLUTCH_PBP_LAST = 2025
_CLUTCH_SECONDS_DEFAULT = 300
_CLUTCH_MARGIN_DEFAULT = 5
_CLUTCH_SEASON_TYPE_DEFAULT = "regular"
_CLUTCH_PBP_ALIAS = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}

def _clutch_end_year(season: object) -> int | None:
    try:
        text = str(season or "").strip()
    except Exception:
        return None
    if len(text) == 7 and text[4] == "-":
        try:
            return 2000 + int(text[5:])
        except (TypeError, ValueError):
            return None
    return None

def _clutch_seconds_of(value: object) -> tuple[int, str | None]:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return _CLUTCH_SECONDS_DEFAULT, (
            f"clutch_seconds '{value}' invalid, using "
            f"{_CLUTCH_SECONDS_DEFAULT}")
    if seconds < 30 or seconds > 720:
        clamped = max(30, min(720, seconds))
        return clamped, f"clutch_seconds {seconds} clamped to {clamped}"
    return seconds, None

def _clutch_margin_of(value: object) -> tuple[int, str | None]:
    try:
        margin = int(value)
    except (TypeError, ValueError):
        return _CLUTCH_MARGIN_DEFAULT, (
            f"clutch_margin '{value}' invalid, using "
            f"{_CLUTCH_MARGIN_DEFAULT}")
    if margin < 1 or margin > 30:
        clamped = max(1, min(30, margin))
        return clamped, f"clutch_margin {margin} clamped to {clamped}"
    return margin, None

def _clutch_season_type_of(value: object) -> tuple[str, str | None]:
    text = str(value or "").strip().lower()
    if text in ("regular", "reg", "002"):
        return "regular", None
    if text in ("playoffs", "playoff", "post", "004"):
        return "playoffs", None
    if text in ("both", "all"):
        return "both", None
    if text == _CLUTCH_SEASON_TYPE_DEFAULT:
        return _CLUTCH_SEASON_TYPE_DEFAULT, None
    return _CLUTCH_SEASON_TYPE_DEFAULT, (
        f"season_type '{value}' invalid, using "
        f"{_CLUTCH_SEASON_TYPE_DEFAULT}")

def _clutch_prefixes(season_type: str) -> set[str]:
    if season_type == "playoffs":
        return {"004"}
    if season_type == "both":
        return {"002", "004"}
    return {"002"}

def _clutch_clock_left(clock: object) -> float | None:
    try:
        text = str(clock)
    except Exception:
        return None
    if not text.startswith("PT") or not text.endswith("S"):
        return None
    try:
        mark = text.index("M")
        return int(text[2:mark]) * 60.0 + float(text[mark + 1:-1])
    except (ValueError, AttributeError):
        return None

def _clutch_pbp_rows(season: str, prefixes: set[str]) -> list[tuple]:
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_pbp" not in tables:
            return []
        ph = ",".join("?" * len(prefixes))
        return con.execute(
            "SELECT game_id, action_number, clock, period, team_tricode,"
            " person_id, player_name, location, score_home, score_away,"
            " action_type, sub_type, description, shot_value, shot_result"
            " FROM silver_hist_pbp WHERE _season = ? AND period >= 4"
            f" AND substr(game_id, 1, 3) IN ({ph})"
            " ORDER BY game_id, action_number",
            [season, *sorted(prefixes)],
        ).fetchall()
    finally:
        con.close()

def _clutch_home_of(rows: list[tuple]) -> dict[str, str]:
    from collections import Counter as _Counter
    votes: dict[str, _Counter] = {}
    for r in rows:
        if (r[7] or "") == "h" and r[4]:
            votes.setdefault(str(r[0]), _Counter())[str(r[4])] += 1
    return {gid: tally.most_common(1)[0][0] for gid, tally in votes.items()
            if tally}

def _clutch_int(raw: object) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(str(raw))
    except (TypeError, ValueError):
        return None

def _clutch_fold(rows: list[tuple], home_of: dict[str, str],
                 seconds: int, margin: int) -> tuple[dict, dict, dict, int]:
    events: dict[str, list[tuple]] = {}
    finals: dict[str, tuple[int, int]] = {}
    scored = 0
    for r in rows:
        gid = str(r[0])
        home = home_of.get(gid)
        if home is None:
            continue
        lead = finals.get(gid)
        if lead is None:
            pending: tuple[int, int] | None = None
        else:
            pending = lead
        sh = _clutch_int(r[8])
        sa = _clutch_int(r[9])
        if sh is not None and sa is not None:
            pending = (sh, sa)
        left = _clutch_clock_left(r[2])
        if pending is not None and left is not None:
            if left <= seconds and abs(pending[0] - pending[1]) <= margin:
                events.setdefault(gid, []).append((r, pending))
                scored += 1
        if sh is not None and sa is not None:
            finals[gid] = (sh, sa)
    return events, finals, home_of, scored

def _clutch_points(action: object, sub: object, desc: object,
                   value: object, result: object) -> tuple[int, int, int]:
    if str(action) == "Made Shot":
        try:
            pts = int(value or 0)
        except (TypeError, ValueError):
            pts = 0
        return pts, 1, 1 if pts == 3 else 0
    if str(action) == "Free Throw":
        if str(desc or "").startswith("MISS"):
            return 0, 0, 0
        return 1, 0, 0
    return 0, 0, 0

def _clutch_is_home(loc: object, tri: object, home: str) -> bool | None:
    if (loc or "") == "h":
        return True
    if (loc or "") == "v":
        return False
    if tri:
        return str(tri) == home
    return None

def _clutch_state(signed: int) -> str:
    if signed > 0:
        return "ahead"
    if signed < 0:
        return "behind"
    return "tied"

def _clutch_player_teams(events: dict[str, list]) -> dict[tuple[str, str], str]:
    from collections import Counter as _Counter
    per: dict[tuple[str, str], _Counter] = {}
    for gid, evts in events.items():
        for r, _ in evts:
            pid = r[5]
            if pid is None or pid == 0:
                continue
            if r[4]:
                per.setdefault((gid, str(pid)), _Counter())[str(r[4])] += 1
    return {key: tally.most_common(1)[0][0] for key, tally in per.items()
            if tally}

def _clutch_shot_slot(r: tuple) -> tuple[int, int, int, int, int, int, int]:
    action = str(r[10])
    pts, fgm, fg3m = _clutch_points(r[10], r[11], r[12], r[13], r[14])
    fga = 1 if action in ("Made Shot", "Missed Shot") else 0
    if action == "Missed Shot":
        fgm = 0
        fg3m = 0
    fg3a = 1 if _clutch_int(r[13]) == 3 and fga else 0
    ftm = fta = 0
    if action == "Free Throw":
        fta = 1
        ftm = 1 if pts else 0
    return pts, fgm, fga, fg3m, fg3a, ftm, fta

def _clutch_slot_credit(slot: dict[str, Any], r: tuple) -> None:
    pts, fgm, fga, fg3m, fg3a, ftm, fta = _clutch_shot_slot(r)
    slot["pts"] += pts
    slot["fgm"] += fgm
    slot["fga"] += fga
    slot["fg3m"] += fg3m
    slot["fg3a"] += fg3a
    slot["ftm"] += ftm
    slot["fta"] += fta

def _clutch_empty_slot(label: str, team: str) -> dict[str, Any]:
    return {"label": label, "team": team, "gp_set": set(),
            "w": 0, "l": 0, "pts": 0, "fgm": 0, "fga": 0,
            "fg3m": 0, "fg3a": 0, "ftm": 0, "fta": 0}

def _clutch_player_totals(events: dict[str, list], teams: dict, names_out: dict):
    from .wpa import _display_name as _wpa_name

    agg: dict[str, dict[str, Any]] = {}
    game_of: dict[str, set[str]] = {}
    for gid, evts in events.items():
        for r, _ in evts:
            pid = r[5]
            if pid is None or pid == 0:
                continue
            key = str(pid)
            tri = teams.get((gid, key), "")
            if not tri and r[4]:
                tri = str(r[4])
            label = _wpa_name(pid, str(r[6] or key))
            names_out[key] = label
            if key not in agg:
                agg[key] = _clutch_empty_slot(label, tri)
            _clutch_slot_credit(agg[key], r)
            game_of.setdefault(key, set()).add(gid)
    return agg, game_of

def _clutch_player_records(teams: dict, home_of: dict, finals: dict,
                           events: dict[str, list]) -> tuple[dict, dict]:
    won: dict[str, int] = {}
    lost: dict[str, int] = {}
    for (gid, key), tri in teams.items():
        if gid not in events:
            continue
        home = home_of.get(gid)
        final = finals.get(gid)
        if home is None or final is None or not tri:
            continue
        if (final[0] > final[1]) == (tri == home):
            won[key] = won.get(key, 0) + 1
        else:
            lost[key] = lost.get(key, 0) + 1
    return won, lost

def _clutch_shooting_row(fga: int, fgm: int, fg3a: int, fg3m: int) -> dict:
    return {"FGA": fga, "FG_PCT": round(fgm / fga, 3) if fga else 0.0,
            "FG3M": fg3m, "FG3A": fg3a,
            "FG3_PCT": round(fg3m / fg3a, 3) if fg3a else 0.0}

def _clutch_team_totals(events: dict[str, list], home_of: dict,
                        finals: dict):
    team_agg: dict[str, dict[str, Any]] = {}
    team_games: dict[str, set[str]] = {}
    team_wins: dict[str, int] = {}
    team_losses: dict[str, int] = {}
    for gid, evts in events.items():
        seen: set[str] = set()
        for r, _ in evts:
            tri = str(r[4] or "")
            if not tri:
                continue
            slot = team_agg.setdefault(
                tri, {"pts": 0, "fgm": 0, "fga": 0, "fg3m": 0, "fg3a": 0,
                      "ftm": 0, "fta": 0})
            _clutch_slot_credit(slot, r)
            seen.add(tri)
        for tri in seen:
            team_games.setdefault(tri, set()).add(gid)
        _clutch_team_records(seen, home_of.get(gid), finals.get(gid),
                             team_wins, team_losses)
    return team_agg, team_games, team_wins, team_losses

def _clutch_team_records(seen: set[str], home: str | None,
                         final: tuple[int, int] | None,
                         team_wins: dict[str, int],
                         team_losses: dict[str, int]) -> None:
    if home is None or final is None:
        return
    home_won = final[0] > final[1]
    for tri in seen:
        if (tri == home) == home_won:
            team_wins[tri] = team_wins.get(tri, 0) + 1
        else:
            team_losses[tri] = team_losses.get(tri, 0) + 1

def _clutch_players(agg: dict, game_of: dict, names: dict,
                    won: dict, lost: dict) -> list[dict[str, Any]]:
    players = []
    for key, slot in agg.items():
        players.append({
            "PLAYER_ID": int(key) if key.isdigit() else key,
            "PLAYER_NAME": names.get(key, slot["label"]),
            "TEAM_ABBREVIATION": slot["team"],
            "GP": len(game_of.get(key, set())),
            "W": won.get(key, 0), "L": lost.get(key, 0),
            "PTS": slot["pts"],
            "FGM": slot["fgm"],
            **_clutch_shooting_row(slot["fga"], slot["fgm"],
                                   slot["fg3a"], slot["fg3m"]),
            "FTM": slot["ftm"], "FTA": slot["fta"],
            "PLUS_MINUS": None,
        })
    return players

def _clutch_squads(team_agg: dict, team_games: dict, team_wins: dict,
                   team_losses: dict) -> list[dict[str, Any]]:
    squads = []
    for tri, slot in team_agg.items():
        squads.append({
            "TEAM_ABBREVIATION": tri,
            "GP": len(team_games.get(tri, set())),
            "W": team_wins.get(tri, 0), "L": team_losses.get(tri, 0),
            "PTS": slot["pts"],
            "FGM": slot["fgm"],
            **_clutch_shooting_row(slot["fga"], slot["fgm"],
                                   slot["fg3a"], slot["fg3m"]),
            "FTM": slot["ftm"], "FTA": slot["fta"],
            "PLUS_MINUS": None,
        })
    return squads

def _clutch_hist_meta(season: str, seconds: int, margin: int,
                      season_type: str, games: int,
                      scored: int) -> dict[str, Any]:
    return {"source": "warehouse:silver_hist_pbp", "season": season,
            "clutch_definition": {"seconds": seconds, "margin": margin,
                                  "season_type": season_type},
            "games": games, "clutch_events": scored,
            "coverage": "clutch events use the score before each play; "
                        "wins follow the final score of games with a clutch "
                        "appearance; plus-minus needs on-court lineups and "
                        "is not derivable from play-by-play"}

def _derive_hist_clutch(season: str, scope: str, seconds: int, margin: int,
                        season_type: str) -> tuple[list | None, dict]:
    rows = _clutch_pbp_rows(season, _clutch_prefixes(season_type))
    if not rows:
        return None, {"source": "warehouse:silver_hist_pbp",
                      "season": season,
                      "error": f"no play-by-play coverage for season {season}"}
    home_of = _clutch_home_of(rows)
    events, finals, _, scored = _clutch_fold(rows, home_of, seconds, margin)
    if not events:
        return [], {"source": "warehouse:silver_hist_pbp", "season": season,
                    "clutch_definition": {"seconds": seconds, "margin": margin,
                                          "season_type": season_type},
                    "games": 0, "clutch_events": 0}
    if scope == "team":
        team_agg, team_games, team_wins, team_losses = _clutch_team_totals(
            events, home_of, finals)
        meta = _clutch_hist_meta(season, seconds, margin, season_type,
                                 len(events), scored)
        return _clutch_squads(team_agg, team_games, team_wins,
                              team_losses), meta
    teams = _clutch_player_teams(events)
    names: dict[str, str] = {}
    agg, game_of = _clutch_player_totals(events, teams, names)
    won, lost = _clutch_player_records(teams, home_of, finals, events)
    meta = _clutch_hist_meta(season, seconds, margin, season_type,
                             len(events), scored)
    return _clutch_players(agg, game_of, names, won, lost), meta

def _clutch_row_common(row: dict[str, Any]) -> dict[str, Any]:
    return {"GP": row.get("GP"), "W": row.get("W"), "L": row.get("L"),
            "PTS": row.get("PTS"), "FG_PCT": row.get("FG_PCT"),
            "FG3_PCT": row.get("FG3_PCT"), "PLUS_MINUS": row.get("PLUS_MINUS")}

def _clutch_player_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"PLAYER_ID": row.get("PLAYER_ID"),
            "PLAYER_NAME": row.get("PLAYER_NAME"),
            **_clutch_row_common(row)}

def _clutch_team_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"TEAM_ABBREVIATION": row.get("TEAM_ABBREVIATION"),
            **_clutch_row_common(row)}

def _clutch_slim(scope: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shape = _clutch_team_row if scope == "team" else _clutch_player_row
    return sorted((shape(r) for r in rows),
                  key=lambda d: (d.get("PTS") or 0), reverse=True)

def _clutch_team_abbr(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        from nba_api.stats.static import teams as _teams
        low = raw.lower()
        for t in _teams.get_teams():
            if low == str(t.get("abbreviation") or "").lower():
                return str(t.get("abbreviation")).upper()
        for t in _teams.get_teams():
            if low == str(t.get("full_name") or "").lower():
                return str(t.get("abbreviation")).upper()
        for t in _teams.get_teams():
            if low == str(t.get("nickname") or "").lower():
                return str(t.get("abbreviation")).upper()
    except Exception:
        pass
    upper = raw.upper()
    alias = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}
    upper = alias.get(upper, upper)
    if upper in {"ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN",
                 "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA",
                 "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX",
                 "POR", "SAC", "SAS", "TOR", "UTA", "WAS"}:
        return upper
    return None

@tool(description='Clutch stats (last 5 min, margin 5 or less), player or team scope.')
def get_clutch(scope: str = "player", season: str | None = None,
               player: str = "",
               clutch_seconds: int = _CLUTCH_SECONDS_DEFAULT,
               clutch_margin: int = _CLUTCH_MARGIN_DEFAULT,
               season_type: str = _CLUTCH_SEASON_TYPE_DEFAULT
               ) -> dict[str, Any]:
    season = resolve_season(season)
    scope = "team" if str(scope).lower().startswith("team") else "player"
    seconds, seconds_warning = _clutch_seconds_of(clutch_seconds)
    margin, margin_warning = _clutch_margin_of(clutch_margin)
    stype, stype_warning = _clutch_season_type_of(season_type)
    warnings = [w for w in
                (seconds_warning, margin_warning, stype_warning) if w]
    year = _clutch_end_year(season)
    standard = (seconds == _CLUTCH_SECONDS_DEFAULT
                and margin == _CLUTCH_MARGIN_DEFAULT
                and stype == _CLUTCH_SEASON_TYPE_DEFAULT)
    if year is not None and _CLUTCH_PBP_FIRST <= year <= _CLUTCH_PBP_LAST:
        derived, meta = _derive_hist_clutch(season, scope, seconds, margin,
                                            stype)
        if derived is None:
            return {"tool": "get_clutch", "ok": False, "rows": [],
                    "error": str(meta.get("error") or "no coverage"),
                    "meta": meta}
        if warnings:
            meta = dict(meta)
            meta["warning"] = "; ".join(warnings)
        if player and scope == "player":
            want = str(player).strip().lower()
            derived = [r for r in derived
                       if str(r.get("PLAYER_NAME") or "").strip().lower()
                       == want]
        return {"tool": "get_clutch", "ok": True,
                "rows": _clutch_slim(scope, derived)[:30], "meta": meta}
    if not standard:
        return {
            "tool": "get_clutch", "ok": False, "rows": [],
            "error": (f"custom clutch definition (last {seconds}s, margin "
                      f"{margin}) needs play-by-play, which covers "
                      f"{_CLUTCH_PBP_FIRST - 1}-{str(_CLUTCH_PBP_FIRST)[-2:]} "
                      f"through {_CLUTCH_PBP_LAST - 1}-"
                      f"{str(_CLUTCH_PBP_LAST)[-2:]} only; season {season} "
                      f"is outside that range"),
            "meta": {"season": season,
                     "clutch_definition": {"seconds": seconds,
                                          "margin": margin,
                                          "season_type": stype}},
        }
    entity = f"{scope}-clutch"
    rows, meta = _warehouse_or_live(
        "silver_clutch", "_season = ? AND _entity = ?",
        [season, entity], lambda: nba_stats.clutch(scope, season), season,
        entity=entity, limit=600,
    )
    if scope == "team" and not rows:
        return {
            "tool": "get_clutch", "ok": False, "rows": [],
            "error": ("team-level clutch records are unavailable; "
                      "player clutch wins and losses cannot be aggregated"),
            "meta": meta,
        }
    if player and scope == "player":
        _want = str(player).strip().lower()
        rows = [r for r in rows
                if str(r.get("PLAYER_NAME") or "").strip().lower() == _want]
    if warnings:
        meta = dict(meta)
        meta["warning"] = "; ".join(warnings)
    slim = _clutch_slim(scope, rows)
    if not slim and year is not None and year < _CLUTCH_PBP_FIRST:
        return {"tool": "get_clutch", "ok": False, "rows": [],
                "error": (f"no clutch coverage for season {season}; "
                          f"play-by-play covers "
                          f"{_CLUTCH_PBP_FIRST - 1}-"
                          f"{str(_CLUTCH_PBP_FIRST)[-2:]} through "
                          f"{_CLUTCH_PBP_LAST - 1}-"
                          f"{str(_CLUTCH_PBP_LAST)[-2:]} and the clutch "
                          f"table covers 2025-26 only"),
                "meta": meta}
    return {"tool": "get_clutch", "ok": True, "rows": slim[:30], "meta": meta}

def _split_bucket(label: str) -> dict[str, Any]:
    return {"split": label, "GP": 0, "FGM": 0, "FGA": 0, "FG_PCT": 0.0,
            "FG3M": 0, "FG3A": 0, "FG3_PCT": 0.0,
            "FTM": 0, "FTA": 0, "PTS": 0}

def _split_credit(bucket: dict[str, Any], pts: int, fgm: int, fga: int,
                  fg3m: int, fg3a: int, ftm: int, fta: int) -> None:
    bucket["PTS"] += pts
    bucket["FGM"] += fgm
    bucket["FGA"] += fga
    bucket["FG3M"] += fg3m
    bucket["FG3A"] += fg3a
    bucket["FTM"] += ftm
    bucket["FTA"] += fta

def _split_finalize(bucket: dict[str, Any]) -> None:
    fga = bucket["FGA"]
    fg3a = bucket["FG3A"]
    bucket["FG_PCT"] = round(bucket["FGM"] / fga, 3) if fga else 0.0
    bucket["FG3_PCT"] = round(bucket["FG3M"] / fg3a, 3) if fg3a else 0.0

_SPLIT_ORDER = ["overall", "ahead", "tied", "behind", "home", "away"]

def _split_definition(seconds: int, margin: int, stype: str) -> dict[str, Any]:
    return {"seconds": seconds, "margin": margin, "season_type": stype}

def _split_failure(season: str, error: str,
                   definition: dict[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {"season": season}
    if definition is not None:
        meta["clutch_definition"] = definition
    return {"tool": "get_situational_splits", "ok": False, "rows": {},
            "error": error, "meta": meta}

def _split_entity_id(scope: str, name: str) -> tuple[int | None, str | None]:
    if scope != "player":
        abbr = _clutch_team_abbr(name)
        return None, (None if abbr is None else abbr)
    from ._core import coerce_player_id as _cpid
    return _cpid(name), None

def _split_event_tricode(scope: str, r: tuple, gid: str, home: str | None,
                         pid: int | None, abbr: str | None,
                         fallbacks: dict) -> str | None:
    if scope == "player":
        try:
            if pid is None or int(r[5] or 0) != pid:
                return None
        except (TypeError, ValueError):
            return None
        return str(r[4] or "") or fallbacks.get((gid, str(pid)), "")
    tri_raw = _CLUTCH_PBP_ALIAS.get(str(r[4] or ""), str(r[4] or ""))
    return None if tri_raw != abbr else tri_raw

def _split_credit_event(buckets: dict[str, Any], state: str,
                        is_home: bool, r: tuple) -> None:
    pts, fgm, fga, fg3m, fg3a, ftm, fta = _clutch_shot_slot(r)
    for label in ("overall", state, "home" if is_home else "away"):
        _split_credit(buckets[label], pts, fgm, fga, fg3m, fg3a, ftm, fta)

def _split_events(scope: str, events: dict[str, list], home_of: dict,
                  pid: int | None, abbr: str | None,
                  fallbacks: dict) -> tuple[dict[str, Any], set[str], str]:
    from .wpa import _display_name as _wpa_name

    buckets = {label: _split_bucket(label) for label in _SPLIT_ORDER}
    games: set[str] = set()
    resolved = ""
    for gid, evts in events.items():
        home = home_of.get(gid)
        for r, pending in evts:
            tri_raw = _split_event_tricode(scope, r, gid, home, pid, abbr,
                                           fallbacks)
            if tri_raw is None:
                continue
            if scope == "player" and r[6]:
                resolved = _wpa_name(pid, str(r[6]))
            is_home = _clutch_is_home(r[7], tri_raw, str(home or ""))
            if is_home is None:
                continue
            signed = pending[0] - pending[1]
            if not is_home:
                signed = -signed
            games.add(gid)
            _split_credit_event(buckets, _clutch_state(signed), is_home, r)
    return buckets, games, resolved

def _split_rows_out(scope: str, name: str, resolved: str, pid: int | None,
                    abbr: str | None, season: str,
                    buckets: dict[str, Any]) -> dict[str, Any]:
    if scope == "player":
        return {"player": resolved or name, "player_id": pid,
                "season": season,
                "splits": [buckets[label] for label in _SPLIT_ORDER]}
    return {"team": abbr, "season": season,
            "splits": [buckets[label] for label in _SPLIT_ORDER]}

@tool(description='Clutch situational splits for one player or team: score state plus venue.')
def get_situational_splits(scope: str = "player", entity: str = "",
                            season: str | None = None,
                            clutch_seconds: int = _CLUTCH_SECONDS_DEFAULT,
                            clutch_margin: int = _CLUTCH_MARGIN_DEFAULT,
                            season_type: str = _CLUTCH_SEASON_TYPE_DEFAULT
                            ) -> dict[str, Any]:
    season = resolve_season(season)
    scope = "team" if str(scope).lower().startswith("team") else "player"
    seconds, seconds_warning = _clutch_seconds_of(clutch_seconds)
    margin, margin_warning = _clutch_margin_of(clutch_margin)
    stype, stype_warning = _clutch_season_type_of(season_type)
    warnings = [w for w in
                (seconds_warning, margin_warning, stype_warning) if w]
    definition = _split_definition(seconds, margin, stype)
    year = _clutch_end_year(season)
    if year is None or not (_CLUTCH_PBP_FIRST <= year <= _CLUTCH_PBP_LAST):
        return _split_failure(
            season,
            (f"no play-by-play coverage for season {season}; "
             f"situational splits cover "
             f"{_CLUTCH_PBP_FIRST - 1}-"
             f"{str(_CLUTCH_PBP_FIRST)[-2:]} through "
             f"{_CLUTCH_PBP_LAST - 1}-"
             f"{str(_CLUTCH_PBP_LAST)[-2:]} only"),
            definition)
    name = str(entity or "").strip()
    if not name:
        return _split_failure(season, "pass one player or team entity")
    try:
        pid, abbr = _split_entity_id(scope, name)
    except ValueError as exc:
        return _split_failure(season, str(exc)[:160])
    if abbr is None and scope != "player":
        return _split_failure(season, f"unknown team: {name}")
    rows = _clutch_pbp_rows(season, _clutch_prefixes(stype))
    home_of = _clutch_home_of(rows)
    events, _, _, scored = _clutch_fold(rows, home_of, seconds, margin)
    fallbacks = _clutch_player_teams(events) if scope == "player" else {}
    buckets, games, resolved = _split_events(scope, events, home_of, pid,
                                             abbr, fallbacks)
    for bucket in buckets.values():
        _split_finalize(bucket)
    buckets["overall"]["GP"] = len(games)
    if not games:
        return _split_failure(
            season, f"no clutch appearances for {name} in {season}",
            definition)
    meta: dict[str, Any] = {
        "source": "warehouse:silver_hist_pbp", "season": season,
        "clutch_definition": definition,
        "clutch_events": scored,
        "state_rule": "score state from the entity side at each play, "
                      "using the score before the play",
    }
    if warnings:
        meta["warning"] = "; ".join(warnings)
    return {"tool": "get_situational_splits", "ok": True,
            "rows": _split_rows_out(scope, name, resolved, pid, abbr, season,
                                    buckets),
            "meta": meta}

def _finals_game_scores(finals: list[dict[str, Any]],
                        season: str) -> dict[str, dict[str, int]]:
    season = resolve_season(season)
    from datetime import datetime as _dt

    dates: dict[str, str] = {}
    for g in finals:
        try:
            dates[_dt.strptime(str(g.get("GAME_DATE")), "%Y-%m-%d")
                  .strftime("%b %-d, %Y")] = str(g.get("GAME_DATE"))
        except (TypeError, ValueError):
            pass
    if not dates:
        return {}
    try:
        from .. import store as _store

        con = _store.connect(read_only=True)
        try:
            ph = ",".join("?" * len(dates))
            rows = con.execute(
                f"SELECT GAME_DATE, split_part(MATCHUP, ' ', 1), "
                f"SUM(PTS) FROM silver_playoff_gamelogs "
                f"WHERE _season = ? AND GAME_DATE IN ({ph}) "
                f"GROUP BY 1, 2",
                [season, *sorted(dates)]).fetchall()
        finally:
            con.close()
    except Exception:
        return {}
    out: dict[str, dict[str, int]] = {}
    for gdate, team, pts in rows:
        iso = dates.get(str(gdate))
        if iso and team:
            out.setdefault(iso, {})[str(team)] = int(pts or 0)
    return out

def _playoff_home_team(matchup: str) -> str:
    if " @ " in matchup:
        return matchup.split(" @ ")[1].strip()
    if " vs. " in matchup:
        return matchup.split(" vs. ")[0].strip()
    return ""

def _playoff_finals_game(g: dict, ta: str, tb: str,
                         scores: dict) -> dict[str, Any]:
    matchup = str(g.get("MATCHUP"))
    game = {"game_id": str(g.get("GAME_ID")),
            "date": str(g.get("GAME_DATE")),
            "matchup": matchup,
            "home": _playoff_home_team(matchup),
            "winner": (ta if g.get("WL") == "W" else tb)}
    sc = scores.get(str(g.get("GAME_DATE")) or "")
    if sc:
        game["score"] = sc
        game["scoreline"] = ", ".join(
            f"{t} {sc[t]}" for t in (ta, tb) if t in sc)
    return game

def _playoff_finals_games(finals: list[dict[str, Any]], ta: str, tb: str,
                          scores: dict) -> list[dict[str, Any]]:
    return [_playoff_finals_game(g, ta, tb, scores) for g in finals
            if str(g.get("TEAM_ABBREVIATION")) == ta]

def _playoff_finals_wins(finals: list[dict[str, Any]]) -> dict[str, int]:
    fwins: dict[str, int] = {}
    for r in finals:
        t = str(r.get("TEAM_ABBREVIATION") or "")
        if r.get("WL") == "W":
            fwins[t] = fwins.get(t, 0) + 1
    return fwins

def _playoff_finals_rows(finals: list[dict[str, Any]], fteams: list[str],
                         season: str) -> dict[str, Any] | None:
    if len(fteams) != 2:
        return None
    ta, tb = fteams[0], fteams[1]
    fwins = _playoff_finals_wins(finals)
    return {
        "round": "NBA Finals",
        "teams": [ta, tb],
        "series_score": (f"{ta} {fwins.get(ta, 0)} - "
                         f"{fwins.get(tb, 0)} {tb}"),
        "winner": max(fwins, key=fwins.get) if fwins else "",
        "games": _playoff_finals_games(
            finals, ta, tb, _finals_game_scores(finals, season)),
    }

def _playoff_finals_dates(finals: list[dict[str, Any]]) -> set[str]:
    from datetime import datetime as _dt

    fdates = set()
    for g in finals:
        try:
            fdates.add(_dt.strptime(
                str(g.get("GAME_DATE")), "%Y-%m-%d"
            ).strftime("%b %-d, %Y"))
        except (TypeError, ValueError):
            pass
    return fdates

def _playoff_finals_leader(season: str, fdates: set[str]):
    from .. import store as _store

    con = _store.connect(read_only=True)
    try:
        ph = ",".join("?" * len(fdates))
        row = con.execute(
            f"SELECT _entity, COUNT(*), ROUND(AVG(PTS), 1) FROM "
            f"silver_playoff_gamelogs WHERE _season = ? "
            f"AND GAME_DATE IN ({ph}) GROUP BY 1 "
            f"ORDER BY 3 DESC LIMIT 1",
            [season, *sorted(fdates)]).fetchone()
        if not row or not row[1]:
            return None
        pid = str(row[0]).replace("player:", "")
        named = con.execute(
            "SELECT DISTINCT PLAYER FROM silver_leaders_pts WHERE "
            "CAST(PLAYER_ID AS VARCHAR) = ?", [pid]).fetchone()
        return (named[0] if named else pid), row[2], len(fdates)
    finally:
        con.close()

def _playoff_finals_mvp_note(finals: dict[str, Any], rows: list[dict],
                             season: str) -> None:
    try:
        fdates = _playoff_finals_dates(rows)
        if not fdates:
            return
        leader = _playoff_finals_leader(season, fdates)
        if leader is None:
            return
        name, ppg, game_count = leader
        finals["finals_mvp_note"] = (
            "The Finals MVP award is not recorded in "
            "this dataset. The leading Finals scorer "
            f"was {name} at {ppg} points per "
            f"game over the {game_count}-game series.")
    except Exception:
        pass

def _playoff_finals_answer(fin: dict[str, Any], season: str) -> str:
    from nba_api.stats.static import teams as _static

    names = {t["abbreviation"]: t["full_name"] for t in _static.get_teams()}
    winner = fin["winner"]
    loser = next((t for t in fin.get("teams", []) if t != winner), "")
    games = fin.get("games", [])
    won = sum(1 for g in games if g.get("winner") == winner)
    lost = (len(games) or 0) - won
    year = season.split("-")[0]
    year = str(int(year) + 1) if year.isdigit() else season
    return (f"The {names.get(winner, winner)} won the {year} NBA Finals, "
            f"beating the {names.get(loser, loser)} {won}-{lost}.")

def _playoff_wins_rows(rows: list[dict[str, Any]]) -> tuple[dict, dict, int]:
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
    return wins, losses, games

@tool(description='Playoff wins per team plus champion for one season.')
def get_playoffs(season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    rows, meta = _warehouse_or_live(
        "silver_playoffs", "_season = ?",
        [season], lambda: nba_stats.playoff_results(season), season,
        limit=600,
    )
    wins, losses, games = _playoff_wins_rows(rows)
    if not rows and meta.get("error"):

        return {"tool": "get_playoffs", "ok": False,
                "error": str(meta["error"])}
    table = sorted(
        ((t, w) for t, w in wins.items()), key=lambda x: x[1], reverse=True)
    champ = table[0][0] if table and table[0][1] >= 12 else ""
    rows_out: dict[str, Any] = {"champion": champ,
            "champion_record":
                {"w": wins.get(champ, 0), "l": losses.get(champ, 0)}
                if champ else {},
            "wins": [{"team": t, "w": w, "l": losses.get(t, 0)}
                     for t, w in table[:16]],
            "games_total": games // 2}

    finals_rows = [r for r in rows if str(r.get("GAME_ID") or "")[7:8] == "4"]
    if finals_rows:
        fteams = sorted({str(r.get("TEAM_ABBREVIATION") or "")
                         for r in finals_rows} - {""})
        finals = _playoff_finals_rows(finals_rows, fteams, season)
        if finals is not None:
            rows_out["finals"] = finals
            _playoff_finals_mvp_note(finals, finals_rows, season)
    from ._core import season_static as _season_static
    if _season_static(season):

        rows_out["result_kind"] = "ACTUAL_RESULTS_NOT_SIMULATION"
        rows_out["summary"] = (
            f"These are the ACTUAL final {season} playoff results"
            + (f" ({champ} champions)" if champ else "")
            + ", recorded games - not a simulation or prediction. "
              "If the ask was to simulate, say simulated odds are "
              "unavailable for a completed season.")

    fin = rows_out.get("finals")
    if isinstance(fin, dict) and fin.get("winner"):
        try:
            meta["deterministic_answer"] = _playoff_finals_answer(fin, season)
        except Exception:
            pass
    return {"tool": "get_playoffs", "ok": True,
            "rows": rows_out,
            "meta": meta}

_BOX_TOTAL_COLUMNS = {
    "PTS": "points", "REB": "reboundsTotal", "AST": "assists",
    "STL": "steals", "BLK": "blocks", "FGM": "fieldGoalsMade",
    "FGA": "fieldGoalsAttempted", "FG3M": "threePointersMade",
    "FG3A": "threePointersAttempted", "FTM": "freeThrowsMade",
    "FTA": "freeThrowsAttempted", "OREB": "reboundsOffensive",
    "DREB": "reboundsDefensive", "TOV": "turnovers", "PF": "foulsPersonal",
}

def _completed_season_totals(stat_category, season, order="DESC"):
    column = _BOX_TOTAL_COLUMNS.get(stat_category)
    if column is None:
        return None
    con = store.connect(read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "silver_boxscores" not in tables:
            return None
        columns = {
            row[1]
            for row in con.execute(
                "PRAGMA table_info(silver_boxscores)").fetchall()
        }
        if not {"PLAYER_ID", "firstName", "familyName", "GAME_ID",
                "teamTricode", column, "comment", "_season"} <= columns:
            return None
        raw = con.execute(
            "SELECT PLAYER_ID, firstName || ' ' || familyName AS PLAYER, "
            "MODE(teamTricode) AS TEAM, "
            "COUNT(DISTINCT GAME_ID) AS GP, "
            f"SUM({column}) AS TOTAL "
            "FROM silver_boxscores WHERE _season = ? "
            "AND (comment IS NULL OR comment = '') "
            "GROUP BY PLAYER_ID, firstName, familyName "
            f"ORDER BY TOTAL {order}",
            [season],
        ).fetchall()
    finally:
        con.close()
    if not raw:
        return None
    rows = [
        {"RANK": index, "PLAYER_ID": row[0], "PLAYER": row[1], "TEAM": row[2],
         "GP": row[3], stat_category: row[4], "PLAYER_NAME": row[1]}
        for index, row in enumerate(raw, 1)
    ]
    meta = {
        "source": "warehouse", "season": season,
        "stat_category": stat_category, "rows": len(rows),
        "cached": True, "static_season": True,
        "qualification": (
            "Season totals summed from warehouse game logs; "
            "games not played are left out."
        ),
        "coverage": (
            "Full player population in warehouse game logs "
            "for the season, ordered by total."
        ),
        **store.warehouse_identity(),
    }
    return rows, meta

_TOTAL_MINUTES_FLOOR = 500
_TOTAL_MINUTES_TS_FLOOR = 1000

class QualificationFloor:

    __slots__ = ("metric", "floor", "label", "cleared_column")

    def __init__(self, metric: str, floor: int, label: str,
                 cleared_column: str) -> None:
        self.metric = metric
        self.floor = floor
        self.label = label
        self.cleared_column = cleared_column

    def payload(self) -> dict[str, Any]:
        return {"metric": self.metric, "floor": self.floor,
                "label": self.label, "cleared_column": self.cleared_column}

class _FloorValueUnavailable(Exception):
    pass

def _floor_rows(con, sql: str, params: list[Any], table: str,
                floor: QualificationFloor) -> list[Any]:
    try:
        return con.execute(sql, params).fetchall()
    except duckdb.Error as exc:
        raise _FloorValueUnavailable(
            f"{table} cannot evidence the {floor.label} qualification "
            f"because the column behind it is unreadable: {exc}") from exc

def _qualified_rate_board(
        con, stat_category: str, season: str, order: str, min_attempts: int,
) -> tuple[list[dict[str, Any]], QualificationFloor, Any]:
    if stat_category == "TS_PCT":
        floor_value = max(_TOTAL_MINUTES_TS_FLOOR, min_attempts)
        qualification = QualificationFloor(
            "total_minutes", floor_value, f"{floor_value:,}+ total minutes",
            "TOTAL_MINUTES")
        raw = _floor_rows(
            con,
            "SELECT PLAYER_NAME, TEAM_ABBREVIATION, GP, MIN, TS_PCT "
            "FROM silver_advanced WHERE _season = ? "
            f"AND GP * MIN >= ? ORDER BY TS_PCT {order}, GP * MIN DESC",
            [season, floor_value], "silver_advanced", qualification)
        rows = [
            {"RANK": index, "PLAYER": row[0], "TEAM": row[1],
             "GP": row[2], "MPG": row[3],
             "TOTAL_MINUTES": row[2] * row[3],
             "TS_PCT": round(float(row[4]) * 100, 1)}
            for index, row in enumerate(raw, 1)
        ]
        return rows, qualification, (
            lambda row: f"{row['TS_PCT']:.1f}% true shooting")

    rate_to_total = {"PPG": "PTS", "RPG": "REB", "APG": "AST",
                     "SPG": "STL", "BPG": "BLK"}
    total_stat = rate_to_total[stat_category]
    table = f"silver_leaders_{total_stat.lower()}"
    qualification = QualificationFloor(
        "total_minutes", _TOTAL_MINUTES_FLOOR,
        f"{_TOTAL_MINUTES_FLOOR}+ total minutes", "MIN")
    raw = _floor_rows(
        con,
        f"SELECT PLAYER, TEAM, GP, MIN,"
        f" {total_stat} / CAST(GP AS DOUBLE) AS RATE "
        f"FROM {table} WHERE _season = ? AND GP > 0"
        f" AND MIN >= {_TOTAL_MINUTES_FLOOR} "
        f"ORDER BY RATE {order}, GP DESC, PLAYER",
        [season], table, qualification)
    rows = [
        {"RANK": index, "PLAYER": row[0], "TEAM": row[1],
         "GP": row[2], "MIN": row[3],
         stat_category: float(row[4])}
        for index, row in enumerate(raw, 1)
    ]
    noun = {"PPG": "points", "RPG": "rebounds", "APG": "assists",
            "SPG": "steals", "BPG": "blocks"}[stat_category]
    return rows, qualification, (
        lambda row: f"{row[stat_category]:.2f} {noun} per game")

def _cleared(lead: dict[str, Any], floor: QualificationFloor) -> str:
    column = floor.cleared_column
    observed = lead.get(column)
    if observed is None:
        raise ValueError(
            f"qualification floor {floor.label} has no published value: the "
            f"leader row carries no {column}, so the floor would publish as a "
            f"label with no number behind it")
    return f"{observed:,.0f} {floor.metric.replace('_', ' ')} over " \
           f"{lead.get('GP')} games"

_RATE_BOARD_CATEGORIES = {"TS_PCT", "PPG", "RPG", "APG", "SPG", "BPG"}

_DIRECTION_ALIASES = {"ascending": "asc", "ascend": "asc",
                      "descending": "desc", "descend": "desc"}

def _leaders_direction(ranking_direction: str) -> str:
    direction = _DIRECTION_ALIASES.get(
        str(ranking_direction).strip().casefold(),
        str(ranking_direction).strip().casefold())
    if direction not in {"asc", "desc"}:
        raise ValueError("ranking_direction must be 'asc' or 'desc'")
    return direction

def _leaders_check_min_attempts(min_attempts: object) -> None:
    if isinstance(min_attempts, bool) or not isinstance(min_attempts, int):
        raise TypeError("min_attempts must be an integer")
    if not 0 <= min_attempts <= 5000:
        raise ValueError("min_attempts must be between 0 and 5000")

def _leaders_unevidenced(stat_category: str, exc: Exception, season: str,
                         direction: str, min_attempts: int) -> dict[str, Any]:
    return {"tool": "get_leaders", "ok": False, "rows": [],
            "error": (f"{exc}; refusing to publish a "
                      f"{stat_category} board whose "
                      f"qualification cannot be evidenced"),
            "meta": {"source": "warehouse", "season": season,
                     "stat_category": stat_category,
                     "ranking_direction": direction,
                     "min_attempts": min_attempts}}

def _leaders_rate_board(stat_category: str, season: str, order: str,
                        direction: str, min_attempts: int):
    con = store.connect(read_only=True)
    try:
        rows, qualification, value = _qualified_rate_board(
            con, stat_category, season, order, min_attempts)
    except _FloorValueUnavailable as exc:
        return None, _leaders_unevidenced(stat_category, exc, season,
                                          direction, min_attempts)
    finally:
        con.close()
    meta = {
        "source": "warehouse", "season": season,
        "stat_category": stat_category, "rows": len(rows),
        "ranking_direction": direction, "min_attempts": min_attempts,
        "qualification": qualification.label,
        "qualification_floor": qualification.payload(),
    }
    return (rows, meta), (value, qualification)

def _leaders_table_board(stat_category: str, season: str, order: str):
    table = f"silver_leaders_{stat_category.lower()}"
    rows, meta = _warehouse_or_live(
        table, "_season = ?",
        [season], lambda: nba_stats.leaders(stat_category, season), season,
    )
    meta["stat_category"] = stat_category
    needs_id_fallback = bool(rows) and not any(
        "PLAYER_ID" in row or "player_id" in row for row in rows
    )
    if (not rows or needs_id_fallback) and season_static(season):
        fallback = _completed_season_totals(stat_category, season, order)
        if fallback is not None:
            rows, meta = fallback
    return rows, meta

def _leaders_fg3_rows(season: str, order: str, min_attempts: int) -> list:
    con = store.connect(read_only=True)
    try:
        raw = con.execute(
            "SELECT PLAYER, TEAM, GP, MIN, FG3M, FG3A, FG3_PCT "
            "FROM silver_leaders_pts WHERE _season = ? "
            f"AND FG3M >= ? AND FG3A >= ? "
            f"ORDER BY FG3_PCT {order}, FG3M DESC",
            [season, 0 if min_attempts else 82, min_attempts]).fetchall()
    finally:
        con.close()
    return [
        {"RANK": i, "PLAYER": r[0], "TEAM": r[1], "GP": r[2],
         "MPG": r[3], "FG3M": r[4], "FG3A": r[5],
         "FG3_PCT": r[6]}
        for i, r in enumerate(raw, 1)
    ]

def _leaders_fg3_meta(rows: list, season: str, direction: str,
                      min_attempts: int, stat_category: str) -> dict[str, Any]:
    qualification = (f"{min_attempts}+ three-point attempts"
                     if min_attempts else "82+ made threes")
    meta = {"source": "warehouse", "season": season,
            "stat_category": stat_category, "rows": len(rows),
            "ranking_direction": direction,
            "min_attempts": min_attempts,
            "qualification": qualification}
    if rows:
        leaders = "; ".join(
            f"{row['PLAYER']} {row['FG3_PCT'] * 100:.1f}% "
            f"({row['FG3M']} makes on {row['FG3A']} attempts)"
            for row in rows[:5]
        )
        meta["deterministic_answer"] = (
            f"Qualified three-point percentage leaders: {leaders}. "
            f"Qualification: {qualification}.")
    return meta

def _leaders_fg3_board(season: str, order: str, direction: str,
                       min_attempts: int, stat_category: str,
                       meta: dict[str, Any]):
    try:
        rows = _leaders_fg3_rows(season, order, min_attempts)
    except Exception:
        return [], meta
    return rows, _leaders_fg3_meta(rows, season, direction, min_attempts,
                                   stat_category)

def _leaders_pin_columns(stat_category: str) -> list[str]:
    pin = ["RANK", "PLAYER", "TEAM", stat_category]
    if stat_category == "FG3_PCT":
        pin.extend(["FG3M", "FG3A"])
    pin.extend(["GP", "MIN", "MPG", "TOTAL_MINUTES"])
    return pin

def _pin_leader_row(r: Any, pin: list[str]) -> Any:
    if not isinstance(r, dict):
        return r
    slim = {k: r[k] for k in pin if k in r}
    for metric in COUNTING_METRICS:
        rate = per_game_value(slim.get(metric), slim.get("GP"))
        if rate is not None:
            slim[per_game_column(metric)] = rate
    for identifier in ("PLAYER_ID", "player_id", "TEAM_ID", "team_id"):
        if identifier in r and identifier not in slim:
            slim[identifier] = r[identifier]
    if "PLAYER" in slim and "PLAYER_NAME" not in slim:
        slim["PLAYER_NAME"] = slim["PLAYER"]
    return slim

def _leaders_lead_answer(pinned: list, lead_answer: tuple, season: str):
    value, qualification = lead_answer
    return (f"{pinned[0]['PLAYER']} leads qualified players at "
            f"{value(pinned[0])} in {season}. Qualification: "
            f"{qualification.label}; "
            f"{_cleared(pinned[0], qualification)}.")

@tool(description='Qualified league leaderboard for one stat category.\n\nranking_direction is ``desc`` for highest-first or ``asc`` for\nlowest-first. min_attempts carries an explicit user volume floor for\npercentage metrics; zero keeps the league qualification.\n\nPercentage boards use the NBA minimums carried by the warehouse\ninstead of an arbitrary attempts floor. For 3P%, the qualification is\n82 made threes over an 82-game season. This keeps the board comparable\nto the official league leaderboard and excludes tiny samples.')
def get_leaders(
    stat_category: str = "PTS", season: str | None = None,
    ranking_direction: str = "desc", min_attempts: int = 0,
) -> dict[str, Any]:
    season = resolve_season(season)
    try:
        stat_category = clamp_stat(stat_category)
    except ValueError:
        return {"tool": "get_leaders", "ok": False, "rows": [],
                "error": f"unknown stat_category: {stat_category!r}",
                "meta": {"source": "warehouse", "season": season}}
    direction = _leaders_direction(ranking_direction)
    _leaders_check_min_attempts(min_attempts)
    order = "ASC" if direction == "asc" else "DESC"

    lead_answer: tuple[Any, QualificationFloor] | None = None
    if stat_category in _RATE_BOARD_CATEGORIES:
        board, lead_answer = _leaders_rate_board(
            stat_category, season, order, direction, min_attempts)
        if board is None:
            return lead_answer
        rows, meta = board
    else:
        rows, meta = _leaders_table_board(stat_category, season, order)

    if stat_category == "FG3_PCT":
        rows, meta = _leaders_fg3_board(season, order, direction,
                                        min_attempts, stat_category, meta)

    pin = _leaders_pin_columns(stat_category)
    pinned = [_pin_leader_row(r, pin) for r in rows]
    if lead_answer is not None and pinned:
        try:
            meta["deterministic_answer"] = _leaders_lead_answer(
                pinned, lead_answer, season)
        except (ValueError, KeyError, TypeError) as exc:
            return {"tool": "get_leaders", "ok": False, "rows": [],
                    "error": (f"refusing to publish a {stat_category} answer "
                              f"whose qualification cannot be evidenced from "
                              f"the published row: {exc}"),
                    "meta": meta}
    if not pinned and str(meta.get("error") or "").strip():
        detail = str(meta.get("error")).strip()
        return {"tool": "get_leaders", "ok": False, "rows": [],
                "error": (f"no {stat_category} leaders for {season}: "
                          f"{detail}"),
                "meta": meta}
    return {"tool": "get_leaders", "ok": True, "rows": pinned, "meta": meta}

@tool(description='Qualified usage-rate board for young players from silver_advanced.\n\nUses total minutes (GP * per-game MIN) as the sample floor. The default\nmeans age 22 or younger with at least 1,000 minutes in the asked season.\nA hard 500-total-minute floor is ALWAYS enforced: the caller may raise\nit but never undercut it.')
def get_young_player_usage(max_age: int = 22, min_minutes: int = 1000,
                           season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    max_age = max(18, min(int(max_age), 25))
    min_minutes = max(500, min(int(min_minutes), 3000))
    con = store.connect(read_only=True)
    try:
        raw = con.execute(
            "SELECT PLAYER_NAME, TEAM_ABBREVIATION, AGE, GP, MIN, USG_PCT "
            "FROM silver_advanced WHERE _season = ? AND AGE <= ? "
            "AND GP * MIN >= ? ORDER BY USG_PCT DESC",
            [season, max_age, min_minutes]).fetchall()
    finally:
        con.close()
    rows = [{"RANK": i, "PLAYER": r[0], "TEAM": r[1], "AGE": r[2],
             "GP": r[3], "MPG": r[4], "MINUTES": round(r[3] * r[4]),
             "USG_PCT": round(float(r[5]) * 100, 1)}
            for i, r in enumerate(raw, 1)]
    meta: dict[str, Any] = {
        "source": "warehouse:silver_advanced", "season": season,
        "max_age": max_age, "min_minutes": min_minutes, "rows": len(rows)}
    if rows:
        lead = rows[0]
        meta["deterministic_answer"] = (
            f"{lead['PLAYER']} leads players age {max_age} or younger in "
            f"usage rate at {lead['USG_PCT']:.1f}% in {season}. "
            f"Qualification: {min_minutes:,}+ total minutes; "
            f"{lead['MINUTES']:,} minutes in {lead['GP']} games.")
    return {"tool": "get_young_player_usage", "ok": True,
            "rows": rows, "meta": meta}

_TEAM_TOTAL_STATS = ("PTS", "REB", "AST", "STL", "BLK", "FG3M", "TOV")
_TEAM_TOTAL_COLUMNS = {
    "PTS": "points",
    "REB": "reboundsTotal",
    "AST": "assists",
    "STL": "steals",
    "BLK": "blocks",
    "FG3M": "threePointersMade",
    "TOV": "turnovers",
}

def _deduped_team_totals(stat: str, season: str):
    season = resolve_season(season)
    column = _TEAM_TOTAL_COLUMNS.get(stat)
    if column is None:
        return None
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_boxscores" not in tables:
            return None
        return con.execute(
            "SELECT MODE(TEAM_ID) AS TEAM_ID, teamTricode AS ABBREV, "
            f"SUM({column}) AS TOTAL, COUNT(DISTINCT GAME_ID) AS GP, "
            f"ROUND(SUM({column}) * 1.0 / COUNT(DISTINCT GAME_ID), 1) "
            "AS PER_GAME "
            "FROM silver_boxscores WHERE _season = ? "
            "AND SUBSTR(GAME_ID, 1, 3) = '002' "
            "AND TEAM_ID IS NOT NULL "
            "AND (comment IS NULL OR comment = '') "
            "GROUP BY teamTricode ORDER BY TOTAL DESC",
            [season]).fetchall()
    finally:
        con.close()

@tool(description='Team totals leaderboard for a counting stat (PTS, REB, AST, STL,\nBLK): player game logs summed by team, with per-game averages.\nUse for "which team leads in total assists" - get_leaders is\nplayer-level only.')
def get_team_leaders(stat_category: str = "AST",
                     season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    try:
        stat = clamp_stat(stat_category)
    except ValueError:
        stat = "PTS"
    if stat not in _TEAM_TOTAL_STATS:
        stat = "AST"
    fetched = _deduped_team_totals(stat, season)
    if fetched is None:
        return {"tool": "get_team_leaders", "ok": False,
                "error": "no team totals data in the warehouse"}
    from nba_api.stats.static import teams as _static
    names = {t["abbreviation"]: t["full_name"]
             for t in _static.get_teams()}

    _alias = {"PHO": "PHX", "CHO": "CHA", "BRK": "BKN"}
    rows = []
    for i, (team_id, abbrev, total, gp, per_game) in enumerate(fetched, 1):
        rows.append({
            "RANK": i,
            "TEAM_ID": int(team_id) if team_id is not None else None,
            "TEAM": names.get(_alias.get(abbrev, abbrev), abbrev),
            "ABBREV": abbrev,
            stat: int(total),
            "GP": int(gp),
            "PER_GAME": per_game,
        })
    leader = rows[0] if rows else None
    leader_line = (f"{leader['TEAM']} lead with {leader[stat]} total "
                   f"{stat} ({leader['PER_GAME']} per game over "
                   f"{leader['GP']} games)") if leader else ""
    meta = {"stat_category": stat, "season": season, "source": "warehouse",
            "rows": len(rows),
            "leader_line": leader_line,
            "note": "team totals summed from player game logs "
                    "(regular season). Cite the leader's TOTAL value "
                    "and per-game verbatim from leader_line - never "
                    "drop the total (QA: points narrative shipped "
                    "'scored the most points with total points and "
                    "122.1 per game', value missing)."}
    return {"tool": "get_team_leaders", "ok": True, "rows": rows,
            "meta": meta}

@tool(description='Top-N team compare on one counting stat: total, per-game, games\nplayed, and the win-loss record joined from standings, in one\nboard. Use for multi-metric team compares ("compare the top 3\nscoring teams: totals, per-game, and wins") - get_team_leaders has\nno records and a delegate fan-out composes nameless tables with\nempty cells or invented numbers (F66). The answer is built\ndeterministically from the rows into meta.deterministic_answer;\ncompose ships it verbatim (v67 design law).')
def get_team_compare(stat_category: str = "PTS", top: int = 3,
                     season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    try:
        stat = clamp_stat(stat_category)
    except ValueError:
        stat = "PTS"
    if stat not in _TEAM_TOTAL_STATS:
        stat = "PTS"
    try:
        top = max(2, min(int(top or 3), 10))
    except (TypeError, ValueError):
        top = 3
    fetched = _deduped_team_totals(stat, season)
    if fetched is None:
        return {"tool": "get_team_compare", "ok": False,
                "error": "no team totals data in the warehouse"}
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        records: dict[str, tuple[int, int]] = {}
        if "silver_standings" in tables:
            for city, name, w, loss in con.execute(
                    "SELECT TeamCity, TeamName, WINS, LOSSES "
                    "FROM silver_standings WHERE _season = ?",
                    [season]).fetchall():
                records[f"{city or ''} {name or ''}".strip()] = (
                    int(w or 0), int(loss or 0))
    finally:
        con.close()
    from nba_api.stats.static import teams as _static
    names = {t["abbreviation"]: t["full_name"]
             for t in _static.get_teams()}

    _alias = {"PHO": "PHX", "CHO": "CHA", "BRK": "BKN"}
    rows = []
    for i, (team_id, abbrev, total, gp, per_game) in enumerate(
            fetched[:top], 1):
        team = names.get(_alias.get(abbrev, abbrev), abbrev)
        w, loss = records.get(team, (None, None))
        rows.append({
            "RANK": i,
            "TEAM_ID": int(team_id) if team_id is not None else None,
            "TEAM": team,
            "ABBREV": abbrev,
            stat: int(total),
            "GP": int(gp),
            "PER_GAME": per_game,
            "W": w,
            "L": loss,
            "RECORD": f"{w}-{loss}" if w is not None else "",
        })
    if not rows:
        return {"tool": "get_team_compare", "ok": False,
                "error": f"no team totals for {season}"}
    leader = rows[0]
    answer = (f"{leader['TEAM']} lead with {leader[stat]} total {stat} "
              f"({leader['PER_GAME']} per game over {leader['GP']} "
              f"games)")
    if leader.get("RECORD"):
        answer += f" and a {leader['RECORD']} record"
    answer += "."
    if len(rows) > 1:
        parts = []
        for r in rows[1:]:
            part = (f"{r['TEAM']}: {r[stat]} total {stat} "
                    f"({r['PER_GAME']} per game)")
            if r.get("RECORD"):
                part += f", {r['RECORD']}"
            parts.append(part)
        answer += " " + "; ".join(parts) + "."
    meta = {"stat_category": stat, "season": season,
            "source": "warehouse", "rows": len(rows),
            "deterministic_answer": answer,
            "note": "deterministic deep-compare lane (F66): ship "
                    "deterministic_answer verbatim - totals and "
                    "per-game come from deduped player game logs, "
                    "records from standings. Never recompose these "
                    "numbers from scratch."}
    return {"tool": "get_team_compare", "ok": True, "rows": rows,
            "meta": meta}

@tool(description='Team four factors (eFG%, TOV%, ORB%, FT rate, plus defensive\nmirrors), computed offline from warehouse team game rows. Use for\n"why are the Thunder good", "team identity", or any four-factors\nask. Pass a team name/abbrev to scope to one team; empty returns\nthe full 30-team board.')
def get_team_four_factors(team: str = "", season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    try:
        _con = store.connect()
        try:
            tables = {r[0] for r in _con.execute("SHOW TABLES").fetchall()}
        finally:
            _con.close()
    except Exception as exc:
        return {"tool": "get_team_four_factors", "ok": False,
                "rows": [], "meta": {},
                "error": f"warehouse read failed: {str(exc)[:120]}"}
    if "silver_four_factors_team" not in tables:
        return {"tool": "get_team_four_factors", "ok": False,
                "rows": [], "meta": {"season": season},
                "error": "warehouse table missing: "
                         "silver_four_factors_team (run "
                         "scripts/build_team_four_factors.py)"}
    where, params = "_season = ?", [season]
    team_q = (team or "").strip()
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
                    "error": f"unknown team '{team_q}'"}
        where += " AND TEAM = ?"
        params.append(match["abbreviation"])
    try:
        rows = store._read_df(
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
    meta = {"season": season, "source": "warehouse",
            "rows": len(rows),
            "note": "computed offline from silver_team_games box "
                    "scores; eFG% = (FGM + 0.5*FG3M)/FGA, TOV% per "
                    "possession estimate, ORB% vs opponent DREB, "
                    "FTr = FTA/FGA. Quote figures verbatim."}
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
    season = resolve_season(season)
    from ._core import clamp_scope

    scope = clamp_scope(scope)
    rows, meta = _warehouse_or_live(
        f"silver_hustle_{scope}", "_season = ?",
        [season], lambda: nba_stats.hustle(scope, season), season,
    )
    return {"tool": "get_hustle", "ok": True, "rows": rows, "meta": meta}

@tool(description='RAPM-lite ratings. Blank player returns top list, else one row.')
def get_rapm(player: str = "", top: int = 10, season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
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
    out = [{"player_id": r[0], "name": r[1],
            "rapm": round(float(r[2] or 0), 2), "possessions": r[3]}
           for r in rows]
    return {"tool": "get_rapm", "ok": True, "rows": out,
            "meta": {"source": "rapm-lite (estimate)", "season": season,
                     "qualification": "players under 500 possessions "
                                      "excluded; estimates shrink "
                                      "toward the prior"}}

def _finder_result(rows: Any, season: str) -> dict[str, Any]:
    return {"tool": "get_finder", "ok": True, "rows": rows,
            "meta": {"source": "warehouse", "season": season}}

def _finder_error(error: str) -> dict[str, Any]:
    return {"tool": "get_finder", "ok": False, "error": error}

def _finder_history_rows(con, season: str, team_abbrev: str) -> list | None:
    if "silver_hist_gamelogs" not in _warehouse_tables(con):
        return None
    q = """SELECT team_abbreviation, game_date, matchup, wl, pts
           FROM silver_hist_gamelogs WHERE _season = ?"""
    cols = {r[1] for r in
            con.execute("PRAGMA table_info(silver_hist_gamelogs)").fetchall()}
    params: list[object] = [season]
    if "season_type" in cols:
        q += " AND season_type = 'regular-season'"
    if team_abbrev:
        q += " AND team_abbreviation = ?"
        params.append(team_abbrev.upper())
    return con.execute(q + " ORDER BY game_date", params).fetchall()

def _finder_player_pts(con, season: str, pid: int) -> list:
    return con.execute(
        """SELECT PTS FROM silver_player_gamelogs
        WHERE _season = ? AND Player_ID = ?""", [season, pid]).fetchall()

def _finder_streak_rows(rows: list) -> dict[str, Any]:
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
    return {"longest_win_streak": best_w, "longest_loss_streak": best_l,
            "games": len(rows)}

def _finder_versus_rows(rows: list, opponent: str) -> dict[str, Any]:
    opp = opponent.upper()
    rel = [r for r in rows if opp in (r[2] or "")]
    won = sum(1 for r in rel if r[3] == "W")
    return {"record": f"{won}-{len(rel) - won}", "games": len(rel)}

def _finder_span_best(rows: list, window: int):
    best = None
    for i in range(len(rows) - window + 1):
        chunk = rows[i:i + window]
        if len({c[0] for c in chunk}) > 1:
            continue
        total = sum(c[4] or 0 for c in chunk)
        if best is None or total > best[0]:
            best = (total, chunk[0][0], chunk[0][1], chunk[-1][1])
    return best

def _finder_span_rows(rows: list, window: int):
    best = _finder_span_best(rows, window)
    if best is None:
        return None
    return {"team": best[1], "window": window, "points": best[0],
            "from": best[2], "to": best[3]}

def _finder_player_game_rows(season: str, pid: int):
    with _owned_connection(None) as con:
        if "silver_player_gamelogs" not in _warehouse_tables(con):
            return "player gamelogs empty", None
        return None, con.execute(
            """SELECT GAME_DATE, PTS FROM silver_player_gamelogs
            WHERE _season = ? AND Player_ID = ?""", [season, pid]).fetchall()

def _finder_streak_key(clock: object):
    from datetime import datetime as _dt

    try:
        return _dt.strptime(str(clock), "%b %d, %Y")
    except (TypeError, ValueError):
        return _dt.min

def _finder_player_streak(season: str, team_abbrev: str):
    from ._core import coerce_player_id as _cpid

    if not team_abbrev:
        return _finder_error("player needed")
    try:
        pid = _cpid(team_abbrev)
    except ValueError as exc:
        return _finder_error(str(exc)[:160])
    err, prows = _finder_player_game_rows(season, pid)
    if err:
        return _finder_error(err)
    if not prows:
        return _finder_error(f"no cached games for player {pid}")
    prows = sorted(prows, key=lambda r: _finder_streak_key(r[0]))
    best = cur = 0
    for _, pts in prows:
        if (pts or 0) >= 20:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return _finder_result({"player_id": pid, "longest_20pt_streak": best,
                           "games": len(prows)}, season)

def _finder_head2head_player(season: str, pid: int) -> list:
    with _owned_connection(None) as con:
        return _finder_player_pts(con, season, pid)

def _finder_ppg(games: list) -> float:
    return round(sum((g[0] or 0) for g in games) / len(games), 1)

def _finder_head2head(season: str, team_abbrev: str, opponent: str):
    from ._core import coerce_player_id as _cpid2

    if not team_abbrev or not opponent:
        return _finder_error("two players needed")
    try:
        pa = _cpid2(team_abbrev)
        pb = _cpid2(opponent)
    except ValueError as exc:
        return _finder_error(str(exc)[:160])
    ra = _finder_head2head_player(season, pa)
    rb = _finder_head2head_player(season, pb)
    if not ra:
        return _finder_error(f"no cached games for player {team_abbrev}")
    if not rb:
        return _finder_error(f"no cached games for player {opponent}")
    return _finder_result(
        {"a": {"player_id": pa, "gp": len(ra), "ppg": _finder_ppg(ra)},
         "b": {"player_id": pb, "gp": len(rb), "ppg": _finder_ppg(rb)}},
        season)

@tool(description='Team finder across history seasons. Modes: streak, versus, span,\nplayer_streak, head2head.')
def get_finder(
    mode: str = "streak", team_abbrev: str = "", opponent: str = "",
    season: str | None = None, window: int = 5,
) -> dict[str, Any]:
    season = resolve_season(season)
    if mode == "player_streak":
        return _finder_player_streak(season, team_abbrev)
    if mode == "head2head":
        return _finder_head2head(season, team_abbrev, opponent)
    with _owned_connection(None) as con:
        rows = _finder_history_rows(con, season, team_abbrev)
    if rows is None:
        return _finder_error("history empty")
    if not rows:
        return _finder_error("no games found")
    if mode == "versus" and opponent:
        return _finder_result(_finder_versus_rows(rows, opponent), season)
    if mode == "span":
        span = _finder_span_rows(rows, window)
        return _finder_result(span, season) if span else _finder_error(
            "no span found")
    return _finder_result(_finder_streak_rows(rows), season)

@tool(description='Back-to-back plus rest-day splits from history game dates.')
def get_rest(team_abbrev: str = "", season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    from datetime import datetime

    from .. import store as _store

    con = _store.connect()
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
    from ._core import season_static as _season_static
    if _season_static(season):

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

ELO_START = 1500.0
ELO_K = 20.0
ELO_HCA_BUILD = 100
ELO_HCA_PREDICT = 65
ELO_PER_POINT = 28.0

def _elo_expected(diff: float) -> float:
    return 1 / (1 + 10 ** (-diff / 400))

def _elo_mov_mult(margin: float | None, diff: float) -> float:
    if margin is None:
        return 1.0
    return ((abs(margin) + 3) ** 0.8) / (7.5 + 0.006 * abs(diff))

def _elo_game_shift(w_elo: float, l_elo: float, w_home: bool,
                    l_home: bool, margin: float | None,
                    k: float = ELO_K) -> float:
    w_adj = w_elo + (ELO_HCA_BUILD if w_home else 0)
    l_adj = l_elo + (ELO_HCA_BUILD if l_home else 0)
    diff = w_adj - l_adj
    return k * _elo_mov_mult(margin, diff) * (1 - _elo_expected(diff))

def _build_elo(rows: list) -> tuple:
    games: dict[str, list] = {}
    for r in rows:
        games.setdefault(r[1], []).append(r)
    elo: dict[str, float] = {}
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    mov_ok = False
    for _, pair in sorted(games.items()):
        if len(pair) != 2:
            continue
        (ta, _, _, ma, wa, pma), (tb, _, _, mb, wb, pmb) = pair
        if (wa == "W") == (wb == "W"):
            continue
        wrow, lrow = (pair[0], pair[1]) if wa == "W" else (pair[1], pair[0])
        wteam, lteam = wrow[0], lrow[0]
        margin = wrow[5]
        if margin is None:
            margin = -(lrow[5]) if lrow[5] is not None else None
        if margin is not None:
            margin = abs(margin)
            mov_ok = True
        elo.setdefault(wteam, ELO_START)
        elo.setdefault(lteam, ELO_START)
        wins[wteam] = wins.get(wteam, 0) + 1
        losses[lteam] = losses.get(lteam, 0) + 1
        shift = _elo_game_shift(elo[wteam], elo[lteam],
                                "vs." in str(wrow[3]),
                                "vs." in str(lrow[3]), margin)
        elo[wteam] += shift
        elo[lteam] -= shift
    return elo, wins, losses, mov_ok

@tool(description='Real ELO win probability between two abbreviations. Neutral unless home_abbrev matches a side.')
def get_win_prob(team_a: str = "", team_b: str = "", season: str | None = None,
                 home_abbrev: str = "") -> dict[str, Any]:
    season = resolve_season(season)
    from .. import store as _store

    if not team_a or not team_b:
        return {"tool": "get_win_prob", "ok": False, "error": "two abbreviations needed"}
    a, b = team_a.upper(), team_b.upper()
    home = (home_abbrev or "").upper()
    con = _store.connect()
    try:
        rows = con.execute(
            """SELECT team_abbreviation, game_id, game_date, matchup, wl,
            plus_minus FROM silver_hist_gamelogs
            WHERE _season = ? ORDER BY game_date, game_id""",
            [season],
        ).fetchall()
    finally:
        con.close()
    rows = [r for r in rows if is_scope_game(r[1], "regular")]
    elo, _, _, _ = _build_elo(rows)
    ra, rb = elo.get(a, ELO_START), elo.get(b, ELO_START)
    ra_adj, rb_adj = ra, rb
    if home == a:
        ra_adj += ELO_HCA_PREDICT
    elif home == b:
        rb_adj += ELO_HCA_PREDICT
    pa = _elo_expected(ra_adj - rb_adj)
    return {"tool": "get_win_prob", "ok": True,
            "rows": {"win_prob": {a: round(pa, 3), b: round(1 - pa, 3)},
                     "elo_a": round(ra), "elo_b": round(rb)},
            "meta": {"source": "warehouse", "season": season,
                     "elo": "538-style MOV-adjusted (K20, HCA100 in build)",
                     "home_edge": 65 if home in (a, b) else 0}}

CAP = {"cap": 165_000_000, "tax": 201_048_000,
       "apron1": 209_661_000, "apron2": 222_372_000}

def _team_salary_lookup(con, name: str) -> str | None:
    from ._core import season_static as _season_static

    if not (_season_static(last_completed_season())
            and "silver_salaries" in _warehouse_tables(con)):
        return None
    try:
        row = con.execute(
            "SELECT TEAM FROM silver_salaries "
            "WHERE LOWER(PLAYER_NAME) = LOWER(?) LIMIT 1", [name]).fetchone()
    except Exception:
        return None
    return str(row[0]) if row and row[0] else None

def _team_leaders_lookup(con, name: str, tables: set[str]) -> str | None:
    if not name or "silver_leaders_pts" not in tables:
        return None
    try:
        row = con.execute(
            "SELECT TEAM FROM silver_leaders_pts "
            "WHERE _season = ? AND LOWER(PLAYER) = LOWER(?) LIMIT 1",
            [last_completed_season(), name]).fetchone()
    except Exception:
        return None
    return str(row[0]) if row and row[0] else None

def _player_id_lookup(con, name: str, tables: set[str]) -> object:
    if not name or "silver_leaders_pts" not in tables:
        return None
    try:
        found = con.execute(
            "SELECT PLAYER_ID FROM silver_leaders_pts "
            "WHERE LOWER(PLAYER) = LOWER(?) LIMIT 1", [name]).fetchone()
    except Exception:
        return None
    return int(found[0]) if found and found[0] is not None else None

def _gamelog_team_lookup(con, pid: object, tables: set[str]) -> str | None:
    if pid is None or "silver_player_gamelogs" not in tables:
        return None
    for where, params in (
            ("Player_ID = ? AND _season = ?", [pid, last_completed_season()]),
            ("Player_ID = ?", [pid])):
        try:
            row = con.execute(
                f"SELECT MATCHUP FROM silver_player_gamelogs "
                f"WHERE {where} LIMIT 1", params).fetchone()
        except Exception:
            row = None
        if row and row[0]:
            return str(row[0]).split()[0].upper()
        if row:
            break
    return None

def _warehouse_tables(con) -> set[str]:
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}

@contextmanager
def _owned_connection(con: object):
    if con is not None:
        yield con
        return
    own = store.connect()
    try:
        yield own
    finally:
        try:
            own.close()
        except Exception:
            pass

def _current_team_for_player(
    player_name: str, player_id: object = None, fallback: str = "",
    con: object = None,
) -> str:
    name = str(player_name or "").strip()
    try:
        with _owned_connection(con) as live:
            tables = _warehouse_tables(live)
            for found in (_team_salary_lookup(live, name),
                          _team_leaders_lookup(live, name, tables)):
                if found:
                    return found
            pid = player_id
            if pid is None:
                pid = _player_id_lookup(live, name, tables)
            abbr = _gamelog_team_lookup(live, pid, tables)
            if abbr:
                return abbr
    except Exception:
        return fallback
    return fallback

def _first_name_compatible(want: str, cand: str) -> bool:
    import difflib as _dl

    a = (want or "").lower().strip()
    b = (cand or "").lower().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and b.startswith(a):
        return True
    if len(b) >= 4 and a.startswith(b):
        return True
    return _dl.SequenceMatcher(None, a, b).ratio() >= 0.9

def _salary_sheet_rows(con: object) -> list | None:
    try:
        if "silver_salaries" not in _warehouse_tables(con):
            return None
        return con.execute(
            "SELECT PLAYER_NAME, SALARY, TEAM FROM silver_salaries").fetchall()
    except Exception:
        return None

def _name_match_tiers(rows: list, wl: str) -> tuple[list, list, list]:
    import difflib as _dl

    exact = [r for r in rows if str(r[0]).lower() == wl]
    subs = [r for r in rows if wl in str(r[0]).lower() and r not in exact]
    lows = [str(r[0]).lower() for r in rows]
    try:
        fuzzy = [r for m in _dl.get_close_matches(wl, lows, n=3, cutoff=0.8)
                 for r in rows
                 if str(r[0]).lower() == m and r not in exact and r not in subs]
    except Exception:
        fuzzy = []
    return exact, subs, fuzzy

def _stale_candidate_team(cand: tuple, con: object) -> str:
    cname, cteam = str(cand[0]), str(cand[2] or "")
    try:
        return _current_team_for_player(cname, None, cteam, con)
    except Exception:
        return cteam

def _resolve_stale_trade_player(want: str, team: str,
                                con: object = None) -> tuple[str, int] | None:
    target = str(team or "").upper()
    w = str(want or "").strip()
    if not w or not target:
        return None
    try:
        with _owned_connection(con) as live:
            rows = _salary_sheet_rows(live)
            if rows is None:
                return None
            wl = w.lower()
            exact, subs, fuzzy = _name_match_tiers(rows, wl)
            wl_first = wl.split()[0] if wl.split() else ""
            strict = len(exact) + len(subs)
            for i, cand in enumerate(exact + subs + fuzzy):
                cname = str(cand[0])
                if i >= strict:
                    c_first = cname.lower().split()[0] if cname.split() else ""
                    if not _first_name_compatible(wl_first, c_first):
                        continue
                if str(_stale_candidate_team(cand, live)).upper() == target:
                    return cname, int(cand[1] or 0)
    except Exception:
        return None
    return None

def _first_token(text: str) -> str:
    parts = str(text or "").lower().split()
    return parts[0] if parts else ""

def _locate_player_team(name: str, con: object) -> tuple[str, str, int] | None:
    w = str(name or "").strip().lower()
    if not w:
        return None
    rows = _salary_sheet_rows(con)
    if rows is None:
        return None
    exact, subs, loose = _name_match_tiers(rows, w)
    fuzzy = [r for r in loose
             if _first_name_compatible(_first_token(w), _first_token(str(r[0])))]
    for cand in (exact + subs + fuzzy)[:1]:
        cname, csal, cteam = str(cand[0]), int(cand[1] or 0), str(cand[2] or "")
        cur = _stale_candidate_team(cand, con)
        return cname, str(cur or cteam).upper(), csal
    return None

def _norm_trade_teams(team_a: str, team_b: str) -> tuple[str, str] | None:
    from .competitive import _resolve_team_abbr

    a = _resolve_team_abbr(team_a) or str(team_a or "").strip().upper()
    b = _resolve_team_abbr(team_b) or str(team_b or "").strip().upper()
    if a and b and a == b:
        return None
    return a, b

def _auto_correct_side(unks: list[str], old_team: str, plist: str,
                       con: object, season: str | None = None):
    located = []
    for u in unks:
        base = u.split(" (suggestions")[0].strip()
        hit = _locate_player_team(base, con)
        if hit is None:
            return None
        located.append((base,) + hit)
    new_teams = {t for _, _, t, _ in located}
    if len(new_teams) != 1:
        return None
    new_team = new_teams.pop()
    if new_team == str(old_team).upper():
        return None
    matched = _match_trade_players(new_team, plist, con, season)
    corrections = [
        f"{cname} is on {t} per the 2026-27 salary sheet "
        f"(not {str(old_team).upper()}); computed for the corrected team"
        for base, cname, t, _s in located
    ]
    return new_team, matched, corrections

class SalaryColumnError(RuntimeError):
    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(detail)


def _resolve_salary_column(scols: set[str], season: str | None) -> str:
    if "SALARY" in scols:
        return "SALARY"
    if season:
        want = "SALARY_" + str(season).strip().replace("-", "_")
        if want in scols:
            return want
    return ""


def _payroll(team: str, con: object = None,
             season: str | None = None) -> tuple[int, list[dict]]:
    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" in tables:
            scols = [r[1] for r in con.execute(
                "PRAGMA table_info(silver_salaries)").fetchall()]
            scol = _resolve_salary_column(set(scols), season)
            if not scol:
                raise SalaryColumnError(
                    "salary_column_unmatched",
                    f"silver_salaries has no salary column for season "
                    f"{season or 'unknown'}")
            rows = con.execute(
                f"SELECT PLAYER_NAME, {scol} FROM silver_salaries "
                "WHERE TEAM = ?",
                [team.upper()],
            ).fetchall()
            if rows:
                players = [{"player": r[0], "salary": r[1]} for r in rows]
                return sum(r[1] or 0 for r in rows), players
        if "silver_cap_players" in tables:
            rows = con.execute(
                """SELECT player, salary FROM silver_cap_players
                WHERE team = ?""",
                [team.upper()],
            ).fetchall()
        else:
            rows = []
    finally:
        if own:
            con.close()
    players = [{"player": r[0], "salary": r[1]} for r in rows]
    return sum(r[1] or 0 for r in rows), players

def _apron_state(payroll: int) -> dict[str, object]:
    return {
        "over_tax": payroll > CAP["tax"],
        "over_apron1": payroll > CAP["apron1"],
        "over_apron2": payroll > CAP["apron2"],
        "room_apron1": CAP["apron1"] - payroll,
        "room_apron2": CAP["apron2"] - payroll,
    }

def _allowed_incoming(outgoing: int, over_apron1: bool) -> tuple[int, str]:
    if over_apron1:
        return outgoing, "100% (above the first apron)"
    return int(outgoing * 1.25 + 250_000), "125% plus $250k (below the first apron)"

def _salary_vintage(con: object = None) -> tuple[str, int, str | None]:
    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            return "", 0, None
        row = con.execute(
            "SELECT _season, COUNT(*), MAX(_fetched_at) FROM silver_salaries "
            "GROUP BY _season ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "", 0, None
        return str(row[0] or ""), int(row[1] or 0), row[2]
    except Exception:
        return "", 0, None
    finally:
        if own:
            con.close()

def _payroll_source(con: object = None) -> str:
    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" in tables:
            season, n, fetched = _salary_vintage(con)
            if n > 300 and season:
                date = f", fetched {str(fetched)[:10]}" if fetched else ""
                return (f"basketball-reference contracts "
                        f"({season} salaries{date}; "
                        f"some players missing or estimated)")
    finally:
        if own:
            con.close()
    return "orojas119/nba-salary-cap (estimated)"

def _salary_date(con: object = None) -> str | None:
    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table in ("silver_salaries", "silver_cap_players"):
            if table not in tables:
                continue
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            if "_fetched_at" not in cols:
                continue
            row = con.execute(f"SELECT MAX(_fetched_at) FROM {table}").fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        return None
    finally:
        if own:
            con.close()
    return None

@tool(description='Payroll plus apron room for one abbreviation. 2026-27 thresholds.')
def get_cap_ledger(team: str = "") -> dict[str, Any]:
    if not team:
        return {"tool": "get_cap_ledger", "ok": False, "error": "team needed"}
    from nba_api.stats.static import teams as _teams
    from ._core import coerce_team_id
    try:
        team_id = coerce_team_id(team)
        team = next(
            item["abbreviation"] for item in _teams.get_teams()
            if item["id"] == team_id)
    except (ValueError, StopIteration):
        return {"tool": "get_cap_ledger", "ok": False,
                "error": f"unknown team: {team}"}
    from .. import store as _store

    con = _store.connect()
    try:
        try:
            total, players = _payroll(team, con)
        except SalaryColumnError as exc:
            return {"tool": "get_cap_ledger", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        source = _payroll_source(con)
        salary_date = _salary_date(con)
        season, _, _ = _salary_vintage(con)
    finally:
        con.close()
    return {"tool": "get_cap_ledger", "ok": True,
            "rows": {"team": team.upper(), "payroll": total,
                     "players": sorted(players, key=lambda p: p["salary"] or 0,
                                       reverse=True)[:15],
                     "room_under_apron2": CAP["apron2"] - total,
                     "over_tax": total > CAP["tax"]},
            "meta": {"source": source, "season": season or "2026-27",
                     "salary_date": salary_date,
                     **{k: v for k, v in CAP.items()}}}

class _RosterIndex:

    __slots__ = ("roster", "lows", "by_low", "disp")

    def __init__(self, roster: list[dict]) -> None:
        import difflib as _dl

        self.roster = roster
        self.lows = [p["player"].lower() for p in roster]
        self.by_low = {p["player"].lower(): p for p in roster}
        self.disp = {p["player"].lower(): p["player"] for p in roster}

    def close_hit(self, w: str) -> dict | None:
        import difflib as _dl

        hit = next((p for p in self.roster if w in p["player"].lower()), None)
        if hit is not None:
            return hit
        fb = _dl.get_close_matches(w, self.lows, n=1, cutoff=0.8)
        if fb and _first_name_compatible(_first_token(w), _first_token(fb[0])):
            return self.by_low[fb[0]]
        return None

    def suggestions(self, w: str) -> list[str]:
        import difflib as _dl

        return [self.disp[s]
                for s in _dl.get_close_matches(w, self.lows, n=2, cutoff=0.6)
                if _first_name_compatible(_first_token(w), _first_token(s))]

def _match_trade_player(orig: str, team: str, index: _RosterIndex,
                        con: object) -> tuple[str, int] | None:
    hit = index.close_hit(orig.lower())
    if hit:
        return hit["player"], hit["salary"] or 0
    return _resolve_stale_trade_player(orig, team, con)

def _unknown_trade_name(orig: str, index: _RosterIndex) -> str:
    sug = index.suggestions(orig.lower())
    return f"{orig} (suggestions: {', '.join(sug)})" if sug else orig

def _match_trade_players(team: str, names: str,
                         con: object = None,
                         season: str | None = None) -> tuple[int, list[str], list[str]]:
    with _owned_connection(con) as live:
        _, roster = _payroll(team, live, season)
        index = _RosterIndex(roster)
        matched: list[str] = []
        unknown: list[str] = []
        total_out = 0
        for orig in [n.strip() for n in names.split(",") if n.strip()]:
            found = _match_trade_player(orig, team, index, live)
            if found:
                matched.append(found[0])
                total_out += found[1]
            else:
                unknown.append(_unknown_trade_name(orig, index))
    return total_out, matched, unknown

def _unknown_player_hints(unknown: list[str], con: object = None) -> list[str]:
    hints: list[str] = []
    from .. import store as _store2

    own = con is None
    try:
        if own:
            con2 = _store2.connect()
        else:
            con2 = con
        try:
            for u in unknown:
                base = u.split(" (suggestions")[0].strip()
                bits = [b for b in base.split() if len(b) > 1]
                like = "%" + "%".join(bits[:2]) + "%" if bits else base
                hit = con2.execute(
                    """SELECT TEAM, PLAYER_NAME FROM silver_salaries
                    WHERE PLAYER_NAME LIKE ? LIMIT 1""",
                    [like],
                ).fetchone()
                if hit:
                    try:
                        cur = _current_team_for_player(
                            str(hit[1]), None, str(hit[0]), con2)
                    except Exception:
                        cur = hit[0]
                    hints.append(f"{base} is on {cur} per salary data")
        finally:
            if own:
                con2.close()
    except Exception:
        pass
    return hints

PICK_VALUE_M: dict[int, float] = {
    1: 45.0, 2: 38.0, 3: 32.0, 4: 28.0, 5: 25.0,
    6: 18.0, 7: 18.0, 8: 18.0, 9: 18.0, 10: 18.0,
    11: 12.0, 12: 12.0, 13: 12.0, 14: 12.0,
    15: 8.0, 16: 8.0, 17: 8.0, 18: 8.0, 19: 8.0, 20: 8.0,
    21: 5.0, 22: 5.0, 23: 5.0, 24: 5.0, 25: 5.0,
    26: 5.0, 27: 5.0, 28: 5.0, 29: 5.0, 30: 5.0,
}

def _pick_value_for_slot(slot: int, is_frp: bool) -> float:
    if is_frp:
        return PICK_VALUE_M.get(max(1, min(slot, 30)), 5.0)
    if 31 <= slot <= 40:
        return 2.5
    return 1.0

_TRADE_CHECK_UNMODELED = (
    "cash in trade", "prior trade exceptions", "taxpayer midlevel hard cap",
    "frozen pick plus Stepien",
    "base-year plus trade-kicker plus minimum-salary plus sign-and-trade",
)

def _trade_guard_vintage_error(con, season: str) -> str | None:
    salary_season, salary_rows, _ = _salary_vintage(con)
    if not (salary_rows and salary_season and salary_season != season):
        return None
    return (f"salary data is for {salary_season}, not {season}; "
            "trade math was not calculated")

def _trade_guard_team_error(con, team: str, players: str) -> str | None:
    for player in [x.strip() for x in str(players).split(",") if x.strip()]:
        row = con.execute(
            "SELECT TEAM FROM silver_salaries WHERE lower(PLAYER_NAME) = lower(?) LIMIT 1",
            [player]).fetchone()
        if row and str(row[0] or "").upper() != team.upper():
            return (f"salary data lists {player} with {row[0]}, "
                    f"not {team.upper()}; trade math was not calculated")
    return None

def _trade_guard(con, season: str, team_a: str, players_a: str, team_b: str,
                 players_b: str) -> str | None:
    guard_error = _trade_guard_vintage_error(con, season)
    if guard_error:
        return guard_error
    for team, players in ((team_a, players_a), (team_b, players_b)):
        if not team:
            continue
        team_error = _trade_guard_team_error(con, team, players)
        if team_error:
            return team_error
    return None

def _infer_trade_side(plist: str, con: object) -> str:
    teams: set[str] = set()
    for nm in [x.strip() for x in str(plist).split(",") if x.strip()]:
        hit = _locate_player_team(nm, con)
        if hit is None:
            return ""
        teams.add(str(hit[1]))
    return teams.pop() if len(teams) == 1 else ""

def _trade_unknown_message(team_a: str, unk_a: list[str], team_b: str,
                           unk_b: list[str], con: object) -> str:
    parts = []
    if unk_a:
        parts.append(f"{team_a.upper()}: {'; '.join(unk_a)}")
    if unk_b:
        parts.append(f"{team_b.upper()}: {'; '.join(unk_b)}")
    msg = "unknown players: " + " | ".join(parts)
    hints = _unknown_player_hints(unk_a + unk_b, con)
    return msg + ". " + "; ".join(hints) if hints else msg

def _trade_autocorrect_side(unknown: list[str], team: str, plist: str,
                            con: object, matched: tuple,
                            season: str | None = None) -> tuple:
    if not unknown:
        return team, matched, []
    fix = _auto_correct_side(unknown, team, plist, con, season)
    if not fix:
        return team, matched, []
    return fix

def _trade_match_sides(team_a: str, players_a: str, team_b: str,
                       players_b: str, con: object,
                       season: str | None = None):
    side_a = _match_trade_players(team_a, players_a, con, season)
    side_b = _match_trade_players(team_b, players_b, con, season)
    corrections: list[str] = []
    team_a, side_a, corr_a = _trade_autocorrect_side(
        side_a[2], team_a, players_a, con, side_a, season)
    corrections.extend(corr_a)
    team_b, side_b, corr_b = _trade_autocorrect_side(
        side_b[2], team_b, players_b, con, side_b, season)
    corrections.extend(corr_b)
    return team_a, side_a, team_b, side_b, corrections

def _trade_side_rows(team: str, side: tuple, payroll: int, state: dict,
                     allow: int, rule: str) -> dict[str, Any]:
    return {"team": team.upper(), "out": side[0], "players": side[1],
            "payroll": payroll, "allowed_in": allow, "match_rule": rule,
            **{k: v for k, v in state.items()}}

def _trade_check_issues(team_a: str, state_a: dict, names_a: list[str],
                        team_b: str, state_b: dict, names_b: list[str],
                        out_a: int, allow_a: int, out_b: int,
                        allow_b: int) -> list[str]:
    issues = []
    if state_a["over_apron2"] and len(names_a) > 1:
        issues.append(f"{team_a.upper()} cannot aggregate above second apron")
    if state_b["over_apron2"] and len(names_b) > 1:
        issues.append(f"{team_b.upper()} cannot aggregate above second apron")
    if out_b > allow_a:
        issues.append(f"{team_a.upper()} takes back too much")
    if out_a > allow_b:
        issues.append(f"{team_b.upper()} takes back too much")
    return issues

def _trade_check_checks(team_a: str, rule_a: str, team_b: str,
                        rule_b: str) -> list[dict[str, Any]]:
    return [
        {"rule": "salary matching", "checked": True,
         "note": f"{team_a.upper()} {rule_a}, {team_b.upper()} {rule_b}"},
        {"rule": "second apron aggregation ban", "checked": True,
         "note": "multi player out banned above second apron"},
        *({"rule": rule, "checked": False, "note": "not modeled"}
          for rule in _TRADE_CHECK_UNMODELED),
    ]

@tool(description='Trade legality check. Player names comma separated per side.\n\nSimplified 2023 CBA: 125 percent plus 250k matching below the first\napron, 100 percent above it, no aggregation above the second apron.\nPicks and exceptions stay out of v1.')
def get_trade_check(
    team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "",
    season: str | None = None,
) -> dict[str, Any]:

    season = resolve_season(season)
    if not players_a and not players_b:
        return {"tool": "get_trade_check", "ok": False,
                "error": "two teams needed"}

    with _owned_connection(None) as guard_con:
        guard_error = _trade_guard(guard_con, season, team_a, players_a,
                                   team_b, players_b)
    if guard_error:
        return {"tool": "get_trade_check", "ok": False, "error": guard_error}

    if (not team_a or not team_b) and players_a and players_b:
        with _owned_connection(None) as infer_con:
            team_a = team_a or _infer_trade_side(players_a, infer_con)
            team_b = team_b or _infer_trade_side(players_b, infer_con)
    if not team_a or not team_b:
        return {"tool": "get_trade_check", "ok": False,
                "error": "two teams needed"}
    norm = _norm_trade_teams(team_a, team_b)
    if norm is None:
        return {"tool": "get_trade_check", "ok": False,
                "error": (f"both sides resolve to the same team "
                          f"({team_a} / {team_b}) - a trade needs two "
                          f"different teams; check the team names")}
    team_a, team_b = norm

    with _owned_connection(None) as con:
        try:
            team_a, side_a, team_b, side_b, corrections = _trade_match_sides(
                team_a, players_a, team_b, players_b, con, season)
        except SalaryColumnError as exc:
            return {"tool": "get_trade_check", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        out_a, names_a, unk_a = side_a
        out_b, names_b, unk_b = side_b
        if unk_a or unk_b:
            return {"tool": "get_trade_check", "ok": False,
                    "error": _trade_unknown_message(
                        team_a, unk_a, team_b, unk_b, con)}
        if not names_a or not names_b:

            empty = team_a.upper() if not names_a else team_b.upper()
            return {"tool": "get_trade_check", "ok": False,
                    "error": (f"no players matched on the {empty} side - "
                              f"not grading a one-sided 'trade'. If you "
                              f"meant a past real-world trade, say which "
                              f"teams and players were in it.")}
        pay_a, _ = _payroll(team_a, con, season)
        pay_b, _ = _payroll(team_b, con, season)
        salary_date = _salary_date(con)
        source = _payroll_source(con)
    state_a = _apron_state(pay_a)
    state_b = _apron_state(pay_b)
    allow_a, rule_a = _allowed_incoming(out_a, bool(state_a["over_apron1"]))
    allow_b, rule_b = _allowed_incoming(out_b, bool(state_b["over_apron1"]))
    issues = _trade_check_issues(team_a, state_a, names_a, team_b, state_b,
                                 names_b, out_a, allow_a, out_b, allow_b)
    return {"tool": "get_trade_check", "ok": True,
            "rows": {"team_a": _trade_side_rows(
                         team_a, side_a, pay_a, state_a, allow_a, rule_a),
                     "team_b": _trade_side_rows(
                         team_b, side_b, pay_b, state_b, allow_b, rule_b),
                     "legal": not issues, "issues": issues,
                     "checks": _trade_check_checks(team_a, rule_a, team_b,
                                                   rule_b),
                     "salary_date": salary_date,
                     **({"attribution_corrections": corrections}
                        if corrections else {}),
                     "disclaimer": "Estimate only, rules simplified. Skips cash, "
                     "prior trade exceptions, taxpayer midlevel, frozen pick, Stepien, "
                     "base-year, trade-kicker, minimum-salary, and sign-and-trade rules. "
                     "Confirm with a cap specialist."},
            "meta": {"source": source, "rules": "v1-simplified",
                     "salary_date": salary_date}}

_TRADE_VALUE_WEIGHTS = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
                        "STL": 2.0, "BLK": 2.0, "TOV": -1.5}

_TRADE_LEADERS_COLUMNS = ["PLAYER", "GP", "PTS", "REB", "AST", "STL",
                         "BLK", "TOV", "FG3M", "FG3_PCT"]

_TRADE_RANK_COLUMNS = ["OFF_RATING_RANK", "DEF_RATING_RANK",
                       "NET_RATING_RANK", "TS_PCT_RANK", "AST_PCT_RANK",
                       "REB_PCT_RANK"]

_TRADE_NEED_COLUMNS = [("need_offense", "OFF_RATING_RANK"),
                       ("need_defense", "DEF_RATING_RANK"),
                       ("need_shooting", "TS_PCT_RANK"),
                       ("need_playmaking", "AST_PCT_RANK"),
                       ("need_rebounding", "REB_PCT_RANK")]

_TRADE_TAG_NEEDS = {"spacer": "need_shooting",
                    "playmaker": "need_playmaking",
                    "defensive playmaker": "need_defense",
                    "efficient scorer": "need_offense",
                    "high-usage creator": "need_offense"}

def _trade_value_norm(s: object) -> str:
    import unicodedata as _ud

    return "".join(c for c in _ud.normalize("NFKD", str(s or ""))
                   if not _ud.combining(c)).strip().lower()

class _TradeWarehouse:

    __slots__ = ("tables", "cols", "gaps")

    def __init__(self, con, prod_season: str, sal_season: str) -> None:
        self.tables = _warehouse_tables(con)
        self.cols = {t: {r[1] for r in
                         con.execute(f"PRAGMA table_info({t})").fetchall()}
                     for t in self.tables if t.startswith("silver_")}
        self.gaps: list[str] = []

    def missing(self, table: str, required: list[str]) -> list[str]:
        have = self.cols.get(table, set())
        return [c for c in required if c not in have]

    def has_leaders(self) -> bool:
        return "silver_leaders_pts" in self.tables

    def note(self, text: str) -> None:
        self.gaps.append(text)

def _trade_leader_rows(con, prod_season: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for r in con.execute(
            "SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV,"
            " FG3M, FG3_PCT FROM silver_leaders_pts WHERE _season = ?",
            [prod_season]).fetchall():
        rows.setdefault(_trade_value_norm(r[0]), {
            "name": r[0], "team": r[1], "gp": r[2] or 0,
            "tot": {"PTS": r[3] or 0, "REB": r[4] or 0, "AST": r[5] or 0,
                    "STL": r[6] or 0, "BLK": r[7] or 0, "TOV": r[8] or 0},
            "fg3m": r[9] or 0, "fg3_pct": r[10]})
    return rows

def _trade_leader_weights(warehouse: _TradeWarehouse) -> dict[str, float]:
    missing = warehouse.missing("silver_leaders_pts", _TRADE_LEADERS_COLUMNS)
    if missing:
        warehouse.note(
            "silver_leaders_pts missing columns skipped at zero weight: "
            + ", ".join(missing))
    return {c: (0.0 if c in missing else w)
            for c, w in _TRADE_VALUE_WEIGHTS.items()}

def _trade_adv_rows(con, warehouse: _TradeWarehouse,
                    prod_season: str) -> dict[str, dict]:
    if "silver_advanced" not in warehouse.tables:
        warehouse.note("silver_advanced missing: age, TS_PCT, USG_PCT "
                       "and NET_RATING unavailable")
        return {}
    missing = warehouse.missing(
        "silver_advanced", ["PLAYER_NAME", "AGE", "TS_PCT", "USG_PCT"])
    if missing:
        warehouse.note("silver_advanced missing columns: " + ", ".join(missing))
    rows: dict[str, dict] = {}
    for r in con.execute(
            "SELECT PLAYER_NAME, AGE, TS_PCT, USG_PCT FROM "
            "silver_advanced WHERE _season = ?", [prod_season]).fetchall():
        rows.setdefault(_trade_value_norm(r[0]),
                        {"age": r[1], "ts": r[2], "usg": r[3]})
    return rows

def _trade_salary_column(scols: set[str]) -> str:
    if "SALARY" in scols:
        return "SALARY"
    return next((c for c in scols if "SALARY" in c.upper()), "")

def _trade_season_scoped(table: str, name_col: str, val_col: str,
                         scols: set[str], sal_season: str):
    if "_season" in scols:
        return (f"SELECT {name_col}, {val_col} FROM {table} WHERE _season = ?",
                [sal_season])
    return f"SELECT {name_col}, {val_col} FROM {table}", []

def _trade_sheet_salaries(con, warehouse: _TradeWarehouse,
                          sal_season: str) -> dict[str, int]:
    salaries: dict[str, int] = {}
    for table, name_col, val_col in (
            ("silver_salaries", "PLAYER_NAME", None),
            ("silver_cap_players", "player", "salary")):
        if table not in warehouse.tables:
            continue
        scols = warehouse.cols.get(table, set())
        val = val_col or _trade_salary_column(scols)
        if not val:
            continue
        query, params = _trade_season_scoped(table, name_col, val, scols,
                                             sal_season)
        for r in con.execute(query, params).fetchall():
            if r[1] is not None:
                salaries.setdefault(_trade_value_norm(r[0]), int(r[1]))
    return salaries

def _trade_team_id_to_abbr() -> dict:
    try:
        from nba_api.stats.static import teams as _static

        return {t["id"]: t["abbreviation"] for t in _static.get_teams()}
    except Exception:
        return {}

def _trade_rating_rows(con, warehouse: _TradeWarehouse,
                       prod_season: str) -> dict[str, dict]:
    if "silver_team_ratings" not in warehouse.tables:
        warehouse.note("silver_team_ratings missing: pick slots assumed "
                       "mid-first and team needs unavailable")
        return {}
    have = warehouse.cols.get("silver_team_ratings", set())
    ranks = [c for c in _TRADE_RANK_COLUMNS if c in have]
    if len(ranks) < len(_TRADE_RANK_COLUMNS):
        warehouse.note("silver_team_ratings missing columns: " + ", ".join(
            c for c in _TRADE_RANK_COLUMNS if c not in ranks))
    names = ["TEAM_ID", "TEAM_NAME"] + ranks
    id_to_abbr = _trade_team_id_to_abbr()
    ratings: dict[str, dict] = {}
    for r in con.execute(
            f"SELECT {', '.join(names)} FROM silver_team_ratings "
            f"WHERE _season = ?", [prod_season]).fetchall():
        row = dict(zip(names, r))
        abbr = id_to_abbr.get(row["TEAM_ID"], "")
        if abbr:
            ratings[str(abbr).upper()] = row
    return ratings

def _trade_dollars_per_point(leaders: dict, salaries: dict,
                             use_w: dict[str, float]) -> float:
    total = score = 0.0
    for key, lead in leaders.items():
        gp = lead["gp"]
        if gp < 20 or key not in salaries:
            continue
        total += salaries[key]
        score += sum(lead["tot"][c] / gp * use_w[c] for c in use_w)
    return (total / score) if score > 0 else 0.0

def _trade_archetypes(lead: dict, gp: int, advanced: dict) -> list[str]:
    per = {c: lead["tot"][c] / gp for c in lead["tot"]}
    tags = []
    if (lead["fg3m"] or 0) / gp >= 2.0:
        tags.append("spacer")
    if per["AST"] >= 5.0:
        tags.append("playmaker")
    if per["STL"] + per["BLK"] >= 1.5:
        tags.append("defensive playmaker")
    if advanced.get("ts") is not None and advanced["ts"] >= 0.60:
        tags.append("efficient scorer")
    if advanced.get("usg") is not None and advanced["usg"] >= 0.28:
        tags.append("high-usage creator")
    return tags

def _trade_value_player(display: str, leaders: dict, adv: dict,
                        salaries: dict, use_w: dict, dpp: float,
                        gaps: list[str]) -> dict[str, Any]:
    key = _trade_value_norm(display)
    lead = leaders.get(key)
    advanced = adv.get(key, {})
    gp = lead["gp"] if lead else 0
    out: dict[str, Any] = {
        "name": display, "salary_26_27": salaries.get(key),
        "age": advanced.get("age"), "gp": gp,
        "ppg": round(lead["tot"]["PTS"] / gp, 1) if lead and gp else 0.0,
        "production_score": None, "est_market_value_m": "unknown",
        "residual_m": "unknown", "archetypes": [],
        "production_source": "2025-26 totals"}
    if not lead or gp < 10:
        gaps.append(
            f"{display}: unknown value treated as 0 in side total "
            "(GP < 10 or no 2025-26 production row)")
        return out
    score = round(sum(lead["tot"][c] / gp * use_w[c] for c in use_w), 2)
    est_m = round(score * dpp / 1e6, 1)
    out["production_score"] = score
    out["est_market_value_m"] = est_m
    if out["salary_26_27"] is not None:
        out["residual_m"] = round(
            (est_m * 1e6 - out["salary_26_27"]) / 1e6, 1)
        rv = out["residual_m"]
        out["residual_note"] = (
            f"surplus value of about ${rv}M (outperforming the contract)"
            if rv >= 0 else
            f"overpaid by an estimated ${abs(rv)}M on this production")
    out["archetypes"] = _trade_archetypes(lead, gp, advanced)
    return out

def _trade_first_round_slot(entry: dict, net_rank: object,
                            giving_abbr: str, prot) -> None:
    if net_rank is None:
        slot = 15
        entry["assumptions"].append(
            f"no ratings row for {giving_abbr.upper()}: assumed "
            "mid-first slot 15")
    else:
        slot = max(1, min(round(31 - net_rank * 0.85), 30))
        entry["assumptions"].append(
            f"slot estimated from {giving_abbr.upper()} net rank {net_rank}")
    if prot:
        n = int(prot.group(1))
        slot = max(slot, n + 1)
        entry["assumptions"].append(
            f"top-{n} protected: conveyance risk applied")
    value = _pick_value_for_slot(slot, True)
    if prot:
        value = round(value * 0.8, 1)
    entry.update(est_slot=slot, est_value_m=value)

def _trade_second_round_slot(entry: dict, desc: str) -> None:
    import re as _re

    m = _re.search(r"\b([3-5]\d)\b", desc)
    slot = int(m.group(1)) if m and 31 <= int(m.group(1)) <= 60 else 45
    entry.update(est_slot=slot,
                 est_value_m=_pick_value_for_slot(slot, False))
    entry["assumptions"].append("second-round slot estimate")

def _trade_value_pick(desc: str, giving_abbr: str, ratings: dict,
                      gaps: list[str]) -> dict[str, Any]:
    import re as _re

    low = desc.lower()
    year = _re.search(r"(\d{4})", desc)
    is_frp = bool(_re.search(r"frp|first[\s-]?round", low))
    is_srp = bool(_re.search(r"\bsrp\b|second[\s-]?round", low))
    prot = _re.search(r"top[-\s]?(\d+)\s*protect", low)
    entry: dict[str, Any] = {"desc": desc, "est_slot": None,
                             "est_value_m": 0.0, "assumptions": []}
    if not year or (not is_frp and not is_srp):
        entry["assumptions"].append("unparseable pick description")
        gaps.append(f"{desc}: unparseable pick, valued at 0")
        return entry
    if is_frp:
        net_rank = (ratings.get(giving_abbr.upper(), {}) or {}).get(
            "NET_RATING_RANK")
        _trade_first_round_slot(entry, net_rank, giving_abbr, prot)
    else:
        _trade_second_round_slot(entry, desc)
    return entry

def _trade_value_picks(raw: str, giving_abbr: str, ratings: dict,
                       gaps: list[str]) -> list[dict]:
    return [_trade_value_pick(desc, giving_abbr, ratings, gaps)
            for desc in [p.strip() for p in str(raw or "").split(",")
                         if p.strip()]]

def _trade_side_total(players: list[dict], picks: list[dict]) -> float:
    return round(sum(p["est_market_value_m"] for p in players
                     if isinstance(p["est_market_value_m"], (int, float)))
                 + sum(k["est_value_m"] for k in picks), 1)

def _trade_grades(winner: str, delta: float, total_a: float, total_b: float,
                  abbr_a: str, abbr_b: str) -> dict[str, str]:
    if winner == "even":
        return {abbr_a: "B", abbr_b: "B"}
    share = abs(delta) / max(total_a, total_b, 1)
    top = abbr_a if winner == abbr_a else abbr_b
    bottom = abbr_b if top == abbr_a else abbr_a
    top_grade = "A" if share >= 0.25 else "A-" if share >= 0.15 else "B+"
    bottom_grade = ("F" if share >= 0.40 else "D" if share >= 0.25
                    else "C+" if share >= 0.15 else "B-")
    return {top: top_grade, bottom: bottom_grade}

def _trade_timeline(ratings: dict, team_abbr: str) -> tuple[str, list]:
    r = ratings.get(team_abbr.upper(), {})
    needs = [name for name, col in _TRADE_NEED_COLUMNS
             if isinstance(r.get(col), (int, float)) and r[col] >= 20]
    net_rank = r.get("NET_RATING_RANK")
    timeline = ("unknown" if not isinstance(net_rank, (int, float))
                else "contender" if net_rank <= 8
                else "rebuilding" if net_rank >= 22 else "middle")
    return timeline, needs

def _trade_fit_notes(player: dict, timeline: str, needs: list) -> list:
    notes = []
    for tag in player.get("archetypes", []):
        need = _TRADE_TAG_NEEDS.get(tag)
        if need and need in needs:
            notes.append(f"{player['name']} fills {need} ({tag})")
    age = player.get("age")
    if isinstance(age, (int, float)) and age >= 32 and timeline == "rebuilding":
        notes.append(f"{player['name']}: timeline clash (age {age:g} "
                     "joining a rebuild)")
    if isinstance(age, (int, float)) and age <= 23 and timeline == "contender":
        notes.append(f"{player['name']}: developmental piece on a contender")
    return notes

def _trade_fit(team_abbr: str, received: list[dict],
               ratings: dict) -> dict[str, Any]:
    timeline, needs = _trade_timeline(ratings, team_abbr)
    notes = [note for player in received
             for note in _trade_fit_notes(player, timeline, needs)]
    notes.append("positional logjam not assessed: no position data "
                 "in warehouse")
    return {"needs": needs, "timeline": timeline, "notes": notes}

def _trade_driver(players_a: list, players_b: list):
    valued = [p for p in players_a + players_b
              if isinstance(p["est_market_value_m"], (int, float))]
    if not valued:
        return None
    return max(valued, key=lambda p: (abs(p["residual_m"])
                                      if isinstance(p["residual_m"],
                                                    (int, float)) else 0))

def _trade_key_add(winner: str, abbr_a: str, players_a: list,
                   players_b: list):
    win_side = players_b if winner == abbr_a else players_a
    got = [p for p in win_side
           if isinstance(p["est_market_value_m"], (int, float))]
    return max(got, key=lambda p: p["est_market_value_m"], default=None)

def _trade_key_fit_note(winner: str, fit: dict, key_add: dict | None) -> str:
    if key_add is None or winner == "even":
        return ""
    notes = fit[winner]["notes"]
    hit = next((n for n in notes if n.startswith(key_add["name"])), "")
    if hit:
        return (f" {key_add['name']} {hit[len(key_add['name']) + 1:]} "
                f"for {winner}.")
    return (f" {key_add['name']} headlines the return for {winner} "
            f"({fit[winner]['timeline']} timeline).")

def _trade_verdict_line(winner: str, total_a: float, total_b: float,
                        delta: float, abbr_a: str, abbr_b: str) -> str:
    if winner == "even":
        return (f"This grades as roughly even, with {abbr_a} at an estimated "
                f"${total_a}M and {abbr_b} at an estimated ${total_b}M, "
                f"a gap of about ${abs(delta)}M.")
    return (f"{winner} wins on estimated value by about ${abs(delta)}M, "
            f"${max(total_a, total_b)}M to ${min(total_a, total_b)}M.")

def _trade_driver_line(driver: dict | None) -> str:
    if driver is None:
        return "No player had enough production data to name a value driver."
    residual = driver["residual_m"]
    res_txt = ("the best value in the deal"
               if isinstance(residual, (int, float)) and residual < 0
               else "the largest gap between salary and production")
    return (f"The biggest driver is {driver['name']}, with an estimated "
            f"${driver['est_market_value_m']}M market value against a "
            f"${(driver['salary_26_27'] or 0) / 1e6:.1f}M salary, "
            f"{res_txt}.")

def _trade_value_sides(con, team_a: str, players_a: str, team_b: str,
                       players_b: str, season: str | None = None):
    _, names_a, unk_a = _match_trade_players(team_a, players_a, con, season)
    _, names_b, unk_b = _match_trade_players(team_b, players_b, con, season)
    if unk_a:
        fix = _auto_correct_side(unk_a, team_a, players_a, con, season)
        if fix:
            team_a, (_, names_a, unk_a), _c = fix
    if unk_b:
        fix = _auto_correct_side(unk_b, team_b, players_b, con, season)
        if fix:
            team_b, (_, names_b, unk_b), _c = fix
    return team_a, names_a, unk_a, team_b, names_b, unk_b

def _trade_value_error(msg: str) -> dict[str, Any]:
    return {"tool": "get_trade_value", "ok": False, "error": msg}

@tool(description='Trade value grade: estimated production value vs salary per side, plus picks.\n\nReasoning layer on top of get_trade_check (which covers cap legality).\nAll dollar figures are rough estimates from 2025-26 production versus\n2026-27 salaries. Picks like "2029 FRP" or "2030 FRP top-4 protected".')
def get_trade_value(
    team_a: str = "", players_a: str = "", team_b: str = "",
    players_b: str = "", picks_a: str = "", picks_b: str = "",
) -> dict[str, Any]:
    if team_a and team_b:
        norm = _norm_trade_teams(team_a, team_b)
        if norm is None:
            return _trade_value_error(
                f"both sides resolve to the same team ({team_a} / {team_b}) "
                "- check the team names")
        team_a, team_b = norm
    from ._core import last_completed_season as _trade_lcs
    prod_season = _trade_lcs()
    sal_season = "2026-27"
    disclaimer = (f"All dollar figures are rough estimates from {prod_season} "
                   "production vs 2026-27 salary data. Not cap-legality advice; "
                   "pair with get_trade_check.")

    if not team_a or not team_b:
        return _trade_value_error("two teams needed")
    with _owned_connection(None) as con:
        try:
            team_a, names_a, unk_a, team_b, names_b, unk_b = _trade_value_sides(
                con, team_a, players_a, team_b, players_b, sal_season)
        except SalaryColumnError as exc:
            return {"tool": "get_trade_value", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        if unk_a or unk_b:
            out = _trade_value_error(_trade_unknown_message(
                team_a, unk_a, team_b, unk_b, con))
            out["reason"] = "unknown_players"
            return out
        if not names_a or not names_b:
            return {"tool": "get_trade_value", "ok": False,
                    "terminal": True,
                    "error": ("I can only grade proposed trades where "
                              "both sides name players. What a past "
                              "trade's other side actually received is "
                              "not in this dataset.")}

        warehouse = _TradeWarehouse(con, prod_season, sal_season)
        if not warehouse.has_leaders():
            return _trade_value_error(
                "cannot value players: silver_leaders_pts missing from "
                "warehouse")
        use_w = _trade_leader_weights(warehouse)
        leaders = _trade_leader_rows(con, prod_season)
        adv = _trade_adv_rows(con, warehouse, prod_season)
        salaries = _trade_sheet_salaries(con, warehouse, sal_season)
        if not salaries:
            warehouse.note("no 2026-27 salary rows: residuals unavailable")
        ratings = _trade_rating_rows(con, warehouse, prod_season)
        payroll_source = _payroll_source(con)

    dpp = _trade_dollars_per_point(leaders, salaries, use_w)
    if not dpp:
        return _trade_value_error(
            "cannot value players: no qualified salary plus production "
            "overlap in warehouse")

    players_a = [_trade_value_player(n, leaders, adv, salaries, use_w, dpp,
                                     warehouse.gaps) for n in names_a]
    players_b = [_trade_value_player(n, leaders, adv, salaries, use_w, dpp,
                                     warehouse.gaps) for n in names_b]
    picks_list_a = _trade_value_picks(picks_a, team_a, ratings, warehouse.gaps)
    picks_list_b = _trade_value_picks(picks_b, team_b, ratings, warehouse.gaps)

    total_a = _trade_side_total(players_a, picks_list_a)
    total_b = _trade_side_total(players_b, picks_list_b)
    delta = round(total_a - total_b, 1)
    abbr_a, abbr_b = team_a.upper(), team_b.upper()
    winner = abbr_a if delta >= 0.5 else abbr_b if delta <= -0.5 else "even"

    fit = {abbr_a: _trade_fit(abbr_a, players_b, ratings),
           abbr_b: _trade_fit(abbr_b, players_a, ratings)}

    key_fit_note = _trade_key_fit_note(
        winner, fit, _trade_key_add(winner, abbr_a, players_a, players_b))
    s1 = _trade_verdict_line(winner, total_a, total_b, delta, abbr_a, abbr_b)
    s2 = _trade_driver_line(_trade_driver(players_a, players_b))
    s3 = key_fit_note.strip() or "Fit notes are limited by missing team data."
    s4 = ("All values are rough estimates from 2025-26 production versus "
          "2026-27 salaries, so this is not cap-legality advice: pair it "
          "with get_trade_check.")

    return {"tool": "get_trade_value", "ok": True,
            "rows": {"team_a": {"team": abbr_a, "players": players_a,
                                "picks": picks_list_a, "side_total_m": total_a},
                     "team_b": {"team": abbr_b, "players": players_b,
                                "picks": picks_list_b, "side_total_m": total_b},
                     "fit": fit,
                     "verdict": {"winner": winner, "delta_m": delta,
                                 "grades": _trade_grades(
                                     winner, delta, total_a, total_b,
                                     abbr_a, abbr_b),
                                 "text": " ".join([s1, s2, s3, s4])},
                     "data_gaps": warehouse.gaps,
                     "disclaimer": disclaimer,
                     "residual_meaning": "residual_m = estimated market "
                     "value minus salary; positive = surplus value "
                     "(outperforming the contract), negative = overpaid"},
            "meta": {"source": payroll_source,
                     "production_season": prod_season,
                     "salary_season": _salary_vintage()[0] or "2026-27",
                     "estimates": True}}

def _norm_draft_year(season: str) -> str:
    season = resolve_season(season)
    s = str(season or "").strip()
    if re.fullmatch(r"(19|20)\d\d", s):
        return s
    m = re.fullmatch(r"((?:19|20)\d\d)-(\d\d)", s)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return str(int(m.group(1)) + 1)
    raise ValueError(
        f"could not match {s!r} to a draft year "
        "(use a calendar year like 2025 or a season slug like 2024-25)")

@tool(description='Draft board: college production plus combine measurements, blended rank.')
def get_draft_board(season: str = "2025") -> dict[str, Any]:
    season = resolve_season(season)
    import unicodedata as _ud

    try:
        season = _norm_draft_year(season)
    except ValueError as exc:
        return {"tool": "get_draft_board", "ok": False, "error": str(exc)}

    from ..sources import cbb as _cbb

    def norm(s: object) -> str:
        return "".join(c for c in _ud.normalize("NFKD", str(s or ""))
                       if not _ud.combining(c)).lower().strip()

    prod = _cbb.get_player_stats(2025 if season == "2025" else int(season))
    if not prod.ok or prod.frame.height == 0:

        rows, meta = _warehouse_or_live(
            "silver_combine", "_season = ?",
            [season], lambda: nba_stats.combine(season), season,
        )
        if rows:
            meta = dict(meta)
            meta["note"] = ("college production stats unavailable; "
                            "combine measurements only")
            return {"tool": "get_draft_board", "ok": True,
                    "rows": rows[:30], "meta": meta}
        return {"tool": "get_draft_board", "ok": False,
                "error": (f"{season} college stats are unavailable "
                          "(upstream source blocked). Draft data covers "
                          "through the 2025 draft; the 2026 lottery and "
                          "class are not in the dataset.")}
    rows, meta = _warehouse_or_live(
        "silver_combine", "_season = ?",
        [season], lambda: nba_stats.combine(season), season,
    )
    meas = {norm(r.get("PLAYER_NAME")): r for r in rows}
    board = []
    for p in prod.frame.to_dicts():
        m = meas.get(norm(p.get("PLAYER_NAME")), {})
        try:
            score = (float(p.get("PTS") or 0) * 2
                     + float(p.get("TS_PCT") or 0) * 50
                     + float(p.get("USG") or 0))
        except (TypeError, ValueError):
            continue
        board.append({"PLAYER": p.get("PLAYER_NAME"), "TEAM": p.get("TEAM"),
                      "PTS": p.get("PTS"), "TS_PCT": p.get("TS_PCT"),
                      "USG": p.get("USG"),
                      "HEIGHT": m.get("HEIGHT_WO_SHOES_FT_IN"),
                      "WINGSPAN": m.get("WINGSPAN_FT_IN"),
                      "SCORE": round(score, 1)})
    board.sort(key=lambda d: d["SCORE"], reverse=True)
    return {"tool": "get_draft_board", "ok": True, "rows": board[:30],
            "meta": {"source": "barttorvik+nba_api", "season": season,
                     "matched_measurements": sum(1 for b in board[:30]
                                                 if b["HEIGHT"]),
                     "formula": "2*PTS + 50*TS + USG"}}

@tool(description='Current rookie class leaderboard (first-year NBA players only).\n\nRookies are defined structurally: a player in the current-season\nstats table with NO row in any prior season (hist or warehouse).\nNever an age proxy, never historical seasons (F46: a "rookies 20+\nppg" query answered from 2023-24 listed Edwards/LaMelo/Wemby; the\nright answer was the current draft class, e.g. Cooper Flagg).\nstat is a per-game column: ppg, rpg, apg, spg, bpg, mpg.')
def get_rookie_leaders(stat: str = "ppg", min_value: float = 0,
                       min_gp: int = 10, limit: int = 15,
                       season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    from .. import store as _store

    col = str(stat or "ppg").strip().upper()
    allowed = {"PPG", "RPG", "APG", "SPG", "BPG", "MPG",
               "FG_PCT", "FG3_PCT", "FT_PCT", "GP"}
    if col not in allowed:
        return {"tool": "get_rookie_leaders", "ok": False,
                "error": f"stat must be one of {sorted(allowed)}"}

    min_gp = max(5, min(int(min_gp), 82))
    sql = f"""
        SELECT PLAYER_ID, PLAYER, TEAM, AGE, GP, MPG, PPG, RPG, APG,
               SPG, BPG, FG_PCT, FG3_PCT, FT_PCT
        FROM silver_player_season
        WHERE _season = ? AND GP >= ? AND {col} >= ?
        ORDER BY {col} DESC
    """
    try:
        con = _store.connect(read_only=True)
        try:
            cur_rows = con.execute(
                sql, [season, int(min_gp), float(min_value)]
            ).fetchdf().to_dict("records")
            hist_names = {r[0] for r in con.execute(
                "SELECT DISTINCT player_name FROM "
                "silver_hist_player_seasons").fetchall()}
            hist_names |= {r[0] for r in con.execute(
                "SELECT DISTINCT PLAYER FROM silver_player_season "
                "WHERE _season <> ?", [season]).fetchall()}
        finally:
            con.close()
    except Exception as exc:
        return {"tool": "get_rookie_leaders", "ok": False,
                "error": f"warehouse read failed: {str(exc)[:160]}"}

    import re as _re
    import unicodedata as _ud

    def _nkey(name: object) -> str:
        n = "".join(c for c in _ud.normalize("NFKD", str(name or ""))
                    if not _ud.combining(c)).lower()
        n = _re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", n).strip()
        return _re.sub(r"[^a-z ]", "", n).strip()

    hist_keys = {_nkey(n) for n in hist_names}
    rows = [r for r in cur_rows
            if _nkey(r.get("PLAYER")) not in hist_keys][:int(limit)]
    return {
        "tool": "get_rookie_leaders", "ok": True, "rows": rows,
        "meta": {
            "season": season,
            "source": ("warehouse silver_player_season plus prior-season "
                       "silver player populations"),
            "method": ("filter to first NBA season by excluding every player "
                       "name present in any prior warehouse season, then rank "
                       f"descending by {col}"),
            "method_kind": "derived",
            "stat": col,
            "stat_unit": ("fraction_0_1" if col in {"FG_PCT", "FG3_PCT", "FT_PCT"}
                          else "games" if col == "GP"
                          else "per_game"),
            "rookie_definition": (
                "first NBA season: no player row in any prior season"),
            "floors": f"GP >= {int(min_gp)}, {col} >= {float(min_value)}",
            "note": "current draft class only; never an age proxy"},
    }

@tool(description="League-wide five-man lineup net-rating leaderboard.\n\nNet rating is PLUS_MINUS per 48 minutes from the warehouse lineup\ntable. A minimum-minutes floor (default 100) is ALWAYS applied and\nstated: a +3 in 4 minutes is a 300.0 'net rating' on a junk slice\nand never tops the board (F50).")
def get_lineup_leaders(min_minutes: int = 100, limit: int = 10,
                       season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    from .. import store as _store

    min_minutes = max(25, min(float(min_minutes), 5000))

    sql = """
        SELECT TEAM_ABBREVIATION, GROUP_NAME, GP,
               ROUND(MIN, 1) AS MIN, PLUS_MINUS,
               ROUND(PLUS_MINUS / NULLIF(MIN, 0) * 48, 1) AS NET48
        FROM silver_lineups
        WHERE _season = ? AND MIN >= ?
        ORDER BY PLUS_MINUS / NULLIF(MIN, 0) DESC NULLS LAST
        LIMIT ?
    """
    try:
        con = _store.connect(read_only=True)
        try:
            raw = con.execute(
                sql, [season, float(min_minutes), int(limit) * 2]
            ).fetchdf().to_dict("records")
            hist = False
            if not raw:

                raw = con.execute(
                    """
                    SELECT team_abbreviation AS TEAM_ABBREVIATION,
                           group_name AS GROUP_NAME, gp AS GP,
                           ROUND(min, 1) AS MIN, plus_minus AS PLUS_MINUS,
                           ROUND(plus_minus / NULLIF(min, 0) * 48, 1)
                               AS NET48
                    FROM silver_hist_lineups
                    WHERE _season = ? AND min >= ?
                    ORDER BY plus_minus / NULLIF(min, 0) DESC NULLS LAST
                    LIMIT ?
                    """,
                    [season, float(min_minutes), int(limit) * 2],
                ).fetchdf().to_dict("records")
                hist = bool(raw)
        finally:
            con.close()
    except Exception as exc:
        return {"tool": "get_lineup_leaders", "ok": False,
                "error": f"warehouse read failed: {str(exc)[:160]}"}
    seen = set()
    rows = []
    for r in raw:
        key = (r.get("TEAM_ABBREVIATION"), r.get("GROUP_NAME"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(r)
        if len(rows) >= int(limit):
            break
    meta = {
        "season": season,
        "formula": "NET48 = PLUS_MINUS per 48 minutes",
        "floor": f"MIN >= {int(min_minutes)} (stated volume floor; "
                 "small-sample units are excluded, F50)"}
    if hist:
        meta["coverage"] = "historical_lineups"
    if not rows:
        return {"tool": "get_lineup_leaders", "ok": False,
                "error": (f"No lineup data on file for {season} at "
                          f"that minutes floor; lineups cover 2009-10 "
                          f"through the current season. Try a lower "
                          f"minutes floor for short seasons.")}
    return {"tool": "get_lineup_leaders", "ok": True, "rows": rows,
            "meta": meta}

@tool(description='Draft combine measurements plus shooting drills for one draft year.')
def get_combine(season: str = "2025") -> dict[str, Any]:
    season = resolve_season(season)
    try:
        season = _norm_draft_year(season)
    except ValueError as exc:
        return {"tool": "get_combine", "ok": False, "error": str(exc)}
    rows, meta = _warehouse_or_live(
        "silver_combine", "_season = ?",
        [season], lambda: nba_stats.combine(season), season,
    )
    if not rows:

        try:
            from .. import store as _store
            con = _store.connect(read_only=True)
            try:
                avail = [r[0] for r in con.execute(
                    "SELECT DISTINCT _season FROM silver_combine "
                    "ORDER BY 1 DESC").fetchall()]
            finally:
                con.close()
        except Exception:
            avail = []
        if avail:
            sub = str(avail[0])
            rows, meta = _warehouse_or_live(
                "silver_combine", "_season = ?",
                [sub], lambda: nba_stats.combine(sub), sub,
            )
            if rows:
                meta = dict(meta)
                meta["note"] = (f"requested draft year {season} is not "
                                f"seeded; showing {sub}, the newest "
                                "available combine year")
                season = sub
    if not rows:
        return {"tool": "get_combine", "ok": False,
                "error": meta.get("error") or "empty upstream response"}
    return {"tool": "get_combine", "ok": True, "rows": rows[:25],
            "meta": meta}

@tool(description='Morning briefing: scoreboard plus top scorers. Date MM/DD/YYYY, blank means latest.')
def get_briefing(game_date: str = "", season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    from datetime import datetime, timedelta

    day = game_date.strip()
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")
    past = is_past_game_date(day)
    games, gmeta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{day}"],
        lambda: nba_stats.scoreboard(day, season), season,
        entity=f"date:{day}", live_first=(not past),
        ttl_s=(TTL_SCOREBOARD_PAST if past else None),
    )
    leaders, _ = _warehouse_or_live(
        "silver_leaders_pts", "_season = ?",
        [season], lambda: nba_stats.leaders("PTS", season), season,
        ttl_s=TTL_LEADERS,
    )
    top = [
        {"PLAYER": r.get("PLAYER"), "TEAM": r.get("TEAM"), "PTS": r.get("PTS")}
        for r in leaders[:5]
    ]
    return {"tool": "get_briefing", "ok": True,
            "rows": {"date": day, "games": games, "top_scorers": top},
            "meta": gmeta}

def _describe_warehouse_schema(cols: dict[str, dict]) -> str:
    return "\n".join(
        f"{table}: {', '.join(columns)}" for table, columns in cols.items())

_SQL_TABLES = [
    "silver_standings", "silver_playoffs", "silver_team_ratings",
    "silver_clutch", "silver_player_gamelogs", "silver_team_games",
    "silver_leaders_pts", "silver_leaders_reb", "silver_leaders_ast",
    "silver_leaders_stl", "silver_leaders_blk", "silver_boxscores",
    "silver_lineups", "silver_shots", "silver_hustle_player",
    "silver_hustle_team", "silver_injuries", "silver_hist_gamelogs",
    "silver_hist_standings", "silver_hist_possessions",
    "silver_hist_shots", "silver_hist_lineups", "silver_salaries",
    "silver_hist_draft", "silver_raptor_player", "silver_raptor_team",
    "silver_hist_player_seasons", "silver_player_season", "silver_advanced",
    "silver_on_off", "silver_four_factors", "silver_four_factors_team",
    "silver_cap_players",
]

RERUN_ROW_CAP = 25
RERUN_TIMEOUT_S = 30

_SCHEMA_TTL_S = 3600.0
_schema_cache: dict[str, object] = {"at": 0.0, "present": [], "cols": {}}
_schema_cache_stats: dict[str, int] = {"hits": 0, "misses": 0}

def _clear_warehouse_schema_cache() -> None:
    _schema_cache["at"] = 0.0
    _schema_cache["present"] = []
    _schema_cache["cols"] = {}
    _schema_cache_stats["hits"] = 0
    _schema_cache_stats["misses"] = 0

def _warehouse_schema_cache_info() -> dict[str, float]:
    return {"hits": _schema_cache_stats["hits"],
            "misses": _schema_cache_stats["misses"],
            "at": _schema_cache["at"]}

_COLUMN_UNITS: dict[str, tuple[str, str]] = {
    "PCT": ("fraction_0_1", "fraction on a 0-1 scale, not a 0-100 number"),
    "MPG": ("minutes_per_game", "minutes per game, not total minutes; "
                               "multiply by GP for a season total"),
    "PPG": ("points_per_game", "points per game, not a season total"),
    "RPG": ("rebounds_per_game", "rebounds per game, not a season total"),
    "APG": ("assists_per_game", "assists per game, not a season total"),
    "SPG": ("steals_per_game", "steals per game, not a season total"),
    "BPG": ("blocks_per_game", "blocks per game, not a season total"),
    "GP": ("games_played", "games played; the denominator for a per-game rate"),
    "GS": ("games_started", "games started, at most GP"),
    "MP": ("total_minutes", "total minutes played across the season"),
    "AGE": ("years", "age in years"),
    "RANK": ("rank", "leading rank; a tie shares it"),
    "RATE": ("per_100_possessions", "rate per 100 possessions"),
}
_COLUMN_PREFIX_UNITS: tuple[tuple[str, tuple[str, str]], ...] = (
    ("_PCT", ("fraction_0_1",
              "fraction on a 0-1 scale, not a 0-100 number")),
    ("_PTS_PER_100", ("points_per_100_possessions",
                      "points per 100 possessions")),
)
_COLUMN_SUFFIXES = ("_PTS", "_REB", "_AST", "_STL", "_BLK", "_TOV", "_MIN")
_PROVENANCE_PREFIXES = ("_PROV_",)


def _column_semantics(name: str) -> tuple[str, str]:
    upper = str(name or "").upper()
    if any(upper.startswith(prefix) for prefix in _PROVENANCE_PREFIXES):
        return ("provenance", "provenance column; never filter or group on it")
    if upper.startswith("_PROV") or upper in {"_SOURCE", "_FETCHED_AT", "_ENTITY"}:
        return ("provenance", "provenance column; never filter or group on it")
    if upper == "_SEASON":
        return ("season", "the season these rows describe; filter on this")
    for prefix, entry in _COLUMN_PREFIX_UNITS:
        if upper.endswith(prefix):
            return entry
    if upper in _COLUMN_UNITS:
        return _COLUMN_UNITS[upper]
    for suffix in _COLUMN_SUFFIXES:
        if upper.endswith(suffix):
            return (f"total_{suffix.lstrip('_').lower()}",
                    f"season total, not per game")
    return ("", "")


def _get_warehouse_schema() -> tuple[list[str], dict[str, dict[str, dict]]]:
    import time as _time

    from .. import store as _store

    now = _time.monotonic()
    at = float(_schema_cache.get("at") or 0.0)
    if now - at < _SCHEMA_TTL_S and _schema_cache.get("present"):
        _schema_cache_stats["hits"] += 1
        return (list(_schema_cache["present"]),
                {k: dict(v) for k, v in
                 _schema_cache["cols"].items()})
    _schema_cache_stats["misses"] += 1
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        present = [t for t in _SQL_TABLES if t in tables]
        cols: dict[str, dict[str, dict[str, str]]] = {}
        for t in present:
            cols[t] = {}
            for row in con.execute(
                    f"PRAGMA table_info({t})").fetchall()[:40]:
                unit, note = _column_semantics(row[1])
                cols[t][row[1]] = {
                    "type": str(row[2]), "unit": unit, "note": note}
    finally:
        con.close()
    _schema_cache["at"] = now
    _schema_cache["present"] = present
    _schema_cache["cols"] = cols
    return (list(present),
            {k: dict(v) for k, v in cols.items()})

import re as _re_mod

_SELECT_RE = _re_mod.compile(r"(?i)^\s*(select|with)\b")
_WRITE_RE = _re_mod.compile(
    r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy|"
    r"vacuum|detach)\b")
_TABLE_REF_RE = _re_mod.compile(r"(?i)from\s+(\w+)|join\s+(\w+)")

def _validate_readonly_sql(sql: str, present: set[str]) -> str:
    sql = (sql or "").strip().rstrip(";").strip()
    if not _SELECT_RE.match(sql):
        raise ValueError("only SELECT/WITH queries are allowed")
    if ";" in sql:
        raise ValueError("stacked statements are not allowed")
    if _WRITE_RE.search(sql):
        raise ValueError("write operations are not allowed")
    used = {a or b for a, b in _TABLE_REF_RE.findall(sql)}
    if not used or not used.issubset(set(present)):
        raise ValueError("unknown or unavailable tables")
    return sql

def _attach_player_names(rows: list[dict]) -> None:
    if not rows:
        return
    has_pid = any("Player_ID" in r or "player_id" in r for r in rows)
    has_name = any(
        any(str(k).lower() in ("player", "player_name", "name")
            for k in r)
        for r in rows)
    if not has_pid or has_name:
        return
    from .splits import _resolve_name as _rname
    for r in rows:
        pid = r.get("Player_ID", r.get("player_id"))
        if pid is None:
            continue
        try:
            r["PLAYER"] = _rname(int(pid), str(pid))
        except (TypeError, ValueError):
            pass

@tool(description='Answer a data question with SQL over warehouse tables. SELECT only.')
async def text_to_sql(question: str) -> dict[str, Any]:
    import re as _re

    from langchain_core.messages import HumanMessage, SystemMessage

    from .. import store as _store
    from ..providers import invoke_with_fallback

    present, cols = _get_warehouse_schema()
    if not present:
        return {"tool": "text_to_sql", "ok": False, "error": "warehouse empty"}
    schema = _describe_warehouse_schema(cols)
    examples = (
        "\nExamples.\nQ: Thunder record this season?\n"
        "SQL: SELECT WINS, LOSSES FROM silver_standings "
        "WHERE TeamCity = 'Oklahoma City' AND _season = '2025-26'\n"
        "Q: OKC wins per season, last 3 seasons?\n"
        "SQL: SELECT _season, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins "
        "FROM silver_hist_gamelogs WHERE team_abbreviation = 'OKC' "
        "AND _season IN ('2025-26', '2024-25', '2023-24') GROUP BY _season\n"
        "Q: Which 5 teams have the highest total payroll?\n"
        "SQL: SELECT TEAM, SUM(SALARY) AS payroll FROM silver_salaries "
        "GROUP BY TEAM ORDER BY payroll DESC LIMIT 5\n"
        "Q: Who has the best clutch FG% with at least 10 GP?\n"
        "SQL: SELECT PLAYER_NAME, FG_PCT FROM silver_clutch "
        "WHERE GP >= 10 ORDER BY FG_PCT DESC LIMIT 5\n"
        "Q: Which top-10 net-rating team plays fastest?\n"
        "SQL: SELECT TEAM_NAME, PACE, NET_RATING FROM silver_team_ratings "
        "WHERE NET_RATING_RANK <= 10 ORDER BY PACE DESC LIMIT 1\n"
        "Q: How strong is the supporting cast around Shai Gilgeous-Alexander on OKC?\n"
        "SQL: SELECT AVG(l.PTS * 1.0 / l.GP) AS cast_ppg, "
        "MAX(r.NET_RATING) AS net_rating, MAX(r.PACE) AS pace "
        "FROM silver_leaders_pts l JOIN silver_team_ratings r "
        "ON r._season = l._season "
        "WHERE l.TEAM = 'OKC' AND l.PLAYER <> 'Shai Gilgeous-Alexander' "
        "AND r.TEAM_NAME LIKE '%Oklahoma%' "
        "AND l._season = '2025-26' AND l.GP >= 10\n"
        "Q: Who has the most playoff wins in 2025-26?\n"
        "SQL: SELECT TEAM_ABBREVIATION, COUNT(*) AS wins FROM silver_playoffs "
        "WHERE WL = 'W' GROUP BY TEAM_ABBREVIATION ORDER BY wins DESC LIMIT 5\n"
        "Q: Who was drafted #1 overall in the June 2003 NBA draft?\n"
        "Note: DRAFT_YEAR is the June draft year.\n"
        "SQL: SELECT OVERALL_PICK, PLAYER_NAME, TEAM_ABBREVIATION FROM silver_hist_draft "
        "WHERE OVERALL_PICK = 1 AND DRAFT_YEAR = 2003\n"
        "Q: What was Michael Jordan's peak RAPTOR season?\n"
        "SQL: SELECT _season, RAPTOR_TOTAL, WAR_TOTAL FROM silver_raptor_player "
        "WHERE PLAYER_NAME = 'Michael Jordan' ORDER BY RAPTOR_TOTAL DESC LIMIT 1\n"
        "Q: What were LeBron James' per-game stats in 2023-24?\n"
        "Note: silver_hist_player_seasons stores per-game averages already; "
        "select PTS/MIN directly, never divide by GP. "
        "Season ints are end-years, so 2023-24 = SEASON 2024 = _season '2023-24'.\n"
        "SQL: SELECT PLAYER_NAME, TEAM_ABBREVIATION, GP, PTS, AST, TS_PCT, NET_RATING "
        "FROM silver_hist_player_seasons WHERE PLAYER_NAME = 'LeBron James' "
        "AND _season = '2023-24'\n"
        "Q: Which players under 24 averaged at least 15 points and 5 assists last season?\n"
        "Note silver_hist_player_seasons stores per-game averages with AGE, PTS, AST "
        "columns and season end-year ints.\n"
        "SQL: SELECT PLAYER_NAME, TEAM_ABBREVIATION, AGE, GP, PTS, AST "
        "FROM silver_hist_player_seasons WHERE AGE < 24 AND PTS >= 15 AND AST >= 5 "
        "AND SEASON = 2024 ORDER BY PTS DESC LIMIT 10\n"
        "Q: What were the best games in March 2026?\n"
        "Note: current-season per-game logs live in silver_player_gamelogs "
        "with UPPERCASE columns (PLAYER_NAME absent - join player ids via "
        "silver_leaders_pts.PLAYER_ID/PLAYER; GAME_DATE, MATCHUP, PTS). "
        "Dates look like 'Mar 30, 2026'; filter months with ILIKE, e.g. "
        "GAME_DATE ILIKE '%Mar%2026'. A 'no such column' error means "
        "wrong table/column spelling - retry with these names, it NEVER "
        "means the games are missing.\n"
        "SQL: SELECT p.PLAYER, g.GAME_DATE, g.MATCHUP, g.PTS FROM "
        "silver_player_gamelogs g JOIN silver_leaders_pts p ON "
        "p.PLAYER_ID = g.Player_ID AND p._season = g._season "
        "WHERE g._season = '2025-26' AND g.GAME_DATE ILIKE '%Mar%2026' "
        "ORDER BY g.PTS DESC LIMIT 10\n"
        "Q: Who led the 2025-26 season in steals?\n"
        "Note: season totals come from silver_leaders_* tables; "
        "never aggregate silver_player_gamelogs for season totals.\n"
        "SQL: SELECT PLAYER, STL FROM silver_leaders_stl "
        "WHERE _season = '2025-26' ORDER BY STL DESC LIMIT 1"
    )
    feedback = ""
    for _ in range(2):
        try:
            resp = await invoke_with_fallback(
                "mistral", "ministral-8b-2512",
                [SystemMessage(content="Reply with SQL only, no prose."),
                 HumanMessage(
                      content="Write one SQLite SELECT using only these tables "
                      "and columns. Match column case exactly as listed.\n"
                      "Rules. Ratio/percentage leaderboards MUST add a "
                      "minimum-volume floor (AST/TOV: AST >= 300; shooting "
                      "pct: attempts >= 300) or the top row is a junk "
                      "small-sample slice. Season totals and season leaders questions MUST use "
                      "the silver_leaders_* tables directly; they hold final official "
                      "season totals. silver_player_gamelogs is an incomplete per-game "
                      "sample: never SUM it to compute season totals, and never join "
                      "per-game tables to leaders tables (fan-out inflates sums).\n"
                      f"Schema:\n{schema}{examples}\nQuestion: {question}{feedback}")])
            sql = _re.sub(r"^```sql|```$", "", str(getattr(resp, "content", "") or ""),
                          flags=_re.MULTILINE).strip()
        except Exception as exc:
            return {"tool": "text_to_sql", "ok": False, "error": str(exc)[:160]}
        if not _re.match(r"(?i)^\s*select\b", sql) or _re.search(
                r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy)\b", sql):
            feedback = "\nPrevious reply was not a single SELECT. Reply with SQL only."
            continue
        try:
            sql = _validate_readonly_sql(sql, set(present))
        except ValueError as vexc:
            feedback = f"\nPrevious reply was rejected: {vexc}. Reply with SQL only."
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
        out_rows = [dict(zip(names, r)) for r in rows[:25]]
        _attach_player_names(out_rows)
        return {"tool": "text_to_sql", "ok": True,
                "rows": out_rows,
                "sql": sql,
                "meta": {"sql": sql[:500], "source": "warehouse"}}
    return {"tool": "text_to_sql", "ok": False,
            "error": ("the warehouse query did not succeed after several "
                      "attempts; answer from results already gathered or "
                      "state plainly that it could not be computed")}

def _execute_with_timeout(con, sql: str, timeout_s: float):
    import threading as _threading

    out: dict[str, Any] = {}

    def _run() -> None:
        try:
            rel = con.execute(sql)
            out["result"] = ([d[0] for d in con.description], rel.fetchall())
        except Exception as exc:
            out["error"] = exc

    th = _threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        try:
            con.close()
        except Exception:
            pass
        raise TimeoutError(f"query exceeded {timeout_s:g}s")
    if "error" in out:
        raise out["error"]
    return out["result"]

async def rerun_sql(sql: str) -> dict[str, Any]:
    import time as _time

    from .. import store as _store

    sql = (sql or "").strip()
    con = _store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    except Exception as exc:
        return {"tool": "rerun_sql", "ok": False,
                "error": str(exc)[:160]}
    finally:
        con.close()
    present = tables & set(_SQL_TABLES)
    if not present:
        return {"tool": "rerun_sql", "ok": False,
                "error": "warehouse empty"}
    try:
        sql = _validate_readonly_sql(sql, present)
    except ValueError as vexc:
        return {"tool": "rerun_sql", "ok": False, "error": str(vexc)[:160]}
    t0 = _time.time()
    con = _store.connect(read_only=True)
    try:
        names, rows = _execute_with_timeout(con, sql, RERUN_TIMEOUT_S)
    except Exception as exc:
        return {"tool": "rerun_sql", "ok": False, "error": str(exc)[:160],
                "sql": sql}
    finally:
        try:
            con.close()
        except Exception:
            pass
    capped = len(rows) > RERUN_ROW_CAP
    return {"tool": "rerun_sql", "ok": True,
            "columns": names,
            "rows": [dict(zip(names, r)) for r in rows[:RERUN_ROW_CAP]],
            "sql": sql, "capped": capped,
            "ms": int((_time.time() - t0) * 1000)}

@tool(description='ELO power ratings from warehouse game results for one season.')
def get_elo(season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_elo", "ok": False, "error": "history empty"}
        rows = con.execute(
            """SELECT team_abbreviation, game_id, game_date, matchup, wl,
            plus_minus FROM silver_hist_gamelogs
            WHERE _season = ? ORDER BY game_date, game_id""",
            [season],
        ).fetchall()
    finally:
        con.close()
    rows = [r for r in rows if is_scope_game(r[1], "regular")]
    elo, wins, losses, mov_ok = _build_elo(rows)
    table = sorted(
        ({"TEAM": t, "ELO": round(v), "W": wins.get(t, 0),
          "L": losses.get(t, 0)} for t, v in elo.items()),
        key=lambda d: d["ELO"], reverse=True,
    )
    for i, row in enumerate(table, 1):
        row["rank"] = i
    return {"tool": "get_elo", "ok": True, "rows": table,
            "meta": {"source": "warehouse", "mov": mov_ok, "season": season}}

@tool(description='ELO power ratings as standings: implied win pct, win equivalents, and Elo-implied spreads. ROADMAP Appendix #3.')
def get_elo_standings(season: str | None = None, opponent: str | None = None,
                      limit: int = 30) -> dict[str, Any]:
    season = resolve_season(season)
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            rows = []
        else:
            rows = con.execute(
                """SELECT team_abbreviation, game_id, game_date, matchup, wl,
                plus_minus FROM silver_hist_gamelogs
                WHERE _season = ? ORDER BY game_date, game_id""",
                [season],
            ).fetchall()
    finally:
        con.close()
    if not rows:
        return {"tool": "get_elo_standings", "ok": True, "rows": [],
                "meta": {"source": "warehouse", "season": season,
                         "data_note": (
                             f"no games in the warehouse for season {season}; "
                             "nothing fabricated")}}
    rows = [r for r in rows if is_scope_game(r[1], "regular")]
    elo, wins, losses, mov_ok = _build_elo(rows)
    anchor_abbr = "AVG"
    anchor_elo = 1500
    if opponent is not None and str(opponent).strip():
        from nba_api.stats.static import teams as _teams

        from ._core import coerce_team_id

        try:
            opp_id = coerce_team_id(opponent)
        except ValueError:
            return {"tool": "get_elo_standings", "ok": False,
                    "error": f"unknown team: {opponent}"}
        by_id = {t["id"]: t["abbreviation"] for t in _teams.get_teams()}
        anchor_abbr = by_id.get(opp_id, "")
        if not anchor_abbr or anchor_abbr not in elo:
            return {"tool": "get_elo_standings", "ok": False,
                    "error": f"unknown team: {opponent}"}
        anchor_elo = round(elo[anchor_abbr])
    table = []
    for t, v in elo.items():
        e = round(v)
        w, l = wins.get(t, 0), losses.get(t, 0)
        pct = round(_elo_expected(e - ELO_START), 4)
        table.append({"abbr": t, "elo": e, "games": w + l, "W": w, "L": l,
                      "elo_win_pct": pct, "win_equiv": round(pct * 82, 1)})
    table.sort(key=lambda d: d["elo"], reverse=True)
    for i, row in enumerate(table, 1):
        row["rank"] = i
    for row in table:
        row["elo_implied_spread"] = round(
            (row["elo"] - anchor_elo) / ELO_PER_POINT, 1)
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 30
    n_games = sum(wins.values())
    return {"tool": "get_elo_standings", "ok": True, "rows": table[:limit],
            "anchor": {"abbr": anchor_abbr, "elo": anchor_elo},
            "meta": {
                "source": "warehouse", "season": season,
                "games": n_games, "teams": len(table), "mov": mov_ok,
                "constants": (
                    "start 1500, K=20, build HCA=100, MOV mult "
                    "((margin+3)^0.8)/(7.5+0.006*|diff|), implied spread "
                    "≈ elo_diff/28"),
                "data_note": (
                    f"ELO computed from {n_games} real games in "
                    f"silver_hist_gamelogs for season {season} (5 seasons "
                    "2021-22 through 2025-26 live in the table; this run "
                    f"used {season} only). plus_minus present on 100% of "
                    "rows, so every game is MOV-adjusted. No games "
                    "fabricated; teams with no games get no rating.")}}

@tool(description='Simulated title and finals odds from ratings, Monte Carlo brackets.')
def get_playoff_sim(season: str | None = None, sims: int = 2000) -> dict[str, Any]:
    season = resolve_season(season)
    from .sim import run_playoff_sim

    try:
        sims = max(100, min(int(sims or 2000), 10000))
    except (TypeError, ValueError):
        sims = 2000
    from ._core import season_static as _season_static
    if _season_static(season):

        _po = get_playoffs.invoke({"season": season})
        if _po.get("ok"):
            _rows = dict(_po.get("rows") or {})

            _champ = _rows.get("champion")
            _rec = _rows.get("champion_record") or {}
            _rows["result_kind"] = "ACTUAL_RESULTS_NOT_SIMULATION"
            _rows["summary"] = (
                f"The {season} season is complete - these are the ACTUAL "
                f"playoff results, not a simulation"
                + (f": {_champ} won the championship "
                   f"{_rec.get('w')}-{_rec.get('l')}. " if _champ else ". ")
                + "Monte Carlo simulated odds are unavailable for a "
                  "completed season; they return when the next season "
                  "begins. Present these numbers as final results only.")
            return {"tool": "get_playoff_sim", "ok": True,
                    "rows": _rows,
                    "meta": {"season": season, "offseason": True,
                             "note": (f"{season} is complete - these are "
                                      "the ACTUAL playoff results, not "
                                      "simulations. Simulated odds return "
                                      "when the next season begins.")}}
        return {"tool": "get_playoff_sim", "ok": False,
                "error": f"{season} is complete - simulations are "
                         f"meaningless for a finished season.",
                "meta": {"season": season, "offseason": True}}
    out = run_playoff_sim(season, sims)
    if not out.get("teams"):
        return {"tool": "get_playoff_sim", "ok": False,
                "error": out.get("meta", {}).get("error", "no field")}
    return {"tool": "get_playoff_sim", "ok": True, "rows": out,
            "meta": {**out.get("meta", {}), "season": season, "sims": sims}}

_CONTRACT_WEIGHTS = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
                     "STL": 2.0, "BLK": 2.0, "TOV": -1.5}

def _contract_norm(s: object) -> str:
    import unicodedata as _ud

    return "".join(
        c for c in _ud.normalize("NFKD", str(s or ""))
        if not _ud.combining(c)
    ).strip().lower()

def _contract_tables(con) -> tuple[bool, set[str]]:
    tables = _warehouse_tables(con)
    return ({"silver_cap_players", "silver_leaders_pts"} <= tables,
            {r[1] for r in
             con.execute("PRAGMA table_info(silver_leaders_pts)").fetchall()})

def _contract_fetched(con) -> tuple[object, object]:
    try:
        return (con.execute(
            "SELECT MAX(_fetched_at) FROM silver_leaders_pts").fetchall()[0][0],
            con.execute(
                "SELECT MAX(_fetched_at) FROM silver_cap_players").fetchall()[0][0])
    except Exception:
        return None, None

def _contract_read(con, season: str):
    ready, have = _contract_tables(con)
    if not ready:
        return "empty", None, None, None, None
    prod = con.execute(
        """SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV
        FROM silver_leaders_pts WHERE _season = ?""", [season]).fetchall()
    cap = con.execute(
        "SELECT player, team, salary FROM silver_cap_players").fetchall()
    prod_date, cap_date = _contract_fetched(con)
    return None, have, prod, cap, (prod_date, cap_date)

def _contract_fitted(cap: list, by_name: dict, min_gp: int,
                     use_w: dict) -> list[dict[str, Any]]:
    fitted = []
    for player, team, salary in cap:
        r = by_name.get(_contract_norm(player))
        if r is None:
            continue
        _, lteam, gp, pts, reb, ast, stl, blk, tov = r
        gp = gp or 0
        if gp < min_gp or gp <= 0:
            continue
        vals = {"PTS": pts or 0, "REB": reb or 0, "AST": ast or 0,
                "STL": stl or 0, "BLK": blk or 0, "TOV": tov or 0}
        fitted.append({
            "PLAYER": player, "TEAM": team or lteam,
            "SALARY": salary or 0, "GP": gp,
            "SCORE": sum(vals[c] / gp * use_w[c] for c in use_w)})
    return fitted

def _contract_regression(fitted: list[dict[str, Any]]) -> tuple[float, float]:
    n = len(fitted)
    mx = sum(f["SCORE"] for f in fitted) / n
    my = sum(f["SALARY"] for f in fitted) / n
    var = sum((f["SCORE"] - mx) ** 2 for f in fitted)
    if var <= 0:
        raise ValueError("no production variance")
    slope = sum((f["SCORE"] - mx) * (f["SALARY"] - my)
                for f in fitted) / var
    intercept = my - slope * mx
    for f in fitted:
        f["PREDICTED"] = int(round(slope * f["SCORE"] + intercept))
        f["RESIDUAL"] = int(f["SALARY"]) - int(f["PREDICTED"])
        f["SCORE"] = round(f["SCORE"], 2)
    return slope, intercept

def _contract_team_scope(team_arg: str) -> str:
    if not team_arg:
        return ""
    try:
        from ._core import coerce_team_id as _cti
        from nba_api.stats.static import teams as _teams

        tid = _cti(team_arg)
        for t in _teams.get_teams():
            if t.get("id") == tid:
                return str(t.get("abbreviation", "")).upper()
    except (ValueError, TypeError):
        return ""
    return ""

def _contract_over_under(fitted: list[dict], span: int) -> list[dict]:
    return (sorted(fitted, key=lambda f: f["RESIDUAL"], reverse=True)[:span]
            + sorted(fitted, key=lambda f: f["RESIDUAL"])[:span])

def _contract_rows(fitted: list[dict], player_arg: str, team_scope: str):
    if player_arg:
        want = _contract_norm(player_arg)
        matched = [f for f in fitted if _contract_norm(f.get("PLAYER")) == want]
        if not matched:
            return None, f"no qualified value row for {player_arg}"
        return matched[:1], None
    if team_scope:
        scoped = [f for f in fitted
                  if str(f.get("TEAM") or "").upper() == team_scope]
        if not scoped:
            return None, f"no qualified players on {team_scope}"
        return _contract_over_under(scoped, 5), None
    return _contract_over_under(fitted, 10), None

@tool(description="Contract value residuals from production vs salary.\n\nReturns league leaders by default; pass team for one roster or player for\none named player's modeled salary and residual.")
def get_contract_value(season: str | None = None, min_gp: int = 20,
                       team: str = "", player: str = "") -> dict[str, Any]:
    season = str(resolve_season(season) or "").strip() or resolve_season(None)
    try:
        min_gp = max(10, min(int(min_gp), 82))
    except (TypeError, ValueError):
        min_gp = 20

    with _owned_connection(None) as con:
        err, have, prod, cap, dates = _contract_read(con, season)
    if err:
        return {"tool": "get_contract_value", "ok": False, "error": err}
    if not prod:
        return {"tool": "get_contract_value", "ok": False,
                "error": f"no production rows for {season}"}
    missing = [c for c in _CONTRACT_WEIGHTS if c not in have]
    use_w = {c: (0.0 if c in missing else w)
             for c, w in _CONTRACT_WEIGHTS.items()}
    by_name: dict[str, tuple] = {}
    for r in prod:
        by_name.setdefault(_contract_norm(r[0]), r)
    fitted = _contract_fitted(cap, by_name, min_gp, use_w)
    if len(fitted) < 2:
        return {"tool": "get_contract_value", "ok": False,
                "error": "not enough qualified players"}
    try:
        slope, intercept = _contract_regression(fitted)
    except ValueError as exc:
        return {"tool": "get_contract_value", "ok": False, "error": str(exc)}
    team_scope = _contract_team_scope(str(team or "").strip())
    rows, row_error = _contract_rows(fitted, str(player or "").strip(),
                                     team_scope)
    if rows is None:
        return {"tool": "get_contract_value", "ok": False, "error": row_error}
    prod_date, cap_date = dates
    return {"tool": "get_contract_value", "ok": True, "rows": rows,
            "meta": {"formula": (
                          "score = PTS + 1.2*REB + 1.5*AST + 2*STL + 2*BLK - "
                          "1.5*TOV (per game); salary_hat = slope*score + "
                          "intercept (OLS by hand); residual = salary - "
                          "salary_hat"),
                     "weights": _CONTRACT_WEIGHTS,
                     "missing_columns_zero_weight": missing,
                     "slope": round(slope, 2), "intercept": round(intercept, 2),
                     "n_qualified": len(fitted), "min_gp": min_gp,
                     "production_season": season,
                     "salary_season": _salary_vintage()[0] or "2026-27",
                     "production_date": prod_date, "salary_date": cap_date,
                     "overpaid_first": True,
                     "team_scope": team_scope or None}}

@tool(description='Star-probability classifier from college production (honest proxy).')
def get_draft_model(season: str = "2025") -> dict[str, Any]:
    season = resolve_season(season)
    try:
        from ..sources import cbb as _cbb
        from sklearn.linear_model import LogisticRegression
        season = _norm_draft_year(season)
        prod = _cbb.get_player_stats(int(season))
        if not prod.ok or prod.frame.height == 0:
            return {"tool": "get_draft_model", "ok": False,
                    "error": prod.error or "college stats empty"}
        feats = ["PTS", "TS_PCT", "USG", "REB", "AST"]
        pls = [p for p in prod.frame.to_dicts()
               if all(p.get(k) is not None for k in feats)]
        if len(pls) < 50:
            return {"tool": "get_draft_model", "ok": False,
                    "error": "not enough rows"}
        scores = [float(p["PTS"]) * 2 + float(p["TS_PCT"]) * 50
                  + float(p["USG"]) for p in pls]
        cut = sorted(scores, reverse=True)[max(0, len(scores) // 10 - 1)]
        y = [1 if s >= cut else 0 for s in scores]
        mus = [sum(float(p[f]) for p in pls) / len(pls) for f in feats]
        sds = []
        for j, f in enumerate(feats):
            v = sum((float(p[f]) - mus[j]) ** 2 for p in pls) / len(pls)
            sds.append(v ** 0.5 or 1.0)
        X = [[(float(p[f]) - mus[j]) / sds[j] for j, f in enumerate(feats)]
             for p in pls]
        clf = LogisticRegression(max_iter=1000).fit(X, y)
        proba = [float(v) for v in clf.predict_proba(X)[:, 1]]
        acc = sum((pr >= 0.5) == bool(t) for pr, t in zip(proba, y)) / len(y)
        top = sorted(range(len(pls)), key=lambda i: proba[i], reverse=True)[:20]
        rows = [{"PLAYER": pls[i].get("PLAYER_NAME"), "TEAM": pls[i].get("TEAM"),
                 "PTS": pls[i].get("PTS"), "TS_PCT": pls[i].get("TS_PCT"),
                 "USG": pls[i].get("USG"), "STAR_P": round(proba[i], 3)}
                for i in top]
        meta = {"source": "barttorvik+sklearn", "season": str(season),
                "n": len(pls), "features": feats,
                "label": "top-decile of 2*PTS+50*TS+USG",
                "accuracy": round(acc, 3),
                "disclaimer": "Label is a production proxy, not real NBA "
                "outcomes. In-sample accuracy only, no cross-validation."}
        return {"tool": "get_draft_model", "ok": True, "rows": rows, "meta": meta}
    except Exception as exc:
        return {"tool": "get_draft_model", "ok": False,
                "error": str(exc)[:200]}

@tool(description='Risers and fallers: last-N win pct vs season win pct, warehouse only.')
def get_risers(season: str | None = None, weeks: int = 4) -> dict[str, Any]:
    season = resolve_season(season)
    from .. import store as _store

    season = str(season or "").strip() or resolve_season(None)
    try:
        weeks = max(1, min(int(weeks or 4), 8))
    except (TypeError, ValueError):
        weeks = 4
    n = max(5, min(round(weeks * 2.5), 15))
    con = _store.connect()
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
    from ._core import season_static as _season_static
    offseason = _season_static(season)
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
    season = resolve_season(season)
    from .. import store as _store

    season = str(season or "").strip() or resolve_season(None)
    try:
        n = max(5, min(int(n or 10), 15))
    except (TypeError, ValueError):
        n = 10
    con = _store.connect()
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
    from ._core import season_static as _season_static
    if _season_static(season):

        meta["offseason"] = True
        meta["note"] = (f"{season} is complete; these are end-of-season "
                        f"form windows, not current risers. No NBA games "
                        f"until preseason.")
    return {"tool": "get_player_risers", "ok": True,
            "rows": {"risers": table[:8], "fallers": table[-8:][::-1]},
            "meta": meta}

def _ensure_leaderboard_snapshots(con: Any) -> None:
    con.execute(
        """CREATE TABLE IF NOT EXISTS leaderboard_snapshots(
        snapshot_date VARCHAR, player VARCHAR, team VARCHAR,
        pts INTEGER, rank INTEGER)"""
    )
    cols = {r[0].lower() for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'leaderboard_snapshots'").fetchall()}
    if "season" not in cols:
        con.execute("ALTER TABLE leaderboard_snapshots ADD COLUMN season VARCHAR")

    con.execute(
        "UPDATE leaderboard_snapshots SET season = ? WHERE season IS NULL",
        [last_completed_season()],
    )

@tool(description="Capture today's top-50 scoring leaderboard. Idempotent per date.")
def snapshot_leaderboard(season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    from datetime import datetime, timezone

    from .. import store as _store

    season = str(season or "").strip() or resolve_season(None)
    today = datetime.now(timezone.utc).date().isoformat()
    con = _store.connect()
    try:
        with _store.write_guard():
            _ensure_leaderboard_snapshots(con)
            hit = con.execute(
                """SELECT COUNT(*) FROM leaderboard_snapshots
                WHERE snapshot_date = ? AND season = ?""",
                [today, season],
            ).fetchone()
            if hit and hit[0]:
                return {"tool": "snapshot_leaderboard", "ok": True,
                        "rows": {"snapshot_date": today,
                                 "captured": int(hit[0]), "added": False},
                        "meta": {"source": "leaderboard_snapshots",
                                 "season": season}}
            leaders = con.execute(
                """SELECT PLAYER, TEAM, PTS, RANK FROM silver_leaders_pts
                WHERE _season = ? ORDER BY RANK ASC LIMIT 50""",
                [season],
            ).fetchall()
            if not leaders:
                return {"tool": "snapshot_leaderboard", "ok": False,
                        "error": f"no scoring leaders for {season}"}
            con.execute(
                "DELETE FROM leaderboard_snapshots WHERE snapshot_date = ? AND season = ?",
                [today, season],
            )
            for player, team, pts, rank in leaders:
                con.execute(
                    "INSERT INTO leaderboard_snapshots VALUES (?,?,?,?,?,?)",
                    [today, player, team, pts, rank, season],
                )
            captured = len(leaders)
    finally:
        con.close()
    return {"tool": "snapshot_leaderboard", "ok": True,
            "rows": {"snapshot_date": today, "captured": captured,
                     "added": True},
            "meta": {"source": "leaderboard_snapshots", "season": season}}

@tool(description='Scoring leaderboard movers: latest snapshot vs the one from days ago.')
def get_leaderboard_deltas(season: str | None = None, days: int = 7) -> dict[str, Any]:
    season = resolve_season(season)
    from datetime import date as _date
    from datetime import timedelta as _td

    from .. import store as _store

    season = str(season or "").strip() or resolve_season(None)
    try:
        days = max(1, int(days or 7))
    except (TypeError, ValueError):
        days = 7
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "leaderboard_snapshots" not in tables:
            return {"tool": "get_leaderboard_deltas", "ok": False,
                    "error": "not enough snapshots — run snapshot_leaderboard daily"}
        dates = [r[0] for r in con.execute(
            """SELECT DISTINCT snapshot_date FROM leaderboard_snapshots
            WHERE season = ? ORDER BY snapshot_date DESC""",
            [season]).fetchall()]
        if len(dates) < 2:
            return {"tool": "get_leaderboard_deltas", "ok": False,
                    "error": "not enough snapshots — run snapshot_leaderboard daily"}
        latest = dates[0]
        try:
            cutoff = _date.fromisoformat(str(latest)) - _td(days=days)
            base = next((d for d in dates[1:]
                         if _date.fromisoformat(str(d)) <= cutoff), dates[-1])
        except (TypeError, ValueError):
            base = dates[-1]
        now_rows = con.execute(
            """SELECT player, team, pts, rank FROM leaderboard_snapshots
            WHERE snapshot_date = ? AND season = ?""",
            [latest, season],
        ).fetchall()
        base_rows = con.execute(
            """SELECT player, team, pts, rank FROM leaderboard_snapshots
            WHERE snapshot_date = ? AND season = ?""",
            [base, season],
        ).fetchall()
    finally:
        con.close()
    now = {str(r[0]).lower(): r for r in now_rows}
    was = {str(r[0]).lower(): r for r in base_rows}
    climbers, fallers, new_entries = [], [], []
    for key, (player, team, pts, rank) in now.items():
        old = was.get(key)
        if old is None:
            new_entries.append({"player": player, "team": team,
                                "pts": pts, "rank": rank})
            continue
        change = (old[3] or 0) - (rank or 0)
        if change > 0:
            climbers.append({"player": player, "team": team,
                             "rank_base": old[3], "rank_now": rank,
                             "rank_change": change,
                             "pts_base": old[2], "pts_now": pts,
                             "pts_change": (pts or 0) - (old[2] or 0)})
        elif change < 0:
            fallers.append({"player": player, "team": team,
                            "rank_base": old[3], "rank_now": rank,
                            "rank_change": change,
                            "pts_base": old[2], "pts_now": pts,
                            "pts_change": (pts or 0) - (old[2] or 0)})
    climbers.sort(key=lambda d: d["rank_change"], reverse=True)
    fallers.sort(key=lambda d: d["rank_change"])
    new_entries.sort(key=lambda d: d["rank"] or 999)
    try:
        span = (_date.fromisoformat(str(latest))
                - _date.fromisoformat(str(base))).days
    except (TypeError, ValueError):
        span = 0
    return {"tool": "get_leaderboard_deltas", "ok": True,
            "rows": {"climbers": climbers[:10], "fallers": fallers[:10],
                     "new_entries": new_entries},
            "meta": {"source": "leaderboard_snapshots", "season": season,
                     "current_date": latest, "base_date": base,
                     "days_requested": days, "days_actual": span}}

_DAY = 24 * 3600

FRESHNESS_RULES: dict[str, tuple[str, float | None]] = {
    "silver_scoreboard": ("daily in season", 36 * 3600),
    "silver_standings": ("daily in season", 36 * 3600),
    "silver_injuries": ("daily in season", 36 * 3600),
    "silver_leaders_pts": ("daily in season", 36 * 3600),
    "silver_leaders_ast": ("daily in season", 36 * 3600),
    "silver_leaders_reb": ("daily in season", 36 * 3600),
    "silver_leaders_stl": ("daily in season", 36 * 3600),
    "silver_leaders_blk": ("daily in season", 36 * 3600),
    "silver_leaders_dreb": ("daily in season", 36 * 3600),
    "silver_leaders_fg_pct": ("daily in season", 36 * 3600),
    "silver_player_gamelogs": ("daily in season", 36 * 3600),
    "silver_player_season": ("static seed (bbref per-game)", None),
    "silver_zone_splits": ("static seed (bbref shooting)", None),
    "silver_team_games": ("daily in season", 36 * 3600),
    "silver_four_factors_team": ("derived from silver_team_games (offline build)", None),
    "silver_boxscores": ("daily in season", 36 * 3600),
    "silver_shots": ("daily in season", 36 * 3600),
    "silver_playoff_inactive": ("static seed (bbref inactive listings)", None),
    "silver_schedule": ("daily in season", 36 * 3600),
    "silver_hustle_player": ("daily in season", 36 * 3600),
    "silver_hustle_team": ("daily in season", 36 * 3600),
    "silver_advanced": ("daily in season", 36 * 3600),
    "silver_four_factors": ("daily in season", 36 * 3600),
    "silver_clutch": ("daily in season", 36 * 3600),
    "silver_team_ratings": ("daily in season", 36 * 3600),
    "silver_on_off": ("daily in season", 36 * 3600),
    "silver_lineups": ("daily in season", 36 * 3600),
    "silver_wowy": ("daily in season", 36 * 3600),
    "silver_rosters": ("daily in season", 36 * 3600),
    "silver_salaries": ("weekly", 7 * _DAY),
    "silver_cap_players": ("weekly", 7 * _DAY),
    "silver_combine": ("weekly", 7 * _DAY),
    "silver_playoffs": ("seasonal", 400 * _DAY),
    "silver_playoff_gamelogs": ("seasonal", 400 * _DAY),
    "silver_hist_gamelogs": ("static", None),
    "silver_hist_draft": ("static", None),
    "silver_hist_hustle": ("static", None),
    "silver_hist_lineups": ("static", None),
    "silver_hist_possessions": ("static", None),
    "silver_hist_shots": ("static", None),
    "silver_hist_standings": ("static", None),
    "silver_hist_player_seasons": ("static", None),
    "silver_raptor_player": ("static", None),
    "silver_raptor_team": ("static", None),
    "silver_rapm": ("static", None),
    "silver_rapm_prior": ("static", None),
    "silver_hist_pbp": ("static", None),
    "silver_bbref_gamelogs_2024_25": ("static", None),
}

def _parse_ts(raw: object):
    from datetime import datetime as _dt, timezone as _tz

    try:
        ts = _dt.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_tz.utc)
    return ts

def _freshness_row(table: str, rows: int, last_fetch: object,
                   now) -> dict[str, Any]:
    label, max_age = FRESHNESS_RULES.get(table, ("unknown", None))
    known = table in FRESHNESS_RULES
    expected, threshold = label, max_age
    if label == "daily in season" and now.month not in _IN_SEASON_MONTHS:
        expected, threshold = "weekly (offseason)", 7 * _DAY
    ts = _parse_ts(last_fetch) if last_fetch else None
    age_hours: float | None = None
    stale: bool | None = None
    if ts is not None:
        age_hours = round((now - ts).total_seconds() / 3600, 1)
        if known:
            stale = threshold is not None and age_hours * 3600 > threshold
    return {"table": table, "rows": rows,
            "last_fetch": str(last_fetch) if ts is not None else "unknown",
            "age_hours": age_hours, "expected": expected, "stale": stale}

def _warehouse_table_meta() -> list[tuple[str, int, str | None]]:
    from .. import store as _store

    con = _store.connect(read_only=True)
    try:
        tables = sorted(
            r[0] for r in con.execute("SHOW TABLES").fetchall()
            if r[0].startswith("silver_"))
        if not tables:
            return []
        has_ts = {}
        for t in tables:
            has_ts[t] = any(
                r[1] == "_fetched_at"
                for r in con.execute(f"PRAGMA table_info({t})").fetchall())
        parts = []
        for t in tables:
            mx = "MAX(_fetched_at)" if has_ts[t] else "CAST(NULL AS VARCHAR)"
            parts.append(f"SELECT '{t}' AS t, COUNT(*) AS n, {mx} AS mx FROM {t}")
        return [(r[0], r[1], r[2]) for r in
                con.execute(" UNION ALL ".join(parts)).fetchall()]
    finally:
        con.close()

@tool(description='Warehouse freshness panel: every silver table, row count, last fetch, stale flag.')
def get_warehouse_freshness() -> dict[str, Any]:
    from datetime import datetime as _dt, timezone as _tz

    now = _dt.now(_tz.utc)
    try:
        meta = _warehouse_table_meta()
    except Exception as exc:
        return {"tool": "get_warehouse_freshness", "ok": False,
                "error": str(exc)[:200]}
    rows = [_freshness_row(t, n, last, now) for t, n, last in meta]
    stale_n = sum(1 for r in rows if r["stale"])
    unknown_n = sum(1 for r in rows if r["stale"] is None)
    return {"tool": "get_warehouse_freshness", "ok": True, "rows": rows,
            "meta": {"source": "warehouse",
                     "generated_at": now.isoformat(),
                     "tables": len(rows), "stale": stale_n,
                     "unknown": unknown_n,
                     "in_season": now.month in _IN_SEASON_MONTHS}}

@tool(description='Multi-season regular-season records for one team, newest first.\n\nThis is a trajectory evidence primitive, not a trend opinion. It reads\ncomplete historical standings and returns record and win percentage for\na bounded number of seasons ending at through_season.')
def get_team_trajectory(
    team: str | int, seasons: int = 3, through_season: str | None = None,
) -> dict[str, Any]:
    through_season = resolve_season(through_season)
    from .. import store as _store
    from ._core import coerce_team_id

    try:
        team_id = coerce_team_id(team)
        limit = max(2, min(int(seasons), 10))
    except (ValueError, TypeError):
        return {"tool": "get_team_trajectory", "ok": False,
                "error": f"unknown team or invalid season count: {team!r}"}
    con = _store.connect(read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_standings" not in tables:
            return {"tool": "get_team_trajectory", "ok": False,
                    "error": "historical standings are unavailable"}
        columns = {row[1] for row in
                   con.execute("PRAGMA table_info(silver_hist_standings)").fetchall()}
        season_type = (" AND season_type = 'regular-season'"
                       if "season_type" in columns else "")
        rows = con.execute(
            "SELECT _season, wins, losses, win_pct "
            "FROM silver_hist_standings WHERE CAST(team_id AS VARCHAR) = ? "
            "AND _season <= ?" + season_type +
            " ORDER BY _season DESC LIMIT ?",
            [str(team_id), through_season, limit],
        ).fetchall()
    except Exception as exc:
        return {"tool": "get_team_trajectory", "ok": False,
                "error": str(exc)[:200]}
    finally:
        con.close()
    if not rows:
        return {"tool": "get_team_trajectory", "ok": False,
                "error": f"no historical standings through {through_season}"}
    return {
        "tool": "get_team_trajectory", "ok": True,
        "rows": [{"team": str(team), "team_id": str(team_id),
                  "season": season, "wins": int(wins),
                  "losses": int(losses), "record": f"{int(wins)}-{int(losses)}",
                  "win_pct": round(float(win_pct), 3)}
                 for season, wins, losses, win_pct in rows],
        "meta": {"source": "warehouse silver_hist_standings",
                 "through_season": through_season,
                 "coverage": "regular-season records, newest first"},
    }
