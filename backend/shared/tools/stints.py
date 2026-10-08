from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from .splits import _resolve_name

_TABLE = "silver_stints"


def _valid_game_id(raw: object) -> str:
    gid = str(raw or "").strip()
    if len(gid) == 10 and gid.isdigit():
        return gid
    return ""


def _no_coverage(game_id: str) -> dict[str, Any]:
    from v2.adapters.coverage import table_seasons

    available = sorted(table_seasons(_TABLE))
    if available:
        asked = (
            f"No stint timeline for game {game_id}. "
            f"Seasons with stint data: {', '.join(available)}. "
            "Which game should be used instead?"
        )
    else:
        asked = (
            f"No stint timeline for game {game_id}. "
            "No stint data is on hand right now. "
            "Which game should be used instead?"
        )
    return {"tool": "get_stint_timeline", "ok": False, "rows": [],
            "error": asked,
            "meta": {"source": f"warehouse:{_TABLE}",
                     "game_id": game_id,
                     "available_seasons": available,
                     "deterministic_answer": asked}}


def _ids(row: dict, side: str) -> list[int]:
    return [int(row[f"{side}_player_{i}"]) for i in range(1, 6)]


def _names(ids: list[int]) -> list[str]:
    return [_resolve_name(pid, str(pid)) for pid in ids]


def _slim(row: dict) -> dict[str, Any]:
    home = _ids(row, "home")
    away = _ids(row, "away")
    return {
        "stint_number": int(row["stint_number"]),
        "poss_start": int(row["poss_start"]),
        "poss_end": int(row["poss_end"]),
        "period_in": int(row["period_in"]),
        "clock_in": str(row["clock_in"]),
        "period_out": int(row["period_out"]),
        "clock_out": str(row["clock_out"]),
        "duration_sec": float(row["duration_sec"]),
        "home_abbr": str(row["home_abbr"]),
        "away_abbr": str(row["away_abbr"]),
        "home_players": home,
        "away_players": away,
        "home_player_names": _names(home),
        "away_player_names": _names(away),
        "score_home_in": int(row["score_home_in"]),
        "score_away_in": int(row["score_away_in"]),
        "score_home_out": int(row["score_home_out"]),
        "score_away_out": int(row["score_away_out"]),
        "home_swing": int(row["home_swing"]),
    }


@tool(description="Ordered 5-man stint timeline for one game: lineups, clocks, scores, swings.")
def get_stint_timeline(game_id: str = "") -> dict[str, Any]:
    gid = _valid_game_id(game_id)
    if not gid:
        return {"tool": "get_stint_timeline", "ok": False, "rows": [],
                "error": "Give a 10-digit game_id.",
                "meta": {"source": f"warehouse:{_TABLE}",
                         "game_id": str(game_id or "")}}
    frame = _store.read_frame(_TABLE, "game_id = ?", [gid])
    if frame is None or frame.height == 0:
        return _no_coverage(gid)
    raw = sorted(frame.to_dicts(), key=lambda r: int(r["stint_number"]))
    rows = [_slim(r) for r in raw]
    last = rows[-1]
    return {"tool": "get_stint_timeline", "ok": True, "rows": rows,
            "meta": {"source": f"warehouse:{_TABLE}",
                     "season": str(raw[0].get("_season") or ""),
                     "game_id": gid,
                     "stints": len(rows),
                     "home_abbr": str(raw[0].get("home_abbr") or ""),
                     "away_abbr": str(raw[0].get("away_abbr") or ""),
                     "final_home": last["score_home_out"],
                     "final_away": last["score_away_out"],
                     **_store.warehouse_identity()}}
