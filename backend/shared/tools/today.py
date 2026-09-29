
from typing import Any
from langchain_core.tools import tool

from ._core import IN_SEASON_MONTHS, SEASON, season_static


def _in_offseason() -> bool:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/New_York")).month not in IN_SEASON_MONTHS


def _warehouse_has_games(season: str, dates: list[str]) -> bool:
    try:
        from .. import store as _store

        frame = _store.read_frame(
            "silver_scoreboard",
            "_season = ? AND _entity IN ("
            + ",".join("?" for _ in dates) + ")",
            [season, *(f"date:{d}" for d in dates)],
        )
        return frame.height > 0
    except Exception:
        return True


def _warehouse_games(date_str: str, season: str) -> tuple[list, bool]:
    try:
        from .. import store as _store
        from .team import game_links

        frame = _store.read_frame(
            "silver_scoreboard",
            "_season = ? AND _entity = ?",
            [season, f"date:{date_str}"],
        )
        rows = frame.to_dicts() if frame.height else []
        for r in rows:
            gid = r.get("GAME_ID")
            if gid:
                r["LINKS"] = game_links(str(gid))
        return rows, True
    except Exception:
        return [], False


def _live_scores_needed(season: str, dates: list[str]) -> bool:
    if season_static(season):
        return False
    if _in_offseason() and not _warehouse_has_games(season, dates):
        return False
    return True


def _games(date_str: str, season: str) -> list:
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


        ex.shutdown(wait=False)


def _scoreboards(season: str) -> tuple[list, list, bool]:
    import concurrent.futures
    from datetime import datetime, timedelta as _td
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))
    yesterday = (now - _td(days=1)).strftime("%m/%d/%Y")
    today = now.strftime("%m/%d/%Y")
    if not _live_scores_needed(season, [yesterday, today]):
        last, last_ok = _warehouse_games(yesterday, season)
        tonight, tonight_ok = _warehouse_games(today, season)
        return last, tonight, bool(last_ok and tonight_ok)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        last = ex.submit(_games, yesterday, season)
        tonight = ex.submit(_games, today, season)
        return last.result(), tonight.result(), True


def normalize_movers(delta: Any, season: str) -> dict[str, Any]:
    empty = {"climbers": [], "fallers": [], "new_entries": []}
    if not isinstance(delta, dict) or not delta.get("ok"):
        error = str(delta.get("error", "")) if isinstance(delta, dict) else ""
        reason = "snapshots_pending" if "not enough snapshots" in error else "unavailable"
        return {"tool": "get_leaderboard_deltas", "ok": True, "rows": empty,
                "meta": {"reason": reason, "season": season}}
    rows = delta.get("rows")
    if not isinstance(rows, dict):
        return {"tool": "get_leaderboard_deltas", "ok": True, "rows": empty,
                "meta": {"reason": "unavailable", "season": season}}
    normalized = {key: list(rows.get(key) or [])
                  for key in ("climbers", "fallers", "new_entries")}
    return {**delta, "ok": True, "rows": normalized}


def _movers_from_delta(delta: Any, season: str) -> list:
    rows = normalize_movers(delta, season)["rows"]
    return [
        *[{"PLAYER": item.get("player"), "TEAM": item.get("team"),
           "RANK_CHANGE": f"+{item.get('rank_change')}",
           "PTS_CHANGE": item.get("pts_change")}
          for item in rows["climbers"][:3]],
        *[{"PLAYER": item.get("player"), "TEAM": item.get("team"),
           "RANK_CHANGE": str(item.get("rank_change")),
           "PTS_CHANGE": item.get("pts_change")}
          for item in rows["fallers"][:3]],
    ]


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
    last_night, tonight, scoreboard_ok = _scoreboards(season)
    return {"tool": "get_today", "ok": True,
            "rows": {"last_night": last_night, "tonight": tonight,
                     "movers": _movers_from_delta(delta, season),
                     "streaks": _streaks(season)},
            "meta": {"date": today, "source": "nba_api+warehouse",
                     "scoreboard_ok": scoreboard_ok}}


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
            last_night, tonight, scoreboard_ok = f_sb.result(timeout=40)
            briefing["rows"]["today"] = {
                "last_night": last_night, "tonight": tonight,
                "movers": _movers_from_delta(delta_res, season),
                "streaks": _streaks(season),
            }
            briefing["meta"]["scoreboard_ok"] = scoreboard_ok
        except Exception as e:
            briefing["rows"]["today"] = {"error": str(e)[:100]}
            briefing["meta"]["scoreboard_ok"] = False
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
