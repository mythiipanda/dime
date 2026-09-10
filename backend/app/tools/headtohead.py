"""Player head-to-head history against one opponent team. Warehouse only.

Answers "How has Tatum done against the Knicks?": the player's game
logs vs that opponent, career-vs-opponent averages next to the season
baseline with deltas, and the team record in those games. Flags small
samples (<5 games) instead of letting averages masquerade as truth.

Player-vs-player is deliberately out of scope. Only 57 players carry
warehouse gamelogs, and game logs carry no defensive-assignment data,
so same-game-line overlap is too sparse for an honest PvsP tool. The
warehouse holds 2025-26 player gamelogs only, so there is no career
baseline beyond this season; the comparison is vs-opponent vs season.
"""

from typing import Any
import datetime as _dt

from langchain_core.tools import tool

from .. import store
from ._core import SEASON, clamp_season, coerce_player_id, coerce_team_id
from .splits import _resolve_name, opponent_abbr, parse_game_date

SMALL_SAMPLE_GP = 5


def _f(value: object) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One summary line over a set of player game logs.

    The line is the domain model: gp plus per-game means plus W/L.
    vs_opponent and season_baseline are two lines; deltas is their diff.
    """
    gp = len(rows or [])
    if gp == 0:
        return {"gp": 0, "ppg": 0.0, "rpg": 0.0, "apg": 0.0,
                "fg_pct": 0.0, "ts_pct": 0.0, "w": 0, "l": 0}
    fgm = sum(_f(r.get("FGM")) for r in rows)
    fga = sum(_f(r.get("FGA")) for r in rows)
    pts = sum(_f(r.get("PTS")) for r in rows)
    fta = sum(_f(r.get("FTA")) for r in rows)
    ts_den = 2 * (fga + 0.44 * fta)
    wins = sum(1 for r in rows if str(r.get("WL") or "").upper() == "W")
    return {
        "gp": gp,
        "ppg": round(pts / gp, 1),
        "rpg": round(sum(_f(r.get("REB")) for r in rows) / gp, 1),
        "apg": round(sum(_f(r.get("AST")) for r in rows) / gp, 1),
        "fg_pct": round(fgm / fga, 3) if fga else 0.0,
        "ts_pct": round(pts / ts_den, 3) if ts_den > 0 else 0.0,
        "w": wins,
        "l": sum(1 for r in rows if str(r.get("WL") or "").upper() == "L"),
    }


def deltas(opp: dict[str, Any], base: dict[str, Any]) -> dict[str, float]:
    """vs-opponent line minus season baseline line, per key."""
    out: dict[str, float] = {}
    for key in ("ppg", "rpg", "apg", "fg_pct", "ts_pct"):
        places = 1 if key.endswith("pg") else 3
        out[key] = round(_f(opp.get(key)) - _f(base.get(key)), places)
    return out


def vs_opponent(rows: list[dict[str, Any]], abbr: str) -> list[dict[str, Any]]:
    """Keep the game logs played against the given opponent abbreviation."""
    want = str(abbr or "").strip().upper()
    return [r for r in (rows or [])
            if opponent_abbr(r.get("MATCHUP")) == want]


def _load_player_games(pid: int, season: str) -> list[dict[str, Any]]:
    # Read-only connect: this tool never writes, and it must not grab a
    # write lock while other agents run against the same warehouse file.
    con = store.connect(read_only=True)
    cols = ("GAME_DATE", "Game_ID", "MATCHUP", "WL", "MIN", "FGM", "FGA",
            "FG3M", "FG3A", "FTM", "FTA", "REB", "AST", "STL", "BLK",
            "TOV", "PTS", "PLUS_MINUS")
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
    rows = [dict(zip(cols, r)) for r in fetched]
    rows.sort(key=lambda r: parse_game_date(r.get("GAME_DATE"))
              or _dt.date.min, reverse=True)
    return rows


def _team_abbr(opponent: str) -> tuple[str, str]:
    """Resolve an opponent to (abbreviation, full name) via the static
    tables every other tool uses. Raises ValueError for unknown teams."""
    tid = coerce_team_id(opponent)
    from nba_api.stats.static import teams

    for t in teams.get_teams():
        if t.get("id") == tid:
            return (str(t.get("abbreviation", "")).upper(),
                    str(t.get("full_name", "")))
    return str(opponent).upper(), str(opponent)


@tool
def get_head_to_head(player: str, opponent: str,
                     season: str = SEASON) -> dict[str, Any]:
    """How a player has done against one opponent team.

    player: name, nickname, or id (same resolution as every other tool).
    opponent: team name, abbreviation, or id, e.g. "Knicks" or "NYK".
    season: 2025-26 only in the warehouse; other seasons clamp.

    Returns the player's game logs against the opponent (most recent
    first), vs-opponent averages next to the season baseline, the deltas
    between them, and the player's team record in those games. Fewer
    than 5 games sets small_sample and says so plainly. Warehouse only;
    player-vs-player is not supported.
    """
    season = clamp_season(season)
    try:
        pid = coerce_player_id(player)
    except ValueError as exc:
        return {"tool": "get_head_to_head", "ok": False, "error": str(exc)}
    try:
        abbr, full_name = _team_abbr(opponent)
    except ValueError as exc:
        return {"tool": "get_head_to_head", "ok": False, "error": str(exc)}
    games = _load_player_games(pid, season)
    if not games:
        return {"tool": "get_head_to_head", "ok": False,
                "error": f"no gamelog data for {player} in the warehouse"
                         f" ({season})"}
    name = _resolve_name(pid, str(player))
    matchup_games = vs_opponent(games, abbr)
    matchup_games.sort(key=lambda r: parse_game_date(r.get("GAME_DATE"))
                       or _dt.date.min, reverse=True)
    baseline = summarize(games)
    opp_line = summarize(matchup_games)
    small = opp_line["gp"] < SMALL_SAMPLE_GP
    if matchup_games:
        own_team = str(matchup_games[0].get("MATCHUP", "")).split(" ")[0]
    else:
        own_team = str(games[0].get("MATCHUP", "")).split(" ")[0]
    game_rows = []
    for g in matchup_games:
        gdate = parse_game_date(g.get("GAME_DATE"))
        game_rows.append({
            "date": gdate.isoformat() if gdate else None,
            "game_id": g.get("Game_ID"),
            "matchup": g.get("MATCHUP"),
            "home": "vs." in str(g.get("MATCHUP") or ""),
            "pts": _f(g.get("PTS")),
            "reb": _f(g.get("REB")),
            "ast": _f(g.get("AST")),
            "stl": _f(g.get("STL")),
            "blk": _f(g.get("BLK")),
            "tov": _f(g.get("TOV")),
            "fgm": _f(g.get("FGM")),
            "fga": _f(g.get("FGA")),
            "fg3m": _f(g.get("FG3M")),
            "fg3a": _f(g.get("FG3A")),
            "min": g.get("MIN"),
            "plus_minus": _f(g.get("PLUS_MINUS")),
            "wl": str(g.get("WL") or "").upper(),
        })
    note = (f"only {opp_line['gp']} game(s) vs {abbr}: treat the averages"
            " as noisy" if small
            else None)
    return {
        "tool": "get_head_to_head",
        "ok": True,
        "rows": {
            "player": name,
            "player_id": pid,
            "player_team": own_team,
            "opponent": abbr,
            "opponent_name": full_name,
            "vs_opponent": opp_line,
            "season_baseline": baseline,
            "deltas": deltas(opp_line, baseline),
            "team_record": f"{opp_line['w']}-{opp_line['l']}",
            "games": game_rows,
            "small_sample": small,
            "note": note,
        },
        "meta": {
            "source": "warehouse",
            "season": season,
            "coverage_note": "silver_player_gamelogs covers 2025-26 only;"
                             " vs-opponent is compared to the season"
                             " baseline, not a career baseline",
        },
    }
