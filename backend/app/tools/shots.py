"""Conversational shot finder for the 2025-26 season.

search_shots answers "all his corner-3 attempts in 4th quarters", "who takes
over fourth quarters (shot volume plus efficiency)", and "end-of-quarter
heave-free shooting" from the silver_shots warehouse table.

Zones reuse the five-zone taxonomy from zone.py (rim, short_mid, long_mid,
corner_3, atb_3), mapped here from the warehouse SHOT_ZONE_BASIC labels
rather than geometry. Warehouse-first only: no live calls. Late-game
filtering is time-based only (period >= 4 plus an optional seconds-remaining
cap) because the table has no score-margin column; results must never be
presented as close-game or clutch splits. Heaves are scrubbed by default and
the exclusion count is disclosed in meta.
"""

from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from ._core import (MAX_ROWS, SEASON, clamp_season, coerce_player_id,
                    coerce_team_id)

TABLE = "silver_shots"
COVERAGE_SEASON = "2025-26"

ZONE_KEYS = ("rim", "short_mid", "long_mid", "corner_3", "atb_3")
THREE_ZONES = frozenset({"corner_3", "atb_3"})

# Domain table mapping warehouse SHOT_ZONE_BASIC labels to the taxonomy.
ZONE_LABEL_MAP = {
    "Restricted Area": "rim",
    "In The Paint (Non-RA)": "short_mid",
    "Mid-Range": "long_mid",
    "Left Corner 3": "corner_3",
    "Right Corner 3": "corner_3",
    "Above the Break 3": "atb_3",
}

ZONE_LEGEND = {
    "rim": "Restricted Area",
    "short_mid": "In The Paint (Non-RA)",
    "long_mid": "Mid-Range",
    "corner_3": "Left/Right Corner 3",
    "atb_3": "Above the Break 3",
}

# Period tokens: first (and only) matching expansion wins. 5 means OT (any
# period >= 5); matching folds 5+ onto it.
_PERIOD_TOKEN_MAP = {
    "1": {1}, "2": {2}, "3": {3}, "4": {4},
    "4th": {4}, "ot": {5}, "1h": {1, 2}, "2h": {3, 4},
}

_MADE_VALUES = ("made", "missed", "any")

_TEAM_ABBR_BY_ID: dict[int, str] = {}


def _team_abbr(team_id: object) -> str | None:
    """Map a warehouse TEAM_ID to its abbreviation via nba_api static data."""
    try:
        tid = int(team_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if tid in _TEAM_ABBR_BY_ID:
        return _TEAM_ABBR_BY_ID[tid]
    try:
        from nba_api.stats.static import teams as _static_teams

        for t in _static_teams.get_teams():
            try:
                _TEAM_ABBR_BY_ID[int(t["id"])] = str(t["abbreviation"])
            except (TypeError, ValueError, KeyError):
                continue
    except Exception:
        return None
    return _TEAM_ABBR_BY_ID.get(tid)


def zone_of_label(label: object) -> str | None:
    """Map a raw SHOT_ZONE_BASIC label to the taxonomy key. Pure function."""
    if label is None:
        return None
    return ZONE_LABEL_MAP.get(str(label).strip())


def parse_zones(raw: str) -> set[str]:
    """Parse comma-separated zone keys; "" means all five. Pure function."""
    token = (raw or "").strip().lower()
    if not token:
        return set(ZONE_KEYS)
    out: set[str] = set()
    for piece in token.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece not in ZONE_KEYS:
            raise ValueError(
                f"unknown zone {piece!r}; valid zones: {', '.join(ZONE_KEYS)}")
        out.add(piece)
    if not out:
        return set(ZONE_KEYS)
    return out


def parse_periods(raw: str) -> set[int] | None:
    """Parse period tokens; "" or None means all periods. Pure function.

    Returns a set of allowed periods with 5 as the OT sentinel (period >= 5).
    """
    token = (raw or "").strip().lower()
    if not token:
        return None
    out: set[int] = set()
    for piece in token.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece not in _PERIOD_TOKEN_MAP:
            raise ValueError(
                f"unknown period {piece!r}; valid tokens: 1-4, ot, 1h, 2h, 4th")
        out |= _PERIOD_TOKEN_MAP[piece]
    if not out:
        return None
    return out


def period_matches(period: object, allowed: set[int] | None) -> bool:
    """Check one period value against a parsed period set. Pure function."""
    if allowed is None:
        return True
    try:
        p = int(period)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if p >= 5:
        return 5 in allowed
    return p in allowed


def parse_made(raw: str) -> str:
    """Validate the made filter (case-insensitive). Pure function."""
    value = (raw or "").strip().lower()
    if value not in _MADE_VALUES:
        raise ValueError(
            f"invalid made filter {raw!r}; use one of: made, missed, any")
    return value


def parse_late_clock(raw: str) -> int | None:
    """Parse the late-clock window as integer seconds. Pure function."""
    token = (raw or "").strip()
    if not token:
        return None
    try:
        seconds = int(token)
    except (TypeError, ValueError):
        raise ValueError(
            f"invalid late_clock {raw!r}; pass integer seconds remaining "
            f"(e.g. '30'), or empty for no clock filter")
    if seconds < 0 or seconds > 720:
        raise ValueError(
            f"invalid late_clock {raw!r}; seconds must be 0-720")
    return seconds


def seconds_left(minutes_remaining: object,
                 seconds_remaining: object) -> int | None:
    """Total seconds left in the period, or None when the clock is missing."""
    try:
        total = int(minutes_remaining) * 60 + int(seconds_remaining)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return total if total >= 0 else None


def is_heave(distance_ft: object, minutes_remaining: object,
             seconds_remaining: object) -> bool:
    """Heave estimate: 30+ ft with 3 or fewer seconds left. Pure function."""
    try:
        far = float(distance_ft) >= 30.0  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    left = seconds_left(minutes_remaining, seconds_remaining)
    return bool(far and left is not None and left <= 3)


def format_clock(minutes_remaining: object,
                 seconds_remaining: object) -> str:
    """Format remaining clock as M:SS, or 'unknown' when missing."""
    left = seconds_left(minutes_remaining, seconds_remaining)
    if left is None:
        return "unknown"
    return f"{left // 60}:{left % 60:02d}"


def efficiency(attempts: int, makes: int,
               threes_made: int) -> dict[str, float]:
    """FG% and eFG% (threes count 1.5x) from raw counts. Pure function."""
    if attempts <= 0:
        return {"fg_pct": 0.0, "efg_pct": 0.0}
    return {
        "fg_pct": round(makes / attempts, 4),
        "efg_pct": round((makes + 0.5 * threes_made) / attempts, 4),
    }


def summarize(shots: list[dict[str, Any]]) -> dict[str, Any]:
    """Overall attempts/makes/efficiency plus distinct games. Pure function.

    Each shot needs zone (taxonomy key or None), made (bool), game_id.
    """
    attempts = len(shots)
    makes = sum(1 for s in shots if s.get("made"))
    threes = sum(1 for s in shots
                 if s.get("made") and s.get("zone") in THREE_ZONES)
    games = len({s.get("game_id") for s in shots
                 if s.get("game_id") is not None})
    return {"attempts": attempts, "makes": makes, "threes_made": threes,
            "games": games, **efficiency(attempts, makes, threes)}


def summarize_by_zone(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per taxonomy zone, in taxonomy order. Pure function."""
    out = []
    for key in ZONE_KEYS:
        group = [s for s in shots if s.get("zone") == key]
        makes = sum(1 for s in group if s.get("made"))
        threes = sum(1 for s in group
                     if s.get("made") and key in THREE_ZONES)
        out.append({"zone": key, "attempts": len(group), "makes": makes,
                    **efficiency(len(group), makes, threes)})
    return out


def summarize_by_period(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per period present; periods 5+ group as OT. Pure function."""
    buckets: dict[Any, list[dict[str, Any]]] = {}
    for s in shots:
        try:
            p = int(s.get("period"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        buckets.setdefault("OT" if p >= 5 else p, []).append(s)
    order = [1, 2, 3, 4, "OT"]
    out = []
    for key in order:
        group = buckets.get(key, [])
        if not group:
            continue
        makes = sum(1 for s in group if s.get("made"))
        threes = sum(1 for s in group
                     if s.get("made") and s.get("zone") in THREE_ZONES)
        out.append({"period": key, "attempts": len(group), "makes": makes,
                    **efficiency(len(group), makes, threes)})
    return out


def disambiguate_last_name(raw: str,
                           pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
    """Match a last name against (player_name, player_id) pairs. Pure.

    Returns {"player_id", "candidates", "ambiguous"}; candidates are
    {"player", "player_id"} dicts sorted by id.
    """
    key = (raw or "").strip().lower()
    hits: dict[int, str] = {}
    for name, pid in pairs:
        if str(name or "").strip().lower() != key:
            continue
        try:
            pid_int = int(pid)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        hits.setdefault(pid_int, str(name))
    candidates = [{"player": hits[pid], "player_id": pid}
                  for pid in sorted(hits)]
    if len(hits) == 1:
        return {"player_id": next(iter(hits)), "candidates": candidates,
                "ambiguous": False}
    return {"player_id": None, "candidates": candidates,
            "ambiguous": len(hits) > 1}


def _resolve_player_id(raw: str,
                       pairs: list[tuple[Any, Any]],
                       rows: list[dict[str, Any]]) -> tuple[int | None, str | None]:
    """Resolve player text to a warehouse PLAYER_ID.

    Full names, nicknames, and numeric ids go through coerce_player_id first
    (required because warehouse PLAYER_NAME is last-name-only). A failed
    lookup falls back to a case-insensitive last-name match; shared last
    names return an error asking for disambiguation.
    """
    text = (raw or "").strip()
    if not text:
        return None, None
    try:
        return coerce_player_id(text), None
    except ValueError:
        pass
    outcome = disambiguate_last_name(text, pairs)
    if outcome["ambiguous"]:
        parts = []
        for cand in outcome["candidates"]:
            abbrs: set[str] = set()
            for r in rows:
                if str(r.get("PLAYER_ID") or "") != str(cand["player_id"]):
                    continue
                try:
                    abbr = _team_abbr(int(r.get("TEAM_ID")))  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                if abbr:
                    abbrs.add(abbr)
            teams = sorted(abbrs)
            suffix = f" ({', '.join(teams)})" if teams else ""
            parts.append(f"{cand['player']} (id={cand['player_id']}){suffix}")
        return None, (
            f"last name {text!r} matches multiple players: "
            f"{'; '.join(parts)}; rerun with a full name or numeric id")
    if outcome["player_id"] is None:
        return None, f"unknown player: {text!r}"
    return outcome["player_id"], None


def _row_matches(row: dict[str, Any], player_id: int | None,
                 team_id: int | None, zones: set[str], three_only: bool,
                 made_filter: str, allowed_periods: set[int] | None,
                 late_seconds: int | None) -> bool:
    if player_id is not None:
        try:
            if int(row.get("PLAYER_ID")) != player_id:  # type: ignore[arg-type]
                return False
        except (TypeError, ValueError):
            return False
    if team_id is not None:
        try:
            if int(row.get("TEAM_ID")) != team_id:  # type: ignore[arg-type]
                return False
        except (TypeError, ValueError):
            return False
    zone = zone_of_label(row.get("SHOT_ZONE_BASIC"))
    if zone not in zones:
        return False
    if three_only:
        shot_type = str(row.get("SHOT_TYPE") or "").upper()
        if zone not in THREE_ZONES and not shot_type.startswith("3PT"):
            return False
    made = str(row.get("SHOT_MADE_FLAG") or "").strip() == "1"
    if made_filter == "made" and not made:
        return False
    if made_filter == "missed" and made:
        return False
    if not period_matches(row.get("PERIOD"), allowed_periods):
        return False
    if late_seconds is not None:
        try:
            period = int(row.get("PERIOD"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        if period < 4:
            return False
        left = seconds_left(row.get("MINUTES_REMAINING"),
                            row.get("SECONDS_REMAINING"))
        if left is None or left > late_seconds:
            return False
    return True


def _sort_key(row: dict[str, Any]) -> tuple[str, int]:
    try:
        event = int(row.get("GAME_EVENT_ID") or 0)
    except (TypeError, ValueError):
        event = 0
    return (str(row.get("GAME_ID") or ""), event)


@tool
def search_shots(player: str = "", team: str = "", zones: str = "",
                 periods: str = "", three_only: bool = False,
                 made: str = "any", late_clock: str = "",
                 exclude_heaves: bool = True, limit: int = 25,
                 season: str = SEASON) -> dict[str, Any]:
    """Conversational shot finder: filter 2025-26 shots by player, team,
    zone, period, makes, and late-clock window, with zone/period aggregates.
    zones: rim, short_mid, long_mid, corner_3, atb_3. periods: 1-4, ot, 1h,
    2h, 4th. late_clock: integer seconds remaining (periods 4+, time-based
    only, not score-aware). Zero matches return ok True with empty
    aggregates."""
    season = clamp_season(season)
    if season != COVERAGE_SEASON:
        return {"tool": "search_shots", "ok": False,
                "error": f"warehouse silver_shots covers the {COVERAGE_SEASON} "
                         f"season only (233,632 shots); requested {season!r}"}
    try:
        wanted_zones = parse_zones(zones)
    except ValueError as exc:
        return {"tool": "search_shots", "ok": False, "error": str(exc)}
    try:
        allowed_periods = parse_periods(periods)
    except ValueError as exc:
        return {"tool": "search_shots", "ok": False, "error": str(exc)}
    try:
        made_filter = parse_made(made)
    except ValueError as exc:
        return {"tool": "search_shots", "ok": False, "error": str(exc)}
    try:
        late_seconds = parse_late_clock(late_clock)
    except ValueError as exc:
        return {"tool": "search_shots", "ok": False, "error": str(exc)}
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = MAX_ROWS
    lim = max(1, min(MAX_ROWS, lim))
    team_id: int | None = None
    if (team or "").strip():
        try:
            team_id = coerce_team_id(team)
        except ValueError:
            return {"tool": "search_shots", "ok": False,
                    "error": f"unknown team: {team!r}"}
    try:
        frame = _store.read_frame(TABLE, "_season = ?", [season])
    except Exception as exc:
        return {"tool": "search_shots", "ok": False,
                "error": f"warehouse read failed: {exc}"}
    if frame.height == 0:
        return {"tool": "search_shots", "ok": False,
                "error": f"no shot rows for season {season} in {TABLE}; "
                         f"coverage is the {COVERAGE_SEASON} season only"}
    rows = frame.to_dicts()
    pairs = [(r.get("PLAYER_NAME"), r.get("PLAYER_ID")) for r in rows]
    player_id, player_error = _resolve_player_id(player, pairs, rows)
    if player_error is not None:
        return {"tool": "search_shots", "ok": False, "error": player_error}
    kept: list[dict[str, Any]] = []
    heaves_excluded = 0
    for row in rows:
        if not _row_matches(row, player_id, team_id, wanted_zones,
                            bool(three_only), made_filter, allowed_periods,
                            late_seconds):
            continue
        if exclude_heaves and is_heave(row.get("SHOT_DISTANCE"),
                                       row.get("MINUTES_REMAINING"),
                                       row.get("SECONDS_REMAINING")):
            heaves_excluded += 1
            continue
        kept.append(row)
    kept.sort(key=_sort_key, reverse=True)
    norm = []
    for row in kept:
        try:
            period = int(row.get("PERIOD"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            period = None
        norm.append({
            "zone": zone_of_label(row.get("SHOT_ZONE_BASIC")),
            "made": str(row.get("SHOT_MADE_FLAG") or "").strip() == "1",
            "period": period,
            "game_id": row.get("GAME_ID"),
        })
    shots = []
    for row in kept[:lim]:
        try:
            distance = float(row.get("SHOT_DISTANCE"))
        except (TypeError, ValueError):
            distance = None
        try:
            period = int(row.get("PERIOD"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            period = None
        shots.append({
            "player": row.get("PLAYER_NAME"),
            "team": _team_abbr(row.get("TEAM_ID")),
            "period": period,
            "clock": format_clock(row.get("MINUTES_REMAINING"),
                                  row.get("SECONDS_REMAINING")),
            "zone": zone_of_label(row.get("SHOT_ZONE_BASIC")),
            "zone_label": row.get("SHOT_ZONE_BASIC"),
            "action": row.get("ACTION_TYPE"),
            "distance_ft": distance,
            "made": str(row.get("SHOT_MADE_FLAG") or "").strip() == "1",
            "game_id": row.get("GAME_ID"),
        })
    aggregate = summarize(norm)
    filters = {
        "player": player, "player_id": player_id,
        "team": team, "team_id": team_id,
        "zones": sorted(wanted_zones),
        "periods": sorted(allowed_periods)
        if allowed_periods is not None else "all",
        "three_only": bool(three_only), "made": made_filter,
        "late_clock_seconds": late_seconds,
        "exclude_heaves": bool(exclude_heaves), "limit": lim,
        "season": season,
    }
    meta = {
        "source": f"warehouse {TABLE}",
        "season": season,
        "shots_scanned": len(rows),
        "shots_matched": len(kept),
        "heaves_excluded": heaves_excluded,
        "games": aggregate["games"],
        "rows_returned": len(shots),
        "zones": ZONE_LEGEND,
        "data_note": (
            f"Warehouse silver_shots coverage is the {COVERAGE_SEASON} season "
            f"only (233,632 shots, regular season and playoffs). PLAYER_NAME "
            f"is last-name-only (e.g. 'Gilgeous-Alexander'). TEAM_NAME/HTM/VTM "
            f"columns are not populated in this table, so team abbreviations "
            f"come from the nba_api static id->abbreviation mapping. GAME_DATE is not "
            f"populated in this table. There is no score-margin column, so "
            f"late-game filtering is time-based only (period >= 4 plus the "
            f"late_clock seconds-remaining cap) and is NOT score-aware: never "
            f"present these results as close-game or clutch splits. Heave "
            f"scrub is an estimate (30+ ft with 3 or fewer seconds left in "
            f"the period); {heaves_excluded} shots excluded here. "
            f"Individual rows are illustrative samples ordered by "
            f"GAME_ID/GAME_EVENT_ID; the aggregates are the answer."
        ),
    }
    return {"tool": "search_shots", "ok": True, "filters": filters,
            "aggregate": aggregate, "by_zone": summarize_by_zone(norm),
            "by_period": summarize_by_period(norm), "shots": shots,
            "meta": meta}
