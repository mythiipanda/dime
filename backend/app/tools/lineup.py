"""Lineup ratings with sample floors. ROADMAP Phase 1 item 2 (Trust).

get_lineup_stats returns the most-used five-man units for a team with
offensive/defensive/net ratings per 100 possessions. Units under
min_possessions (default 100) are hidden, not presented as signal, and
units spending most of their time in blowouts are flagged. Warehouse-first.
"""

from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from .team import _lineup_key
from ..sources import nba_stats
from ._core import SEASON, TTL_PBPSTATS, _warehouse_or_live, coerce_team_id

BLOWOUT_MARGIN = 20
BLOWOUT_SHARE_FLAG = 0.5


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


def _apply_sample_floor(
    units: list[dict[str, Any]], min_possessions: int, include_small: bool,
) -> tuple[list[dict[str, Any]], int, str]:
    """Split units into visible vs hidden under the possession floor.

    Pure function; kept testable so the floor can never silently regress.
    """
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
    """Best five-man unit among sample-floor-passing units.

    Pure function; kept testable so "best lineup" can never silently drift
    back to "most-used lineup". Selection rule: highest NET_RATING among
    units with poss >= min_possessions (tiny-sample/override units never
    win); ties broken by higher possessions (larger sample = more reliable),
    then by order (units are poss-sorted, so a full tie keeps the first).
    """
    eligible = [u for u in units if u.get("poss", 0) >= min_possessions]
    if not eligible:
        return None
    return max(eligible,
               key=lambda u: (u.get("NET_RATING", 0.0),
                              u.get("poss", 0)))


def _possession_aggs(team_id: int, season: str) -> dict[tuple[int, ...], dict] | None:
    """Per-lineup possession counts, points for/against, and blowout share.

    Margin is reconstructed from running score per game, so blowout-heavy
    units are detected even though the warehouse has no garbage-time flag.
    """
    try:
        rows = _store._read_df(
            "SELECT game_id, possession_number, offense_team_id,"
            " defense_team_id, points,"
            " off_player_1, off_player_2, off_player_3, off_player_4, off_player_5,"
            " def_player_1, def_player_2, def_player_3, def_player_4, def_player_5"
            " FROM silver_hist_possessions"
            " WHERE _season = ? AND (offense_team_id = ? OR defense_team_id = ?)"
            " AND count_as_possession = 'true'",
            [season, team_id, team_id],
        )
    except Exception:
        return None
    if not rows:
        return None
    rows.sort(key=lambda r: (str(r.get("game_id")),
                             int(r.get("possession_number") or 0)))
    agg: dict[tuple[int, ...], dict] = {}
    runs: dict[str, dict[int, int]] = {}
    for r in rows:
        try:
            off_tid, def_tid = int(r["offense_team_id"]), int(r["defense_team_id"])
            pts = int(r["points"] or 0)
        except (TypeError, ValueError, KeyError):
            continue
        game = str(r.get("game_id"))
        run = runs.setdefault(game, {})
        off_run, def_run = run.get(off_tid, 0), run.get(def_tid, 0)
        if off_tid == team_id:
            margin = off_run - def_run
            players = [r.get(f"off_player_{i}") for i in range(1, 6)]
        elif def_tid == team_id:
            margin = def_run - off_run
            players = [r.get(f"def_player_{i}") for i in range(1, 6)]
        else:
            continue
        if any(p is None for p in players):
            continue
        try:
            unit = tuple(sorted(int(p) for p in players))
        except (TypeError, ValueError):
            continue
        a = agg.setdefault(unit, {"off_poss": 0, "def_poss": 0, "pf": 0,
                                  "pa": 0, "blowout": 0})
        if off_tid == team_id:
            a["off_poss"] += 1
            a["pf"] += pts
        else:
            a["def_poss"] += 1
            a["pa"] += pts
        if abs(margin) >= BLOWOUT_MARGIN:
            a["blowout"] += 1
        run[off_tid] = off_run + pts
        run[def_tid] = def_run
    return agg or None


@tool
def get_lineup_stats(
    team: str | int, season: str = SEASON, min_possessions: int = 100,
    include_small: bool = False, limit: int = 10,
) -> dict[str, Any]:
    """Five-man lineup ratings with sample floors. Names, abbrevs, or ids.

    Units under min_possessions (default 100) are hidden; blowout-heavy
    units are flagged. Ratings are per 100 possessions, warehouse-first.
    The best lineup (highest NET_RATING among units meeting the floor) is
    returned in the top-level best_net_unit field and flagged per-row as
    is_best_net_unit, so it is never the most-used unit by default.
    """
    try:
        team_id = coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_lineup_stats", "ok": False,
                "error": str(exc)[:160]}
    rows, meta = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_PBPSTATS,
    )
    if not rows:
        return {"tool": "get_lineup_stats", "ok": True, "rows": [],
                "meta": {**meta, "data_note": (
                    f"no lineup data for team {team_id} in season {season} "
                    "in the warehouse or upstream; nothing estimated, "
                    "nothing fabricated")}}
    agg = None
    try:
        agg = _possession_aggs(team_id, season)
    except Exception:
        agg = None
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
    visible = visible[:limit]
    meta_out = {**meta,
                "sample_floor": f"{min_possessions} possessions",
                "blowout_rule": (f"flagged at {round(BLOWOUT_SHARE_FLAG * 100)}% "
                                 f"of possessions with a {BLOWOUT_MARGIN}+ "
                                 "point margin"),
                "scope": ("ratings per 100 offensive/defensive possessions; "
                          "full-game totals include garbage time unless "
                          "filtered by the blowout flag"),
                "data_note": (
                    "play-level possession data (verified against gamelog "
                    "totals) drives ratings and possession counts; "
                    "silver_lineups MIN is from a partial upstream fetch, "
                    "so minutes are estimated as poss/2" if not estimated else
                    "play-level data missing; ratings estimated from "
                    "lineup minutes") + (f"; {warning}" if warning else "")}
    return {"tool": "get_lineup_stats", "ok": True, "rows": visible,
            "best_net_unit": best, "meta": meta_out}
