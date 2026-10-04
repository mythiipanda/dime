
import math
from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from ._core import clamp_season, coerce_team_id, last_completed_season, resolve_season

TABLE = "silver_hist_shots"




ZONE_RULES: tuple[tuple[str, Any, str], ...] = (
    ("rim", lambda dist, ax, three: dist < 8.0, "{dist} < 8.0"),
    ("corner_3", lambda dist, ax, three: three and ax >= 220,
     "{three} AND {ax} >= 220"),
    ("atb_3", lambda dist, ax, three: three, "{three}"),
    ("short_mid", lambda dist, ax, three: dist < 14.0, "{dist} < 14.0"),
    ("long_mid", lambda dist, ax, three: True, "TRUE"),
)

ZONE_KEYS = tuple(key for key, _, _ in ZONE_RULES)

ZONE_LEGEND = {
    "rim": "shots within 8 ft of the hoop",
    "short_mid": "2pt shots 8-14 ft out",
    "long_mid": "2pt shots 14 ft+ out",
    "corner_3": "3pt shots with |x| >= 22 ft (corner region)",
    "atb_3": "3pt shots above the break",
}


def zone_of(x: float, y: float, shot_value: int) -> str:
    try:
        dist = math.hypot(float(x), float(y)) / 10.0
    except (TypeError, ValueError):
        dist = 999.0
    try:
        ax = abs(float(x))
    except (TypeError, ValueError):
        ax = 0.0
    three = int(shot_value or 0) == 3
    for key, rule, _ in ZONE_RULES:
        if rule(dist, ax, three):
            return key
    return "long_mid"


def zone_case_sql(x_col: str = "x_legacy", y_col: str = "y_legacy",
                    v_col: str = "shot_value") -> str:
    dist = (
        f"(CASE WHEN {x_col} IS NULL OR {y_col} IS NULL THEN 999.0 ELSE "
        f"SQRT(CAST({x_col} AS DOUBLE) * CAST({x_col} AS DOUBLE) + "
        f"CAST({y_col} AS DOUBLE) * CAST({y_col} AS DOUBLE)) / 10.0 END)"
    )
    ax = f"COALESCE(ABS(CAST({x_col} AS DOUBLE)), 0.0)"
    three = f"COALESCE(({v_col} = 3), FALSE)"
    whens = " ".join(
        f"WHEN {sql.format(dist=dist, ax=ax, three=three)} THEN '{key}'"
        for key, _, sql in ZONE_RULES[:-1]
    )
    return f"(CASE {whens} ELSE '{ZONE_RULES[-1][0]}' END)"


def zone_made_sql(result_col: str = "shot_result") -> str:
    return f"(LOWER({result_col}) = 'made')"


def fetch_zone_aggregates(table: str, year: int,
                          groups: tuple[str, ...] = (),
                          where: str = "",
                          params: list[object] | None = None) -> list[dict[str, Any]]:
    case = zone_case_sql()
    made = zone_made_sql()
    cols = "".join(f"{g}, " for g in groups)
    filt = f" AND {where}" if where else ""
    by = ", ".join([*groups, "zone"])
    rows = _store._read_df(
        f"SELECT {cols}{case} AS zone, COUNT(*) AS fga, "
        f"SUM(CASE WHEN {made} THEN 1 ELSE 0 END) AS fgm "
        f"FROM {table} WHERE season = ?{filt} GROUP BY {by}",
        [year, *(params or [])],
    )
    return [
        {**r, "fga": int(r["fga"]), "fgm": int(r["fgm"])}
        for r in rows
    ]


def fetch_max_fetched_at(table: str, year: int) -> str:
    rows = _store._read_df(
        f"SELECT MAX(_fetched_at) AS m FROM {table} WHERE season = ?",
        [year],
    )
    val = rows[0].get("m") if rows else None
    return str(val) if val else "unknown"


def season_year(season: str) -> int:
    season = resolve_season(season)
    return int(clamp_season(season)[:4]) + 1


def _blank_zone() -> dict[str, int]:
    return {"fga": 0, "fgm": 0, "three_made": 0}


def aggregate_zones(shots: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
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


def _coverage_bounds() -> str:
    try:
        rows = _store._read_df(
            f"SELECT MIN(_season) AS lo, MAX(_season) AS hi FROM {TABLE}", [])
    except Exception:
        return "unknown"
    if not rows:
        return "unknown"
    return f"{rows[0].get('lo')} through {rows[0].get('hi')}"


@tool
def get_team_shot_zones(teams: str = "league",
                        season: str | None = None) -> dict[str, Any]:
    """League-wide team shot-zone diet: per-zone attempt share and eFG
    with league baselines and deltas. teams is "league" or a comma-separated
    list of team names/abbrevs/ids. Zones: rim, short_mid, long_mid,
    corner_3, atb_3."""
    season = resolve_season(season)
    season = clamp_season(season)
    year = season_year(season)
    grouped = fetch_zone_aggregates(TABLE, year,
                                    groups=("team_id", "team_tricode"))
    if not grouped:
        return {"tool": "get_team_shot_zones", "ok": False,
                "error": f"no shot rows for season {season} in {TABLE}; "
                         f"coverage is seasons {_coverage_bounds()}"}
    full_agg: dict[int, dict[str, Any]] = {}
    for r in grouped:
        tid = r.get("team_id")
        if tid is None or (isinstance(tid, float) and math.isnan(tid)):
            continue
        tid = int(tid)
        entry = full_agg.setdefault(
            tid, {"team_id": tid,
                  "team_abbr": r.get("team_tricode") or "",
                  "zones": {k: _blank_zone() for k in ZONE_KEYS}})
        zone = str(r.get("zone"))
        z = entry["zones"][zone]
        z["fga"] += int(r["fga"])
        z["fgm"] += int(r["fgm"])
        if zone in ("corner_3", "atb_3"):
            z["three_made"] += int(r["fgm"])
    frame_ids = set(full_agg)
    wanted, unknown = _parse_teams(teams, frame_ids)

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
    meta = {
        "source": f"warehouse {TABLE}",
        "season": season,
        "fetched_at": fetch_max_fetched_at(TABLE, year),
        "teams_requested": teams,
        "teams_returned": len(agg),
        "data_note": (
            f"Historical shot-level data from sportsdataverse nba_stats_shots, "
            f"backfilled 2026-09-10. Warehouse coverage: completed seasons "
            f"2009-10 through 2025-26 (hustle tracking from 2015-16), regular season and playoffs. "
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
