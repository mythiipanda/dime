"""Streak finders over warehouse game logs. Longest or active, ranked."""

import datetime as _dt
from typing import Any, Callable

from langchain_core.tools import tool

from ._core import SEASON, clamp_season, clamp_scope

STAT_ALIASES = {
    "points": "PTS", "point": "PTS", "pts": "PTS",
    "rebounds": "REB", "rebound": "REB", "reb": "REB", "boards": "REB",
    "assists": "AST", "assist": "AST", "ast": "AST", "dimes": "AST",
    "threes": "FG3M", "three": "FG3M", "3pt": "FG3M", "fg3m": "FG3M",
    "three-pointers": "FG3M", "three-pointer": "FG3M",
    "steals": "STL", "steal": "STL", "stl": "STL",
    "blocks": "BLK", "block": "BLK", "blk": "BLK",
    "double-doubles": "DD2", "double-double": "DD2", "dd": "DD2",
    "triple-doubles": "TD3", "triple-double": "TD3", "td": "TD3",
    "wins": "W", "win": "W",
    "losses": "L", "loss": "L",
}

SIMPLE_STATS = ("PTS", "REB", "AST", "FG3M", "STL", "BLK")

DEFAULT_THRESHOLDS = {
    "PTS": 30.0, "REB": 10.0, "AST": 10.0,
    "FG3M": 4.0, "STL": 3.0, "BLK": 3.0,
}

DD_CATS = ("PTS", "REB", "AST", "STL", "BLK")


def _num(value: object) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dd_count(row: dict[str, Any]) -> int:
    return sum(1 for c in DD_CATS if _num(row.get(c)) >= 10)


def _cond_for(stat_key: str, threshold: float) -> Callable[[dict], bool]:
    if stat_key == "W":
        return lambda r: str(r.get("WL") or "").upper() == "W"
    if stat_key == "L":
        return lambda r: str(r.get("WL") or "").upper() == "L"
    if stat_key == "DD2":
        return lambda r: _dd_count(r) >= 2
    if stat_key == "TD3":
        return lambda r: _dd_count(r) >= 3
    return lambda r, t=threshold: _num(r.get(stat_key)) >= t


def _value_for(stat_key: str) -> Callable[[dict], Any]:
    if stat_key in ("W", "L"):
        return lambda r: str(r.get("WL") or "").upper()
    if stat_key in ("DD2", "TD3"):
        return lambda r: _dd_count(r)
    return lambda r: _num(r.get(stat_key))


def _parse_player_date(s: object) -> _dt.date | None:
    try:
        return _dt.datetime.strptime(str(s or "").strip(), "%b %d, %Y").date()
    except (TypeError, ValueError):
        return None


def _parse_team_date(s: object) -> _dt.date | None:
    try:
        return _dt.datetime.strptime(str(s or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def compute_streaks(
    games: list[dict[str, Any]],
    cond: Callable[[dict[str, Any]], bool],
    value_of: Callable[[dict[str, Any]], Any],
    mode: str = "longest",
    top: int = 10,
) -> list[dict[str, Any]]:
    """Rank streaks across holders from pre-sorted or unsorted game rows.

    Each game needs holder, holder_id, date (datetime.date), and the raw
    stat fields cond/value_of read. Returns one streak per qualifying
    holder: their longest run for mode longest, their trailing run for
    mode active (skipped when the trailing game fails cond).
    """
    by_holder: dict[tuple[Any, str], list[dict[str, Any]]] = {}
    for g in games:
        if g.get("date") is None:
            continue
        by_holder.setdefault((g.get("holder_id"), g.get("holder")), []).append(g)
    out: list[dict[str, Any]] = []
    for (hid, holder), gs in by_holder.items():
        gs = sorted(gs, key=lambda g: g["date"])
        runs: list[tuple[int, int]] = []
        i = 0
        while i < len(gs):
            if not cond(gs[i]):
                i += 1
                continue
            j = i
            while j + 1 < len(gs) and cond(gs[j + 1]):
                j += 1
            runs.append((i, j))
            i = j + 1
        if not runs:
            continue
        last = len(gs) - 1
        if mode == "active":
            si, ei = runs[-1]
            if ei != last:
                continue
        else:
            best = max(ei - si for si, ei in runs)
            si, ei = max(
                (r for r in runs if r[1] - r[0] == best), key=lambda r: r[1])
        out.append({
            "holder": holder,
            "holder_id": hid,
            "streak": ei - si + 1,
            "start_date": gs[si]["date"].isoformat(),
            "end_date": gs[ei]["date"].isoformat(),
            "active": ei == last,
            "span": [
                {"date": gs[k]["date"].isoformat(), "value": value_of(gs[k])}
                for k in range(si, ei + 1)
            ],
        })
    out.sort(key=lambda s: str(s["holder"]))
    out.sort(key=lambda s: s["end_date"], reverse=True)
    out.sort(key=lambda s: -s["streak"])
    # One row per holder, always: duplicate (holder_id, holder) keys from
    # mixed-name source rows must never surface the same team twice
    # (QA F17: Thunder appeared twice in the top 10).
    seen: set = set()
    deduped: list[dict[str, Any]] = []
    for s in out:
        key = s["holder_id"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)
    return deduped[: max(1, min(int(top or 10), 25))]


def _load_player_games(season: str) -> tuple[list[dict], dict]:
    from .. import store as _store
    from .splits import _resolve_name

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_player_gamelogs" not in tables:
            return [], {"error": "player gamelogs empty"}
        rows = con.execute(
            """SELECT Player_ID, GAME_DATE, PTS, REB, AST, STL, BLK, FG3M
               FROM silver_player_gamelogs WHERE _season = ?
               ORDER BY Player_ID, GAME_DATE""",
            [season],
        ).fetchall()
    finally:
        con.close()
    games = []
    for pid, gdate, pts, reb, ast, stl, blk, fg3m in rows:
        d = _parse_player_date(gdate)
        if d is None:
            continue
        games.append({
            "holder": _resolve_name(int(pid), f"Player {pid}"),
            "holder_id": int(pid),
            "date": d,
            "PTS": pts, "REB": reb, "AST": ast,
            "STL": stl, "BLK": blk, "FG3M": fg3m,
        })
    scanned = len({g["holder_id"] for g in games})
    return games, {"players_scanned": scanned}


def _load_team_games(season: str) -> tuple[list[dict], dict]:
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return [], {"error": "team history empty"}
        cols = {r[1] for r in
                con.execute("PRAGMA table_info(silver_hist_gamelogs)").fetchall()}
        q = ("SELECT team_abbreviation, team_name, game_date, matchup, wl,"
             " pts, reb, ast, fg3m, stl, blk FROM silver_hist_gamelogs"
             " WHERE _season = ?")
        if "season_type" in cols:
            q += " AND season_type = 'regular-season'"
        rows = con.execute(q + " ORDER BY team_abbreviation, game_date",
                           [season]).fetchall()
    finally:
        con.close()
    games = []
    for abbr, tname, gdate, matchup, wl, pts, reb, ast, fg3m, stl, blk in rows:
        d = _parse_team_date(gdate)
        if d is None:
            continue
        games.append({
            "holder": str(abbr or "").upper(),
            "holder_id": str(abbr or "").upper(),
            "team_name": tname,
            "date": d,
            "WL": str(wl or "").upper(),
            "PTS": pts, "REB": reb, "AST": ast,
            "FG3M": fg3m, "STL": stl, "BLK": blk,
        })
    scanned = len({g["holder_id"] for g in games})
    return games, {"teams_scanned": scanned, "regular_season_only": True}


@tool
def get_streaks(stat: str = "points", threshold: float | None = None,
                scope: str = "player", season: str = SEASON,
                mode: str = "longest", top: int = 10) -> dict[str, Any]:
    """Longest or currently-active streaks, ranked league-wide.

    stat: points/rebounds/assists/threes/steals/blocks/double-doubles/
    triple-doubles, or wins/losses for team scope. threshold: minimum per
    game (defaults: 30 pts, 10 reb/ast, 4 threes, 3 stl/blk; ignored for
    double-doubles, triple-doubles, wins, losses). scope: player or team.
    mode: longest or active. Warehouse only; active means the streak
    includes the holder's latest game on record.
    """
    stat_key = STAT_ALIASES.get(str(stat or "").strip().lower())
    if stat_key is None:
        return {"tool": "get_streaks", "ok": False,
                "error": f"unknown stat: {stat}",
                "supported": sorted(set(STAT_ALIASES))}
    scope = clamp_scope(scope)
    season = clamp_season(season)
    mode = "active" if str(mode or "").strip().lower().startswith("active") \
        else "longest"
    if stat_key in ("W", "L"):
        if scope != "team":
            return {"tool": "get_streaks", "ok": False,
                    "error": "wins/losses streaks need scope='team'"}
    elif stat_key in ("DD2", "TD3"):
        if scope != "player":
            return {"tool": "get_streaks", "ok": False,
                    "error": "double-doubles/triple-doubles need scope='player'"}
    thr: float | None = None
    if stat_key in SIMPLE_STATS:
        if scope == "team" and threshold is None:
            return {"tool": "get_streaks", "ok": False,
                    "error": "team stat streaks need an explicit threshold"
                    " (e.g. threshold=120 for team points)"}
        thr = (float(threshold) if threshold is not None
               else DEFAULT_THRESHOLDS[stat_key])
        if thr <= 0:
            return {"tool": "get_streaks", "ok": False,
                    "error": "threshold must be positive"}
    if scope == "player":
        games, coverage = _load_player_games(season)
    else:
        games, coverage = _load_team_games(season)
    if "error" in coverage:
        return {"tool": "get_streaks", "ok": False, "error": coverage["error"]}
    if not games:
        return {"tool": "get_streaks", "ok": False,
                "error": f"no games for {season}"}
    streaks = compute_streaks(games, _cond_for(stat_key, thr or 0.0),
                              _value_for(stat_key), mode, top)
    label = {"W": "wins", "L": "losses", "DD2": "double-doubles",
             "TD3": "triple-doubles"}.get(stat_key, stat_key.lower())
    meta: dict[str, Any] = {
        "source": "warehouse", "season": season, "mode": mode,
        "stat": label, "scope": scope,
    }
    if thr is not None:
        meta["threshold"] = thr
    meta["coverage"] = coverage
    return {"tool": "get_streaks", "ok": True,
            "rows": {"streaks": streaks, "count": len(streaks)}, "meta": meta}
