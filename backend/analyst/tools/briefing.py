from typing import Any

from langchain_core.tools import tool

from .common import call_sync, finish_strict_rows, sanitize_for_wire
from .errors import enrich_error


def _briefing_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    date_val = raw_rows.get("date", "")
    games = raw_rows.get("games")
    if isinstance(games, list) and games:
        return [{"date": date_val, **g} for g in games if isinstance(g, dict)]
    top_scorers = raw_rows.get("top_scorers")
    if isinstance(top_scorers, list) and top_scorers:
        return [{"date": date_val, **s} for s in top_scorers if isinstance(s, dict)]
    if date_val:
        return [{"date": date_val, "games_count": 0, "status": "no games scheduled or completed"}]
    return []


def _today_game_rows(items: Any, category: str, default_status: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in items or []:
        if not isinstance(g, dict):
            continue
        vpts = g.get("VISITOR_TEAM_PTS")
        hpts = g.get("HOME_TEAM_PTS")
        home_abbr = g.get("HOME_TEAM_ABBREVIATION")
        away_abbr = g.get("VISITOR_TEAM_ABBREVIATION")
        rows.append({
            "category": category,
            "home_team": home_abbr,
            "away_team": away_abbr,
            "score": f"{vpts if vpts is not None else '?'}-{hpts if hpts is not None else '?'}",
            "status": g.get("GAME_STATUS_TEXT") or default_status,
            "player": None,
            "team": None,
            "detail": f"{away_abbr or '?'} @ {home_abbr or '?'}",
        })
    return rows


def _today_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    rows = _today_game_rows(raw_rows.get("last_night"), "last_night", "FINAL")
    rows.extend(_today_game_rows(raw_rows.get("tonight"), "tonight", "SCHEDULED"))
    for m in raw_rows.get("movers") or []:
        if isinstance(m, dict):
            rows.append({
                "category": "mover", "home_team": None, "away_team": None,
                "score": None, "status": None,
                "player": m.get("PLAYER"), "team": m.get("TEAM"),
                "detail": f"{m.get('RANK_CHANGE', '')} rank ({m.get('PTS_CHANGE', '')} pts)".strip(),
            })
    for s in raw_rows.get("streaks") or []:
        if isinstance(s, dict):
            rows.append({
                "category": "streak", "home_team": None, "away_team": None,
                "score": f"{s.get('W', '')}-{s.get('L', '')}".strip("-"),
                "status": s.get("STREAK"), "player": None, "team": s.get("TEAM"),
                "detail": f"{s.get('GAMES', '')} games".strip(),
            })
    return rows


def _mb_game_rows(items: Any, section: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in items or []:
        if not isinstance(g, dict):
            continue
        vpts = g.get("VISITOR_TEAM_PTS")
        hpts = g.get("HOME_TEAM_PTS")
        home_abbr = g.get("HOME_TEAM_ABBREVIATION")
        away_abbr = g.get("VISITOR_TEAM_ABBREVIATION")
        rows.append({
            "section": section,
            "headline": f"{away_abbr or '?'} @ {home_abbr or '?'}",
            "detail": f"{vpts if vpts is not None else '?'}-{hpts if hpts is not None else '?'} {g.get('GAME_STATUS_TEXT') or ''}".strip(),
            "team": home_abbr,
            "player": None,
        })
    return rows


def _mb_today_rows(today_data: Any) -> list[dict[str, Any]]:
    if not isinstance(today_data, dict):
        return []
    rows = _mb_game_rows(today_data.get("last_night"), "last_night")
    rows.extend(_mb_game_rows(today_data.get("tonight"), "tonight"))
    for m in today_data.get("movers") or []:
        if isinstance(m, dict):
            rows.append({
                "section": "today_movers",
                "headline": f"{m.get('PLAYER')} ({m.get('TEAM')})",
                "detail": f"{m.get('RANK_CHANGE', '')} rank ({m.get('PTS_CHANGE', '')} pts)",
                "team": m.get("TEAM"),
                "player": m.get("PLAYER"),
            })
    for s in today_data.get("streaks") or []:
        if isinstance(s, dict):
            rows.append({
                "section": "streaks",
                "headline": f"{s.get('TEAM')} {s.get('STREAK')}",
                "detail": f"{s.get('W')}-{s.get('L')} record over {s.get('GAMES')} games",
                "team": s.get("TEAM"),
                "player": None,
            })
    return rows


def _mb_watchlist_identity(etype: str, eid: Any, snap: dict[str, Any]) -> tuple[Any, Any, Any]:
    if etype == "player":
        return eid, snap.get("team"), snap.get("player") or eid
    if etype == "team":
        return None, eid, snap.get("name") or snap.get("team") or eid
    return None, None, eid


def _mb_watchlist_detail(etype: str, added: Any, snap: dict[str, Any]) -> str | None:
    bits = [f"Added {added}"] if added else []
    if snap.get("found"):
        if etype == "player":
            stat_bits = [f"{snap[k]} {u}" for k, u in (("ppg", "PPG"), ("rpg", "RPG"), ("apg", "APG")) if snap.get(k) is not None]
            if stat_bits:
                bits.append(" / ".join(stat_bits))
        elif snap.get("record"):
            bits.append(str(snap.get("record")))
    return " \u00b7 ".join(bits) if bits else None


def _mb_watchlist_rows(items: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for w in items or []:
        if not isinstance(w, dict):
            continue
        etype = str(w.get("entity_type") or "").strip().lower()
        eid = w.get("entity_id")
        snap = w.get("snapshot") if isinstance(w.get("snapshot"), dict) else {}
        player_val, team_val, label = _mb_watchlist_identity(etype, eid, snap)
        kind = etype if etype in ("player", "team") else ""
        headline = f"Watching {kind} {label}" if kind and label else (f"Watching {label}" if label else None)
        rows.append({
            "section": "watchlist",
            "headline": headline,
            "detail": _mb_watchlist_detail(etype, w.get("added_at"), snap),
            "team": team_val,
            "player": player_val,
        })
    return rows


def _mb_movers_rows(movers_data: Any) -> list[dict[str, Any]]:
    if not isinstance(movers_data, dict):
        return []
    rows: list[dict[str, Any]] = []
    for category in ("climbers", "fallers", "new_entries"):
        for m in movers_data.get(category) or []:
            if not isinstance(m, dict):
                continue
            detail = (
                f"new #{m.get('rank')} ({m.get('pts')} pts)"
                if category == "new_entries"
                else f"{m.get('rank_change')} rank ({m.get('pts_change')} pts)"
            )
            rows.append({
                "section": f"movers_{category}",
                "headline": f"{m.get('player')} ({m.get('team')})",
                "detail": detail,
                "team": m.get("team"),
                "player": m.get("player"),
            })
    return rows


def _morning_briefing_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    rows = _mb_today_rows(raw_rows.get("today") or {})
    rows.extend(_mb_watchlist_rows(raw_rows.get("watchlist")))
    rows.extend(_mb_movers_rows(raw_rows.get("movers")))
    return rows


def register() -> dict[str, Any]:
    from shared.tools.league import get_briefing as _orig_get_briefing
    try:
        from shared.tools.today import (
            get_morning_briefing as _orig_get_morning_briefing,
            get_today as _orig_get_today,
        )
    except ImportError:
        from backend.shared.tools.today import (
            get_morning_briefing as _orig_get_morning_briefing,
            get_today as _orig_get_today,
        )

    @tool("get_briefing", description=_orig_get_briefing.description)
    def get_briefing(game_date: str = "", season: str | None = None) -> dict:
        res = call_sync(_orig_get_briefing, "get_briefing", {"game_date": game_date, "season": season})
        default_cols = ["date", "matchup", "score", "status", "top_scorer", "top_pts"]
        rows = _briefing_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        if not res.get("ok"):
            enrich_error("get_briefing", res)
        return sanitize_for_wire(res)

    @tool("get_today", description=_orig_get_today.description)
    def get_today(season: str | None = None) -> dict:
        cols = ["category", "home_team", "away_team", "score", "status", "player", "team", "detail"]
        res = call_sync(_orig_get_today, "get_today", {"season": season})
        return finish_strict_rows(res, "get_today", cols, "Today home view lookup failed", _today_rows, fixed_cols=True)

    @tool("get_morning_briefing", description=_orig_get_morning_briefing.description)
    def get_morning_briefing(season: str | None = None) -> dict:
        cols = ["section", "headline", "detail", "team", "player"]
        res = call_sync(_orig_get_morning_briefing, "get_morning_briefing", {"season": season})
        return finish_strict_rows(
            res, "get_morning_briefing", cols, "Morning briefing lookup failed",
            _morning_briefing_rows, fixed_cols=True,
        )

    return {
        "get_briefing": get_briefing,
        "get_today": get_today,
        "get_morning_briefing": get_morning_briefing,
    }
