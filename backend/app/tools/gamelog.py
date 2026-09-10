"""Player game-log search. One flexible filter over the warehouse logs.

Answers "show me all 40-point games by X this season", "X's games vs
BOS", "X's triple-doubles in March". Warehouse only, read-only.

Scope is deliberately player-scoped: silver_player_gamelogs holds
2025-26 logs for 57 seeded players, so there is no league-wide mode
and no historical seasons. Triple-doubles and double-doubles are
counted the Stathead way: 10+ in three (or two) of
PTS/REB/AST/STL/BLK."""

import datetime as _dt
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


def _load_player_games(pid: int, season: str) -> list[dict[str, Any]]:
    """Normalized game rows, most recent first. Read-only connect."""
    cols = ("GAME_DATE", "MATCHUP", "WL", "MIN", "FGM", "FGA", "FG3M",
            "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL",
            "BLK", "TOV", "PF", "PTS", "PLUS_MINUS")
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_player_gamelogs" not in tables:
            return []
        fetched = con.execute(
            "SELECT " + ", ".join(cols) + " FROM silver_player_gamelogs"
            " WHERE Player_ID = ? AND _season = ?",
            [pid, season],
        ).fetchall()
    finally:
        con.close()
    games = []
    for raw in fetched:
        r = dict(zip(cols, raw))
        d = parse_game_date(r.get("GAME_DATE"))
        if d is None:
            continue
        matchup = str(r.get("MATCHUP") or "")
        games.append({
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


def _describe_filters(f: dict[str, Any]) -> str:
    bits = []
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
    player: str,
    min_points: float | None = None,
    min_rebounds: float | None = None,
    min_assists: float | None = None,
    min_pra: float | None = None,
    triple_double: bool = False,
    double_double: bool = False,
    opponent: str | None = None,
    month: str | int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    home_away: str | None = None,
    season: str = SEASON,
    limit: int = 50,
) -> dict[str, Any]:
    """Filter one player's game logs by stat thresholds, opponent, time, or home/away.

    player: name, nickname, or id (same resolution as every other tool).
    min_points / min_rebounds / min_assists: per-game stat floors
    (e.g. min_points=40 for 40-point games). min_pra: points + rebounds
    + assists floor. triple_double / double_double: keep only games
    with 10+ in 3 (or 2) of PTS/REB/AST/STL/BLK. opponent: team name or
    abbreviation, e.g. "Knicks" or "NYK". month: name, number, or
    YYYY-MM. start_date / end_date: YYYY-MM-DD, inclusive. home_away:
    "home" or "away". season: 2025-26 only in the warehouse.
    Returns matching games, most recent first, with the total match
    count (rows beyond limit are counted, not returned).
    Warehouse only; player-scoped, no league-wide mode.
    """
    season = clamp_season(season)
    try:
        pid = coerce_player_id(player)
    except ValueError as exc:
        return {"tool": "search_game_logs", "ok": False, "error": str(exc)}
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
        "opponent": abbr, "month": mon,
        "start_date": lo, "end_date": hi, "home_away": ha,
    }
    games = _load_player_games(pid, season)
    if not games:
        return {"tool": "search_game_logs", "ok": False,
                "error": f"no gamelog data for {player} in the warehouse"
                         f" ({season})"}
    name = _resolve_name(pid, str(player))
    matched = [g for g in games if _matches(g, filters)]
    lim = _clamp_limit(limit)
    capped = len(matched) > lim
    return {
        "tool": "search_game_logs",
        "ok": True,
        "rows": {
            "player": name,
            "player_id": pid,
            "player_team": games[0]["matchup"].split(" ")[0],
            "filters": _describe_filters(filters),
            "total": len(matched),
            "returned": min(len(matched), lim),
            "capped": capped,
            "matches": [_row_out(g) for g in matched[:lim]],
        },
        "meta": {
            "source": "warehouse",
            "season": season,
            "coverage_note": "silver_player_gamelogs covers 2025-26 only"
                             " (57 seeded players); date filters use game"
                             " dates within that season",
        },
    }
