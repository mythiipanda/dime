import json
from typing import Any

from langchain_core.tools import tool

from .. import store as _store

_TABLE = "silver_possessions"


def _valid_game_id(raw: object) -> str:
    gid = str(raw or "").strip()
    if len(gid) == 10 and gid.isdigit():
        return gid
    return ""


def _parse_min_sec(text: str) -> float | None:
    try:
        parts = str(text or "").strip().split(":")
        if len(parts) != 2:
            return None
        minutes = int(parts[0])
        seconds = float(parts[1])
        if minutes < 0 or seconds < 0 or seconds >= 60:
            return None
        return minutes * 60.0 + seconds
    except (TypeError, ValueError):
        return None


def _parse_clock_range(raw: object) -> tuple[float, float] | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    parts = text.split("-")
    if len(parts) != 2:
        return None
    high = _parse_min_sec(parts[0])
    low = _parse_min_sec(parts[1])
    if high is None or low is None:
        return None
    return (min(low, high), max(low, high))


def _no_coverage(game_id: str) -> dict[str, Any]:
    from v2.adapters.coverage import table_seasons

    available = sorted(table_seasons(_TABLE))
    if available:
        asked = (
            f"No possession log for game {game_id}. "
            f"Seasons with possession data: {', '.join(available)}. "
            "Which game should be used instead?"
        )
    else:
        asked = (
            f"No possession log for game {game_id}. "
            "No possession data is on hand right now. "
            "Which game should be used instead?"
        )
    return {"tool": "get_possession_log", "ok": False, "rows": [],
            "error": asked,
            "meta": {"source": f"warehouse:{_TABLE}",
                     "game_id": game_id,
                     "available_seasons": available,
                     "deterministic_answer": asked}}


def _slim(row: dict) -> dict[str, Any]:
    try:
        events = json.loads(str(row.get("events") or "[]"))
        if not isinstance(events, list):
            events = []
    except (TypeError, ValueError):
        events = []
    return {
        "possession_number": int(row["possession_number"]),
        "period": int(row["period"]),
        "clock_in": str(row["clock_in"]),
        "clock_out": str(row["clock_out"]),
        "off_abbr": str(row["off_abbr"]),
        "def_abbr": str(row["def_abbr"]),
        "events": events,
        "points": int(row["points"]),
        "wpa_delta": float(row["wpa_delta"]),
        "score_home_in": int(row["score_home_in"]),
        "score_away_in": int(row["score_away_in"]),
        "score_home_out": int(row["score_home_out"]),
        "score_away_out": int(row["score_away_out"]),
    }


@tool(description="Possession-by-possession log for one game: order, clocks, offense, events, points, WPA swings.")
def get_possession_log(game_id: str = "", period: int | None = None,
                       clock_range: str | None = None) -> dict[str, Any]:
    gid = _valid_game_id(game_id)
    if not gid:
        return {"tool": "get_possession_log", "ok": False, "rows": [],
                "error": "Give a 10-digit game_id.",
                "meta": {"source": f"warehouse:{_TABLE}",
                         "game_id": str(game_id or "")}}
    wanted_period: int | None = None
    if period is not None:
        try:
            wanted_period = int(period)
        except (TypeError, ValueError):
            wanted_period = None
        if wanted_period is None or wanted_period < 1:
            return {"tool": "get_possession_log", "ok": False, "rows": [],
                    "error": "Give period as a positive quarter number.",
                    "meta": {"source": f"warehouse:{_TABLE}",
                             "game_id": gid}}
    window = _parse_clock_range(clock_range)
    if clock_range is not None and str(clock_range).strip() and window is None:
        return {"tool": "get_possession_log", "ok": False, "rows": [],
                "error": "Give clock_range as M:SS-M:SS, e.g. 8:00-4:00.",
                "meta": {"source": f"warehouse:{_TABLE}",
                         "game_id": gid}}
    frame = _store.read_frame(_TABLE, "game_id = ?", [gid])
    if frame is None or frame.height == 0:
        return _no_coverage(gid)
    raw = sorted(frame.to_dicts(), key=lambda r: int(r["possession_number"]))
    if wanted_period is not None:
        raw = [r for r in raw if int(r["period"]) == wanted_period]
    if window is not None:
        raw = [r for r in raw
               if window[0] <= float(r["clock_in_sec"]) <= window[1]]
    rows = [_slim(r) for r in raw]
    if not rows:
        return {"tool": "get_possession_log", "ok": True, "rows": rows,
                "meta": {"source": f"warehouse:{_TABLE}",
                         "game_id": gid,
                         "possessions": 0,
                         "period": wanted_period,
                         "clock_range": str(clock_range or ""),
                         "note": "Game exists but no possessions match "
                                 "the given filters.",
                         **_store.warehouse_identity()}}
    last = rows[-1]
    meta: dict[str, Any] = {"source": f"warehouse:{_TABLE}",
                            "season": str(raw[0].get("_season") or ""),
                            "game_id": gid,
                            "possessions": len(rows),
                            "period": wanted_period,
                            "clock_range": str(clock_range or ""),
                            "final_home": last["score_home_out"],
                            "final_away": last["score_away_out"],
                            **_store.warehouse_identity()}
    return {"tool": "get_possession_log", "ok": True, "rows": rows,
            "meta": meta}
