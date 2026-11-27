import math
import sys
from typing import Any

from langchain_core.tools import tool
from ...lineup_variants import SeasonType, MeasureType, PerMode, validate_variants


def _pkg():
    return sys.modules[__package__]


def _competitive_lineup_nets(
    team_id: int, season: str,
) -> dict[tuple[int, ...], tuple[float, int]] | None:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ... import store as _store

    con = _store.connect(read_only=True)
    try:
        pros = con.execute(
            "SELECT offense_team_id, defense_team_id, points,"
            " off_player_1, off_player_2, off_player_3,"
            " off_player_4, off_player_5,"
            " def_player_1, def_player_2, def_player_3,"
            " def_player_4, def_player_5"
            " FROM silver_hist_possessions"
            " WHERE _season = ?"
            " AND (offense_team_id = ? OR defense_team_id = ?)"
            " AND garbage = 0"
            " AND count_as_possession = 'true'",
            [season, team_id, team_id],
        ).fetchall()
    finally:
        try:
            con.close()
        except Exception:
            pass
    if not pros:
        return None
    agg: dict[tuple[int, ...], list[float]] = {}
    for row in pros:
        unit, pf, pa = _poss_unit(row, team_id)
        if unit is None:
            continue
        a = agg.setdefault(unit, [0.0, 0.0, 0])
        a[0] += pf
        a[1] += pa
        a[2] += 1
    out: dict[tuple[int, ...], tuple[float, int]] = {}
    for unit, (pf, pa, poss) in agg.items():
        net = round((pf - pa) / poss * 100, 1) if poss else 0.0
        out[unit] = (net, int(poss))
    return out


def _poss_unit(row: tuple, team_id: int) -> tuple[tuple[int, ...] | None, float, float]:
    try:
        off_tid, def_tid = row[0], row[1]
        pts = row[2] or 0
    except (IndexError, TypeError):
        return None, 0, 0
    if off_tid == team_id:
        raw = sorted(row[3:8])
        pf, pa = pts, 0
    elif def_tid == team_id:
        raw = sorted(row[8:13])
        pf, pa = 0, pts
    else:
        return None, 0, 0
    if any(v is None for v in raw):
        return None, 0, 0
    try:
        return tuple(int(v) for v in raw), pf, pa
    except (TypeError, ValueError):
        return None, 0, 0


def _lineup_key(row: dict[str, Any]) -> tuple[int, ...] | None:
    gid = row.get("GROUP_ID")
    if gid:
        try:
            parts = [int(p) for p in str(gid).split("-") if p.strip().isdigit()]
            if len(parts) == 5:
                return tuple(sorted(parts))
        except (TypeError, ValueError):
            pass
    return None


_HIST_LINEUP_PAIRS = (
    ("group_id", "GROUP_ID"), ("group_name", "GROUP_NAME"),
    ("team_id", "TEAM_ID"), ("team_abbreviation", "TEAM_ABBREVIATION"),
    ("gp", "GP"), ("min", "MIN"), ("pts", "PTS"),
    ("plus_minus", "PLUS_MINUS"), ("fga", "FGA"), ("oreb", "OREB"),
    ("tov", "TOV"), ("fta", "FTA"),
    ("off_rating", "OFF_RATING"), ("def_rating", "DEF_RATING"),
    ("net_rating", "NET_RATING"), ("pace", "PACE"),
)


_HIST_LINEUP_ROWS_CACHE: dict[tuple, list[dict[str, Any]]] = {}


def _hist_lineup_rows(team_id: int, season: str, season_type: SeasonType = 'regular-season', measure_type: MeasureType = 'base', per_mode: PerMode = 'totals') -> list[dict[str, Any]]:
    validate_variants(season_type, measure_type, per_mode)
    from ... import store as _identity_store
    try:
        frozen = tuple(sorted(_identity_store.warehouse_identity().items()))
    except Exception:
        frozen = ()
    cache_key = (team_id, season, season_type, measure_type, per_mode, frozen)
    cached = _HIST_LINEUP_ROWS_CACHE.get(cache_key)
    if cached is not None:
        return [dict(r) for r in cached]
    try:
        from ... import store as _store
        base_columns = ', '.join(f'base.{lower} AS base_{lower}' for lower, _ in _HIST_LINEUP_PAIRS[:-4])
        found = _store._read_df(
            "SELECT b.*, a.off_rating, a.def_rating, a.net_rating, a.pace, " + base_columns +
            " FROM (SELECT * EXCLUDE (off_rating, def_rating, net_rating, pace)"
            " FROM silver_hist_lineups WHERE _season = ? AND team_id = ?"
            " AND season_type = ? AND measure_type = ? AND per_mode = ?) b"
            " LEFT JOIN silver_hist_lineups a ON a.group_id = b.group_id"
            " AND a.team_id = b.team_id AND a._season = b._season"
            " AND a.season_type = b.season_type AND a.per_mode = b.per_mode"
            " AND a.measure_type = 'advanced'"
            " LEFT JOIN silver_hist_lineups base ON base.group_id = b.group_id"
            " AND base.team_id = b.team_id AND base._season = b._season"
            " AND base.season_type = b.season_type AND base.per_mode = b.per_mode"
            " AND base.measure_type = 'base'",
            [season, team_id, season_type, measure_type, per_mode],
        )
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for r in found or []:
        try:
            r = {key: value for key, value in r.items()
                 if value is not None and not (isinstance(value, float) and math.isnan(value))}
            row = {upper: r.get(lower) if r.get(lower) is not None else r.get(f'base_{lower}')
                   for lower, upper in _HIST_LINEUP_PAIRS}
            if measure_type != 'base':
                row.update({key.upper(): value for key, value in r.items()
                            if value is not None and not key.startswith(('_', 'base_'))})
            out.append(row)
        except Exception:
            continue
    if len(_HIST_LINEUP_ROWS_CACHE) > 96:
        _HIST_LINEUP_ROWS_CACHE.clear()
    _HIST_LINEUP_ROWS_CACHE[cache_key] = out
    return [dict(r) for r in out]


def _by_last_name_index():
    try:
        from nba_api.stats.static import players as _static_players

        _all = _static_players.get_players()
        _by_last = {}
        for p in _all:
            last = str(p.get("last_name", "")).lower()
            if last:
                _by_last.setdefault(last, p["id"])
        return _by_last
    except Exception:
        return {}


def _lineup_key_fuzzy(r, _by_last):
    try:
        parts = [t.strip().lower().split()[-1]
                 for t in str(r.get("GROUP_NAME", "")).split("-")]
        ids = [_by_last[t] for t in parts if t in _by_last]
        if len(ids) == 5:
            return tuple(sorted(ids))
    except (TypeError, ValueError, IndexError):
        pass
    return None


def _apply_competitive_nets(rows, comp):
    if comp is None:
        for r in rows:
            r["competitive_net"] = None
            r["competitive_poss"] = None
            r["competitive_note"] = "possessions missing for team/season"
        return
    _by_last = _by_last_name_index()
    for r in rows:
        key = _lineup_key(r)
        if key is None and _by_last:
            key = _lineup_key_fuzzy(r, _by_last)
        if key is not None and key in comp:
            net, poss = comp[key]
            r["competitive_net"] = net
            r["competitive_poss"] = poss
            if poss < 50:
                r["SAMPLE"] = "small: under 50 competitive possessions"
        else:
            r["competitive_net"] = None
            r["competitive_poss"] = 0
            r["SAMPLE"] = "small: under 50 competitive possessions"


@tool(description='Five-man lineup stats for one team: all qualifying units sorted by minutes. For per-unit ratings with sample floors use get_lineup_stats; for the league-wide board use get_lineup_leaders; for a player on-versus-off split (not units) use get_on_off.')
def get_lineups(team_id: str | int, season: str | None = None, season_type: SeasonType = 'regular-season', measure_type: MeasureType = 'base', per_mode: PerMode = 'totals') -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        season = pkg.clamp_season(season)
        team_id = pkg.coerce_team_id(team_id)
    except (pkg.InvalidSeasonError, ValueError) as exc:
        return {"tool": "get_lineups", "ok": False, "error": str(exc)[:240]}
    rows, meta = pkg._warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: pkg.nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=pkg.TTL_PBPSTATS,
    )
    if not rows or (season_type, measure_type, per_mode) != ('regular-season', 'base', 'totals'):
        rows = pkg._hist_lineup_rows(team_id, season, season_type, measure_type, per_mode)
        if rows:
            meta = {**meta, "source": "warehouse",
                    "coverage": "historical_lineups"}
    for r in rows:
        tier, est = pkg._sample_tier(r.get("MIN"))
        r["SAMPLE_TIER"] = tier
        r["EST_POSS"] = est
        if tier == "small":
            r["SAMPLE"] = "small: under ~100 possessions"
    rows = sorted(rows, key=lambda r: float(r.get("MIN") or 0), reverse=True)
    comp = None
    if season_type == 'regular-season':
        try:
            comp = pkg._competitive_lineup_nets(team_id, season)
        except Exception:
            pass
    pkg._apply_competitive_nets(rows, comp)
    if season_type != 'regular-season':
        for row in rows:
            row['competitive_note'] = 'competitive nets unavailable for playoffs: possessions are not season-type filtered'
    meta = {**meta,
            'season_type': season_type,
            'competitive_note': ('whole-season possession coverage' if season_type == 'regular-season'
                                 else 'competitive nets omitted: possessions are not season-type filtered'),
            "scope": f"Lineup nets are full-game totals for {season_type} {season} "
            "with no margin or clock filter, so garbage time is included."}
    return {"tool": "get_lineups", "ok": True, "rows": rows, "meta": meta}


def _slim_unit_row(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "GROUP_NAME": u.get("GROUP_NAME"),
        "EST_MIN": u.get("EST_MIN"),
        "GP": u.get("GP"),
        "poss": u.get("poss"),
        "OFF_RATING": u.get("OFF_RATING"),
        "DEF_RATING": u.get("DEF_RATING"),
        "NET_RATING": u.get("NET_RATING"),
        "PLUS_MINUS": u.get("PLUS_MINUS"),
        "is_best_net_unit": bool(u.get("is_best_net_unit")),
        "flags": list(u.get("flags") or []),
    }


CORE_GP_FLOOR = 20


def _tier_players(players: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    def _gp(p: dict[str, Any]) -> int:
        try:
            return int(p.get("GP") or 0)
        except (TypeError, ValueError):
            return 0

    def _mpg(p: dict[str, Any]) -> float:
        try:
            return float(p.get("MPG") or 0)
        except (TypeError, ValueError):
            return 0.0

    by_mpg = sorted(players, key=_mpg, reverse=True)
    core = [p for p in by_mpg if _gp(p) >= CORE_GP_FLOOR][:5]
    core_ids = {id(p) for p in core}
    rest = [p for p in by_mpg if id(p) not in core_ids]
    return {
        "core": core,
        "bench": rest[:5],
        "fringe": rest[5:10],
    }


def _thin_rotation_flags(
    *,
    players: list[dict[str, Any]],
    most_used_share: float,
    bench_diffs: list[float | None],
    cached_onoff: int,
) -> list[str]:
    if not players:
        return []
    flags: list[str] = []
    try:
        deep15 = sum(1 for p in players if float(p.get("MPG") or 0) >= 15)
    except (TypeError, ValueError):
        deep15 = 0
    try:
        deep10 = sum(1 for p in players if float(p.get("MPG") or 0) >= 10)
    except (TypeError, ValueError):
        deep10 = 0
    if deep15 < 8:
        flags.append(
            f"thin rotation: only {deep15} players at 15+ MPG"
            " (a healthy rotation runs 8-10 deep)"
        )
    if deep10 < 10:
        flags.append(f"short bench: only {deep10} players at 10+ MPG")
    try:
        share = float(most_used_share or 0)
    except (TypeError, ValueError):
        share = 0.0
    if share >= 0.35:
        flags.append(
            "heavy reliance: the most-used unit takes"
            f" {round(share * 100)}% of sampled lineup minutes"
        )
    diffs = [d for d in (bench_diffs or []) if isinstance(d, (int, float))]
    if len(diffs) >= 3:
        avg = sum(diffs) / len(diffs)
        if avg <= -3:
            flags.append(
                "bench drag: rotation players 6-10 average"
                f" {avg:+.1f} on/off"
            )
    try:
        cached = int(cached_onoff or 0)
    except (TypeError, ValueError):
        cached = 0
    if cached < 8:
        flags.append(
            f"on/off coverage thin: only {cached} of the top 10"
            " have cached on/off"
        )
    return flags


def _closing_candidates(
    units: list[dict[str, Any]], top_units: int, min_possessions: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    distinct: list[dict[str, Any]] = []
    for u in units or []:
        key = str(u.get("GROUP_NAME") or "")
        if key in seen:
            continue
        seen.add(key)
        distinct.append(u)
    eligible = [u for u in distinct if (u.get("poss") or 0) >= min_possessions]
    ordered = sorted(eligible, key=lambda u: float(u.get("NET_RATING") or 0), reverse=True)
    return [_slim_unit_row(u) for u in ordered[:top_units]]


def _avg_diff(rows: list[dict[str, Any]]) -> float | None:
    diffs = [r.get("DIFF") for r in rows
             if r.get("CACHED") and isinstance(r.get("DIFF"), (int, float))]
    if not diffs:
        return None
    return round(sum(diffs) / len(diffs), 1)


def _rotation_minute_share(tiers: dict[str, list[dict[str, Any]]]) -> float:
    top15 = (tiers["core"] + tiers["bench"] + tiers["fringe"])[:15]
    try:
        total_min = sum(float(p.get("MIN") or 0) for p in top15)
        core_min = sum(float(p.get("MIN") or 0) for p in tiers["core"])
        return round(core_min / total_min, 3) if total_min > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _most_used_unit_share(units: list[dict[str, Any]]) -> float:
    try:
        total_est = sum(float(u.get("EST_MIN") or 0) for u in units)
        top_est = float(units[0].get("EST_MIN") or 0) if units else 0.0
        return (top_est / total_est) if total_est > 0 else 0.0
    except (TypeError, ValueError, IndexError):
        return 0.0


def _rotation_closers(
    players: list[dict[str, Any]], clutch_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    ids = {p.get("PLAYER_ID") for p in players if p.get("PLAYER_ID") is not None}
    closers: list[dict[str, Any]] = []
    for r in clutch_rows:
        if ids and r.get("PLAYER_ID") not in ids:
            continue
        closers.append({
            "PLAYER": r.get("PLAYER_NAME") or r.get("PLAYER"),
            "PLAYER_ID": r.get("PLAYER_ID"),
            "GP": r.get("GP"),
            "W": r.get("W"),
            "L": r.get("L"),
            "MIN": r.get("MIN"),
        })
        if len(closers) >= 8:
            break
    clutch_note = (
        "warehouse silver_clutch is player-scope only"
        " (last 5 min, margin <=5); team-level clutch splits live"
        " in get_clutch, not duplicated here"
    )
    if not closers:
        clutch_note += "; no cached clutch minutes for this team's players"
    return closers, clutch_note


def _assemble_rotation_report(
    *,
    team_id: int,
    abbrev: str,
    season: str,
    min_possessions: int,
    top_units: int,
    players: list[dict[str, Any]],
    units: list[dict[str, Any]],
    clutch_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    players = players or []
    units = units or []
    clutch_rows = clutch_rows or []
    tiers = pkg._tier_players(players)
    bench_rows = tiers["bench"]
    top10 = (tiers["core"] + bench_rows)[:10]
    slimmed = [_slim_unit_row(u) for u in units]
    thin = (pkg._thin_rotation_flags(
        players=players,
        most_used_share=_most_used_unit_share(units),
        bench_diffs=[p.get("DIFF") for p in bench_rows],
        cached_onoff=sum(1 for p in top10 if p.get("CACHED")),
    ) if (players or units) else [])
    try:
        total_poss = sum(int(u.get("poss") or 0) for u in units)
    except (TypeError, ValueError):
        total_poss = 0
    closers, clutch_note = _rotation_closers(players, clutch_rows)
    return {
        "tool": "get_rotation_check",
        "ok": True,
        "rows": {
            "team": {"id": team_id, "abbrev": abbrev},
            "coverage": {
                "season": season,
                "units": len(units),
                "total_unit_poss": total_poss,
                "minutes_basis": (
                    "lineup EST_MIN = poss/2; lineup MIN is full-season"
                    " 2025-26 (silver_lineups, sportsdataverse seeds);"
                    " player MIN is season-to-date"
                    " from silver_hist_player_seasons"
                ),
            },
            "tiers": tiers,
            "starter_bench_split": {
                "starter_min_share": _rotation_minute_share(tiers),
                "starter_avg_diff": _avg_diff(tiers["core"]),
                "bench_avg_diff": _avg_diff(bench_rows),
                "bench_cached": sum(1 for p in bench_rows if p.get("CACHED")),
            },
            "most_used_unit": slimmed[0] if slimmed else None,
            "closing_candidates": pkg._closing_candidates(units, top_units, min_possessions),
            "thin_flags": thin,
            "clutch_context": {"note": clutch_note, "closers": closers},
        },
        "meta": {
            "source": "warehouse",
            "season": season,
            "team_id": team_id,
            "sample_floor": f"{min_possessions} possessions",
            "data_note": (
                "warehouse-only; lineup EST_MIN = poss/2; silver_lineups"
                " MIN is full-season 2025-26 (sportsdataverse seeds); units under the"
                f" {min_possessions}-possession floor are hidden by"
                " get_lineup_stats, never presented as signal; player MIN is"
                " season-to-date from silver_hist_player_seasons and on/off"
                " from silver_on_off; every number is labeled with its source"
                " table and coverage in coverage/meta"
            ),
        },
    }


def _fetch_rotation_players(season: str, abbrev: str) -> list[dict[str, Any]]:
    season = _pkg().resolve_season(season)
    from ... import store as _store

    return _store._read_df(
        "SELECT player_id, player_name, gp, min, pts"
        " FROM silver_hist_player_seasons"
        " WHERE _season = ? AND team_abbreviation = ?",
        [season, abbrev],
    )


def _fetch_rotation_onoff(
    season: str, pid: object,
) -> tuple[float | None, float | None, float | None, bool]:
    season = _pkg().resolve_season(season)
    from ... import store as _store

    try:
        cached = _store._read_df(
            'SELECT Stat, "On", "Off", "On-Off" FROM silver_on_off'
            " WHERE _season = ? AND _entity = ?",
            [season, f"player:{pid}"],
        )
    except Exception:
        return None, None, None, False
    if not cached:
        return None, None, None, False
    for r in cached:
        if r.get("Stat") == "Pts per 100 Possessions":
            try:
                return float(r.get("On")), float(r.get("Off")), float(r.get("On-Off")), True
            except (TypeError, ValueError):
                return None, None, None, True
    return None, None, None, True


def _fetch_rotation_clutch(season: str, team_id: int) -> list[dict[str, Any]]:
    season = _pkg().resolve_season(season)
    from ... import store as _store

    try:
        return _store._read_df(
            "SELECT PLAYER_NAME, PLAYER_ID, GP, W, L, MIN FROM silver_clutch"
            " WHERE _season = ? AND TEAM_ID = ? ORDER BY MIN DESC",
            [season, team_id],
        )
    except Exception:
        return []


async def _fetch_rotation_units(
    team: str | int, season: str, min_possessions: int,
) -> list[dict[str, Any]]:
    season = _pkg().resolve_season(season)
    from ..lineup import get_lineup_stats

    res = await get_lineup_stats.ainvoke({
        "team": team,
        "season": season,
        "min_possessions": min_possessions,
        "include_small": False,
        "limit": 25,
    })
    if not isinstance(res, dict) or not res.get("ok"):
        return []
    return res.get("rows") or []


@tool(description='Rotation and closing-unit check from warehouse five-man units, minutes, and cached on/off.')
async def get_rotation_check(
    team: str | int = "", season: str | None = None, min_possessions: int = 100,
    top_units: int = 5,
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        tid = pkg.coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_rotation_check", "ok": False,
                "error": str(exc)[:160]}
    abbr = pkg._abbrev(team)
    try:
        raw_players = pkg._fetch_rotation_players(season, abbr)
    except Exception:
        raw_players = []
    enriched: list[dict[str, Any]] = []
    for r in raw_players:
        try:
            pid = r.get("player_id", r.get("PLAYER_ID"))
            name = r.get("player_name", r.get("PLAYER") or r.get("player"))
            gp = r.get("gp", r.get("GP") or 0)
            minutes = r.get("min", r.get("MIN") or 0)
            pts = r.get("pts", r.get("PTS") or 0)
            try:
                gp_f = int(gp or 0)
            except (TypeError, ValueError):
                gp_f = 0
            try:
                mpg = float(minutes or 0)
            except (TypeError, ValueError):
                mpg = 0.0
            try:
                ppg = float(pts or 0)
            except (TypeError, ValueError):
                ppg = 0.0

            min_f = round(mpg * gp_f, 1) if gp_f > 0 else 0.0
            pts_f = round(ppg * gp_f, 1) if gp_f > 0 else 0.0
            on, off, diff, cached = pkg._fetch_rotation_onoff(season, pid)
            enriched.append({
                "PLAYER": name, "PLAYER_ID": pid, "GP": gp_f, "MIN": min_f,
                "MPG": round(mpg, 1), "PPG": round(ppg, 1), "PTS": pts_f,
                "ON": on, "OFF": off,
                "DIFF": diff, "CACHED": cached,
            })
        except Exception:
            continue

    enriched = sorted(enriched, key=lambda p: float(p.get("MPG") or 0),
                      reverse=True)[:15]
    try:
        units = await pkg._fetch_rotation_units(team, season, min_possessions)
    except Exception:
        units = []
    clutch_rows = pkg._fetch_rotation_clutch(season, tid)
    return pkg._assemble_rotation_report(
        team_id=tid, abbrev=abbr, season=season,
        min_possessions=min_possessions, top_units=top_units,
        players=enriched, units=units, clutch_rows=clutch_rows,
    )
