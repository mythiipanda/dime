import sys
from typing import Any

from .zones import (
    SMALL_SAMPLE_MIN,
    TABLE,
    ZONE_LABEL_MAP,
    efficiency,
)


def _pkg():
    return sys.modules[__package__]


def _warehouse_conn() -> Any:
    return _pkg()._store.connect(read_only=True)


def _zone_case_sql() -> str:
    whens = " ".join(
        f"WHEN '{label}' THEN '{zone}'"
        for label, zone in ZONE_LABEL_MAP.items()
    )
    return f"CASE SHOT_ZONE_BASIC {whens} END"


def _three_sql(zone_expr: str) -> str:
    return (
        f"({zone_expr} IN ('corner_3', 'atb_3') "
        f"OR upper(SHOT_TYPE) LIKE '3PT%')"
    )


def _heave_sql() -> str:
    return (
        "(COALESCE(SHOT_DISTANCE, 0) >= 30 AND "
        "COALESCE(MINUTES_REMAINING * 60 + SECONDS_REMAINING, 999999) <= 3)"
    )


def _where_sql(
    season: str,
    player_id: int | None,
    team_id: int | None,
    wanted_zones: set[str],
    allowed_periods: set[int] | None,
    late_seconds: int | None,
    three_only: bool,
    made_filter: str,
    include_ot: bool = True,
) -> tuple[str, list[object]]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    zone_expr = _zone_case_sql()
    clauses = ["_season = ?"]
    params: list[object] = [season]
    if player_id is not None:
        clauses.append("PLAYER_ID = ?")
        params.append(player_id)
    if team_id is not None:
        clauses.append("TEAM_ID = ?")
        params.append(team_id)
    placeholders = ", ".join("?" for _ in wanted_zones)
    clauses.append(f"{zone_expr} IN ({placeholders})")
    params.extend(sorted(wanted_zones))
    if allowed_periods is not None:
        explicit = sorted(p for p in allowed_periods if p < 5)
        parts = []
        if explicit:
            parts.append(f"PERIOD IN ({', '.join('?' for _ in explicit)})")
            params.extend(explicit)
        if 5 in allowed_periods:
            parts.append("PERIOD >= 5")
        clauses.append("(" + " OR ".join(parts) + ")")
    if late_seconds is not None:
        clauses.append(
            "PERIOD >= 4"
            if (include_ot or allowed_periods is not None)
            else "PERIOD = 4"
        )
        clauses.append(
            "COALESCE(MINUTES_REMAINING * 60 + SECONDS_REMAINING, 999999) <= ?"
        )
        params.append(late_seconds)
        clauses.append("(MINUTES_REMAINING * 60 + SECONDS_REMAINING) >= 0")
    if three_only:
        clauses.append(_three_sql(zone_expr))
    if made_filter == "made":
        clauses.append("SHOT_MADE_FLAG = '1'")
    elif made_filter == "missed":
        clauses.append("COALESCE(SHOT_MADE_FLAG, '') <> '1'")
    return " AND ".join(clauses), params


def _qrows(
    con: Any, sql: str, params: list[object]
) -> list[dict[str, Any]]:
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


_AGG_SELECT = """COUNT(*) AS attempts,
    SUM(CASE WHEN SHOT_MADE_FLAG = '1' THEN 1 ELSE 0 END) AS makes,
    SUM(CASE WHEN SHOT_MADE_FLAG = '1' AND {three} THEN 1 ELSE 0 END)
        AS threes_made,
    COUNT(DISTINCT GAME_ID) AS games"""


def _resolve_player(
    con: Any, season: str, raw: str
) -> tuple[int | None, str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    text = (raw or "").strip()
    if not text:
        return None, "none", None
    try:
        return int(text), "ok", None
    except (TypeError, ValueError):
        pass
    pairs = [
        (r["PLAYER_NAME"], r["PLAYER_ID"])
        for r in _qrows(
            con,
            "SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM silver_shots "
            "WHERE _season = ? AND lower(PLAYER_NAME) = lower(?)",
            [season, text],
        )
    ]
    if len(pairs) == 1:
        try:
            return int(pairs[0][1]), "ok", None
        except (TypeError, ValueError):
            pass
    if len(pairs) > 1:
        outcome = pkg.disambiguate_last_name(text, pairs)
        return None, "ambiguous", outcome["candidates"]
    last_token = text.split()[-1]
    token_pairs = [
        (r["PLAYER_NAME"], r["PLAYER_ID"])
        for r in _qrows(
            con,
            "SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM silver_shots "
            "WHERE _season = ? AND lower(PLAYER_NAME) = lower(?)",
            [season, last_token],
        )
    ]
    if len(token_pairs) == 1 and last_token.lower() != text.lower():
        try:
            return int(token_pairs[0][1]), "ok", None
        except (TypeError, ValueError):
            pass
    try:
        return pkg.coerce_player_id(text), "ok", None
    except ValueError:
        pass
    if len(token_pairs) > 1:
        outcome = pkg.disambiguate_last_name(last_token, token_pairs)
        return None, "ambiguous", outcome["candidates"]
    rows = _qrows(
        con,
        "SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM silver_shots "
        "WHERE _season = ?",
        [season],
    )
    outcome = pkg.disambiguate_last_name(
        text, [(r["PLAYER_NAME"], r["PLAYER_ID"]) for r in rows]
    )
    if outcome["ambiguous"]:
        return None, "ambiguous", outcome["candidates"]
    if outcome["player_id"] is None:
        return None, "unknown", f"unknown player: {text!r}"
    return outcome["player_id"], "ok", None


def _disambiguation_payload(
    con: Any,
    season: str,
    text: str,
    candidates: list[dict[str, Any]],
    where_np: str,
    params_np: list[object],
    heave_filter: str,
) -> list[dict[str, Any]]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    ids = [c["player_id"] for c in candidates]
    in_list = ", ".join("?" for _ in ids)
    zone_expr = _zone_case_sql()
    agg_rows = {
        r["PLAYER_ID"]: r
        for r in _qrows(
            con,
            f"""SELECT PLAYER_ID, {_AGG_SELECT.format(three=_three_sql(zone_expr))}
                FROM silver_shots
                WHERE {where_np} AND PLAYER_ID IN ({in_list}){heave_filter}
                GROUP BY PLAYER_ID""",
            params_np + ids,
        )
    }
    team_rows = _qrows(
        con,
        f"""SELECT DISTINCT PLAYER_ID, TEAM_ID FROM silver_shots
            WHERE _season = ? AND PLAYER_ID IN ({in_list})""",
        [season] + ids,
    )
    teams_by_id: dict[Any, set[str]] = {}
    for r in team_rows:
        abbr = pkg._team_abbr(r["TEAM_ID"])
        if abbr:
            teams_by_id.setdefault(r["PLAYER_ID"], set()).add(abbr)
    out = []
    for cand in candidates:
        pid = cand["player_id"]
        agg = agg_rows.get(pid, {})
        attempts = int(agg.get("attempts") or 0)
        makes = int(agg.get("makes") or 0)
        threes = int(agg.get("threes_made") or 0)
        full = pkg._player_full_name(pid) or cand["player"]
        out.append(
            {
                "player_id": pid,
                "player": full,
                "last_name": cand["player"],
                "teams": sorted(teams_by_id.get(pid, set())),
                "attempts": attempts,
                "makes": makes,
                "threes_made": threes,
                **efficiency(attempts, makes, threes),
                "small_sample": attempts < SMALL_SAMPLE_MIN,
            }
        )
    out.sort(key=lambda r: r["attempts"], reverse=True)
    return out


def _ambiguous_response(
    con: Any,
    season: str,
    text: str,
    candidates: list[dict[str, Any]],
    team_id: int | None,
    wanted_zones: set[str],
    folded: set[int] | None,
    three_only: bool,
    made_filter: str,
    late_seconds: int | None,
    exclude_heaves: bool,
    group: str,
    include_ot: bool = True,
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    heave_filter = "" if not exclude_heaves else f" AND NOT {_heave_sql()}"
    where_np, params_np = pkg._where_sql(
        season,
        None,
        team_id,
        wanted_zones,
        folded,
        late_seconds,
        three_only,
        made_filter,
        include_ot,
    )
    enriched = _disambiguation_payload(
        con, season, text, candidates, where_np, params_np, heave_filter
    )
    filters = {
        "player": text,
        "player_id": None,
        "team_id": team_id,
        "zones": sorted(wanted_zones),
        "periods": (
            [p if p != 5 else "OT" for p in sorted(folded)]
            if folded is not None
            else "all"
        ),
        "three_only": bool(three_only),
        "made": made_filter,
        "late_clock_seconds": late_seconds,
        "exclude_heaves": bool(exclude_heaves),
        "group_by": group,
        "season": season,
    }
    meta = {
        "source": f"warehouse {TABLE}",
        "season": season,
        "clutch_safe": False,
        "score_aware": False,
        "data_note": (
            "Late-game filtering is time-based only (period >= 4 plus the "
            "late_clock seconds-remaining cap); there is no score-margin "
            "column, so results are NOT score-aware: never present them as "
            "close-game or clutch splits."
        ),
    }
    return {
        "tool": "search_shots",
        "ok": True,
        "disambiguation": {
            "query": text,
            "candidates": enriched,
            "note": (
                f"last name {text!r} matches {len(enriched)} players "
                f"(sorted by attempts under your filters); rerun with a "
                f"full name or numeric player_id"
            ),
        },
        "filters": filters,
        "meta": meta,
    }
