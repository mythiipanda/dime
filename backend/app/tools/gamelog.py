"""Player game-log search. One flexible filter over the warehouse logs.

Answers "show me all 40-point games by X this season", "X's games vs
BOS", "X's triple-doubles in March", and league-wide asks like "who
had the most 50-point games this season". Warehouse only, read-only.

Scope: silver_player_gamelogs holds 2025-26 regular-season logs for 57
seeded players; silver_playoff_gamelogs holds the playoff logs
(playoffs=True). No historical seasons. Triple-doubles and
double-doubles are counted the Stathead way: 10+ in three (or two) of
PTS/REB/AST/STL/BLK."""

import datetime as _dt
from collections import Counter
from typing import Any

from langchain_core.tools import tool

from .. import store
from ._core import SEASON, clamp_season, coerce_player_id
from .headtohead import _team_abbr
from .splits import _resolve_name, is_home, opponent_abbr, parse_game_date

MAX_LIMIT = 50

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

DD_CATS = ("PTS", "REB", "AST", "STL", "BLK")


def _f(value: object) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dd_count(row: dict[str, Any]) -> int:
    return sum(1 for c in DD_CATS if _f(row.get(c)) >= 10)


def _parse_month(month: object) -> int | None:
    """Accept a month name, number, or YYYY-MM string. None on failure."""
    if month is None or month == "":
        return None
    s = str(month).strip().lower()
    if s in MONTH_NAMES:
        return MONTH_NAMES[s]
    import re as _re

    m = _re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m:
        n = int(m.group(2))
        return n if 1 <= n <= 12 else None
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 12 else None
    short = {k[:3]: v for k, v in MONTH_NAMES.items()}
    return short.get(s[:3])


def _parse_iso_date(s: object) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(str(s or "").strip())
    except (TypeError, ValueError):
        return None


def _positive(value: object, name: str) -> float | None:
    """Float threshold that must be >= 0; None when not given. Raises
    ValueError with a human message for garbage input."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, got {value!r}")
    if v < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")
    return v


def _clamp_limit(value: object) -> int:
    try:
        return max(1, min(int(value), MAX_LIMIT))
    except (TypeError, ValueError):
        return MAX_LIMIT


def _table_for(playoffs: bool) -> str:
    return "silver_playoff_gamelogs" if playoffs else "silver_player_gamelogs"


def _load_games(table: str, season: str,
                pid: int | None = None) -> list[dict[str, Any]]:
    """Normalized game rows, most recent first. Read-only connect.

    pid None loads every player (league-wide mode); otherwise one player.
    Each row carries player_id so callers can group.
    """
    cols = ("GAME_DATE", "MATCHUP", "WL", "MIN", "FGM", "FGA", "FG3M",
            "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL",
            "BLK", "TOV", "PF", "PTS", "PLUS_MINUS")
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if table not in tables:
            return []
        where = "_season = ?"
        params: list[object] = [season]
        if pid is not None:
            where = "Player_ID = ? AND " + where
            params = [pid, season]
        fetched = con.execute(
            "SELECT Player_ID, " + ", ".join(cols) + f" FROM {table}"
            " WHERE " + where,
            params,
        ).fetchall()
    finally:
        con.close()
    games = []
    for raw in fetched:
        r = dict(zip(("Player_ID",) + cols, raw))
        d = parse_game_date(r.get("GAME_DATE"))
        if d is None:
            continue
        matchup = str(r.get("MATCHUP") or "")
        games.append({
            "player_id": r.get("Player_ID"),
            "date": d,
            "matchup": matchup,
            "opponent": opponent_abbr(matchup),
            "home": is_home(matchup),
            "wl": str(r.get("WL") or "").upper(),
            "min": r.get("MIN"),
            "pts": _f(r.get("PTS")),
            "reb": _f(r.get("REB")),
            "ast": _f(r.get("AST")),
            "stl": _f(r.get("STL")),
            "blk": _f(r.get("BLK")),
            "tov": _f(r.get("TOV")),
            "pf": _f(r.get("PF")),
            "fgm": _f(r.get("FGM")),
            "fga": _f(r.get("FGA")),
            "fg3m": _f(r.get("FG3M")),
            "fg3a": _f(r.get("FG3A")),
            "plus_minus": _f(r.get("PLUS_MINUS")),
            "dd_count": _dd_count(r),
        })
    games.sort(key=lambda g: g["date"], reverse=True)
    return games


def _load_player_games(pid: int, season: str) -> list[dict[str, Any]]:
    """Regular-season logs for one player (kept for callers/tests)."""
    return _load_games(_table_for(False), season, pid)


def _playoff_coverage() -> str:
    """Seasons present in the playoff table, for explicit no-data errors."""
    try:
        con = store.connect(read_only=True)
        try:
            seasons = sorted(
                r[0] for r in con.execute(
                    "SELECT DISTINCT _season FROM silver_playoff_gamelogs"
                ).fetchall() if r[0]
            )
        finally:
            con.close()
    except Exception:
        seasons = []
    if not seasons:
        return "no playoff seasons stored yet"
    return "playoff coverage: " + ", ".join(seasons)


def _matches(g: dict[str, Any], f: dict[str, Any]) -> bool:
    """One predicate over a normalized game row. Filters AND together."""
    if f["min_points"] is not None and g["pts"] < f["min_points"]:
        return False
    if f["min_rebounds"] is not None and g["reb"] < f["min_rebounds"]:
        return False
    if f["min_assists"] is not None and g["ast"] < f["min_assists"]:
        return False
    if f["min_pra"] is not None and g["pts"] + g["reb"] + g["ast"] < f["min_pra"]:
        return False
    if f["double_double"] and g["dd_count"] < 2:
        return False
    if f["triple_double"] and g["dd_count"] < 3:
        return False
    if f["opponent"] is not None and g["opponent"] != f["opponent"]:
        return False
    if f["month"] is not None and g["date"].month != f["month"]:
        return False
    if f["start_date"] is not None and g["date"] < f["start_date"]:
        return False
    if f["end_date"] is not None and g["date"] > f["end_date"]:
        return False
    if f["home_away"] is not None and g["home"] != (f["home_away"] == "home"):
        return False
    return True


def _describe_filters(f: dict[str, Any], playoffs: bool = False) -> str:
    bits = []
    if playoffs:
        bits.append("in the playoffs")
    if f.get("best_game"):
        bits.append("best game (most points)")
    if f["min_points"] is not None:
        bits.append(f"{f['min_points']:g}+ points")
    if f["min_rebounds"] is not None:
        bits.append(f"{f['min_rebounds']:g}+ rebounds")
    if f["min_assists"] is not None:
        bits.append(f"{f['min_assists']:g}+ assists")
    if f["min_pra"] is not None:
        bits.append(f"{f['min_pra']:g}+ points+rebounds+assists")
    if f["triple_double"]:
        bits.append("triple-doubles")
    elif f["double_double"]:
        bits.append("double-doubles")
    if f["opponent"] is not None:
        bits.append(f"vs {f['opponent']}")
    if f["month"] is not None:
        bits.append(_dt.date(2000, f["month"], 1).strftime("%B"))
    if f["start_date"] is not None or f["end_date"] is not None:
        lo = f["start_date"].isoformat() if f["start_date"] else "..."
        hi = f["end_date"].isoformat() if f["end_date"] else "..."
        bits.append(f"{lo} to {hi}")
    if f["home_away"] is not None:
        bits.append("home games" if f["home_away"] == "home" else "away games")
    return ", ".join(bits) or "all games"


def _row_out(g: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": g["date"].isoformat(),
        "opponent": g["opponent"],
        "matchup": g["matchup"],
        "home": g["home"],
        "pts": g["pts"],
        "reb": g["reb"],
        "ast": g["ast"],
        "stl": g["stl"],
        "blk": g["blk"],
        "tov": g["tov"],
        "fgm": g["fgm"],
        "fga": g["fga"],
        "fg3m": g["fg3m"],
        "min": g["min"],
        "plus_minus": g["plus_minus"],
        "wl": g["wl"],
    }


@tool
def search_game_logs(
    player: str | None = None,
    league_wide: bool = False,
    team_wide: bool = False,
    min_points: float | None = None,
    min_rebounds: float | None = None,
    min_assists: float | None = None,
    min_pra: float | None = None,
    triple_double: bool = False,
    double_double: bool = False,
    best_game: bool = False,
    opponent: str | None = None,
    month: str | int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    home_away: str | None = None,
    playoffs: bool = False,
    season: str = SEASON,
    limit: int = 50,
) -> dict[str, Any]:
    """Filter game logs by stat thresholds, opponent, time, or home/away.

    player: name, nickname, or id (same resolution as every other tool).
    Required unless league_wide=True or team_wide=True.
    league_wide: when True, ignore player and return per-player match
    counts across the whole warehouse (answers "who had the most
    50-point games this season").
    team_wide: when True, ignore player and return per-team match
    counts across the whole warehouse (answers "which team had the
    most 50-point games this season"). Each matched game counts for
    the team the player was on that night (first token of MATCHUP,
    e.g. "LAL vs. BOS" -> "LAL"), so a mid-season trade attributes
    each game to the team at game time, not the current team.
    playoffs: when True, read silver_playoff_gamelogs instead of the
    regular-season table.
    min_points / min_rebounds / min_assists: per-game stat floors
    (e.g. min_points=40 for 40-point games). min_pra: points + rebounds
    + assists floor. triple_double / double_double: keep only games
    with 10+ in 3 (or 2) of PTS/REB/AST/STL/BLK. opponent: team name or
    abbreviation, e.g. "Knicks" or "NYK". month: name, number, or
    YYYY-MM. start_date / end_date: YYYY-MM-DD, inclusive. home_away:
    "home" or "away". season: 2025-26 only in the warehouse.
    best_game: when True, ignore the limit and return only the single
    highest-scoring game (answers "best game" / "career high" phrasing).
    Returns matching games, most recent first, with the total match
    count (rows beyond limit are counted, not returned). A player with
    no rows in the chosen scope is an explicit ok:False error, never a
    silent 0.
    Warehouse only; 2025-26 only.
    """
    season = clamp_season(season)
    table = _table_for(bool(playoffs))
    scope = "playoff" if playoffs else "regular-season"
    league_wide = bool(league_wide)
    team_wide = bool(team_wide)
    pid: int | None = None
    if not league_wide and not team_wide:
        if player is None or str(player).strip() == "":
            return {"tool": "search_game_logs", "ok": False,
                    "error": "player is required unless league_wide=True"
                             " or team_wide=True"}
        try:
            pid = coerce_player_id(player)
        except ValueError as exc:
            return {"tool": "search_game_logs", "ok": False,
                    "error": str(exc)}
    try:
        thr_points = _positive(min_points, "min_points")
        thr_rebounds = _positive(min_rebounds, "min_rebounds")
        thr_assists = _positive(min_assists, "min_assists")
        thr_pra = _positive(min_pra, "min_pra")
    except ValueError as exc:
        return {"tool": "search_game_logs", "ok": False, "error": str(exc)}
    abbr: str | None = None
    if opponent is not None and str(opponent).strip() != "":
        try:
            abbr, _full = _team_abbr(opponent)
        except ValueError as exc:
            return {"tool": "search_game_logs", "ok": False,
                    "error": str(exc)}
    mon = _parse_month(month)
    if month is not None and str(month).strip() != "" and mon is None:
        return {"tool": "search_game_logs", "ok": False,
                "error": f"could not parse month: {month!r}"
                         " (use a name, 1-12, or YYYY-MM)"}
    lo = _parse_iso_date(start_date)
    if start_date is not None and str(start_date).strip() != "" and lo is None:
        return {"tool": "search_game_logs", "ok": False,
                "error": f"could not parse start_date: {start_date!r}"
                         " (use YYYY-MM-DD)"}
    hi = _parse_iso_date(end_date)
    if end_date is not None and str(end_date).strip() != "" and hi is None:
        return {"tool": "search_game_logs", "ok": False,
                "error": f"could not parse end_date: {end_date!r}"
                         " (use YYYY-MM-DD)"}
    ha: str | None = None
    if home_away is not None and str(home_away).strip() != "":
        ha = str(home_away).strip().lower()
        if ha not in ("home", "away"):
            return {"tool": "search_game_logs", "ok": False,
                    "error": "home_away must be 'home' or 'away'"}
    filters = {
        "min_points": thr_points, "min_rebounds": thr_rebounds,
        "min_assists": thr_assists, "min_pra": thr_pra,
        "double_double": bool(double_double),
        "triple_double": bool(triple_double),
        "best_game": bool(best_game),
        "opponent": abbr, "month": mon,
        "start_date": lo, "end_date": hi, "home_away": ha,
    }
    games = _load_games(table, season, pid)
    if not games:
        if league_wide or team_wide:
            return {"tool": "search_game_logs", "ok": False,
                    "error": f"no {scope} gamelog data in the warehouse"
                             f" ({season})"
                             + (f"; {_playoff_coverage()}" if playoffs
                                else "")}
        label = player if player is not None else f"player {pid}"
        err = (f"no {scope} gamelog data for {label} in the warehouse"
               f" ({season})")
        if playoffs:
            err += f"; {_playoff_coverage()}"
        return {"tool": "search_game_logs", "ok": False, "error": err}
    matched = [g for g in games if _matches(g, filters)]
    lim = _clamp_limit(limit)
    if league_wide:
        counts: dict[int, int] = {}
        for g in matched:
            counts[g["player_id"]] = counts.get(g["player_id"], 0) + 1
        leaders = [
            {"player": _resolve_name(p, str(p)), "player_id": p,
             "count": c}
            for p, c in sorted(
                counts.items(),
                key=lambda kv: (-kv[1],
                                _resolve_name(kv[0], str(kv[0]))))
        ]
        return {
            "tool": "search_game_logs",
            "ok": True,
            "rows": {
                "league_wide": True,
                "scope": "playoffs" if playoffs else "regular",
                "filters": _describe_filters(filters, playoffs),
                "total_players": len(leaders),
                "returned": min(len(leaders), lim),
                "capped": len(leaders) > lim,
                "leaders": leaders[:lim],
            },
            "meta": {
                "source": "warehouse",
                "season": season,
                "coverage_note": _coverage_note(table),
            },
        }
    if team_wide:
        # Group by the player's own team that night: first token of
        # MATCHUP ("LAL vs. BOS" -> "LAL", "LAL @ BOS" -> "LAL"). A
        # mid-season trade attributes each game to the team the player
        # was on that night, not their current team.
        counts_t: dict[str, int] = {}
        for g in matched:
            tabbr = str(g.get("matchup") or "").split(" ")[0].upper() or "UNK"
            counts_t[tabbr] = counts_t.get(tabbr, 0) + 1
        leaders_t = []
        for tabbr, c in sorted(counts_t.items(),
                               key=lambda kv: (-kv[1], kv[0])):
            try:
                _a, _full = _team_abbr(tabbr)
            except ValueError:
                _a, _full = tabbr, tabbr
            leaders_t.append({"team_abbr": _a, "team": _full,
                              "count": c})
        return {
            "tool": "search_game_logs",
            "ok": True,
            "rows": {
                "team_wide": True,
                "scope": "playoffs" if playoffs else "regular",
                "filters": _describe_filters(filters, playoffs),
                "total_teams": len(leaders_t),
                "returned": min(len(leaders_t), lim),
                "capped": len(leaders_t) > lim,
                "leaders": leaders_t[:lim],
            },
            "meta": {
                "source": "warehouse",
                "season": season,
                "coverage_note": _coverage_note(table),
            },
        }
    assert pid is not None
    name = _resolve_name(pid, str(player))
    if best_game:
        # "best game" / "career high": the single max-points game.
        matched = sorted(matched, key=lambda g: g["pts"], reverse=True)[:1]
    capped = len(matched) > lim
    wl = Counter(str(g.get("wl") or "").upper() for g in matched)
    record = {"w": wl.get("W", 0), "l": wl.get("L", 0),
              "games": wl.get("W", 0) + wl.get("L", 0)}
    return {
        "tool": "search_game_logs",
        "ok": True,
        "rows": {
            "player": name,
            "player_id": pid,
            "player_team": games[0]["matchup"].split(" ")[0],
            "scope": "playoffs" if playoffs else "regular",
            "filters": _describe_filters(filters, playoffs),
            "total": len(matched),
            "returned": min(len(matched), lim),
            "capped": capped,
            "record": record,
            "matches": [_row_out(g) for g in matched[:lim]],
        },
        "meta": {
            "source": "warehouse",
            "season": season,
            "coverage_note": _coverage_note(table),
        },
    }


def _coverage_note(table: str) -> str:
    if table == "silver_playoff_gamelogs":
        return ("silver_playoff_gamelogs covers playoff logs for seeded"
                " players only; date filters use game dates within the"
                f" season ({_playoff_coverage()})")
    return ("silver_player_gamelogs covers 2025-26 regular season only"
            " (57 seeded players); date filters use game dates within"
            " that season")
