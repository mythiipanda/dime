"""League-wide team shot-zone diet. ROADMAP Phase 2 item 6.

get_team_shot_zones answers "which teams shoot at the rim most?" and
"what is X's corner-three rate vs league?" from silver_hist_shots.

Zone taxonomy is a five-zone domain table, not scattered conditionals:
rim (< 8 ft), short mid (8-14 ft), long mid (14 ft+), corner 3, above-break 3.
Zones are derived geometrically from the warehouse's x_legacy/y_legacy
(tenths of a foot) because the source table carries no zone labels.

Warehouse-first. No live calls. The source backfill covers completed
seasons 2021-22 through 2025-26, regular season and playoffs.
"""

import math
from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from ._core import SEASON, clamp_season, coerce_team_id

TABLE = "silver_hist_shots"

# Zone taxonomy as an ordered rule table: first matching rule wins.
# Each rule is (zone_key, predicate(dist_ft, abs_x_ft10, is_three)).
# x is in tenths of a foot, so |x| >= 220 marks the corner region.
ZONE_RULES: tuple[tuple[str, Any], ...] = (
    ("rim", lambda dist, ax, three: dist < 8.0),
    ("corner_3", lambda dist, ax, three: three and ax >= 220),
    ("atb_3", lambda dist, ax, three: three),
    ("short_mid", lambda dist, ax, three: dist < 14.0),
    ("long_mid", lambda dist, ax, three: True),
)

ZONE_KEYS = tuple(key for key, _ in ZONE_RULES)

ZONE_LEGEND = {
    "rim": "shots within 8 ft of the hoop",
    "short_mid": "2pt shots 8-14 ft out",
    "long_mid": "2pt shots 14 ft+ out",
    "corner_3": "3pt shots with |x| >= 22 ft (corner region)",
    "atb_3": "3pt shots above the break",
}


def zone_of(x: float, y: float, shot_value: int) -> str:
    """Classify one shot into the five-zone taxonomy. Pure function."""
    try:
        dist = math.hypot(float(x), float(y)) / 10.0
    except (TypeError, ValueError):
        dist = 999.0
    try:
        ax = abs(float(x))
    except (TypeError, ValueError):
        ax = 0.0
    three = int(shot_value or 0) == 3
    for key, rule in ZONE_RULES:
        if rule(dist, ax, three):
            return key
    return "long_mid"


def season_year(season: str) -> int:
    """Map '2025-26' to the warehouse's integer season (end year)."""
    return int(clamp_season(season)[:4]) + 1


def _blank_zone() -> dict[str, int]:
    return {"fga": 0, "fgm": 0, "three_made": 0}


def aggregate_zones(shots: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Fold shot dicts into per-team per-zone attempt/make counts.

    Each shot needs team_id, team_abbr, made (bool), and either a
    precomputed zone or x/y/shot_value to classify. Pure function.
    """
    teams: dict[int, dict[str, Any]] = {}
    for s in shots:
        tid = s.get("team_id")
        if tid is None:
            continue
        tid = int(tid)
        zone = s.get("zone") or zone_of(s.get("x"), s.get("y"),
                                        s.get("shot_value", 0))
        made = bool(s.get("made"))
        entry = teams.setdefault(tid, {"team_id": tid,
                                       "team_abbr": s.get("team_abbr", ""),
                                       "zones": {k: _blank_zone()
                                                 for k in ZONE_KEYS}})
        z = entry["zones"][zone]
        z["fga"] += 1
        if made:
            z["fgm"] += 1
            if zone in ("corner_3", "atb_3"):
                z["three_made"] += 1
    return teams


def league_baselines(teams: dict[int, dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Pooled league totals per zone: share of all shots and eFG. Pure."""
    total_fga = sum(z["fga"] for t in teams.values()
                    for z in t["zones"].values())
    out: dict[str, dict[str, float]] = {}
    for key in ZONE_KEYS:
        fga = sum(t["zones"][key]["fga"] for t in teams.values())
        fgm = sum(t["zones"][key]["fgm"] for t in teams.values())
        threes = sum(t["zones"][key]["three_made"] for t in teams.values())
        out[key] = {
            "fga": fga,
            "share": round(fga / total_fga, 4) if total_fga else 0.0,
            "efg": round((fgm + 0.5 * threes) / fga, 4) if fga else 0.0,
        }
    return out


def build_rows(teams: dict[int, dict[str, Any]],
               baselines: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """One row per team plus a LEAGUE baseline row. Shares, eFG, deltas in pp."""
    rows: list[dict[str, Any]] = [{
        "team": "LEAGUE", "team_id": 0,
        "shots": sum(b["fga"] for b in baselines.values()),
        **{f"{k}_share": b["share"] for k, b in baselines.items()},
        **{f"{k}_efg": b["efg"] for k, b in baselines.items()},
    }]
    for t in sorted(teams.values(), key=lambda x: str(x["team_abbr"])):
        team_fga = sum(z["fga"] for z in t["zones"].values())
        row: dict[str, Any] = {
            "team": t["team_abbr"], "team_id": t["team_id"], "shots": team_fga,
        }
        for key in ZONE_KEYS:
            z = t["zones"][key]
            share = z["fga"] / team_fga if team_fga else 0.0
            efg = ((z["fgm"] + 0.5 * z["three_made"]) / z["fga"]
                   if z["fga"] else 0.0)
            row[f"{key}_share"] = round(share, 4)
            row[f"{key}_efg"] = round(efg, 4)
            row[f"{key}_share_delta_pp"] = round(
                (share - baselines[key]["share"]) * 100, 2)
            row[f"{key}_efg_delta_pp"] = round(
                (efg - baselines[key]["efg"]) * 100, 2)
        rows.append(row)
    return rows


def _zone_leaders(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Leader per zone: the team the league desk should name for "who leads
    this zone" questions.

    Pure function; kept testable so a zone leader can never silently drift
    back to "the first row scanned". Selection rule: highest
    {zone}_share_delta_pp among team rows (the LEAGUE baseline row is not
    eligible). share_delta is the criterion because zone questions are
    about shot diet (who shoots the most at the rim / from the corner),
    not efficiency. Ties broken by higher {zone}_share (more of the diet
    at that zone), then by output order (rows are abbr-sorted, so a full
    tie keeps the first team alphabetically).
    """
    out: dict[str, dict[str, Any]] = {}
    for key in ZONE_KEYS:
        best = max(rows,
                   key=lambda r: (r.get(f"{key}_share_delta_pp", 0.0),
                                  r.get(f"{key}_share", 0.0)))
        out[key] = {
            "team": best["team"],
            "team_id": best["team_id"],
            "share": best[f"{key}_share"],
            "share_delta_pp": best[f"{key}_share_delta_pp"],
            "shots": best["shots"],
        }
    return out


def _parse_teams(raw: str, frame_team_ids: set[int]) -> tuple[set[int], list[str]]:
    wanted: set[int] = set()
    unknown: list[str] = []
    token = (raw or "").strip()
    if not token or token.lower() in ("league", "all"):
        return set(frame_team_ids), []
    for piece in token.replace(";", ",").split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            wanted.add(coerce_team_id(piece))
        except ValueError:
            unknown.append(piece)
    return wanted, unknown


@tool
def get_team_shot_zones(teams: str = "league",
                        season: str = SEASON) -> dict[str, Any]:
    """League-wide team shot-zone diet: per-zone attempt share and eFG
    with league baselines and deltas. teams is "league" or a comma-separated
    list of team names/abbrevs/ids. Zones: rim, short_mid, long_mid,
    corner_3, atb_3."""
    season = clamp_season(season)
    year = season_year(season)
    frame = _store.read_frame(TABLE, "season = ?", [year])
    if frame.height == 0:
        return {"tool": "get_team_shot_zones", "ok": False,
                "error": f"no shot rows for season {season} in {TABLE}; "
                         f"coverage is seasons 2021-22 through 2025-26"}
    frame_ids = {int(t) for t in frame.select("team_id").to_series().to_list()}
    wanted, unknown = _parse_teams(teams, frame_ids)
    all_shots = [{
        "team_id": int(r.get("team_id") or 0),
        "team_abbr": r.get("team_tricode") or "",
        "x": r.get("x_legacy"), "y": r.get("y_legacy"),
        "shot_value": r.get("shot_value", 0),
        "made": str(r.get("shot_result") or "").lower() == "made",
    } for r in frame.to_dicts() if r.get("team_id") is not None]
    full_agg = aggregate_zones(all_shots)
    # League baselines always come from every team that season.
    baselines = league_baselines(full_agg)
    agg = {tid: t for tid, t in full_agg.items() if tid in wanted}
    if not agg:
        return {"tool": "get_team_shot_zones", "ok": False,
                "error": f"no shot rows matched teams {teams!r} for {season}"}
    rows = build_rows(agg, baselines)
    leaders = _zone_leaders(rows[1:])
    for key, leader in leaders.items():
        for row in rows[1:]:
            row[f"is_{key}_share_leader"] = row["team_id"] == leader["team_id"]
    rows[0].update({f"is_{key}_share_leader": False for key in ZONE_KEYS})
    fetched = [str(v) for v in frame.select("_fetched_at").to_series()
               .to_list() if v]
    meta = {
        "source": f"warehouse {TABLE}",
        "season": season,
        "fetched_at": max(fetched) if fetched else "unknown",
        "teams_requested": teams,
        "teams_returned": len(agg),
        "data_note": (
            f"Historical shot-level data from sportsdataverse nba_stats_shots, "
            f"backfilled 2026-09-10. Warehouse coverage: completed seasons "
            f"2021-22 through 2025-26, regular season and playoffs. "
            f"Zones are derived geometrically from shot x/y coordinates "
            f"(not source labels): {', '.join(f'{k}={v}' for k, v in ZONE_LEGEND.items())}. "
            f"League baselines are pooled across all 30 teams for {season}. "
            f"Deltas are in percentage points vs the league baseline. "
            f"Current-season data is not available in the warehouse; do not "
            f"present {season} numbers as live or current-week."
        ),
        "zones": ZONE_LEGEND,
    }
    if unknown:
        meta["unknown_teams"] = unknown
    return {"tool": "get_team_shot_zones", "ok": True, "rows": rows,
            "zone_leaders": leaders, "meta": meta}
