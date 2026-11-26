from typing import Any

from langchain_core.tools import tool

from .. import store
from ._core import (
    InvalidSeasonError,
    clamp_season,
    coerce_player_id,
    coerce_team_id,
    resolve_season,
)
from .zone import ZONE_KEYS, ZONE_LEGEND, zone_case_sql, zone_made_sql

TABLE = "silver_hist_shots"
TRACKING_TABLE = "silver_tracking_pt_stats"

PHASE_SQL = "CASE WHEN substr(game_id, 1, 3) = '004' THEN 'playoffs' ELSE 'regular_season' END"

FAMILY_SQL = """CASE
WHEN sub_type ILIKE '%Pullup%' OR sub_type ILIKE '%Pull-Up%'
     OR sub_type ILIKE '%Step Back%' OR sub_type ILIKE '%Fadeaway%'
     OR sub_type ILIKE '%Turnaround%' THEN 'pull_up'
WHEN sub_type = 'Jump Shot' THEN 'catch_and_shoot'
WHEN sub_type ILIKE '%Layup%' OR sub_type ILIKE '%Dunk%'
     OR sub_type ILIKE '%Finger Roll%' OR sub_type ILIKE '%Hook%'
     OR sub_type ILIKE '%Putback%' OR sub_type ILIKE '%Tip%' THEN 'rim_finish'
ELSE 'other' END"""

FAMILY_LEGEND = {
    "pull_up": "self-created jumpers (pull-up, step-back, fadeaway, turnaround)",
    "catch_and_shoot": "spot-up jumpers (PBP sub_type 'Jump Shot')",
    "rim_finish": "layups, dunks, hooks, tips, putbacks",
    "other": "remaining shot sub_types",
}

_FAMILY_ORDER = ("catch_and_shoot", "pull_up", "rim_finish", "other")


def _agg(kind: str, year: int, subject_sql: str, params: list[Any]
         ) -> list[dict[str, Any]]:
    bucket = zone_case_sql() if kind == "zone" else FAMILY_SQL
    made = zone_made_sql()
    return store._read_df(
        f"SELECT {bucket} AS bucket, {PHASE_SQL} AS phase, "
        f"COUNT(*) AS fga, "
        f"SUM(CASE WHEN {made} THEN 1 ELSE 0 END) AS fgm, "
        f"SUM(CASE WHEN {made} AND shot_value = 3 THEN 1 ELSE 0 END) AS tpm "
        f"FROM {TABLE} WHERE season = ? AND {subject_sql} "
        f"GROUP BY 1, 2",
        [year, *params],
    )


def _pair(rows: list[dict[str, Any]], kind: str,
          order: tuple[str, ...]) -> list[dict[str, Any]]:
    by_bucket: dict[str, dict[str, dict[str, Any]]] = {}
    totals = {"regular_season": 0, "playoffs": 0}
    for r in rows:
        phase = str(r["phase"])
        fga = int(r["fga"] or 0)
        totals[phase] = totals.get(phase, 0) + fga
        by_bucket.setdefault(str(r["bucket"]), {})[phase] = {
            "fga": fga,
            "fgm": int(r["fgm"] or 0),
            "tpm": int(r["tpm"] or 0),
        }
    out = []
    for bucket in order:
        if bucket not in by_bucket:
            continue
        rs = by_bucket[bucket].get("regular_season",
                                   {"fga": 0, "fgm": 0, "tpm": 0})
        po = by_bucket[bucket].get("playoffs",
                                   {"fga": 0, "fgm": 0, "tpm": 0})

        def efg(s: dict[str, Any]) -> float | None:
            if not s["fga"]:
                return None
            return round((s["fgm"] + 0.5 * s["tpm"]) / s["fga"], 4)

        def share(s: dict[str, Any], phase: str) -> float | None:
            if not totals.get(phase):
                return None
            return round(s["fga"] / totals[phase], 4)

        rs_efg, po_efg = efg(rs), efg(po)
        rs_share, po_share = share(rs, "regular_season"), share(po, "playoffs")
        out.append({
            "kind": kind,
            "bucket": bucket,
            "rs_fga": rs["fga"], "rs_fgm": rs["fgm"],
            "rs_efg": rs_efg, "rs_share": rs_share,
            "po_fga": po["fga"], "po_fgm": po["fgm"],
            "po_efg": po_efg, "po_share": po_share,
            "efg_delta_pp": round((po_efg - rs_efg) * 100, 1)
            if rs_efg is not None and po_efg is not None else None,
            "share_delta_pp": round((po_share - rs_share) * 100, 1)
            if rs_share is not None and po_share is not None else None,
        })
    return out


def _tracking_section(scope: str, pid: int | None, tid: int | None,
                      want_team: str, season: str) -> dict[str, Any]:
    try:
        if TRACKING_TABLE not in store.tables():
            raise KeyError(TRACKING_TABLE)
    except Exception:
        return {"available": False,
                "note": f"{TRACKING_TABLE} not seeded; run "
                        "backend/scripts/seed_tracking.py with "
                        "--season-types \"Regular Season,Playoffs\" to add "
                        "measured catch-and-shoot and pull-up splits."}
    rows: list[dict[str, Any]] = []
    for measure in ("CatchShoot", "PullUpShot"):
        for season_type, phase in (("", "regular_season"),
                                   (":playoffs", "playoffs")):
            entity = f"ptstats:{scope}:{measure}{season_type}"
            frame = store.read_frame_optional(
                TRACKING_TABLE, "_season = ? AND _entity = ?",
                [season, entity])
            if frame is None or frame.height == 0:
                continue
            for raw in frame.to_dicts():
                if scope == "player":
                    try:
                        if int(raw.get("PLAYER_ID") or -1) != pid:
                            continue
                    except (TypeError, ValueError):
                        continue
                else:
                    same_id = raw.get("TEAM_ID") == tid
                    same_abbr = (
                        str(raw.get("TEAM_ABBREVIATION") or "").strip().upper()
                        == want_team.upper())
                    if not (same_id or same_abbr):
                        continue
                slim = {k: raw.get(k) for k in raw if k is not None}
                slim["measure_type"] = measure
                slim["phase"] = phase
                rows.append(slim)
    if not rows:
        return {"available": False,
                "note": "no playoff tracking rows seeded for this subject "
                        "and season; see seed_tracking.py --season-types"}
    fetched = store._read_df(
        f"SELECT MAX(_fetched_at) AS m FROM {TRACKING_TABLE} "
        f"WHERE _season = ?", [season])
    return {"available": True, "rows": rows,
            "source": f"warehouse {TRACKING_TABLE} (nba_api LeagueDashPtStats)",
            "fetched_at": str(fetched[0]["m"]) if fetched else "unknown"}


@tool(description=(
    "Regular season vs playoffs shooting splits for one player or team in one "
    "season: zone diet and eFG plus shot-family splits (catch-and-shoot vs "
    "pull-up vs rim) with playoff-minus-regular deltas in percentage points. "
    "Warehouse-first from silver_hist_shots; measured tracking splits appear "
    "when seeded. Zones here are geometric court regions, not basketball-reference "
    "distance buckets: when the ask names silver_zone_splits or distance buckets "
    "(0-3ft, 3-10ft, 10-16ft, 16ft-3pt, 3pt), query silver_zone_splits via sql_exec "
    "instead. Give exactly one of player or team. Entity-scoped — for a "
    "league-wide split leaderboard or qualifying pool, run one sql_exec GROUP BY "
    "over silver_hist_shots (zone geometry is documented on get_zone_deltas) "
    "joined to silver_boxscores for position pools; never loop this tool per player."))
def get_phase_shot_splits(player: str = "", team: str = "",
                          season: str | None = None) -> dict[str, Any]:
    season = resolve_season(season)
    try:
        season = clamp_season(season)
    except InvalidSeasonError as exc:
        return {"tool": "get_phase_shot_splits", "ok": False, "rows": [],
                "error": str(exc)}
    want_player = str(player or "").strip()
    want_team = str(team or "").strip()
    if bool(want_player) == bool(want_team):
        return {"tool": "get_phase_shot_splits", "ok": False, "rows": [],
                "error": "Give exactly one of player or team, not both and "
                         "not neither.",
                "meta": {"source": f"warehouse {TABLE}", "season": season}}
    scope = "player" if want_player else "team"
    try:
        pid = coerce_player_id(want_player) if want_player else None
        tid = coerce_team_id(want_team) if want_team else None
    except ValueError as exc:
        return {"tool": "get_phase_shot_splits", "ok": False, "rows": [],
                "error": str(exc),
                "meta": {"source": f"warehouse {TABLE}", "season": season}}
    year = int(season[:4]) + 1
    if scope == "player":
        subject_sql, params = "person_id = ?", [pid]
    else:
        subject_sql, params = "team_id = ?", [tid]
    zone_rows = _pair(_agg("zone", year, subject_sql, params), "zone",
                      ZONE_KEYS)
    family_rows = _pair(_agg("family", year, subject_sql, params), "family",
                        _FAMILY_ORDER)
    if not zone_rows and not family_rows:
        return {"tool": "get_phase_shot_splits", "ok": False, "rows": [],
                "error": f"no shot rows for {want_player or want_team} "
                         f"in {season}",
                "meta": {"source": f"warehouse {TABLE}", "season": season}}
    po_fga = sum(r["po_fga"] for r in zone_rows)
    rows = zone_rows + family_rows
    meta = {
        "source": f"warehouse {TABLE}",
        "season": season,
        "scope": scope,
        "subject": want_player or want_team,
        "fetched_at": "",
        "playoff_games_sample": po_fga,
        "zone_legend": ZONE_LEGEND,
        "family_legend": FAMILY_LEGEND,
    }
    src = store._read_df(
        f"SELECT DISTINCT _source AS s, MAX(_fetched_at) AS m FROM {TABLE} "
        f"WHERE season = ? GROUP BY _source", [year])
    meta["sources"] = [{"table": TABLE, "provider": r["s"],
                        "fetched_at": str(r["m"]),
                        "covers": "regular season + playoffs"} for r in src]
    meta["tracking"] = _tracking_section(scope, pid, tid, want_team, season)
    meta["data_note"] = (
        "Zones are derived geometrically from shot x/y coordinates "
        "(not source labels). Shot families are heuristic groupings of PBP "
        "sub_type; measured catch-and-shoot and pull-up splits come from "
        "the tracking section when seeded. Phase is read from game_id "
        "prefix (002 = regular season, 004 = playoffs).")
    if not po_fga:
        meta["warning"] = ("subject has no playoff shots on file for this "
                           "season; playoff columns are empty")
    return {"tool": "get_phase_shot_splits", "ok": True, "rows": rows,
            "meta": meta}
