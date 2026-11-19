import sys
from typing import Any

from langchain_core.tools import tool

from .filters import (
    _AGG_SELECT,
    _ambiguous_response,
    _heave_sql,
    _qrows,
    _three_sql,
    _zone_case_sql,
)
from .zones import (
    SMALL_SAMPLE_MIN,
    TABLE,
    ZONE_KEYS,
    ZONE_LEGEND,
    efficiency,
    fold_ot,
    format_clock,
    group_row,
    parse_group_by,
    parse_include_ot,
    parse_late_clock,
    parse_made,
    parse_periods,
    parse_zones,
)


def _pkg():
    return sys.modules[__package__]


@tool(
    description='Conversational shot finder: filter warehouse shots by player, team,\nzone, period, makes, and late-clock window, with zone/period aggregates\nplus optional per-player/per-team leaderboards.\n\nzones: rim, short_mid, long_mid, corner_3, atb_3 (comma-separated;\n"" = all). periods: 1-4, ot, 1h, 2h, 4th (comma-separated; "" = all).\nlate_clock: integer seconds remaining (periods 4+, time-based only, not\nscore-aware). group_by: "" | "player" | "team" -- per-player/per-team\nvolume + efficiency leaderboards sorted by attempts (this is how you\nanswer "who takes over fourth quarters"). include_ot: auto (default --\novertime is included when a 4th-quarter/2nd-half window is selected,\nwhen overtime is explicitly selected (periods=\'ot\'), or when late_clock\nis given without an explicit period filter), yes, no.\nperiods=\'4th\' includes overtime by default; pass include_ot=no to get\nexactly the 4th quarter. Zero matches return ok True with empty\naggregates and an explanatory note, never silent zeros. Results are\ntime-based only, never score-aware (meta.clutch_safe=false); TS% is not\nshown because the table has no free-throw attempts.'
)
def search_shots(
    player: str = "",
    team: str = "",
    zones: str = "",
    periods: str = "",
    three_only: bool = False,
    made: str = "any",
    late_clock: str = "",
    exclude_heaves: bool = True,
    limit: int = 25,
    season: str | None = None,
    group_by: str = "",
    include_ot: str = "auto",
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.clamp_season(pkg.resolve_season(season))
    _shot_seasons = pkg._shots_seasons()
    if season not in _shot_seasons:
        if _shot_seasons:
            _shot_err = f"warehouse silver_shots covers {', '.join(_shot_seasons)} (233,632 shots); requested {season!r}"
        else:
            _shot_err = f"warehouse silver_shots has no season on hand; requested {season!r}"
        return {"tool": "search_shots", "ok": False, "error": _shot_err}
    try:
        wanted_zones = parse_zones(zones)
        allowed_periods = parse_periods(periods)
        made_filter = parse_made(made)
        late_seconds = parse_late_clock(late_clock)
        group = parse_group_by(group_by)
    except ValueError as exc:
        return {"tool": "search_shots", "ok": False, "error": str(exc)}
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = pkg.MAX_ROWS
    lim = max(1, min(pkg.MAX_ROWS, lim))

    ot_default = (allowed_periods is not None and (4 in allowed_periods or 5 in allowed_periods)) or (
        allowed_periods is None and late_seconds is not None
    )
    try:
        ot = parse_include_ot(include_ot, ot_default)
    except ValueError as exc:
        return {"tool": "search_shots", "ok": False, "error": str(exc)}
    folded = fold_ot(allowed_periods, ot)
    team_id: int | None = None
    if (team or "").strip():
        try:
            team_id = pkg.coerce_team_id(team)
        except ValueError:
            return {"tool": "search_shots", "ok": False, "error": f"unknown team: {team!r}"}
    try:
        con = pkg._warehouse_conn()
    except Exception as exc:
        return {"tool": "search_shots", "ok": False, "error": f"warehouse read failed: {exc}"}
    try:
        player_id, status, payload = pkg._resolve_player(con, season, player)
        if status == "unknown":
            return {"tool": "search_shots", "ok": False, "error": payload}
        if status == "ambiguous":
            return _ambiguous_response(
                con, season, player, payload, team_id, wanted_zones,
                folded, three_only, made_filter, late_seconds, exclude_heaves, group, ot,
            )
        return _run_search(
            con, season, player, team, player_id, team_id, wanted_zones, folded,
            three_only, made_filter, late_seconds, exclude_heaves, lim, group, ot, periods, late_clock,
        )
    finally:
        con.close()


def _run_search(
    con: Any, season: str, player: str, team: str, player_id: int | None, team_id: int | None,
    wanted_zones: set[str], folded: set[int] | None, three_only: bool, made_filter: str,
    late_seconds: int | None, exclude_heaves: bool, lim: int, group: str, ot: bool,
    periods_raw: str, late_raw: str,
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    _shot_seasons = pkg._shots_seasons()
    zone_expr = _zone_case_sql()
    heave = _heave_sql()
    where, params = pkg._where_sql(
        season, player_id, team_id, wanted_zones, folded, late_seconds, three_only, made_filter, ot,
    )
    heave_filter = "" if not exclude_heaves else f" AND NOT {heave}"
    scanned = con.execute("SELECT COUNT(*) FROM silver_shots WHERE _season = ?", [season]).fetchone()[0]
    aggregate, heaves_excluded = _shot_totals(con, where, params, zone_expr, heave, heave_filter, exclude_heaves)
    by_zone = _shots_by_zone(con, where, params, zone_expr, heave_filter)
    by_period = _shots_by_period(con, where, params, zone_expr, heave_filter)
    grouped = _shots_grouped(con, where, params, zone_expr, heave_filter, group)
    shots = _shot_rows(con, where, params, zone_expr, heave_filter, lim)
    filters = {
        "player": player, "player_id": player_id, "team": team, "team_id": team_id,
        "zones": sorted(wanted_zones),
        "periods": [p if p != 5 else "OT" for p in sorted(folded)] if folded is not None else "all",
        "three_only": bool(three_only), "made": made_filter, "late_clock_seconds": late_seconds,
        "exclude_heaves": bool(exclude_heaves), "limit": lim, "season": season,
        "group_by": group, "include_ot": ot,
    }
    meta = _shot_meta(
        season, _shot_seasons, scanned, aggregate, heaves_excluded,
        aggregate["games"], len(shots), ot, folded, exclude_heaves,
    )
    if aggregate["small_sample"]:
        meta["sample_warning"] = (
            f"only {aggregate['attempts']} attempts -- percentages are noisy; "
            f"treat fg/efg as illustrative, not quotable"
        )
    if aggregate["attempts"] == 0:
        meta["note"] = _empty_note(folded, late_seconds, periods_raw)
    out: dict[str, Any] = {
        "tool": "search_shots", "ok": True, "filters": filters, "aggregate": aggregate,
        "by_zone": by_zone, "by_period": by_period, "shots": shots, "meta": meta,
    }
    if group == "player":
        out["by_player"] = grouped
    elif group == "team":
        out["by_team"] = grouped
    return out


def _shot_totals(con, where, params, zone_expr, heave, heave_filter, exclude_heaves):
    agg = _qrows(
        con,
        f"""SELECT {_AGG_SELECT.format(three=_three_sql(zone_expr))}
            FROM silver_shots WHERE {where}{heave_filter}""",
        params,
    )[0]
    attempts = int(agg["attempts"] or 0)
    makes = int(agg["makes"] or 0)
    threes = int(agg["threes_made"] or 0)
    games = int(agg["games"] or 0)
    heaves_excluded = 0
    if exclude_heaves:
        heaves_excluded = int(
            _qrows(con, f"SELECT COUNT(*) AS n FROM silver_shots WHERE {where} AND {heave}", params)[0]["n"] or 0
        )
    aggregate = {
        "attempts": attempts, "makes": makes, "threes_made": threes, "games": games,
        **efficiency(attempts, makes, threes), "small_sample": attempts < SMALL_SAMPLE_MIN,
    }
    return aggregate, heaves_excluded


def _shots_by_zone(con, where, params, zone_expr, heave_filter):
    by_zone = []
    for r in _qrows(
        con,
        f"""SELECT {zone_expr} AS zone, {_AGG_SELECT.format(three=_three_sql(zone_expr))}
            FROM silver_shots WHERE {where}{heave_filter} GROUP BY 1""",
        params,
    ):
        z_attempts = int(r["attempts"] or 0)
        z_makes = int(r["makes"] or 0)
        z_threes = int(r["threes_made"] or 0)
        by_zone.append({
            "zone": r["zone"], "attempts": z_attempts, "makes": z_makes,
            **efficiency(z_attempts, z_makes, z_threes), "small_sample": z_attempts < SMALL_SAMPLE_MIN,
        })
    by_zone.sort(key=lambda r: ZONE_KEYS.index(r["zone"]) if r["zone"] in ZONE_KEYS else 99)
    return by_zone


def _shots_by_period(con, where, params, zone_expr, heave_filter):
    by_period = []
    for r in _qrows(
        con,
        f"""SELECT CASE WHEN PERIOD >= 5 THEN 'OT' ELSE CAST(PERIOD AS VARCHAR) END AS period,
                {_AGG_SELECT.format(three=_three_sql(zone_expr))}
            FROM silver_shots WHERE {where}{heave_filter} GROUP BY 1""",
        params,
    ):
        p_attempts = int(r["attempts"] or 0)
        p_makes = int(r["makes"] or 0)
        p_threes = int(r["threes_made"] or 0)
        label: Any = "OT" if r["period"] == "OT" else int(r["period"])
        by_period.append({
            "period": label, "attempts": p_attempts, "makes": p_makes,
            **efficiency(p_attempts, p_makes, p_threes), "small_sample": p_attempts < SMALL_SAMPLE_MIN,
        })
    by_period.sort(key=lambda r: 99 if r["period"] == "OT" else r["period"])
    return by_period


def _shots_grouped(con, where, params, zone_expr, heave_filter, group):
    pkg = _pkg()
    grouped: list[dict[str, Any]] = []
    if group == "player":
        sql = f"""SELECT PLAYER_ID, {_AGG_SELECT.format(three=_three_sql(zone_expr))}
                    FROM silver_shots WHERE {where}{heave_filter}
                    GROUP BY PLAYER_ID ORDER BY attempts DESC"""
        for r in _qrows(con, sql, params):
            pid = r["PLAYER_ID"]
            row = group_row(
                int(r["attempts"] or 0), int(r["makes"] or 0),
                int(r["threes_made"] or 0), int(r["games"] or 0),
            )
            row["player_id"] = int(pid)
            row["player"] = pkg._player_full_name(pid) or f"id:{pid}"
            grouped.append(row)
    elif group == "team":
        sql = f"""SELECT TEAM_ID, {_AGG_SELECT.format(three=_three_sql(zone_expr))}
                    FROM silver_shots WHERE {where}{heave_filter}
                    GROUP BY TEAM_ID ORDER BY attempts DESC"""
        for r in _qrows(con, sql, params):
            tid = r["TEAM_ID"]
            row = group_row(
                int(r["attempts"] or 0), int(r["makes"] or 0),
                int(r["threes_made"] or 0), int(r["games"] or 0),
            )
            row["team_id"] = int(tid)
            row["team"] = pkg._team_abbr(tid)
            grouped.append(row)
    return grouped


def _shot_rows(con, where, params, zone_expr, heave_filter, lim):
    pkg = _pkg()
    shots = []
    for r in _qrows(
        con,
        f"""SELECT PLAYER_NAME AS player, PLAYER_ID, TEAM_ID, PERIOD AS period,
                MINUTES_REMAINING, SECONDS_REMAINING, {zone_expr} AS zone,
                SHOT_ZONE_BASIC AS zone_label, ACTION_TYPE AS action,
                SHOT_DISTANCE AS distance_ft, SHOT_MADE_FLAG, GAME_ID
            FROM silver_shots WHERE {where}{heave_filter}
            ORDER BY hash(GAME_ID, GAME_EVENT_ID, PLAYER_ID, PERIOD, MINUTES_REMAINING, SECONDS_REMAINING)
            LIMIT {lim}""",
        params,
    ):
        try:
            distance = float(r["distance_ft"])
        except (TypeError, ValueError):
            distance = None
        try:
            period = int(r["period"])
        except (TypeError, ValueError):
            period = None
        shots.append({
            "player_id": int(r["PLAYER_ID"]),
            "player": pkg._player_full_name(r["PLAYER_ID"]) or r["player"],
            "team_id": int(r["TEAM_ID"]),
            "team": pkg._team_abbr(r["TEAM_ID"]),
            "period": period,
            "clock": format_clock(r["MINUTES_REMAINING"], r["SECONDS_REMAINING"]),
            "zone": r["zone"],
            "zone_label": r["zone_label"],
            "action": r["action"],
            "distance_ft": distance,
            "made": str(r["SHOT_MADE_FLAG"] or "").strip() == "1",
            "game_id": r["GAME_ID"],
        })
    return shots


def _ot_msg(ot, folded) -> str:
    if ot and folded is not None and 4 in folded and 5 in folded:
        return "'4th' selects the 4th quarter plus overtime"
    if folded is not None and 5 not in folded:
        return "overtime excluded by include_ot=no"
    return "all periods selected (overtime included)"


def _shot_meta(
    season, shot_seasons, scanned, aggregate, heaves_excluded,
    games, rows_returned, ot, folded, exclude_heaves,
):
    if exclude_heaves:
        heave_msg = (
            f"Heave scrub is an estimate (30+ ft with 3 or fewer seconds "
            f"left in the period); {heaves_excluded} shots excluded here."
        )
    else:
        heave_msg = (
            "Heave scrub is DISABLED; heaves are INCLUDED in these "
            "aggregates (30+ ft with 3 or fewer seconds left in the period)."
        )
    ot_msg = _ot_msg(ot, folded)
    return {
        "source": f"warehouse {TABLE}", "season": season, "shots_scanned": int(scanned),
        "shots_matched": aggregate["attempts"], "heaves_excluded": heaves_excluded,
        "games": games, "rows_returned": rows_returned, "zones": ZONE_LEGEND,
        "clutch_safe": False, "score_aware": False,
        "data_note": (
            f"Warehouse silver_shots coverage is {', '.join(shot_seasons) or 'no season on hand'} "
            f"(233,632 shots, regular season and playoffs). PLAYER_NAME is last-name-only "
            f"(e.g. 'Gilgeous-Alexander'). TEAM_NAME/HTM/VTM columns are not populated in this table, "
            f"so team abbreviations come from the nba_api static id->abbreviation mapping. GAME_DATE is not "
            f"populated in this table. Periods: {ot_msg}; use periods='ot' for overtime only, "
            f"include_ot=no for exactly the 4th quarter. There is no score-margin column, so late-game "
            f"filtering is time-based only (period >= 4 plus the late_clock seconds-remaining cap) and is NOT "
            f"score-aware: never present these results as close-game or clutch splits (meta.clutch_safe=false). "
            f"{heave_msg} TS% is not shown because the table has no free-throw attempts; 'points' are "
            f"field-goal points only (2*FGM + 3PTM). Individual rows are a deterministic pseudo-random mix "
            f"across the season, not the latest games; the aggregates are the answer."
        ),
    }


def _empty_note(folded, late_seconds, periods_raw) -> str:
    if late_seconds is not None and folded is not None and not any(p >= 4 for p in folded):
        return (
            f"late_clock={late_seconds}s only applies to periods 4+ "
            f"(incl. overtime), but periods={periods_raw!r} excludes "
            f"them, so zero shots can match by construction. Drop "
            f"late_clock or widen periods (e.g. '2h', '4th', 'ot')."
        )
    return (
        "No shots matched the combined filters. PLAYER_NAME is "
        "last-name-only (e.g. 'Tatum'), teams resolve from "
        "abbreviations or full names, and late_clock only applies "
        "to periods 4+ (incl. overtime)."
    )
