from datetime import date as _date, datetime, timedelta as _td, timezone
import re as _re
from typing import Any
import unicodedata as _ud

from langchain_core.tools import tool

from ._helpers import _pkg


@tool(description='Current rookie class leaderboard (first-year NBA players only).\n\nRookies are defined structurally: a player in the current-season\nstats table with NO row in any prior season (hist or warehouse).\nNever an age proxy, never historical seasons (F46: a "rookies 20+\nppg" query answered from 2023-24 listed Edwards/LaMelo/Wemby; the\nright answer was the current draft class, e.g. Cooper Flagg).\nstat is a per-game column: ppg, rpg, apg, spg, bpg, mpg.')
def get_rookie_leaders(stat: str = "ppg", min_value: float = 0,
                       min_gp: int = 10, limit: int = 15,
                       season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
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
        con = pkg.store.connect(read_only=True)
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
                       season: str | None = None, playoffs: bool = False) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
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
        con = pkg.store.connect(read_only=True)
        try:
            raw = con.execute(
                sql, [season, float(min_minutes), int(limit) * 2]
            ).fetchdf().to_dict("records")
            hist = False
            if not raw or playoffs:
                raw = con.execute(
                    """
                    SELECT team_abbreviation AS TEAM_ABBREVIATION,
                           group_name AS GROUP_NAME, gp AS GP,
                           ROUND(min, 1) AS MIN, plus_minus AS PLUS_MINUS,
                           ROUND(plus_minus / NULLIF(min, 0) * 48, 1)
                               AS NET48
                    FROM silver_hist_lineups
                    WHERE _season = ? AND min >= ?
                      AND season_type = ?
                      AND measure_type = 'base' AND per_mode = 'totals'
                    ORDER BY plus_minus / NULLIF(min, 0) DESC NULLS LAST
                    LIMIT ?
                    """,
                    [season, float(min_minutes), 'playoffs' if playoffs else 'regular-season', int(limit) * 2],
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
        [_pkg().last_completed_season()],
    )


@tool(description="Capture today's top-50 scoring leaderboard. Idempotent per date.")
def snapshot_leaderboard(season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = str(pkg.resolve_season(season) or "").strip() or pkg.resolve_season(None)
    today = datetime.now(timezone.utc).date().isoformat()
    con = pkg.store.connect(read_only=True)
    try:
        with pkg.store.write_guard():
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
    pkg = _pkg()
    season = str(pkg.resolve_season(season) or "").strip() or pkg.resolve_season(None)
    try:
        days = max(1, int(days or 7))
    except (TypeError, ValueError):
        days = 7
    con = pkg.store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "leaderboard_snapshots" not in tables:
            return {"tool": "get_leaderboard_deltas", "ok": False,
                    "error": "not enough snapshots \u2014 run snapshot_leaderboard daily"}
        dates = [r[0] for r in con.execute(
            """SELECT DISTINCT snapshot_date FROM leaderboard_snapshots
            WHERE season = ? ORDER BY snapshot_date DESC""",
            [season]).fetchall()]
        if len(dates) < 2:
            return {"tool": "get_leaderboard_deltas", "ok": False,
                    "error": "not enough snapshots \u2014 run snapshot_leaderboard daily"}
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
    climbers.sort(key=lambda d: (-(d["rank_change"] or 0),
                                 str(d["player"] or "").casefold(),
                                 str(d["player"] or "")))
    fallers.sort(key=lambda d: ((d["rank_change"] or 0),
                                str(d["player"] or "").casefold(),
                                str(d["player"] or "")))
    new_entries.sort(key=lambda d: ((d["rank"] or 999),
                                    str(d["player"] or "").casefold(),
                                    str(d["player"] or "")))
    try:
        span = (_date.fromisoformat(str(latest))
                - _date.fromisoformat(str(base))).days
    except (TypeError, ValueError):
        span = 0
    return {"tool": "get_leaderboard_deltas", "ok": True,
            "rows": {"climbers": climbers, "fallers": fallers,
                     "new_entries": new_entries},
            "meta": {"source": "leaderboard_snapshots", "season": season,
                     "current_date": latest, "base_date": base,
                     "days_requested": days, "days_actual": span}}
