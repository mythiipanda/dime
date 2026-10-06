
from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from ._core import (MAX_ROWS, clamp_season, coerce_player_id, coerce_team_id, resolve_season)

TABLE = "silver_shots"

def _shots_seasons() -> list[str]:
    try:
        con = _store.connect(read_only=True)
        try:
            rows = con.execute(
                "SELECT DISTINCT _season FROM silver_shots").fetchall()
        finally:
            try:
                con.close()
            except Exception:
                pass
    except Exception:
        return []
    return sorted(r[0] for r in rows if r and r[0])

ZONE_KEYS = ("rim", "short_mid", "long_mid", "corner_3", "atb_3")
THREE_ZONES = frozenset({"corner_3", "atb_3"})

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

_PERIOD_TOKEN_MAP = {
    "1": {1}, "2": {2}, "3": {3}, "4": {4},
    "4th": {4}, "ot": {5}, "1h": {1, 2}, "2h": {3, 4},
}

_MADE_VALUES = ("made", "missed", "any")
_GROUP_BY_VALUES = ("", "player", "team")

SMALL_SAMPLE_MIN = 10

_TEAM_ABBR_BY_ID: dict[int, str] = {}
_PLAYER_NAME_BY_ID: dict[int, str] = {}
_STATIC_LOADED = {"teams": False, "players": False}

def _team_abbr(team_id: object) -> str | None:
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        return None
    if tid in _TEAM_ABBR_BY_ID:
        return _TEAM_ABBR_BY_ID[tid]
    if _STATIC_LOADED["teams"]:
        return None
    try:
        from nba_api.stats.static import teams as _static_teams

        for t in _static_teams.get_teams():
            try:
                _TEAM_ABBR_BY_ID[int(t["id"])] = str(t["abbreviation"])
            except (TypeError, ValueError, KeyError):
                continue
    except Exception:
        return None
    finally:
        _STATIC_LOADED["teams"] = True
    return _TEAM_ABBR_BY_ID.get(tid)

def _player_full_name(player_id: object) -> str | None:
    try:
        pid = int(player_id)
    except (TypeError, ValueError):
        return None
    if pid in _PLAYER_NAME_BY_ID:
        return _PLAYER_NAME_BY_ID[pid]
    if _STATIC_LOADED["players"]:
        return None
    try:
        from nba_api.stats.static import players as _static_players

        for p in _static_players.get_players():
            try:
                _PLAYER_NAME_BY_ID[int(p["id"])] = str(p["full_name"])
            except (TypeError, ValueError, KeyError):
                continue
    except Exception:
        return None
    finally:
        _STATIC_LOADED["players"] = True
    return _PLAYER_NAME_BY_ID.get(pid)

def zone_of_label(label: object) -> str | None:
    if label is None:
        return None
    return ZONE_LABEL_MAP.get(str(label).strip())

def parse_zones(raw: str) -> set[str]:
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
    if allowed is None:
        return True
    try:
        p = int(period)
    except (TypeError, ValueError):
        return False
    if p >= 5:
        return 5 in allowed
    return p in allowed

def parse_made(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value not in _MADE_VALUES:
        raise ValueError(
            f"invalid made filter {raw!r}; use one of: made, missed, any")
    return value

def parse_late_clock(raw: str) -> int | None:
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

def parse_group_by(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in _GROUP_BY_VALUES:
        return value
    raise ValueError(
        f"invalid group_by {raw!r}; use one of: player, team (or empty for none)")

def parse_include_ot(raw: str, default: bool) -> bool:
    token = (raw or "").strip().lower()
    if token in ("", "auto"):
        return default
    if token in ("yes", "true", "1", "y"):
        return True
    if token in ("no", "false", "0", "n"):
        return False
    raise ValueError(
        f"invalid include_ot {raw!r}; use auto, yes, or no")

def fold_ot(periods: set[int] | None, include_ot: bool) -> set[int] | None:
    if periods is None or not include_ot:
        return periods
    return set(periods) | {5}

def seconds_left(minutes_remaining: object,
                 seconds_remaining: object) -> int | None:
    try:
        total = int(minutes_remaining) * 60 + int(seconds_remaining)
    except (TypeError, ValueError):
        return None
    return total if total >= 0 else None

def is_heave(distance_ft: object, minutes_remaining: object,
             seconds_remaining: object) -> bool:
    try:
        far = float(distance_ft) >= 30.0
    except (TypeError, ValueError):
        return False
    left = seconds_left(minutes_remaining, seconds_remaining)
    return bool(far and left is not None and left <= 3)

def format_clock(minutes_remaining: object,
                 seconds_remaining: object) -> str:
    left = seconds_left(minutes_remaining, seconds_remaining)
    if left is None:
        return "unknown"
    return f"{left // 60}:{left % 60:02d}"

def efficiency(attempts: int, makes: int,
               threes_made: int) -> dict[str, float]:
    if attempts <= 0:
        return {"fg_pct": 0.0, "efg_pct": 0.0}
    return {
        "fg_pct": round(makes / attempts, 4),
        "efg_pct": round((makes + 0.5 * threes_made) / attempts, 4),
    }

def summarize(shots: list[dict[str, Any]]) -> dict[str, Any]:
    attempts = len(shots)
    makes = sum(1 for s in shots if s.get("made"))
    threes = sum(1 for s in shots
                 if s.get("made") and s.get("zone") in THREE_ZONES)
    games = len({s.get("game_id") for s in shots
                 if s.get("game_id") is not None})
    return {"attempts": attempts, "makes": makes, "threes_made": threes,
            "games": games, **efficiency(attempts, makes, threes)}

def summarize_by_zone(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    buckets: dict[Any, list[dict[str, Any]]] = {}
    for s in shots:
        try:
            p = int(s.get("period"))
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

def group_row(attempts: int, makes: int, threes_made: int,
              games: int = 0) -> dict[str, Any]:
    row: dict[str, Any] = {
        "attempts": attempts,
        "makes": makes,
        "threes_made": threes_made,
        "points": 2 * makes + threes_made,
        **efficiency(attempts, makes, threes_made),
        "small_sample": attempts < SMALL_SAMPLE_MIN,
    }
    if games:
        row["games"] = games
    return row

def disambiguate_last_name(raw: str,
                           pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
    key = (raw or "").strip().lower()
    hits: dict[int, str] = {}
    for name, pid in pairs:
        if str(name or "").strip().lower() != key:
            continue
        try:
            pid_int = int(pid)
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

def _warehouse_conn() -> Any:
    return _store.connect(read_only=True)

def _zone_case_sql() -> str:
    whens = " ".join(f"WHEN '{label}' THEN '{zone}'"
                     for label, zone in ZONE_LABEL_MAP.items())
    return f"CASE SHOT_ZONE_BASIC {whens} END"

def _three_sql(zone_expr: str) -> str:
    return (f"({zone_expr} IN ('corner_3', 'atb_3') "
            f"OR upper(SHOT_TYPE) LIKE '3PT%')")

def _heave_sql() -> str:
    return ("(COALESCE(SHOT_DISTANCE, 0) >= 30 AND "
            "COALESCE(MINUTES_REMAINING * 60 + SECONDS_REMAINING, 999999) <= 3)")

def _where_sql(season: str, player_id: int | None, team_id: int | None,
               wanted_zones: set[str], allowed_periods: set[int] | None,
               late_seconds: int | None, three_only: bool,
               made_filter: str, include_ot: bool = True
               ) -> tuple[str, list[object]]:
    season = resolve_season(season)
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
            parts.append(
                f"PERIOD IN ({', '.join('?' for _ in explicit)})")
            params.extend(explicit)
        if 5 in allowed_periods:
            parts.append("PERIOD >= 5")
        clauses.append("(" + " OR ".join(parts) + ")")
    if late_seconds is not None:

        clauses.append("PERIOD >= 4"
                       if (include_ot or allowed_periods is not None)
                       else "PERIOD = 4")
        clauses.append(
            "COALESCE(MINUTES_REMAINING * 60 + SECONDS_REMAINING, 999999) <= ?")
        params.append(late_seconds)
        clauses.append("(MINUTES_REMAINING * 60 + SECONDS_REMAINING) >= 0")
    if three_only:
        clauses.append(_three_sql(zone_expr))
    if made_filter == "made":
        clauses.append("SHOT_MADE_FLAG = '1'")
    elif made_filter == "missed":
        clauses.append("COALESCE(SHOT_MADE_FLAG, '') <> '1'")
    return " AND ".join(clauses), params

def _qrows(con: Any, sql: str,
           params: list[object]) -> list[dict[str, Any]]:
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

_AGG_SELECT = """COUNT(*) AS attempts,
    SUM(CASE WHEN SHOT_MADE_FLAG = '1' THEN 1 ELSE 0 END) AS makes,
    SUM(CASE WHEN SHOT_MADE_FLAG = '1' AND {three} THEN 1 ELSE 0 END)
        AS threes_made,
    COUNT(DISTINCT GAME_ID) AS games"""

def _resolve_player(con: Any, season: str,
                    raw: str) -> tuple[int | None, str, Any]:
    season = resolve_season(season)
    text = (raw or "").strip()
    if not text:
        return None, "none", None
    try:
        return int(text), "ok", None
    except (TypeError, ValueError):
        pass
    pairs = [(r["PLAYER_NAME"], r["PLAYER_ID"]) for r in _qrows(
        con,
        "SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM silver_shots "
        "WHERE _season = ? AND lower(PLAYER_NAME) = lower(?)",
        [season, text])]
    if len(pairs) == 1:
        try:
            return int(pairs[0][1]), "ok", None
        except (TypeError, ValueError):
            pass
    if len(pairs) > 1:
        outcome = disambiguate_last_name(text, pairs)
        return None, "ambiguous", outcome["candidates"]
    last_token = text.split()[-1]
    token_pairs = [(r["PLAYER_NAME"], r["PLAYER_ID"]) for r in _qrows(
        con,
        "SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM silver_shots "
        "WHERE _season = ? AND lower(PLAYER_NAME) = lower(?)",
        [season, last_token])]
    if len(token_pairs) == 1 and last_token.lower() != text.lower():

        try:
            return int(token_pairs[0][1]), "ok", None
        except (TypeError, ValueError):
            pass
    try:
        return coerce_player_id(text), "ok", None
    except ValueError:
        pass
    if len(token_pairs) > 1:
        outcome = disambiguate_last_name(last_token, token_pairs)
        return None, "ambiguous", outcome["candidates"]
    rows = _qrows(con,
                  "SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM silver_shots "
                  "WHERE _season = ?", [season])
    outcome = disambiguate_last_name(
        text, [(r["PLAYER_NAME"], r["PLAYER_ID"]) for r in rows])
    if outcome["ambiguous"]:
        return None, "ambiguous", outcome["candidates"]
    if outcome["player_id"] is None:
        return None, "unknown", f"unknown player: {text!r}"
    return outcome["player_id"], "ok", None

def _disambiguation_payload(con: Any, season: str, text: str,
                            candidates: list[dict[str, Any]],
                            where_np: str, params_np: list[object],
                            heave_filter: str) -> list[dict[str, Any]]:
    season = resolve_season(season)
    ids = [c["player_id"] for c in candidates]
    in_list = ", ".join("?" for _ in ids)
    zone_expr = _zone_case_sql()
    agg_rows = {r["PLAYER_ID"]: r for r in _qrows(
        con,
        f"""SELECT PLAYER_ID, {_AGG_SELECT.format(three=_three_sql(zone_expr))}
            FROM silver_shots
            WHERE {where_np} AND PLAYER_ID IN ({in_list}){heave_filter}
            GROUP BY PLAYER_ID""",
        params_np + ids)}
    team_rows = _qrows(
        con,
        f"""SELECT DISTINCT PLAYER_ID, TEAM_ID FROM silver_shots
            WHERE _season = ? AND PLAYER_ID IN ({in_list})""",
        [season] + ids)
    teams_by_id: dict[Any, set[str]] = {}
    for r in team_rows:
        abbr = _team_abbr(r["TEAM_ID"])
        if abbr:
            teams_by_id.setdefault(r["PLAYER_ID"], set()).add(abbr)
    out = []
    for cand in candidates:
        pid = cand["player_id"]
        agg = agg_rows.get(pid, {})
        attempts = int(agg.get("attempts") or 0)
        makes = int(agg.get("makes") or 0)
        threes = int(agg.get("threes_made") or 0)
        full = _player_full_name(pid) or cand["player"]
        out.append({
            "player_id": pid,
            "player": full,
            "last_name": cand["player"],
            "teams": sorted(teams_by_id.get(pid, set())),
            "attempts": attempts,
            "makes": makes,
            "threes_made": threes,
            **efficiency(attempts, makes, threes),
            "small_sample": attempts < SMALL_SAMPLE_MIN,
        })
    out.sort(key=lambda r: r["attempts"], reverse=True)
    return out

@tool(description='Conversational shot finder: filter warehouse shots by player, team,\nzone, period, makes, and late-clock window, with zone/period aggregates\nplus optional per-player/per-team leaderboards.\n\nzones: rim, short_mid, long_mid, corner_3, atb_3 (comma-separated;\n"" = all). periods: 1-4, ot, 1h, 2h, 4th (comma-separated; "" = all).\nlate_clock: integer seconds remaining (periods 4+, time-based only, not\nscore-aware). group_by: "" | "player" | "team" -- per-player/per-team\nvolume + efficiency leaderboards sorted by attempts (this is how you\nanswer "who takes over fourth quarters"). include_ot: auto (default --\novertime is included when a 4th-quarter/2nd-half window is selected,\nwhen overtime is explicitly selected (periods=\'ot\'), or when late_clock\nis given without an explicit period filter), yes, no.\nperiods=\'4th\' includes overtime by default; pass include_ot=no to get\nexactly the 4th quarter. Zero matches return ok True with empty\naggregates and an explanatory note, never silent zeros. Results are\ntime-based only, never score-aware (meta.clutch_safe=false); TS% is not\nshown because the table has no free-throw attempts.')
def search_shots(player: str = "", team: str = "", zones: str = "",
                 periods: str = "", three_only: bool = False,
                 made: str = "any", late_clock: str = "",
                 exclude_heaves: bool = True, limit: int = 25,
                 season: str | None = None, group_by: str = "",
                 include_ot: str = "auto") -> dict[str, Any]:
    season = resolve_season(season)
    season = clamp_season(season)
    _shot_seasons = _shots_seasons()
    if season not in _shot_seasons:
        if _shot_seasons:
            _shot_err = (f"warehouse silver_shots covers "
                         f"{', '.join(_shot_seasons)} (233,632 shots); "
                         f"requested {season!r}")
        else:
            _shot_err = ("warehouse silver_shots has no season on hand; "
                         f"requested {season!r}")
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
        lim = MAX_ROWS
    lim = max(1, min(MAX_ROWS, lim))

    ot_default = ((allowed_periods is not None
                   and (4 in allowed_periods or 5 in allowed_periods))
                  or (allowed_periods is None and late_seconds is not None))
    try:
        ot = parse_include_ot(include_ot, ot_default)
    except ValueError as exc:
        return {"tool": "search_shots", "ok": False, "error": str(exc)}
    folded = fold_ot(allowed_periods, ot)
    team_id: int | None = None
    if (team or "").strip():
        try:
            team_id = coerce_team_id(team)
        except ValueError:
            return {"tool": "search_shots", "ok": False,
                    "error": f"unknown team: {team!r}"}
    try:
        con = _warehouse_conn()
    except Exception as exc:
        return {"tool": "search_shots", "ok": False,
                "error": f"warehouse read failed: {exc}"}
    try:
        player_id, status, payload = _resolve_player(con, season, player)
        if status == "unknown":
            return {"tool": "search_shots", "ok": False, "error": payload}
        if status == "ambiguous":
            return _ambiguous_response(
                con, season, player, payload, team_id, wanted_zones, folded,
                three_only, made_filter, late_seconds, exclude_heaves, group, ot)
        return _run_search(
            con, season, player, team, player_id, team_id, wanted_zones,
            folded, three_only, made_filter, late_seconds, exclude_heaves,
            lim, group, ot, periods, late_clock)
    finally:
        con.close()

def _ambiguous_response(con: Any, season: str, text: str,
                        candidates: list[dict[str, Any]],
                        team_id: int | None, wanted_zones: set[str],
                        folded: set[int] | None, three_only: bool,
                        made_filter: str, late_seconds: int | None,
                        exclude_heaves: bool, group: str,
                        include_ot: bool = True) -> dict[str, Any]:
    season = resolve_season(season)
    heave_filter = "" if not exclude_heaves else f" AND NOT {_heave_sql()}"
    where_np, params_np = _where_sql(
        season, None, team_id, wanted_zones, folded, late_seconds,
        three_only, made_filter, include_ot)
    enriched = _disambiguation_payload(
        con, season, text, candidates, where_np, params_np, heave_filter)
    filters = {
        "player": text, "player_id": None,
        "team_id": team_id,
        "zones": sorted(wanted_zones),
        "periods": ([p if p != 5 else "OT" for p in sorted(folded)]
                    if folded is not None else "all"),
        "three_only": bool(three_only), "made": made_filter,
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
        "tool": "search_shots", "ok": True,
        "disambiguation": {
            "query": text,
            "candidates": enriched,
            "note": (f"last name {text!r} matches {len(enriched)} players "
                     f"(sorted by attempts under your filters); rerun with a "
                     f"full name or numeric player_id"),
        },
        "filters": filters,
        "meta": meta,
    }

def _run_search(con: Any, season: str, player: str, team: str,
                player_id: int | None, team_id: int | None,
                wanted_zones: set[str], folded: set[int] | None,
                three_only: bool, made_filter: str,
                late_seconds: int | None, exclude_heaves: bool, lim: int,
                group: str, ot: bool, periods_raw: str,
                late_raw: str) -> dict[str, Any]:
    season = resolve_season(season)
    _shot_seasons = _shots_seasons()
    zone_expr = _zone_case_sql()
    heave = _heave_sql()
    where, params = _where_sql(
        season, player_id, team_id, wanted_zones, folded, late_seconds,
        three_only, made_filter, ot)
    heave_filter = "" if not exclude_heaves else f" AND NOT {heave}"
    scanned = con.execute(
        "SELECT COUNT(*) FROM silver_shots WHERE _season = ?",
        [season]).fetchone()[0]

    agg = _qrows(
        con,
        f"""SELECT {_AGG_SELECT.format(three=_three_sql(zone_expr))}
            FROM silver_shots WHERE {where}{heave_filter}""",
        params)[0]
    attempts = int(agg["attempts"] or 0)
    makes = int(agg["makes"] or 0)
    threes = int(agg["threes_made"] or 0)
    games = int(agg["games"] or 0)
    heaves_excluded = 0
    if exclude_heaves:
        heaves_excluded = int(_qrows(
            con,
            f"SELECT COUNT(*) AS n FROM silver_shots "
            f"WHERE {where} AND {heave}", params)[0]["n"] or 0)

    aggregate = {"attempts": attempts, "makes": makes,
                 "threes_made": threes, "games": games,
                 **efficiency(attempts, makes, threes),
                 "small_sample": attempts < SMALL_SAMPLE_MIN}

    by_zone = []
    for r in _qrows(
            con,
            f"""SELECT {zone_expr} AS zone,
                    {_AGG_SELECT.format(three=_three_sql(zone_expr))}
                FROM silver_shots WHERE {where}{heave_filter}
                GROUP BY 1""", params):
        z_attempts = int(r["attempts"] or 0)
        z_makes = int(r["makes"] or 0)
        z_threes = int(r["threes_made"] or 0)
        by_zone.append({"zone": r["zone"], "attempts": z_attempts,
                        "makes": z_makes,
                        **efficiency(z_attempts, z_makes, z_threes),
                        "small_sample": z_attempts < SMALL_SAMPLE_MIN})
    by_zone.sort(key=lambda r: ZONE_KEYS.index(r["zone"])
                 if r["zone"] in ZONE_KEYS else 99)

    by_period = []
    for r in _qrows(
            con,
            f"""SELECT CASE WHEN PERIOD >= 5 THEN 'OT'
                        ELSE CAST(PERIOD AS VARCHAR) END AS period,
                    {_AGG_SELECT.format(three=_three_sql(zone_expr))}
                FROM silver_shots WHERE {where}{heave_filter}
                GROUP BY 1""", params):
        p_attempts = int(r["attempts"] or 0)
        p_makes = int(r["makes"] or 0)
        p_threes = int(r["threes_made"] or 0)
        label: Any = "OT" if r["period"] == "OT" else int(r["period"])
        by_period.append({"period": label, "attempts": p_attempts,
                          "makes": p_makes,
                          **efficiency(p_attempts, p_makes, p_threes),
                          "small_sample": p_attempts < SMALL_SAMPLE_MIN})
    by_period.sort(key=lambda r: 99 if r["period"] == "OT" else r["period"])

    grouped: list[dict[str, Any]] = []
    if group == "player":
        for r in _qrows(
                con,
                f"""SELECT PLAYER_ID,
                        {_AGG_SELECT.format(three=_three_sql(zone_expr))}
                    FROM silver_shots WHERE {where}{heave_filter}
                    GROUP BY PLAYER_ID ORDER BY attempts DESC""", params):
            pid = r["PLAYER_ID"]
            row = group_row(int(r["attempts"] or 0), int(r["makes"] or 0),
                            int(r["threes_made"] or 0),
                            int(r["games"] or 0))
            row["player_id"] = int(pid)
            row["player"] = _player_full_name(pid) or f"id:{pid}"
            grouped.append(row)
    elif group == "team":
        for r in _qrows(
                con,
                f"""SELECT TEAM_ID,
                        {_AGG_SELECT.format(three=_three_sql(zone_expr))}
                    FROM silver_shots WHERE {where}{heave_filter}
                    GROUP BY TEAM_ID ORDER BY attempts DESC""", params):
            tid = r["TEAM_ID"]
            row = group_row(int(r["attempts"] or 0), int(r["makes"] or 0),
                            int(r["threes_made"] or 0),
                            int(r["games"] or 0))
            row["team_id"] = int(tid)
            row["team"] = _team_abbr(tid)
            grouped.append(row)

    shots = []
    for r in _qrows(
            con,
            f"""SELECT PLAYER_NAME AS player, PLAYER_ID, TEAM_ID,
                    PERIOD AS period,
                    MINUTES_REMAINING, SECONDS_REMAINING,
                    {zone_expr} AS zone,
                    SHOT_ZONE_BASIC AS zone_label,
                    ACTION_TYPE AS action,
                    SHOT_DISTANCE AS distance_ft,
                    SHOT_MADE_FLAG, GAME_ID
                FROM silver_shots WHERE {where}{heave_filter}
                ORDER BY hash(GAME_ID, GAME_EVENT_ID, PLAYER_ID, PERIOD,
                              MINUTES_REMAINING, SECONDS_REMAINING)
                LIMIT {lim}""", params):
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
            "player": _player_full_name(r["PLAYER_ID"]) or r["player"],
            "team_id": int(r["TEAM_ID"]),
            "team": _team_abbr(r["TEAM_ID"]),
            "period": period,
            "clock": format_clock(r["MINUTES_REMAINING"],
                                  r["SECONDS_REMAINING"]),
            "zone": r["zone"],
            "zone_label": r["zone_label"],
            "action": r["action"],
            "distance_ft": distance,
            "made": str(r["SHOT_MADE_FLAG"] or "").strip() == "1",
            "game_id": r["GAME_ID"],
        })

    filters = {
        "player": player, "player_id": player_id,
        "team": team, "team_id": team_id,
        "zones": sorted(wanted_zones),
        "periods": ([p if p != 5 else "OT" for p in sorted(folded)]
                    if folded is not None else "all"),
        "three_only": bool(three_only), "made": made_filter,
        "late_clock_seconds": late_seconds,
        "exclude_heaves": bool(exclude_heaves), "limit": lim,
        "season": season,
        "group_by": group,
        "include_ot": ot,
    }
    if exclude_heaves:
        heave_msg = (
            f"Heave scrub is an estimate (30+ ft with 3 or fewer seconds "
            f"left in the period); {heaves_excluded} shots excluded here.")
    else:
        heave_msg = (
            "Heave scrub is DISABLED; heaves are INCLUDED in these "
            "aggregates (30+ ft with 3 or fewer seconds left in the period).")
    ot_msg = ("'4th' selects the 4th quarter plus overtime"
              if ot and folded is not None and 4 in folded and 5 in folded
              else ("overtime excluded by include_ot=no"
                    if folded is not None and 5 not in folded
                    else "all periods selected (overtime included)"))
    meta: dict[str, Any] = {
        "source": f"warehouse {TABLE}",
        "season": season,
        "shots_scanned": int(scanned),
        "shots_matched": attempts,
        "heaves_excluded": heaves_excluded,
        "games": games,
        "rows_returned": len(shots),
        "zones": ZONE_LEGEND,
        "clutch_safe": False,
        "score_aware": False,
        "data_note": (
            f"Warehouse silver_shots coverage is "
            f"{', '.join(_shot_seasons) or 'no season on hand'} "
            f"(233,632 shots, regular season and playoffs). PLAYER_NAME "
            f"is last-name-only (e.g. 'Gilgeous-Alexander'). TEAM_NAME/HTM/VTM "
            f"columns are not populated in this table, so team abbreviations "
            f"come from the nba_api static id->abbreviation mapping. GAME_DATE is not "
            f"populated in this table. Periods: {ot_msg}; use periods='ot' "
            f"for overtime only, include_ot=no for exactly the 4th quarter. "
            f"There is no score-margin column, so late-game filtering is "
            f"time-based only (period >= 4 plus the late_clock "
            f"seconds-remaining cap) and is NOT score-aware: never present "
            f"these results as close-game or clutch splits "
            f"(meta.clutch_safe=false). {heave_msg} TS% is not shown "
            f"because the table has no free-throw attempts; 'points' are "
            f"field-goal points only (2*FGM + 3PTM). Individual rows are a "
            f"deterministic pseudo-random mix across the season, not the "
            f"latest games; the aggregates are the answer."
        ),
    }
    if aggregate["small_sample"]:
        meta["sample_warning"] = (
            f"only {attempts} attempts -- percentages are noisy; "
            f"treat fg/efg as illustrative, not quotable")
    if attempts == 0:
        if (late_seconds is not None and folded is not None
                and not any(p >= 4 for p in folded)):
            meta["note"] = (
                f"late_clock={late_seconds}s only applies to periods 4+ "
                f"(incl. overtime), but periods={periods_raw!r} excludes "
                f"them, so zero shots can match by construction. Drop "
                f"late_clock or widen periods (e.g. '2h', '4th', 'ot').")
        else:
            meta["note"] = (
                "No shots matched the combined filters. PLAYER_NAME is "
                "last-name-only (e.g. 'Tatum'), teams resolve from "
                "abbreviations or full names, and late_clock only applies "
                "to periods 4+ (incl. overtime).")
    out: dict[str, Any] = {
        "tool": "search_shots", "ok": True, "filters": filters,
        "aggregate": aggregate, "by_zone": by_zone,
        "by_period": by_period, "shots": shots, "meta": meta,
    }
    if group == "player":
        out["by_player"] = grouped
    elif group == "team":
        out["by_team"] = grouped
    return out
