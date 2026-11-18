import sys
from dataclasses import dataclass
from typing import Any, NamedTuple

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


def _series_date_key(s: object) -> str:
    import datetime as _dt

    raw = str(s or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return _dt.datetime.strptime(raw.title(), fmt).date().isoformat()
        except (TypeError, ValueError):
            continue
    return raw


def _playoff_series(games: list[dict[str, Any]], a: str,
                    b: str) -> list[dict[str, Any]]:
    by_round: dict[str, list[dict[str, Any]]] = {}
    for game in games:
        if game.get("phase") != "playoffs":
            continue
        code = str(game.get("round_code") or "")
        by_round.setdefault(code, []).append(game)
    records: list[dict[str, Any]] = []
    for code in sorted(by_round):
        round_games = by_round[code]
        tally = {a: sum(1 for g in round_games if g.get("winner") == a),
                 b: sum(1 for g in round_games if g.get("winner") == b)}
        undecided = len(round_games) - tally[a] - tally[b]
        winner = (a if tally[a] > tally[b]
                  else (b if tally[b] > tally[a] else None))
        records.append({
            "round_code": code,
            "round": str(round_games[0].get("round") or ""),
            "games": len(round_games),
            "games_undecided": undecided,
            "games_won": tally,
            "winner": winner,
        })
    return records


def _collect_games(rows, limit):
    games: list[dict[str, Any]] = []
    seen: set[str] = set()
    for (gid, gdate, matchup, wl, pts, opp_pts, reb, ast, stl,
         blk, tov) in rows:
        if str(gid) in seen:
            continue
        seen.add(str(gid))
        games.append({
            "game_id": str(gid), "date": str(gdate),
            "matchup": str(matchup),
            "wl": str(wl).upper() if wl else None,
            "pts": pts, "opp_pts": opp_pts, "reb": reb,
            "ast": ast, "stl": stl, "blk": blk, "tov": tov,
        })
        if len(games) >= limit:
            break
    return games


def _team_games_rows(con, tables, tid, abbr, season, limit, playoffs):
    if not playoffs and "silver_team_games" in tables:
        rows = con.execute(
            """SELECT g.Game_ID, g.GAME_DATE, g.MATCHUP, g.WL,
                      g.PTS, o.PTS, g.REB, g.AST, g.STL, g.BLK, g.TOV
               FROM silver_team_games g
               LEFT JOIN silver_team_games o
                 ON o._season = g._season AND o.Game_ID = g.Game_ID
                AND o._entity != g._entity
               WHERE g._season = ? AND g._entity = ?
               ORDER BY strptime(g.GAME_DATE, '%b %d, %Y') DESC
               LIMIT ?""",
            [season, f"team:{tid}", limit * 4],
        ).fetchall()
        return _collect_games(rows, limit), None
    if playoffs and "silver_playoffs" in tables:
        rows = con.execute(
            """SELECT g.GAME_ID, g.GAME_DATE, g.MATCHUP, g.WL,
                      g.PTS, o.PTS, g.REB, g.AST, g.STL, g.BLK, g.TOV
               FROM silver_playoffs g
               LEFT JOIN silver_playoffs o
                 ON o._season = g._season AND o.GAME_ID = g.GAME_ID
                AND o.TEAM_ABBREVIATION != g.TEAM_ABBREVIATION
               WHERE g._season = ? AND g.TEAM_ABBREVIATION = ?
               ORDER BY coalesce(try_strptime(g.GAME_DATE, '%b %d, %Y'),
                                 try_strptime(g.GAME_DATE, '%Y-%m-%d')) DESC
               LIMIT ?""",
            [season, abbr, limit * 4],
        ).fetchall()
        return _collect_games(rows, limit), None
    if playoffs:
        return [], "team game table not present in warehouse"
    return [], None


@tool(description='A team\'s recent games, most recent first: date, matchup, W/L,\nteam and opponent points, plus team REB/AST/STL/BLK/TOV. Use for\n"show me the <team> last N games" asks - this is the TEAM game log,\nnever search_game_logs (that tool is per-player and its team_wide\nmode returns match counts, not games). team: name, nickname,\nabbreviation, or id. limit: 1-30. playoffs: read silver_playoffs\n(team-level playoff rows) instead of the regular-season table.\nWarehouse only; 2025-26 only.')
def get_team_game_log(team: str, limit: int = 10,
                      playoffs: bool = False,
                      season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ... import store as _store

    try:
        tid = pkg.coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_team_game_log", "ok": False, "error": str(exc)}
    try:
        limit = max(1, min(int(limit or 10), 30))
    except (TypeError, ValueError):
        limit = 10
    abbr = pkg._abbrev(team)
    covered = pkg._team_game_seasons()
    if covered and not playoffs and season not in covered:
        return {"tool": "get_team_game_log", "ok": False,
                "error": (f"no regular-season games found for {abbr} "
                          f"in {season}. Team game coverage: "
                          f"{', '.join(sorted(covered))}.")}

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        games, err = _team_games_rows(con, tables, tid, abbr, season,
                                      limit, playoffs)
        if err is not None:
            return {"tool": "get_team_game_log", "ok": False, "error": err}
    finally:
        con.close()
    source = "warehouse:silver_team_games"
    hist_served = False
    if not games and not playoffs and pkg.season_static(season):
        hist = pkg._hist_game_log_rows(tid, season, limit)
        if hist:
            games = hist
            source = "warehouse:silver_hist_gamelogs"
            hist_served = True
    if not games:
        suffix = (f" Team game coverage: {', '.join(sorted(covered))}."
                  if covered else "")
        return {"tool": "get_team_game_log", "ok": False,
                "error": f"no {'playoff' if playoffs else 'regular-season'} "
                         f"games found for {abbr} in {season}." + suffix}
    window = pkg._team_game_window(tid, abbr, season, playoffs, hist_served)
    meta: dict[str, Any] = {
        "season": season, "source": source,
        "scope": "playoffs" if playoffs else "regular season",
        "returned_games": len(games),
    }
    if window:
        total = window.get("season_games") or 0
        meta.update(window)
        meta["partial_window"] = bool(total and len(games) < total)
        first = window.get("first_date") or "unknown start"
        last = window.get("last_date") or "unknown end"
        meta["coverage_note"] = (
            f"{abbr} {season} {('playoffs' if playoffs else 'regular season')}: "
            f"{total} games from {first} to {last}; "
            f"showing {len(games)} most recent.")
    return {"tool": "get_team_game_log", "ok": True,
            "team": abbr, "games": games, "rows": games, "meta": meta}


_SERIES_PHASES = ("regular season", "playoffs")

_PLAYOFF_ROUND = {"1": "first round", "2": "conference semifinals",
                  "3": "conference finals", "4": "NBA Finals"}


def _winner_from(wl: Any, a: str, b: str) -> str | None:
    mark = str(wl or "").strip().upper()
    return a if mark == "W" else (b if mark == "L" else None)


def _meeting(game_id: Any, game_date: Any, matchup: Any, wl: Any,
             pts_a: Any, pts_b: Any, a: str, b: str, phase: str,
             round_code: Any = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "game_id": str(game_id or ""),
        "date": str(game_date or ""),
        "matchup": str(matchup or ""),
        "phase": phase,
        "winner": _winner_from(wl, a, b),
        f"{a.lower()}_pts": pts_a,
        f"{b.lower()}_pts": pts_b,
    }
    if round_code is not None:
        record["round_code"] = round_code
        record["round"] = _PLAYOFF_ROUND.get(round_code, "playoffs")
    return record


class _SeriesQuery(NamedTuple):
    season: str
    a: str
    b: str
    id_a: int
    id_b: int


class _SeriesSource(NamedTuple):
    table: str
    phase: str
    encodes_rounds: bool
    rows_sql: str
    rows_args: Any


_SERIES_SOURCES = (
    _SeriesSource(
        "silver_team_games", "regular season", False,
        """SELECT g.Game_ID, g.GAME_DATE, g.MATCHUP, g.WL, g.PTS, o.PTS,
                  (g.MATCHUP ILIKE ?) AS is_meeting
           FROM silver_team_games g
           LEFT JOIN silver_team_games o
             ON o._season = g._season AND o.Game_ID = g.Game_ID
            AND o._entity = ?
           WHERE g._season = ? AND g._entity = ?""",
        lambda q: [f"%{q.b}%", f"team:{q.id_b}", q.season, f"team:{q.id_a}"]),
    _SeriesSource(
        "silver_hist_gamelogs", "regular season", False,
        """SELECT g.game_id,
                  UPPER(STRFTIME(CAST(g.game_date AS DATE), '%b %d, %Y')),
                  g.matchup, g.wl, g.pts, o.pts,
                  (g.matchup ILIKE ?) AS is_meeting
           FROM silver_hist_gamelogs g
           LEFT JOIN silver_hist_gamelogs o
             ON o._season = g._season AND o.game_id = g.game_id
            AND o.team_id != g.team_id AND o.season_type = 'regular-season'
           WHERE g._season = ? AND (g.team_id = ? OR g.team_abbreviation = ?)
             AND g.season_type = 'regular-season'""",
        lambda q: [f"%{q.b}%", q.season, q.id_a, q.a]),
    _SeriesSource(
        "silver_playoffs", "playoffs", True,
        """SELECT g.Game_ID, g.GAME_DATE, g.MATCHUP, g.WL, g.PTS, o.PTS,
                  (g.MATCHUP ILIKE ?) AS is_meeting
           FROM silver_playoffs g
           LEFT JOIN silver_playoffs o
             ON o._season = g._season AND o.Game_ID = g.Game_ID
            AND o.TEAM_ABBREVIATION = ?
           WHERE g._season = ? AND g.TEAM_ABBREVIATION = ?""",
        lambda q: [f"%{q.b}%", q.b, q.season, q.a]),
    _SeriesSource(
        "silver_playoff_gamelogs", "playoffs", True,
        """SELECT DISTINCT Game_ID, GAME_DATE, MATCHUP, WL, NULL, NULL,
                  (MATCHUP ILIKE ?) AS is_meeting
           FROM silver_playoff_gamelogs
           WHERE _season = ?""",
        lambda q: [f"{q.a} % {q.b}", q.season]),
)


def _series_from(con: Any, tables: set[str],
                 query: _SeriesQuery) -> tuple[dict[str, dict[str, Any]],
                                               list[dict[str, Any]]]:
    coverage: dict[str, dict[str, Any]] = {}
    meetings: list[dict[str, Any]] = []
    for source in _SERIES_SOURCES:
        slot = coverage.setdefault(
            source.phase, {"source": None, "consulted": []})
        slot["consulted"].append(source.table)
        if slot["source"] is not None or source.table not in tables:
            continue
        rows = con.execute(
            source.rows_sql, source.rows_args(query)).fetchall()
        if not rows:
            continue
        slot["source"] = source.table
        for gid, gdate, matchup, wl, pts, opp_pts, is_meeting in rows:
            if not is_meeting:
                continue
            meetings.append(_meeting(
                gid, gdate, matchup, wl, pts, opp_pts, query.a, query.b,
                source.phase,
                str(gid)[7:8] if source.encodes_rounds else None))
    return coverage, meetings


def _consulted_tables(coverage: dict[str, dict[str, Any]]) -> list[str]:
    return [name for phase in _SERIES_PHASES
            for name in coverage[phase]["consulted"]]


def _season_not_covered_error(a: str, b: str, season: str,
                              coverage: dict[str, dict[str, Any]]) -> str:
    return (f"no warehouse table holds {season} for {a} or {b}, so their "
            f"meetings cannot be counted or ruled out. Tables consulted: "
            f"{', '.join(_consulted_tables(coverage))}. This is a coverage "
            f"gap, not evidence the teams never met. Do not report a 0-0 "
            f"record.")


def _no_meetings_error(a: str, b: str, season: str,
                       coverage: dict[str, dict[str, Any]]) -> str:
    uncovered = [phase for phase in _SERIES_PHASES
                 if coverage[phase]["source"] is None]
    gap = ""
    if uncovered:
        gap = (f" No {' nor '.join(uncovered)} table holds {season} rows, "
               f"so this is not evidence the teams never met.")
    return (f"{a} and {b} have no recorded meetings in {season}. Tables "
            f"consulted: {', '.join(_consulted_tables(coverage))}. Do not "
            f"report a 0-0 record - say the meetings are not in the "
            f"dataset.{gap}")


def _series_source(coverage: dict[str, dict[str, Any]],
                   phase: str) -> str | None:
    return coverage[phase]["source"]


def _series_unreadable_error(season: str, cause: object) -> str:
    return (f"the warehouse could not be read for {season}, so whether these "
            f"teams met is unknown rather than absent: {cause}. Tables this "
            f"question reads: "
            f"{', '.join(source.table for source in _SERIES_SOURCES)}. Do not "
            f"report a 0-0 record.")


def _resolve_series_teams(team_a, team_b, season):
    from ..competitive import _resolve_team_abbr
    from nba_api.stats.static import teams as _static_teams

    a = _resolve_team_abbr(team_a)
    b = _resolve_team_abbr(team_b)
    if not a or not b:
        return None, f"could not resolve team(s): {team_a} / {team_b}"
    if a == b:
        return None, "two different teams needed"
    ids = {str(t.get("abbreviation") or "").upper(): t.get("id")
           for t in _static_teams.get_teams()}
    id_a, id_b = ids.get(a), ids.get(b)
    if id_a is None or id_b is None:
        return None, (f"no warehouse team id for "
                      f"{a if id_a is None else b}, so {season} meetings "
                      f"cannot be looked up without guessing")
    return (a, b, id_a, id_b), None


def _series_summary(games, a, b, playoff_source):
    phases = sorted({g["phase"] for g in games})
    games_won = {a: sum(1 for g in games if g.get("winner") == a),
                 b: sum(1 for g in games if g.get("winner") == b)}
    games_by_phase = {phase: sum(1 for g in games if g["phase"] == phase)
                      for phase in phases}
    games_won_by_phase = {
        phase: {a: sum(1 for g in games if g["phase"] == phase
                       and g.get("winner") == a),
                b: sum(1 for g in games if g["phase"] == phase
                       and g.get("winner") == b)}
        for phase in phases}
    undecided = len(games) - games_won[a] - games_won[b]
    summary = {
        "games": len(games),
        "games_undecided": undecided,
        "games_won": games_won,
        "games_by_phase": games_by_phase,
        "games_won_by_phase": games_won_by_phase,
    }
    if playoff_source is None:
        summary["series_played"] = None
        summary["series_won"] = None
        summary["series"] = None
    else:
        series = _playoff_series(games, a, b)
        summary["series_played"] = len(series)
        summary["series_won"] = {a: sum(1 for s in series if s["winner"] == a),
                                 b: sum(1 for s in series if s["winner"] == b)}
        summary["series"] = series
    return summary


def _series_meta(a, b, season, reg_source, playoff_source,
                 tables, series_sources, coverage, games):
    return {"source": "warehouse team + playoff gamelogs",
            "season": season,
            "regular_season_source": reg_source,
            "playoff_source": playoff_source,
            "playoff_tables_present": {
                source.table: source.table in tables
                for source in series_sources
                if source.phase == "playoffs"},
            "coverage": coverage,
            "unscored_games": sorted(
                g["game_id"] for g in games
                if f"{a.lower()}_pts" not in g
                or g.get(f"{a.lower()}_pts") is None),
            "note": ("games_won counts games; series_won counts "
                     "playoff series, one per round")}


@tool(description='Head-to-head between two TEAMS: every meeting this season, regular\nseason and playoffs, with winner and scores when tracked. Use for\n"how did X do against Y", "X vs Y record", "season series".')
def get_season_series(team_a: str, team_b: str,
                      season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    resolved, err = _resolve_series_teams(team_a, team_b, season)
    if err is not None:
        return {"tool": "get_season_series", "ok": False, "error": err}
    a, b, id_a, id_b = resolved

    from ... import store as _store

    con = _store.connect(read_only=True)
    try:
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            coverage, games = _series_from(
                con, tables, _SeriesQuery(season, a, b, id_a, id_b))
        except Exception as exc:
            return {"tool": "get_season_series", "ok": False,
                    "error": _series_unreadable_error(season, exc)}
        reg_source = _series_source(coverage, "regular season")
        playoff_source = _series_source(coverage, "playoffs")
        if reg_source is None:
            return {"tool": "get_season_series", "ok": False,
                    "error": _season_not_covered_error(a, b, season, coverage)}
    finally:
        con.close()

    if not games:
        return {"tool": "get_season_series", "ok": False,
                "error": _no_meetings_error(a, b, season, coverage)}
    games.sort(key=lambda g: _series_date_key(g["date"]))
    summary = _series_summary(games, a, b, playoff_source)
    return {"tool": "get_season_series", "ok": True,
            "rows": {"teams": [a, b], "summary": summary, "games": games},
            "meta": _series_meta(a, b, season, reg_source, playoff_source,
                                 tables, _SERIES_SOURCES, coverage, games)}


_TRAILING_SPLIT = "last10"
_TRAILING_SPLIT_SIZE = 10

_SPLIT_WINDOW_KINDS = {
    "home": ("venue", "regular-season games at home"),
    "away": ("venue", "regular-season games on the road"),
    "wins": ("outcome", "regular-season games won"),
    "losses": ("outcome", "regular-season games lost"),
    _TRAILING_SPLIT: (
        "trailing_games",
        f"the {_TRAILING_SPLIT_SIZE} most recent regular-season games"),
}


@dataclass(frozen=True)
class ScoredWindow:

    kind: str
    label: str
    season: str
    phase: str
    games: int

    def payload(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "season": self.season,
                "phase": self.phase, "games": self.games}


def _split_window(split: str, season: str, games: int) -> ScoredWindow:
    kind, label = _SPLIT_WINDOW_KINDS.get(
        split, ("calendar_month", f"regular-season games in {split}"))
    return ScoredWindow(kind=kind, label=label, season=season,
                        phase="regular season", games=games)


@tool(description='Home/away, wins/losses, last-10, monthly record plus PPG from cached gamelog.')
def get_team_splits(team: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        tid = pkg.coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_team_splits", "ok": False, "error": str(exc)[:160]}
    from datetime import datetime as _dt
    from ... import store as _store
    con = _store.connect()
    try:
        rows = con.execute(
            "SELECT MATCHUP, WL, GAME_DATE, PTS FROM silver_team_games"
            " WHERE _season = ? AND _entity = ?",
            [season, f"team:{tid}"],
        ).fetchall()
    finally:
        con.close()
    source = "silver_team_games"
    if not rows:
        rows = [(str(row.get("MATCHUP") or ""), str(row.get("WL") or ""),
                 str(row.get("GAME_DATE") or ""), row.get("PTS"))
                for row in pkg._hist_team_games(tid, season)]
        source = "silver_hist_gamelogs"
    if not rows:
        return {"tool": "get_team_splits", "ok": False,
                "error": f"no cached games for team {tid}"}

    def _dkey(d: object) -> object:
        try:
            return _dt.strptime(str(d).title(), "%b %d, %Y")
        except (TypeError, ValueError):
            return _dt.min

    def _row(split: str, rs: list) -> dict[str, Any]:
        gp = len(rs)
        w = sum(1 for r in rs if r[1] == "W")
        l = sum(1 for r in rs if r[1] == "L")
        scored = [r for r in rs if r[3] is not None]
        ppg = (round(sum(float(r[3]) for r in scored) / len(scored), 1)
               if scored else None)
        return {"split": split,
                "window": _split_window(split, season, gp).payload(),
                "GP": gp, "W": w, "L": l, "UNDECIDED": gp - w - l,
                "PPG": ppg, "PPG_GAMES": len(scored)}

    out = [_row("home", [r for r in rows if "@" not in str(r[0])]),
           _row("away", [r for r in rows if "@" in str(r[0])]),
           _row("wins", [r for r in rows if r[1] == "W"]),
           _row("losses", [r for r in rows if r[1] == "L"])]
    ordered = sorted(rows, key=lambda r: _dkey(r[2]), reverse=True)
    out.append(_row(_TRAILING_SPLIT, ordered[:_TRAILING_SPLIT_SIZE]))
    months: dict[str, list] = {}
    for r in sorted(rows, key=lambda r: _dkey(r[2])):
        months.setdefault(str(r[2])[:3].upper(), []).append(r)
    out.extend(_row(m, rs) for m, rs in months.items())
    return {"tool": "get_team_splits", "ok": True, "rows": out,
            "meta": {"source": source, "season": season, "team_id": tid}}
