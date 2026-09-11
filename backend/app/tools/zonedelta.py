"""Player-vs-league zone efficiency deltas. ROADMAP appendix item 6.

get_zone_deltas answers "where does X beat league average, and by how
much" for shooting zones from silver_hist_shots.

This does not duplicate get_team_shot_zones (team zone diet: attempt
shares and eFG per team). This is player efficiency: per-zone FG% vs the
pooled league-average FG% for the same season, with a per-zone attempts
floor so small samples never present as skill.

Warehouse-first. No live calls. Zones reuse the five-zone taxonomy in
zone.py because the source table carries no zone labels. Documented
estimates only.
"""

from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from ._core import coerce_player_id
from .zone import ZONE_KEYS, ZONE_LEGEND, zone_of

TABLE = "silver_hist_shots"

MIN_SEASON, MAX_SEASON = 2010, 2025
MIN_FLOOR, MAX_FLOOR = 10, 200
DEFAULT_FLOOR = 50


def clamp_season_year(season: object) -> int:
    try:
        year = int(str(season).strip()[:4])
    except (TypeError, ValueError, AttributeError):
        return MAX_SEASON
    return max(MIN_SEASON, min(MAX_SEASON, year))


def clamp_floor(value: object) -> int:
    try:
        return max(MIN_FLOOR, min(MAX_FLOOR, int(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_FLOOR


def season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _is_made(row: dict[str, Any]) -> bool:
    return str(row.get("shot_result") or "").lower() == "made"


def _display_name(person_id: int, fallback: str) -> str:
    try:
        from nba_api.stats.static import players as _players
    except Exception:
        return fallback
    try:
        for row in _players.get_players():
            if int(row.get("id")) == person_id:
                return str(row.get("full_name") or fallback)
    except (TypeError, ValueError):
        pass
    return fallback


def fold_zones(shots: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Fold shot dicts into per-zone attempt/make counts. Pure function."""
    out = {key: {"fga": 0, "fgm": 0} for key in ZONE_KEYS}
    for s in shots:
        zone = zone_of(s.get("x"), s.get("y"), s.get("shot_value", 0))
        out[zone]["fga"] += 1
        if _is_made(s):
            out[zone]["fgm"] += 1
    return out


def build_deltas(player: dict[str, dict[str, int]],
                 league: dict[str, dict[str, int]],
                 floor: int) -> tuple[list[dict[str, Any]], list[str]]:
    """One row per zone at or above the attempts floor, sorted by delta
    descending. Zones below the floor come back as excluded names. Pure."""
    rows: list[dict[str, Any]] = []
    excluded: list[str] = []
    for key in ZONE_KEYS:
        p, base = player[key], league[key]
        if p["fga"] < floor:
            excluded.append(key)
            continue
        fg = p["fgm"] / p["fga"]
        lg = base["fgm"] / base["fga"] if base["fga"] else 0.0
        rows.append({
            "zone": key,
            "attempts": p["fga"],
            "makes": p["fgm"],
            "fg_pct": round(fg, 3),
            "league_fg_pct": round(lg, 3),
            "delta_pp": round((fg - lg) * 100, 2),
            "league_attempts": base["fga"],
        })
    rows.sort(key=lambda r: r["delta_pp"], reverse=True)
    return rows, excluded


@tool
def get_zone_deltas(player: str, season: int = MAX_SEASON,
                    min_attempts: int = DEFAULT_FLOOR) -> dict[str, Any]:
    """Player-vs-league shooting-zone efficiency: per-zone FG% vs the
    pooled league-average FG% for the same season, with delta in
    percentage points. Zones below min_attempts (default 50, clamped
    10..200) are excluded. Season is the end year (2010..2025)."""
    warnings: list[str] = []
    year = clamp_season_year(season)
    try:
        raw_year = int(str(season).strip()[:4])
        year_ok = True
    except (TypeError, ValueError, AttributeError):
        raw_year, year_ok = MAX_SEASON, False
    if not year_ok:
        warnings.append(f"season '{season}' invalid, using {MAX_SEASON}")
    elif raw_year != year:
        warnings.append(f"season {raw_year} clamped to {year}")
    floor = clamp_floor(min_attempts)
    try:
        raw_floor = int(min_attempts)  # type: ignore[arg-type]
        floor_ok = True
    except (TypeError, ValueError):
        raw_floor, floor_ok = DEFAULT_FLOOR, False
    if not floor_ok:
        warnings.append(
            f"min_attempts '{min_attempts}' invalid, using {DEFAULT_FLOOR}")
    elif raw_floor != floor:
        warnings.append(f"min_attempts {raw_floor} clamped to {floor}")
    try:
        person_id = coerce_player_id(player)
    except ValueError as exc:
        return {"tool": "get_zone_deltas", "ok": False,
                "rows": {}, "meta": {"season": year,
                                     "season_label": season_label(year)},
                "error": str(exc)}
    frame = _store.read_frame(TABLE, "season = ?", [year])
    if frame.height == 0:
        return {"tool": "get_zone_deltas", "ok": False, "rows": {},
                "meta": {"season": year,
                         "season_label": season_label(year)},
                "error": f"no shot rows for season {season_label(year)} "
                         f"in {TABLE}"}
    all_shots = [{
        "person_id": r.get("person_id"),
        "x": r.get("x_legacy"), "y": r.get("y_legacy"),
        "shot_value": r.get("shot_value", 0),
        "shot_result": r.get("shot_result"),
    } for r in frame.to_dicts()]
    league = fold_zones(all_shots)
    mine = fold_zones([s for s in all_shots
                       if s.get("person_id") is not None
                       and int(s["person_id"]) == person_id])
    total = sum(z["fga"] for z in mine.values())
    name = _display_name(person_id, str(player).strip())
    if total == 0:
        return {"tool": "get_zone_deltas", "ok": False, "rows": {},
                "meta": {"season": year, "season_label": season_label(year)},
                "error": f"no shot rows for player {name!r} in "
                         f"{season_label(year)}; warehouse player names "
                         f"resolve through roster ids, surnames alone "
                         f"may be ambiguous"}
    zones, excluded = build_deltas(mine, league, floor)
    fetched = [str(v) for v in frame.select("_fetched_at").to_series()
               .to_list() if v]
    meta: dict[str, Any] = {
        "source": f"warehouse {TABLE}",
        "season": year,
        "season_label": season_label(year),
        "fetched_at": max(fetched) if fetched else "unknown",
        "player": name,
        "person_id": person_id,
        "player_shots": total,
        "min_attempts": floor,
        "excluded_zones": excluded,
        "data_note": (
            f"Historical shot-level data from sportsdataverse "
            f"nba_stats_shots. Zones are derived geometrically from shot "
            f"x/y coordinates (not source labels): "
            f"{', '.join(f'{k}={v}' for k, v in ZONE_LEGEND.items())}. "
            f"League averages pool every shot from {season_label(year)}. "
            f"Zones below {floor} attempts are excluded, never presented "
            f"as skill. FG% is makes over attempts, not eFG. Documented "
            f"estimates only; do not present as live or current-week."
        ),
        "zones": ZONE_LEGEND,
    }
    if not zones:
        meta["note"] = (f"{name} has {total} tracked shots but no zone "
                        f"reaches the {floor}-attempt floor")
    if warnings:
        meta["warning"] = "; ".join(warnings)
    return {"tool": "get_zone_deltas", "ok": True,
            "rows": {"player": name, "person_id": person_id,
                     "season": year, "season_label": season_label(year),
                     "zones": zones},
            "meta": meta}
