import ast
from datetime import datetime as _dt
import json
from typing import Any

from langchain_core.tools import tool

from .._core import coerce_player_id, coerce_team_id
from ..gamelog import playoff_inactive_note as _pin
from ..splits import _resolve_name as _rn
from ._helpers import _owned_connection, _pkg, _warehouse_tables


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
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ...sources import espn

    rows, meta = pkg._warehouse_or_live(
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
    pkg = _pkg()
    store = pkg.store
    season = pkg.resolve_season(season)
    frame = store.read_frame(
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
    pkg = _pkg()
    season = pkg.resolve_season(season)
    rows, meta = pkg._warehouse_or_live(
        "silver_standings", "_season = ?",
        [season], lambda: pkg.nba_stats.standings(season), season,
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
    pkg = _pkg()
    season = str(pkg.resolve_season(season) or "").strip() or pkg.resolve_season(None)
    try:
        top = max(1, min(int(top or 5), 15))
    except (TypeError, ValueError):
        top = 5

    con = pkg.store.connect()
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
    try:
        return _dt.strptime(str(clock), "%b %d, %Y")
    except (TypeError, ValueError):
        return _dt.min


def _finder_player_streak(season: str, team_abbrev: str):
    if not team_abbrev:
        return _finder_error("player needed")
    try:
        pid = coerce_player_id(team_abbrev)
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
    if not team_abbrev or not opponent:
        return _finder_error("two players needed")
    try:
        pa = coerce_player_id(team_abbrev)
        pb = coerce_player_id(opponent)
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
    season = _pkg().resolve_season(season)
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


@tool(description='Multi-season regular-season records for one team, newest first.\n\nThis is a trajectory evidence primitive, not a trend opinion. It reads\ncomplete historical standings and returns record and win percentage for\na bounded number of seasons ending at through_season.')
def get_team_trajectory(
    team: str | int, seasons: int = 3, through_season: str | None = None,
) -> dict[str, Any]:
    pkg = _pkg()
    through_season = pkg.resolve_season(through_season)
    try:
        team_id = coerce_team_id(team)
        limit = max(2, min(int(seasons), 10))
    except (ValueError, TypeError):
        return {"tool": "get_team_trajectory", "ok": False,
                "error": f"unknown team or invalid season count: {team!r}"}
    con = pkg.store.connect(read_only=True)
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
