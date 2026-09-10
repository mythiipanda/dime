"""Today home view. One-call aggregate for app open."""

from typing import Any
from langchain_core.tools import tool

from ._core import SEASON


def _games(date_str: str, season: str) -> list:
    """Fetch games with a hard timeout — live API can hang."""
    import concurrent.futures

    from .team import get_games_on_date

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = ex.submit(
            get_games_on_date.invoke,
            {"game_date": date_str, "season": season},
        )
        res = fut.result(timeout=15)
        return res.get("rows", []) or []
    except Exception:
        return []
    finally:
        # Don't wait for the worker — that's what makes the timeout real.
        # The orphaned thread dies on its own; we don't block on it.
        ex.shutdown(wait=False)


def _scoreboards(season: str) -> tuple[list, list]:
    import concurrent.futures
    from datetime import datetime, timedelta as _td
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))
    yesterday = (now - _td(days=1)).strftime("%m/%d/%Y")
    today = now.strftime("%m/%d/%Y")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        last = ex.submit(_games, yesterday, season)
        tonight = ex.submit(_games, today, season)
        return last.result(), tonight.result()


def _movers_from_delta(delta: Any) -> list:
    try:
        drows = delta.get("rows", {}) if delta.get("ok") else {}
        climbers = (drows.get("climbers", []) or [])[:3]
        fallers = (drows.get("fallers", []) or [])[:3]
        movers = [
            {"PLAYER": c.get("player"), "TEAM": c.get("team"),
             "RANK_CHANGE": f"+{c.get('rank_change')}",
             "PTS_CHANGE": c.get("pts_change")}
            for c in climbers
        ] + [
            {"PLAYER": f.get("player"), "TEAM": f.get("team"),
             "RANK_CHANGE": str(f.get("rank_change")),
             "PTS_CHANGE": f.get("pts_change")}
            for f in fallers
        ]
        if not movers:
            movers = [{"note": "no leaderboard movement in the last 7 days"}]
    except Exception:
        movers = []
    return movers


def _streaks(season: str) -> list[dict[str, Any]]:
    streaks: list[dict[str, Any]] = []
    try:
        from .. import store as _store

        con = _store.connect()
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if "silver_standings" in tables:
                rows = con.execute(
                    "SELECT TeamCity, TeamName, WINS, LOSSES,"
                    " CurrentStreak, strCurrentStreak FROM silver_standings"
                    " WHERE _season = ?",
                    [season],
                ).fetchall()
            else:
                rows = []
        finally:
            con.close()
        for city, name, w, loss, cur, scur in rows:
            try:
                n = abs(int(cur or 0))
            except (TypeError, ValueError):
                n = 0
            if n >= 3:
                streaks.append({
                    "TEAM": f"{city or ''} {name or ''}".strip(),
                    "W": w, "L": loss,
                    "STREAK": scur, "GAMES": n,
                })
        streaks.sort(key=lambda d: d["GAMES"], reverse=True)
    except Exception:
        streaks = []
    return streaks


@tool
def get_today(season: str = SEASON) -> dict[str, Any]:
    """Today home view: last night's results, tonight's games, leaderboard movers, streaks."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from .league import get_leaderboard_deltas

    now = datetime.now(ZoneInfo("America/New_York"))
    today = now.strftime("%m/%d/%Y")
    try:
        delta = get_leaderboard_deltas.invoke({"season": season, "days": 7})
    except Exception:
        delta = None
    last_night, tonight = _scoreboards(season)
    return {"tool": "get_today", "ok": True,
            "rows": {"last_night": last_night, "tonight": tonight,
                     "movers": _movers_from_delta(delta),
                     "streaks": _streaks(season)},
            "meta": {"date": today, "source": "nba_api+warehouse"}}


@tool
def get_morning_briefing(season: str = SEASON) -> dict[str, Any]:
    """Morning briefing: today's games, watchlist updates, leaderboard movers.

    Deterministic pipeline for app open. Combines get_today, get_watchlist,
    and get_leaderboard_deltas into one response.
    """
    import concurrent.futures as _cf

    from .league import get_leaderboard_deltas
    from .watchlist import get_watchlist

    briefing: dict[str, Any] = {
        "tool": "get_morning_briefing", "ok": True, "rows": {}, "meta": {"season": season}
    }
    with _cf.ThreadPoolExecutor(max_workers=3) as ex:
        f_sb = ex.submit(_scoreboards, season)
        f_wl = ex.submit(get_watchlist.invoke, {"season": season})
        f_delta = ex.submit(
            get_leaderboard_deltas.invoke, {"season": season, "days": 7})
        try:
            delta_res = f_delta.result(timeout=40)
        except Exception as e:
            delta_res = {"error": str(e)[:100]}
        if isinstance(delta_res, str):
            try:
                import json as _json

                delta_res = _json.loads(delta_res)
            except Exception as e:
                delta_res = {"error": str(e)[:100]}
        try:
            last_night, tonight = f_sb.result(timeout=40)
            briefing["rows"]["today"] = {
                "last_night": last_night, "tonight": tonight,
                "movers": _movers_from_delta(delta_res),
                "streaks": _streaks(season),
            }
        except Exception as e:
            briefing["rows"]["today"] = {"error": str(e)[:100]}
        try:
            wl_res = f_wl.result(timeout=40)
            if isinstance(wl_res, str):
                import json as _json
                wl_res = _json.loads(wl_res)
            if wl_res.get("ok"):
                briefing["rows"]["watchlist"] = wl_res["rows"]
                briefing["meta"]["watchlist_count"] = wl_res["meta"].get("count", 0)
        except Exception as e:
            briefing["rows"]["watchlist"] = {"error": str(e)[:100]}
        try:
            if isinstance(delta_res, str):
                import json as _json
                delta_res = _json.loads(delta_res)
            if delta_res.get("ok"):
                briefing["rows"]["movers"] = delta_res["rows"]
            else:
                briefing["rows"]["movers"] = {"note": delta_res.get("error", "no deltas")}
        except Exception as e:
            briefing["rows"]["movers"] = {"error": str(e)[:100]}
    return briefing
