import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


def _season_year(pkg, season: str) -> int:
    from ..zone import season_year
    return season_year(season)


def _minutes_to_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if ":" in text:
        mm, _, ss = text.partition(":")
        try:
            return float(mm) + float(ss) / 60.0
        except ValueError:
            return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


_TEAM_GAMES_CTE = """
    team_games AS (
        SELECT g.game_id, g.wl, g.pts - o.pts AS margin
        FROM silver_hist_gamelogs g
        JOIN silver_hist_gamelogs o
          ON o.game_id = g.game_id AND o.team_abbreviation <> g.team_abbreviation
        WHERE g.season = ?
          AND g.season_type = 'regular-season'
          AND g.team_abbreviation = ?
    )
"""


def _player_teams(con, pid: int, season_slug: str) -> list[tuple[str, int, int]]:
    rows = con.execute(
        """
        SELECT teamTricode, TEAM_ID, COUNT(DISTINCT GAME_ID)
        FROM silver_boxscores
        WHERE PLAYER_ID = ? AND _season = ?
        GROUP BY teamTricode, TEAM_ID
        ORDER BY 3 DESC
        """,
        [pid, season_slug],
    ).fetchall()
    return [(r[0], int(r[1]), int(r[2])) for r in rows]


def _split_rows(con, pid: int, tricode: str, year: int) -> list[dict[str, Any]]:
    rows = con.execute(
        f"""
        WITH played AS (
            SELECT DISTINCT GAME_ID FROM silver_boxscores
            WHERE PLAYER_ID = ? AND _season = ?
        ),
        {_TEAM_GAMES_CTE}
        SELECT CASE WHEN p.GAME_ID IS NULL THEN 'missed' ELSE 'played' END AS split,
               COUNT(*) AS games,
               SUM(CASE WHEN t.wl = 'W' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN t.wl = 'L' THEN 1 ELSE 0 END) AS losses,
               ROUND(AVG(t.margin), 1) AS avg_margin
        FROM team_games t LEFT JOIN played p ON p.GAME_ID = t.game_id
        GROUP BY 1 ORDER BY 1 DESC
        """,
        [pid, f"{year - 1}-{str(year)[-2:]}", year, tricode],
    ).fetchall()
    out = []
    for split, games, wins, losses, margin in rows:
        out.append({
            "split": split,
            "games": int(games),
            "wins": int(wins),
            "losses": int(losses),
            "win_pct": round(wins / games, 3) if games else None,
            "avg_margin": margin,
        })
    return out


def _teammate_rows(con, pid: int, tid: int, other_pid: int, season_slug: str) -> list[dict[str, Any]]:
    rows = con.execute(
        """
        WITH target AS (
            SELECT GAME_ID, points, fieldGoalsAttempted, plusMinusPoints
            FROM silver_boxscores
            WHERE PLAYER_ID = ? AND TEAM_ID = ? AND _season = ?
        ),
        tm AS (
            SELECT DISTINCT GAME_ID FROM silver_boxscores
            WHERE PLAYER_ID = ? AND TEAM_ID = ? AND _season = ?
        )
        SELECT CASE WHEN m.GAME_ID IS NULL THEN 'teammate_out' ELSE 'teammate_in' END AS split,
               COUNT(*) AS games,
               ROUND(AVG(t.points), 1) AS pts,
               ROUND(AVG(t.fieldGoalsAttempted), 1) AS fga,
               ROUND(AVG(t.plusMinusPoints), 1) AS plus_minus
        FROM target t LEFT JOIN tm m ON m.GAME_ID = t.GAME_ID
        GROUP BY 1 ORDER BY 1 DESC
        """,
        [pid, tid, season_slug, other_pid, tid, season_slug],
    ).fetchall()
    return [
        {
            "split": split,
            "games": int(games),
            "pts": pts,
            "fga": fga,
            "plus_minus": pm,
        }
        for split, games, pts, fga, pm in rows
    ]


def _ranking_rows(con, year: int, min_minutes: float, min_missed: int, limit: int) -> tuple[list[dict[str, Any]], int]:
    season_slug = f"{year - 1}-{str(year)[-2:]}"
    players = con.execute(
        """
        SELECT PLAYER_ID, TEAM_ID, MAX(teamTricode) AS tricode,
               COUNT(DISTINCT GAME_ID) AS gp
        FROM silver_boxscores
        WHERE _season = ?
        GROUP BY PLAYER_ID, TEAM_ID
        """,
        [season_slug],
    ).fetchall()
    by_player: dict[int, dict[str, Any]] = {}
    for pid, tid, tricode, gp in players:
        entry = by_player.setdefault(int(pid), {"teams": set(), "gp": 0, "tid": int(tid), "tricode": tricode})
        entry["teams"].add(tricode)
        entry["gp"] += int(gp)
        if int(gp) > entry.get("best_gp", -1):
            entry.update({"tid": int(tid), "tricode": tricode, "best_gp": int(gp)})
    minutes = con.execute(
        """
        SELECT PLAYER_ID, AVG(CAST(split_part(minutes, ':', 1) AS DOUBLE)
               + CAST(split_part(minutes, ':', 2) AS DOUBLE) / 60.0) AS mpg
        FROM silver_boxscores WHERE _season = ?
          AND minutes ~ '^[0-9]+:[0-9]+$'
        GROUP BY PLAYER_ID
        """,
        [season_slug],
    ).fetchall()
    mpg = {int(p): float(m or 0) for p, m in minutes}
    team_gp = {
        r[0]: int(r[1]) for r in con.execute(
            "SELECT team_abbreviation, COUNT(*) FROM silver_hist_gamelogs "
            "WHERE season = ? AND season_type = 'regular-season' GROUP BY team_abbreviation",
            [year],
        ).fetchall()
    }
    qualifying = [
        (pid, e) for pid, e in by_player.items()
        if len(e["teams"]) == 1
        and mpg.get(pid, 0.0) >= min_minutes
        and team_gp.get(e["tricode"], 0) - e["gp"] >= min_missed
    ]
    names = {int(r[0]): r[1] for r in con.execute(
        "SELECT DISTINCT PLAYER_ID, firstName || ' ' || familyName "
        "FROM silver_boxscores WHERE _season = ?",
        [season_slug],
    ).fetchall()}
    rows: list[dict[str, Any]] = []
    for pid, e in qualifying:
        split = _split_rows(con, pid, e["tricode"], year)
        played = next((s for s in split if s["split"] == "played"), None)
        missed = next((s for s in split if s["split"] == "missed"), None)
        if not played or not missed:
            continue
        rows.append({
            "player": names.get(pid, str(pid)),
            "player_id": pid,
            "team": e["tricode"],
            "games_missed": missed["games"],
            "games_played": played["games"],
            "win_pct_with": played["win_pct"],
            "win_pct_without": missed["win_pct"],
            "win_drop": round((played["win_pct"] or 0) - (missed["win_pct"] or 0), 3),
        })
    rows.sort(key=lambda r: r["win_drop"], reverse=True)
    return rows[:limit], len(rows)


@tool(
    description="Game-level availability impact: split a team's results into the games a "
    "player played versus the games they missed (game counts, record, win pct, average "
    "margin). Pass a player for the single-player split; add teammate to split that "
    "player's own per-game scoring/FGA/plus-minus by the teammate's presence; or leave "
    "player empty for a league-wide ranking of high-minute one-team players by win-rate "
    "drop when sitting (min_minutes/min_missed qualifiers). Warehouse coverage: "
    "2015-16 onward, regular season. Possession-level net rating with the player "
    "on vs off the floor is a different question — use get_on_off (one player) "
    "or get_on_off_leaders (boards and pairs)."
)
def get_availability_impact(player: str = "", season: str | None = None,
                            teammate: str = "", min_minutes: float = 28.0,
                            min_missed: int = 15, limit: int = 5) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    year = _season_year(pkg, season)
    try:
        limit = max(1, min(int(limit or 5), 25))
    except (TypeError, ValueError):
        limit = 5
    try:
        min_missed = max(1, int(min_missed or 15))
    except (TypeError, ValueError):
        min_missed = 15
    try:
        min_minutes = max(0.0, float(min_minutes or 0))
    except (TypeError, ValueError):
        min_minutes = 28.0
    try:
        con = pkg.store.connect(read_only=True)
    except Exception as exc:
        return {"tool": "get_availability_impact", "ok": False,
                "error": f"warehouse unavailable: {exc}"[:240]}
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        missing = [t for t in ("silver_boxscores", "silver_hist_gamelogs") if t not in tables]
        if missing:
            return {"tool": "get_availability_impact", "ok": False,
                    "error": f"{', '.join(missing)} not loaded; availability splits unavailable"}
        covered = con.execute(
            "SELECT DISTINCT _season FROM silver_boxscores ORDER BY 1").fetchall()
        span = [r[0] for r in covered]
        season_slug = f"{year - 1}-{str(year)[-2:]}"
        if season_slug not in span:
            return {"tool": "get_availability_impact", "ok": False,
                    "error": (f"no boxscore coverage for {season_slug}; "
                              f"silver_boxscores spans {span[0]} through {span[-1]}")}
        meta = {"source": "warehouse", "season": season_slug, "coverage": "regular-season"}
        raw = str(player or "").strip()
        if not raw:
            rows, pool = _ranking_rows(con, year, min_minutes, min_missed, limit)
            if not rows:
                return {"tool": "get_availability_impact", "ok": False,
                        "error": (f"no qualifying players for {season_slug} "
                                  f"(one team, mpg>={min_minutes}, missed>={min_missed})")}
            return {"tool": "get_availability_impact", "ok": True, "rows": rows,
                    "meta": {**meta, "qualifying_pool": pool}}
        try:
            pid = pkg.coerce_player_id(raw)
        except ValueError as exc:
            return {"tool": "get_availability_impact", "ok": False, "error": str(exc)}
        teams = _player_teams(con, pid, season_slug)
        if not teams:
            return {"tool": "get_availability_impact", "ok": False,
                    "error": f"no {season_slug} boxscore games on file for player {pid}"}
        if teammate:
            try:
                other = pkg.coerce_player_id(teammate)
            except ValueError as exc:
                return {"tool": "get_availability_impact", "ok": False, "error": str(exc)}
            tricode, tid, _ = teams[0]
            rows = _teammate_rows(con, pid, tid, other, season_slug)
            if not rows:
                return {"tool": "get_availability_impact", "ok": False,
                        "error": f"no shared-team games for players {pid}/{other} on {tricode} in {season_slug}"}
            return {"tool": "get_availability_impact", "ok": True, "rows": rows,
                    "meta": {**meta, "team": tricode, "teammate": other}}
        rows = []
        for tricode, _, _gp in teams:
            rows.extend(_split_rows(con, pid, tricode, year))
        if not rows:
            return {"tool": "get_availability_impact", "ok": False,
                    "error": f"no team game log coverage for {season_slug}"}
        out = {"tool": "get_availability_impact", "ok": True, "rows": rows,
               "meta": {**meta, "teams": [t[0] for t in teams]}}
        if len(teams) > 1:
            out["meta"]["note"] = "player appeared for multiple teams; splits are per team in row order"
        return out
    finally:
        try:
            con.close()
        except Exception:
            pass
