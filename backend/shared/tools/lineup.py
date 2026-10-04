
from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from .team import _hist_lineup_rows, _lineup_key
from ..sources import nba_stats
from ._core import MAX_ROWS, TTL_PBPSTATS, _warehouse_or_live, coerce_team_id, last_completed_season, resolve_season

BLOWOUT_MARGIN = 20
BLOWOUT_SHARE_FLAG = 0.5




_ALL_ROWS = 100_000


def _ratings(pf: float, off_poss: int, pa: float,
            def_poss: int) -> dict[str, float]:
    if off_poss <= 0 or def_poss <= 0:
        return {"OFF_RATING": 0.0, "DEF_RATING": 0.0, "NET_RATING": 0.0}
    off = round(pf / off_poss * 100, 1)
    deff = round(pa / def_poss * 100, 1)
    return {"OFF_RATING": off, "DEF_RATING": deff,
            "NET_RATING": round(off - deff, 1)}


def _flags(poss: int, blowout_share: float, min_possessions: int,
           estimated: bool) -> list[str]:
    flags: list[str] = []
    if poss < min_possessions:
        flags.append(
            f"tiny-sample: {poss} possessions under the "
            f"{min_possessions}-possession floor, not signal")
    if blowout_share >= BLOWOUT_SHARE_FLAG:
        flags.append(
            f"blowout-heavy: {round(blowout_share * 100)}% of possessions "
            f"played with a {BLOWOUT_MARGIN}+ point margin")
    if estimated:
        flags.append("estimated-possessions: no play-level data, "
                     "ratings from MIN*2 possessions")
    return flags


def _canon_row_key(r: dict[str, Any]) -> tuple[float, str]:
    try:
        minutes = float(r.get("MIN") or 0)
    except (TypeError, ValueError):
        minutes = 0.0
    return (minutes, str(r.get("_fetched_at") or ""))


def _dedupe_lineup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canon: dict[str, dict[str, Any]] = {}
    for r in rows or []:
        gid = str(r.get("GROUP_ID") or r.get("GROUP_NAME") or "")
        prev = canon.get(gid)
        if prev is None or _canon_row_key(r) > _canon_row_key(prev):
            canon[gid] = r
    return list(canon.values())


def _apply_sample_floor(
    units: list[dict[str, Any]], min_possessions: int, include_small: bool,
) -> tuple[list[dict[str, Any]], int, str]:
    visible: list[dict[str, Any]] = []
    hidden = 0
    for u in units:
        if u.get("poss", 0) >= min_possessions:
            visible.append(u)
        else:
            hidden += 1
            if include_small:
                u = {**u, "signal": "not-trustworthy",
                     "flags": [*u.get("flags", []),
                               "tiny-sample: shown by explicit override, "
                               "do not present as signal"]}
                visible.append(u)
    warning = ""
    if hidden:
        warning = (f"{hidden} unit(s) under the {min_possessions}-possession "
                   "floor hidden")
        if not include_small:
            warning += " — pass include_small=True to view them with warnings"
    return visible, hidden, warning


def _best_net_unit(units: list[dict[str, Any]],
                   min_possessions: int) -> dict[str, Any] | None:
    eligible = [u for u in units if u.get("poss", 0) >= min_possessions]
    if not eligible:
        return None
    return max(eligible,
               key=lambda u: (u.get("NET_RATING", 0.0),
                              u.get("poss", 0)))


_POSSESSION_AGGS_SQL = (
    "SELECT p1, p2, p3, p4, p5,"
    " COUNT(*) FILTER (offense_team_id = ?) AS off_poss,"
    " COUNT(*) FILTER (offense_team_id <> ?) AS def_poss,"
    " COALESCE(SUM(points) FILTER (offense_team_id = ?), 0) AS pf,"
    " COALESCE(SUM(points) FILTER (offense_team_id <> ?), 0) AS pa,"
    " COUNT(*) FILTER (ABS(margin) >= ?) AS blowout"
    " FROM ("
    " SELECT offense_team_id, COALESCE(points, 0) AS points,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_1 ELSE def_player_1 END AS p1,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_2 ELSE def_player_2 END AS p2,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_3 ELSE def_player_3 END AS p3,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_4 ELSE def_player_4 END AS p4,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_5 ELSE def_player_5 END AS p5,"
    " COALESCE(SUM(CASE WHEN offense_team_id = ?"
    " THEN COALESCE(points, 0) ELSE 0 END) OVER w"
    " - SUM(CASE WHEN offense_team_id <> ?"
    " THEN COALESCE(points, 0) ELSE 0 END) OVER w, 0) AS margin"
    " FROM silver_hist_possessions"
    " WHERE _season = ? AND (offense_team_id = ? OR defense_team_id = ?)"
    " AND count_as_possession = 'true'"
    " AND ((offense_team_id = ?"
    " AND off_player_1 IS NOT NULL AND off_player_2 IS NOT NULL"
    " AND off_player_3 IS NOT NULL AND off_player_4 IS NOT NULL"
    " AND off_player_5 IS NOT NULL)"
    " OR (offense_team_id <> ? AND defense_team_id = ?"
    " AND def_player_1 IS NOT NULL AND def_player_2 IS NOT NULL"
    " AND def_player_3 IS NOT NULL AND def_player_4 IS NOT NULL"
    " AND def_player_5 IS NOT NULL))"
    " WINDOW w AS (PARTITION BY game_id ORDER BY possession_number"
    " ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)"
    " ) GROUP BY p1, p2, p3, p4, p5"
)


def _possession_aggs(team_id: int, season: str) -> dict[tuple[int, ...], dict] | None:
    season = resolve_season(season)
    key = _aggs_cache_key(team_id, season)
    hit = _AGGS_CACHE.get(key)
    if hit is not None:
        return {u: dict(v) for u, v in hit.items()} or None
    try:
        rows = _store._read_df(
            _POSSESSION_AGGS_SQL,
            [team_id, team_id, team_id, team_id, BLOWOUT_MARGIN,
             team_id, team_id, team_id, team_id, team_id,
             team_id, team_id, season, team_id, team_id,
             team_id, team_id, team_id],
        )
    except Exception:
        return None
    if not rows:
        return None
    agg: dict[tuple[int, ...], dict] = {}
    for r in rows:
        try:
            unit = tuple(sorted(int(r[f"p{i}"]) for i in range(1, 6)))
            agg[unit] = {"off_poss": int(r["off_poss"] or 0),
                         "def_poss": int(r["def_poss"] or 0),
                         "pf": int(r["pf"] or 0),
                         "pa": int(r["pa"] or 0),
                         "blowout": int(r["blowout"] or 0)}
        except (TypeError, ValueError, KeyError):
            continue
    if len(_AGGS_CACHE) > 96:
        _AGGS_CACHE.clear()
    _AGGS_CACHE[key] = agg
    return {u: dict(v) for u, v in agg.items()} or None


def _aggs_cache_key(team_id: int, season: str) -> tuple:
    try:
        frozen = tuple(sorted(_store.warehouse_identity().items()))
    except Exception:
        frozen = ()
    return (team_id, season, frozen)


_AGGS_CACHE: dict[tuple, dict[tuple[int, ...], dict]] = {}


def _safe_aggs(team_id: int, season: str) -> dict[tuple[int, ...], dict] | None:
    try:
        return _possession_aggs(team_id, season)
    except Exception:
        return None


def _fetch_lineup_inputs(
    team_id: int, season: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict | None]:
    rows, meta = _warehouse_or_live(
        "silver_lineups",
        "_season = ? AND TEAM_ID = ? AND (_entity LIKE 'lineups:%' OR _entity = ?)",
        [season, team_id, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_PBPSTATS, limit=_ALL_ROWS,
    )
    return rows, meta, _safe_aggs(team_id, season)


@tool
def get_lineup_stats(
    team: str | int, season: str | None = None, min_possessions: int = 100,
    include_small: bool = False, limit: int = 10,
) -> dict[str, Any]:
    """Five-man lineup ratings with sample floors. Names, abbrevs, or ids.

    Units under min_possessions (default 100) are hidden; blowout-heavy
    units are flagged. Ratings are per 100 possessions, warehouse-first.
    The best lineup (highest NET_RATING among units meeting the floor) is
    returned in the top-level best_net_unit field and flagged per-row as
    is_best_net_unit, so it is never the most-used unit by default.
    """
    season = resolve_season(season)
    try:
        team_id = coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_lineup_stats", "ok": False,
                "error": str(exc)[:160]}
    rows, meta, agg = _fetch_lineup_inputs(team_id, season)
    hist = False
    if not rows:
        rows = _hist_lineup_rows(team_id, season)
        hist = bool(rows)
        if hist:
            meta = {**meta, "source": "warehouse",
                    "coverage": "historical_lineups"}
    if not rows:
        return {"tool": "get_lineup_stats", "ok": True, "rows": [],
                "meta": {**meta, "data_note": (
                    f"no lineup data for team {team_id} in season {season} "
                    "in the warehouse or upstream; nothing estimated, "
                    "nothing fabricated")}}
    rows_in = len(rows)
    rows = _dedupe_lineup_rows(rows)
    meta = {**meta, "rows_before_dedupe": rows_in,
            "rows_after_dedupe": len(rows)}
    estimated = agg is None
    units: list[dict[str, Any]] = []
    for r in rows:
        key = _lineup_key(r)
        name = r.get("GROUP_NAME") or "unknown"
        a = agg.get(key) if (agg is not None and key is not None) else None
        if a is not None:
            off_poss, def_poss = a["off_poss"], a["def_poss"]
            pf, pa = float(a["pf"]), float(a["pa"])
            poss = off_poss + def_poss
            blowout_share = round(a["blowout"] / poss, 3) if poss else 0.0
            if hist:
                est_min = round(float(r.get("MIN") or 0), 1)
            else:
                est_min = round(poss / 2, 1)
        else:
            poss = int(round(float(r.get("MIN") or 0) * 2))
            off_poss = def_poss = poss // 2
            pf = float(r.get("PTS") or 0)
            pa = pf - float(r.get("PLUS_MINUS") or 0)
            blowout_share = 0.0
            est_min = round(float(r.get("MIN") or 0), 1)
        flags = _flags(poss, blowout_share, min_possessions, estimated)
        units.append({
            "GROUP_NAME": name, "EST_MIN": est_min, "GP": r.get("GP"),
            "poss": poss, "off_poss": off_poss, "def_poss": def_poss,
            **_ratings(pf, off_poss, pa, def_poss),
            "PLUS_MINUS": r.get("PLUS_MINUS"),
            "blowout_share": blowout_share, "flags": flags})
    units.sort(key=lambda u: u["poss"], reverse=True)
    visible, hidden, warning = _apply_sample_floor(units, min_possessions,
                                                  include_small)
    best = _best_net_unit(visible, min_possessions)
    for u in visible:
        u["is_best_net_unit"] = u is best


    visible = visible[: min(limit, MAX_ROWS)]
    if hist:
        minute_note = ("minutes are clock minutes from the warehouse "
                       "lineup table")
    elif estimated:
        minute_note = ("play-level data missing; ratings estimated from "
                       "lineup minutes")
    else:
        minute_note = ("silver_lineups MIN is from a partial upstream "
                       "fetch, so minutes are estimated as poss/2")
    if not estimated:
        data_note = ("play-level possession data (verified against gamelog "
                     "totals) drives ratings and possession counts; "
                     + minute_note)
    else:
        data_note = minute_note
    meta_out = {**meta,
                "sample_floor": f"{min_possessions} possessions",
                "blowout_rule": (f"flagged at {round(BLOWOUT_SHARE_FLAG * 100)}% "
                                 f"of possessions with a {BLOWOUT_MARGIN}+ "
                                 "point margin"),
                "scope": ("ratings per 100 offensive/defensive possessions; "
                          "full-game totals include garbage time unless "
                          "filtered by the blowout flag"),
                "data_note": data_note + (f"; {warning}" if warning else "")}
    return {"tool": "get_lineup_stats", "ok": True, "rows": visible,
            "best_net_unit": best, "meta": meta_out}
