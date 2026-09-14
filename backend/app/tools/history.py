"""Historical league leaders from warehouse season totals only."""

import difflib as _dl
from typing import Any, Union

from langchain_core.tools import tool

from .. import store

MIN_YEAR, MAX_YEAR = 2015, 2025
MIN_GP = 20

CATEGORIES: dict[str, dict[str, Any]] = {
    "pts": {"column": "pts", "label": "PTS", "decimals": 1},
    "reb": {"column": "reb", "label": "REB", "decimals": 1},
    "ast": {"column": "ast", "label": "AST", "decimals": 1},
    "stl": {"column": "stl", "label": "STL", "decimals": 1},
    "blk": {"column": "blk", "label": "BLK", "decimals": 1},
    "tov": {"column": "tov", "label": "TOV", "decimals": 1},
    "fgm": {"column": "fgm", "label": "FGM", "decimals": 1},
    "fga": {"column": "fga", "label": "FGA", "decimals": 1},
    "fg_pct": {"column": "fg_pct", "label": "FG%", "decimals": 3, "denominator": "fga"},
    "fg3m": {"column": "fg3m", "label": "FG3M", "decimals": 1},
    "fg3a": {"column": "fg3a", "label": "FG3A", "decimals": 1},
    "fg3_pct": {"column": "fg3_pct", "label": "FG3%", "decimals": 3, "denominator": "fg3a"},
    "ftm": {"column": "ftm", "label": "FTM", "decimals": 1},
    "fta": {"column": "fta", "label": "FTA", "decimals": 1},
    "ft_pct": {"column": "ft_pct", "label": "FT%", "decimals": 3, "denominator": "fta"},
    "ts_pct": {"column": "ts_pct", "label": "TS%", "decimals": 3},
    "min": {"column": "min", "label": "MIN", "decimals": 1},
    "raptor": {"column": "RAPTOR_TOTAL", "label": "RAPTOR", "decimals": 2, "raptor_only": True},
}

MODE_ALIASES = {
    "leaders": "leaders",
    "per-season": "leaders",
    "per_season": "leaders",
    "best": "best",
    "single-season": "best",
    "single_season": "best",
    "campaigns": "best",
}

CATEGORY_ALIASES: dict[str, str] = {
    "scoring": "pts", "points": "pts", "point": "pts", "pts": "pts",
    "rebounds": "reb", "rebound": "reb", "boards": "reb", "board": "reb",
    "reb": "reb",
    "assists": "ast", "assist": "ast", "dimes": "ast", "dime": "ast",
    "ast": "ast",
    "steals": "stl", "steal": "stl", "stl": "stl",
    "blocks": "blk", "block": "blk", "blk": "blk",
    "threes": "fg3m", "three": "fg3m", "three_pointers": "fg3m",
    "three_pointer": "fg3m", "fg3m": "fg3m",
    "field_goal_pct": "fg_pct", "fg_percentage": "fg_pct",
    "field_goal_percentage": "fg_pct", "fg_pct": "fg_pct",
    "free_throw_pct": "ft_pct", "ft_percentage": "ft_pct",
    "free_throw_percentage": "ft_pct", "ft_pct": "ft_pct",
    "minutes": "min", "minute": "min", "mins": "min", "min": "min",
}


def season_label(end_year: object) -> str:
    y = int(str(end_year).strip()[:4])
    return f"{y - 1}-{str(y)[-2:]}"


def normalize_category(name: object) -> str | None:
    key = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in key:
        key = key.replace("__", "_")
    if key in CATEGORIES:
        return key
    return CATEGORY_ALIASES.get(key)


def closest_category(name: object) -> str | None:
    key = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
    pool = sorted(set(CATEGORIES) | set(CATEGORY_ALIASES))
    hit = _dl.get_close_matches(key, pool, n=1, cutoff=0.6)
    if not hit:
        return None
    return CATEGORY_ALIASES.get(hit[0], hit[0])


def _parse_year_raw(value: object, fallback: int) -> tuple[int, bool]:
    try:
        return int(str(value).strip()[:4]), True
    except (TypeError, ValueError, AttributeError):
        return fallback, False


def _clamp_year(value: object, fallback: int) -> int:
    year, _ = _parse_year_raw(value, fallback)
    return max(MIN_YEAR, min(MAX_YEAR, year))


def _clamp_limit(value: object) -> int:
    try:
        return max(1, min(25, int(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 10


def normalize_mode(mode: object) -> str:
    return MODE_ALIASES.get(str(mode or "").strip().lower(), "leaders")


RAPTOR_JOIN = ("LEFT JOIN silver_raptor_player r ON LOWER(r.PLAYER_NAME) = "
               "LOWER(h.player_name) AND r.SEASON = h.season")


def _tables() -> set[str]:
    con = store.connect()
    try:
        return {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()


def _round_value(decimals: int, value: object) -> float | None:
    try:
        out = round(float(value), decimals)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _row(spec: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    value = _round_value(spec["decimals"], raw.get("value"))
    season = raw.get("season")
    try:
        label = season_label(season) if season is not None else None
    except (TypeError, ValueError):
        label = None
    out: dict[str, Any] = {
        "player": raw.get("player_name"),
        "team": raw.get("team_abbreviation"),
        "season": season,
        "season_label": label,
        "gp": raw.get("gp"),
        "value": value,
        "display": f"{value:.{spec['decimals']}f}" if value is not None else None,
    }
    raptor = _round_value(2, raw.get("raptor"))
    if raptor is not None:
        out["raptor"] = raptor
    return out


def _query(spec: dict[str, Any], where: str, params: list,
           limit: int, raptor: bool) -> list[dict[str, Any]]:
    if spec.get("raptor_only") and not raptor:
        return []
    if spec.get("raptor_only"):
        select = "h.player_name, h.team_abbreviation, h.season, h.gp, r.RAPTOR_TOTAL AS value, r.RAPTOR_TOTAL AS raptor"
        join = RAPTOR_JOIN
        order = "r.RAPTOR_TOTAL"
        extra = "AND r.RAPTOR_TOTAL IS NOT NULL AND h.min >= 20"
    else:
        col = spec["column"]
        raptor_col = ", r.RAPTOR_TOTAL AS raptor" if raptor else ""
        select = (f"h.player_name, h.team_abbreviation, h.season, h.gp, "
                  f"h.{col} AS value{raptor_col}")
        join = RAPTOR_JOIN if raptor else ""
        order = f"h.{col}"
        extra = f"AND h.{col} IS NOT NULL"
        if spec.get("denominator"):
            extra += f" AND h.{spec['denominator']} >= 2.0"
    rows = store._read_df(
        f"""SELECT {select} FROM silver_hist_player_seasons h {join}
        WHERE {where} AND h.gp >= {MIN_GP} {extra}
        ORDER BY {order} DESC LIMIT {limit}""",
        params,
    )
    return [_row(spec, r) for r in rows if _round_value(spec["decimals"], r.get("value")) is not None]


@tool
def get_historical_leaders(category: str = "pts",
                           start_season: Union[int, str, None] = 2015,
                           end_season: Union[int, str, None] = 2025,
                           limit: Union[int, str, None] = 10,
                           mode: str = "leaders") -> dict[str, Any]:
    """League leaders per season or best single seasons from history. Seasons are end-years (2025 means 2024-25), clamped to 2015..2025.

    Seasons are end-years clamped to 2015..2025. Values are per-game
    warehouse estimates. Empty ranges report honestly, never fabricated.
    """
    canon = normalize_category(category)
    if canon is None:
        valid = ", ".join(sorted(CATEGORIES))
        hint = closest_category(category)
        err = f"unknown category '{category}'; valid categories: {valid}"
        if hint:
            err += f"; did you mean '{hint}'?"
        return {"tool": "get_historical_leaders", "ok": False, "rows": {},
                "meta": {}, "error": err}
    spec = CATEGORIES[canon]
    warnings: list[str] = []
    raw_start, start_ok = _parse_year_raw(start_season, MIN_YEAR)
    raw_end, end_ok = _parse_year_raw(end_season, MAX_YEAR)
    if not start_ok:
        warnings.append(f"start_season '{start_season}' invalid, using {MIN_YEAR}")
    if not end_ok:
        warnings.append(f"end_season '{end_season}' invalid, using {MAX_YEAR}")
    if min(raw_start, raw_end) > MAX_YEAR or max(raw_start, raw_end) < MIN_YEAR:
        return {"tool": "get_historical_leaders", "ok": False, "rows": {},
                "meta": {"category": canon,
                         "requested_range": [raw_start, raw_end]},
                "error": f"no {spec['label']} coverage for seasons {raw_start}..{raw_end}"}
    start, end = raw_start, raw_end
    if start > end:
        start, end = end, start
        warnings.append(f"reversed range swapped to {start}..{end}")
    clamped_start = max(MIN_YEAR, min(MAX_YEAR, start))
    clamped_end = max(MIN_YEAR, min(MAX_YEAR, end))
    if clamped_start != start:
        warnings.append(f"start_season {start} clamped to {clamped_start}")
    if clamped_end != end:
        warnings.append(f"end_season {end} clamped to {clamped_end}")
    start, end = clamped_start, clamped_end
    try:
        raw_limit = int(limit)  # type: ignore[arg-type]
        limit_ok = True
    except (TypeError, ValueError):
        raw_limit = 10
        limit_ok = False
    if not limit_ok:
        warnings.append(f"limit '{limit}' invalid, using 10")
    limit = max(1, min(25, raw_limit))
    if limit_ok and limit != raw_limit:
        warnings.append(f"limit {raw_limit} clamped to {limit}")
    mode = normalize_mode(mode)
    try:
        tables = _tables()
    except Exception:
        tables = set()
    if "silver_hist_player_seasons" not in tables:
        return {"tool": "get_historical_leaders", "ok": False, "rows": {},
                "meta": {"category": canon},
                "error": "warehouse table missing: silver_hist_player_seasons"}
    raptor = "silver_raptor_player" in tables
    try:
        if mode == "best":
            rows = _query(spec, "h.season BETWEEN ? AND ?", [start, end], limit, raptor)
            payload: dict[str, Any] = {"leaders": rows}
        else:
            seasons = []
            for year in range(start, end + 1):
                top = _query(spec, "h.season = ?", [year], limit, raptor)
                if top:
                    seasons.append({"season": year, "leaders": top})
            payload = {"seasons": seasons}
            rows = [r for s in seasons for r in s["leaders"]]
    except Exception as exc:
        return {"tool": "get_historical_leaders", "ok": False, "rows": {},
                "meta": {"category": canon, "start_season": start, "end_season": end},
                "error": f"warehouse read failed: {str(exc)[:120]}"}
    if not rows:
        return {"tool": "get_historical_leaders", "ok": False, "rows": {},
                "meta": {"category": canon, "start_season": start, "end_season": end,
                         "mode": mode, "source": "warehouse (documented estimates)"},
                "error": f"no {spec['label']} coverage for seasons {start}..{end}"}
    qual = f"GP>={MIN_GP}" + (" MIN>=20" if canon == "raptor" else "")
    meta: dict[str, Any] = {
        "category": canon, "label": spec["label"], "mode": mode,
        "start_season": start, "end_season": end, "limit": limit,
        "display_range": f"{season_label(start)} to {season_label(end)}",
        "qualification": qual,
        "source": "warehouse (documented estimates)",
        "values": "per-game season averages; RAPTOR from five-year-old model, not current form",
        "raptor_available": raptor,
    }
    if warnings:
        meta["warning"] = "; ".join(warnings)
    return {"tool": "get_historical_leaders", "ok": True, "rows": payload, "meta": meta}
