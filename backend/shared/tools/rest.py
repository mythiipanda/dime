"""Rest advantage over warehouse scoreboard games. Edge before tip-off.

Rest is calendar days since a team's previous game minus 1, so a
back-to-back is rest_days == 0 and the team's first game in scope has
no baseline (None). Edge is own rest minus opponent rest before the
same game, both read off the two teams' own schedules. Warehouse only;
nothing is estimated or fabricated.
"""

import datetime as _dt
from dataclasses import dataclass
from typing import Any

import duckdb
from langchain_core.tools import tool

from ._core import SEASON, clamp_season

_REST_NOTE = (
    "Rest = calendar days since the team's previous game minus 1; "
    "edge = own rest minus opponent rest before the same game. "
    "First game in scope has no rest baseline."
)


@dataclass
class TeamGame:
    """One team-game: a single team's side of one scoreboard game."""

    date: _dt.date
    team: str
    opponent: str
    home: bool
    pts_for: int
    pts_against: int
    won: bool
    season_type: str  # "regular" | "playoffs"
    rest_days: int | None = None
    opp_rest_days: int | None = None
    rest_diff: int | None = None


def build_schedule(rows: list[dict[str, Any]]) -> list[TeamGame]:
    """Expand scoreboard rows into per-team games with rest gaps filled.

    Pure: no warehouse access. Each row needs date (datetime.date),
    home_team, visitor_team (abbreviations), home_pts, visitor_pts
    (ints), and season_type ("regular" | "playoffs"). Returns one
    TeamGame per team per game, sorted by (team, date). rest_days is
    (date - previous team game date).days - 1, None for the team's
    first game in scope; rest_diff is own rest minus the opponent's
    rest before the same game, None when either side has no baseline.
    """
    games: list[TeamGame] = []
    for r in rows or []:
        d = r.get("date")
        if not isinstance(d, _dt.date):
            continue
        home = str(r.get("home_team") or "").upper()
        vis = str(r.get("visitor_team") or "").upper()
        if not home or not vis:
            continue
        try:
            hp = int(r.get("home_pts"))  # type: ignore[arg-type]
            vp = int(r.get("visitor_pts"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        st = str(r.get("season_type") or "regular")
        games.append(TeamGame(date=d, team=home, opponent=vis, home=True,
                              pts_for=hp, pts_against=vp, won=hp > vp,
                              season_type=st))
        games.append(TeamGame(date=d, team=vis, opponent=home, home=False,
                              pts_for=vp, pts_against=hp, won=vp > hp,
                              season_type=st))
    by_team: dict[str, list[TeamGame]] = {}
    for g in games:
        by_team.setdefault(g.team, []).append(g)
    for gs in by_team.values():
        gs.sort(key=lambda g: g.date)
        prev: _dt.date | None = None
        for g in gs:
            if prev is None:
                g.rest_days = None
            else:
                g.rest_days = (g.date - prev).days - 1
            prev = g.date
    mirror = {(g.date, g.team, g.opponent): g for g in games}
    for g in games:
        opp = mirror.get((g.date, g.opponent, g.team))
        g.opp_rest_days = opp.rest_days if opp is not None else None
        if g.rest_days is None or g.opp_rest_days is None:
            g.rest_diff = None
        else:
            g.rest_diff = g.rest_days - g.opp_rest_days
    games.sort(key=lambda g: (g.team, g.date))
    return games


def summarize_team(games: list[TeamGame]) -> dict[str, Any]:
    """One summary line over a team's games. Pure: no warehouse access."""
    games = list(games or [])
    gp = len(games)
    wins = sum(1 for g in games if g.won)
    losses = sum(1 for g in games if not g.won)
    dist = {"b2b": 0, "1_day": 0, "2_days": 0, "3_plus": 0}
    for g in games:
        r = g.rest_days
        if r is None:
            continue
        if r <= 0:
            dist["b2b"] += 1
        elif r == 1:
            dist["1_day"] += 1
        elif r == 2:
            dist["2_days"] += 1
        else:
            dist["3_plus"] += 1
    measured = [g.rest_days for g in games if g.rest_days is not None]
    diffs = [g.rest_diff for g in games if g.rest_diff is not None]
    edge = [g for g in games
            if g.rest_diff is not None and g.rest_diff > 0]
    even = [g for g in games
            if g.rest_diff is not None and g.rest_diff == 0]
    disadvantage = [g for g in games
                    if g.rest_diff is not None and g.rest_diff < 0]

    def _record(gs: list[TeamGame]) -> str:
        w = sum(1 for g in gs if g.won)
        return f"{w}-{len(gs) - w}"

    return {
        "games": gp,
        "wins": wins,
        "losses": losses,
        "back_to_backs": sum(1 for g in games if g.rest_days == 0),
        "rest_distribution": dist,
        "avg_rest_days": round(sum(measured) / len(measured), 2)
        if measured else 0.0,
        "avg_rest_diff": round(sum(diffs) / len(diffs), 2)
        if diffs else 0.0,
        "record_with_edge": _record(edge),
        "record_even": _record(even),
        "record_at_disadvantage": _record(disadvantage),
        "games_with_edge_measured": len(diffs),
        "quotable": f"{_record(edge)} with a rest edge vs "
                    f"{_record(disadvantage)} at a rest disadvantage "
                    f"({_record(even)} on even rest)",
    }


def _parse_scoreboard_date(s: object) -> _dt.date | None:
    try:
        return _dt.datetime.strptime(str(s or "")[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _resolve_team(raw: object) -> str | None:
    """Resolve an abbrev, full name, nickname, or city to an abbreviation.

    Case-insensitive over the static tables, like headtohead. Returns
    None when nothing matches.
    """
    from nba_api.stats.static import teams

    s = str(raw or "").strip().lower()
    if not s:
        return None
    for t in teams.get_teams():
        if s == str(t.get("abbreviation") or "").lower():
            return str(t.get("abbreviation")).upper()
    for t in teams.get_teams():
        if s == str(t.get("full_name") or "").lower():
            return str(t.get("abbreviation")).upper()
    for t in teams.get_teams():
        if s == str(t.get("nickname") or "").lower():
            return str(t.get("abbreviation")).upper()
    for t in teams.get_teams():
        if s == str(t.get("city") or "").lower():
            return str(t.get("abbreviation")).upper()
    return None


def _classify_scoreboard_rows(
    fetched: list[tuple],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Split raw scoreboard tuples into classified rows plus drop counts.

    Pure: no warehouse access. fetched are raw SQL tuples
    (GAME_DATE_EST, GAME_ID, home, vis, hp, vp). Rows with NULL scores
    (unscored preseason games), unknown game_id prefixes, or unparseable
    dates are dropped and counted, never entering rest math.
    """
    rows: list[dict[str, Any]] = []
    dropped = {"null_score": 0, "unknown_game_type": 0,
               "unparseable_date": 0}
    for gdate, gid, home, vis, hp, vp in fetched:
        if hp is None or vp is None:
            dropped["null_score"] += 1
            continue
        d = _parse_scoreboard_date(gdate)
        if d is None:
            dropped["unparseable_date"] += 1
            continue
        prefix = str(gid or "")[:3]
        if prefix == "002":
            st = "regular"
        elif prefix == "004":
            st = "playoffs"
        else:
            dropped["unknown_game_type"] += 1
            continue
        rows.append({
            "date": d,
            "home_team": str(home or "").upper(),
            "visitor_team": str(vis or "").upper(),
            "home_pts": hp,
            "visitor_pts": vp,
            "season_type": st,
        })
    return rows, dropped


def _load_scoreboard(
    season: str,
) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    from .. import store as _store

    # Read-only connect: this tool never writes, and it must not grab a
    # write lock while seed jobs run against the same warehouse file.
    con = _store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_scoreboard" not in tables:
            return [], {"null_score": 0, "unknown_game_type": 0,
                        "unparseable_date": 0}, \
                "warehouse is empty (silver_scoreboard missing)"
        fetched = con.execute(
            """SELECT GAME_DATE_EST, GAME_ID, HOME_TEAM_ABBREVIATION,
                      VISITOR_TEAM_ABBREVIATION, HOME_TEAM_PTS,
                      VISITOR_TEAM_PTS
                FROM silver_scoreboard
                WHERE _season = ?""",
            [season],
        ).fetchall()
    finally:
        con.close()
    rows, dropped = _classify_scoreboard_rows(fetched)
    return rows, dropped, ""


def _game_row(g: TeamGame) -> dict[str, Any]:
    return {
        "date": g.date.isoformat(),
        "opponent": g.opponent,
        "home": g.home,
        "result": "W" if g.won else "L",
        "pts_for": g.pts_for,
        "pts_against": g.pts_against,
        "rest_days": g.rest_days,
        "opp_rest_days": g.opp_rest_days,
        "rest_diff": g.rest_diff,
    }


@tool
def get_rest_advantage(team: str = "league", season: str = SEASON,
                       season_type: str = "all", date: str = "",
                       opponent: str = "") -> dict[str, Any]:
    """Rest advantage: who had the fresher legs before each game.

    team: 3-letter abbrev, full team name, or "league"/"" for all 30
    teams. season_type: regular, playoffs, or all (default). Games are
    filtered to the season_type BEFORE rest gaps are computed, so rest
    never leaks across the filter boundary. Warehouse only; the first
    game in scope has no rest baseline and reports None.
    date: optional YYYY-MM-DD; team mode only. With date and no
    opponent, returns the team's single game on that date (summary
    still covers the full season as quotable context). opponent:
    optional second team; team mode only. Team + opponent + date
    returns the completed matchup on that date when one exists, else a
    pre-tip-off preview projecting each side's rest from its last
    completed game before that date (preview mode: not a warehouse
    game record). Team + opponent with no date returns their most
    recent completed matchup.
    """
    season = clamp_season(season)
    st = str(season_type or "all").strip().lower()
    if st not in ("regular", "playoffs", "all"):
        return {"tool": "get_rest_advantage", "ok": False,
                "error": f"bad season_type: {season_type}"
                         " (use regular, playoffs, or all)"}
    want_all = (not str(team or "").strip()
                or str(team).strip().lower() == "league")
    date_str = str(date or "").strip()
    opp_raw = str(opponent or "").strip()
    if want_all and (date_str or opp_raw):
        return {"tool": "get_rest_advantage", "ok": False,
                "error": "date and opponent require a specific team"
                         " (not league)"}
    day: _dt.date | None = None
    if date_str:
        try:
            day = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return {"tool": "get_rest_advantage", "ok": False,
                    "error": f"bad date: {date_str} (use YYYY-MM-DD)"}
    abbr: str | None = None
    if not want_all:
        abbr = _resolve_team(team)
        if abbr is None:
            return {"tool": "get_rest_advantage", "ok": False,
                    "error": f"unknown team: {team}"}
    opp_abbr: str | None = None
    if opp_raw:
        opp_abbr = _resolve_team(opp_raw)
        if opp_abbr is None:
            return {"tool": "get_rest_advantage", "ok": False,
                    "error": f"unknown team: {opponent}"}
    try:
        rows, dropped, error = _load_scoreboard(season)
    except (duckdb.IOException, duckdb.ConnectionException, duckdb.Error):
        return {"tool": "get_rest_advantage", "ok": False,
                "error": "warehouse temporarily unavailable "
                         "(file lock contention); retry shortly"}
    if error:
        return {"tool": "get_rest_advantage", "ok": False, "error": error}
    if st != "all":
        rows = [r for r in rows if r["season_type"] == st]
    if not rows:
        detail = f"no {st} games for {season}" if st != "all" \
            else f"no games for {season}"
        return {"tool": "get_rest_advantage", "ok": False, "error": detail}
    schedule = build_schedule(rows)
    by_team: dict[str, list[TeamGame]] = {}
    for g in schedule:
        by_team.setdefault(g.team, []).append(g)
    games_scanned = len(rows)
    meta: dict[str, Any] = {
        "source": "warehouse",
        "season": season,
        "season_type": st,
        "coverage": {"games_scanned": games_scanned,
                      "teams": len(by_team),
                      "games_dropped": sum(dropped.values()),
                      "games_dropped_detail": dict(dropped)},
        "note": _REST_NOTE + f" Games filtered to '{st}' before"
                " computing rest gaps. Dropped scoreboard rows (null"
                " scores, unknown game types, unparseable dates) never"
                " enter rest math.",
    }
    if date_str:
        meta["date"] = date_str
    if want_all:
        teams = [{"team": t, **summarize_team(gs)}
                 for t, gs in sorted(by_team.items())]
        teams.sort(key=lambda s: s["avg_rest_diff"], reverse=True)
        return {"tool": "get_rest_advantage", "ok": True,
                "rows": {"teams": teams, "count": len(teams)}, "meta": meta}
    assert abbr is not None
    games = by_team.get(abbr, [])
    if not games:
        return {"tool": "get_rest_advantage", "ok": False,
                "error": f"no {st} games for {abbr} in {season}"}
    summary = summarize_team(games)
    if opp_abbr is not None and day is not None:
        # (a) completed matchup on the exact date.
        on_date = [g for g in games
                   if g.date == day and g.opponent == opp_abbr]
        if on_date:
            g = on_date[0]
            return {"tool": "get_rest_advantage", "ok": True,
                    "rows": {"team": abbr, "opponent": opp_abbr,
                             "summary": summary,
                             "games": [_game_row(g)]}, "meta": meta}
        # (b) preview mode: rest from each side's last completed game
        # strictly before D, within the season_type filter.
        assert day is not None
        own_prior = [g for g in games if g.date < day]
        opp_prior = [g for g in by_team.get(opp_abbr, [])
                     if g.date < day]
        if not own_prior:
            return {"tool": "get_rest_advantage", "ok": False,
                    "error": f"no completed games for {abbr} before "
                             f"{date_str} — cannot establish a rest "
                             "baseline"}
        if not opp_prior:
            return {"tool": "get_rest_advantage", "ok": False,
                    "error": f"no completed games for {opp_abbr} before "
                             f"{date_str} — cannot establish a rest "
                             "baseline"}
        last_own = own_prior[-1]
        last_opp = opp_prior[-1]
        rest_own = (day - last_own.date).days - 1
        rest_opp = (day - last_opp.date).days - 1
        meta["note"] = meta["note"] + " Pre-tip-off projection computed" \
            " from each team's last completed game; not a warehouse" \
            " game record."
        return {"tool": "get_rest_advantage", "ok": True,
                "rows": {"team": abbr, "opponent": opp_abbr,
                         "summary": summary,
                         "preview": {"date": date_str,
                                     "team_rest_days": rest_own,
                                     "team_last_game":
                                         last_own.date.isoformat(),
                                     "opp_rest_days": rest_opp,
                                     "opp_last_game":
                                         last_opp.date.isoformat(),
                                     "rest_diff": rest_own - rest_opp}},
                "meta": meta}
    if opp_abbr is not None:
        matchups = [g for g in games if g.opponent == opp_abbr]
        if not matchups:
            return {"tool": "get_rest_advantage", "ok": False,
                    "error": f"no completed games between {abbr} and "
                             f"{opp_abbr} in {season}"}
        g = matchups[-1]
        return {"tool": "get_rest_advantage", "ok": True,
                "rows": {"team": abbr, "opponent": opp_abbr,
                         "summary": summary,
                         "games": [_game_row(g)]}, "meta": meta}
    if day is not None:
        on_date = [g for g in games if g.date == day]
        if not on_date:
            return {"tool": "get_rest_advantage", "ok": False,
                    "error": f"no game for {abbr} on {date_str} in "
                             f"{season}"}
        return {"tool": "get_rest_advantage", "ok": True,
                "rows": {"team": abbr, "summary": summary,
                         "games": [_game_row(on_date[0])]}, "meta": meta}
    return {"tool": "get_rest_advantage", "ok": True,
            "rows": {"team": abbr, "summary": summary,
                     "games": [_game_row(g) for g in games]}, "meta": meta}
