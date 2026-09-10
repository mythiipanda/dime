"""Historical league leaders from warehouse season totals only."""

from typing import Any

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


def normalize_category(name: object) -> str | None:
    key = str(name or "").strip().lower().replace(" ", "_")
    return key if key in CATEGORIES else None


def _clamp_year(value: object, fallback: int) -> int:
    try:
        year = int(str(value).strip()[:4])
    except (TypeError, ValueError):
        return fallback
    return max(MIN_YEAR, min(MAX_YEAR, year))


def _clamp_limit(value: object) -> int:
    try:
        return max(1, min(25, int(value)))
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
    out: dict[str, Any] = {
        "player": raw.get("player_name"),
        "team": raw.get("team_abbreviation"),
        "season": raw.get("season"),
        "gp": raw.get("gp"),
        "value": value,
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
def get_historical_leaders(category: str = "pts", start_season: int = 2015,
                           end_season: int = 2025, limit: int = 10,
                           mode: str = "leaders") -> dict[str, Any]:
    """League leaders per season or best single seasons from history.

    Seasons are end-years clamped to 2015..2025. Values are per-game
    warehouse estimates. Empty ranges report honestly, never fabricated.
    """
    canon = normalize_category(category)
    if canon is None:
        valid = ", ".join(sorted(CATEGORIES))
        return {"tool": "get_historical_leaders", "ok": False, "rows": {},
                "meta": {}, "error": f"unknown category '{category}'; valid categories: {valid}"}
    spec = CATEGORIES[canon]
    start = _clamp_year(start_season, MIN_YEAR)
    end = _clamp_year(end_season, MAX_YEAR)
    if start > end:
        start, end = end, start
    limit = _clamp_limit(limit)
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
        "qualification": qual,
        "source": "warehouse (documented estimates)",
        "values": "per-game season averages; RAPTOR from five-year-old model, not current form",
        "raptor_available": raptor,
    }
    return {"tool": "get_historical_leaders", "ok": True, "rows": payload, "meta": meta}
