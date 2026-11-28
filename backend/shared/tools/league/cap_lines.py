import math as _math
import re as _re
from typing import Any

from ..cap_rules import CAP_GROWTH_ASSUMPTION

_KEYS = ("cap", "tax", "apron1", "apron2")
_SEASON_RE = _re.compile(r"(\d{4})-(\d{2})")


def _season_start(season: str) -> int | None:
    match = _SEASON_RE.fullmatch(str(season or ""))
    if not match:
        return None
    start = int(match.group(1))
    if int(match.group(2)) != (start + 1) % 100:
        return None
    return start


def _coerce_lines(*values: Any) -> dict[str, int] | None:
    lines: dict[str, int] = {}
    try:
        for key, value in zip(_KEYS, values):
            if value is None:
                return None
            number = float(value)
            if not _math.isfinite(number) or number <= 0:
                return None
            lines[key] = int(round(number))
    except (TypeError, ValueError):
        return None
    return lines


def _dedupe(rows: list[tuple[str, dict[str, int] | None]]
            ) -> tuple[dict[str, dict[str, int]], set[str]]:
    variants: dict[str, dict[tuple[int, ...], dict[str, int]]] = {}
    for season, lines in rows:
        if _season_start(season) is None or lines is None:
            continue
        key = tuple(lines[name] for name in _KEYS)
        variants.setdefault(season, {})[key] = lines
    unique = {season: next(iter(values.values()))
              for season, values in variants.items() if len(values) == 1}
    conflicts = {season for season, values in variants.items() if len(values) > 1}
    return unique, conflicts


def _query_rows(con, sql: str) -> list[tuple]:
    try:
        return con.execute(sql).fetchall()
    except Exception:
        return []


def _history_lines(con) -> tuple[dict[str, dict[str, int]], set[str]]:
    rows = _query_rows(
        con,
        "SELECT season_label, salary_cap, luxury_tax, apron_1, apron_2 "
        "FROM silver_cap_history")
    return _dedupe([(str(row[0] or ""), _coerce_lines(*row[1:5]))
                    for row in rows])


def _room_lines(con) -> tuple[dict[str, dict[str, int]], set[str]]:
    rows = _query_rows(
        con,
        "SELECT CAP_SEASON, PROJECTED_CAP, PROJECTED_TAX, "
        "PROJECTED_APRON1, PROJECTED_APRON2 FROM silver_cap_room")
    return _dedupe([(str(row[0] or ""), _coerce_lines(*row[1:5]))
                    for row in rows])


def _error(season: str, message: str) -> dict[str, Any]:
    return {"ok": False, "season": season, "lines": None,
            "source": None, "projected": False, "exact": False,
            "error": message}


def _ok(season: str, lines: dict[str, int], source: str, projected: bool,
        exact: bool, **extra: Any) -> dict[str, Any]:
    return {"ok": True, "season": season, "lines": dict(lines),
            "source": source, "projected": projected, "exact": exact,
            "error": None, **extra}


def _missing_error(season: str) -> str:
    return (f"cap-line data unavailable for {season}; exact evaluation requires "
            "silver_cap_history coverage for historical seasons or "
            "silver_cap_room coverage for projected seasons")


def _source_data_lines() -> dict[str, dict[str, int]]:
    from ...sources.cap_history import APRON, ROWS, label

    out: dict[str, dict[str, int]] = {}
    for end_year, cap_m, tax_m in ROWS:
        aprons = APRON.get(end_year)
        if tax_m is None or aprons is None:
            continue
        out[label(end_year)] = {
            "cap": int(round(cap_m * 1_000_000)),
            "tax": int(round(tax_m * 1_000_000)),
            "apron1": int(round(aprons[0] * 1_000_000)),
            "apron2": int(round(aprons[1] * 1_000_000))}
    return out


def _baseline_candidates(history: dict[str, dict[str, int]],
                         room: dict[str, dict[str, int]]) -> list[tuple[int, str, dict[str, int], str]]:
    rows = []
    for source, table in (("silver_cap_history", history),
                          ("cap_history_source_data", _source_data_lines()),
                          ("silver_cap_room", room)):
        for season, lines in table.items():
            start = _season_start(season)
            if start is not None:
                rows.append((start, season, lines, source))
    return rows


def resolve_cap_lines(con, season: str, *,
                      allow_extrapolation: bool = False) -> dict[str, Any]:
    season = str(season or "").strip()
    start = _season_start(season)
    if start is None:
        return _error(season, f"cap-line season '{season}' is invalid; use YYYY-YY")
    history, history_conflicts = _history_lines(con)
    room, room_conflicts = _room_lines(con)
    source_data = _source_data_lines()
    if season in history:
        return _ok(season, history[season], "silver_cap_history", False, True)
    if season in source_data:
        return _ok(season, source_data[season], "cap_history_source_data",
                   False, True)
    if season in room:
        return _ok(season, room[season], "silver_cap_room", True, True)
    if season in history_conflicts or season in room_conflicts:
        return _error(season, f"conflicting cap-line rows for {season}")
    if not allow_extrapolation:
        return _error(season, _missing_error(season))
    candidates = _baseline_candidates(history, room)
    if not candidates:
        return _error(season, _missing_error(season))
    best: dict[int, tuple[int, str, dict[str, int], str]] = {}
    rank = {"silver_cap_history": 0, "cap_history_source_data": 1,
            "silver_cap_room": 2}
    for row in candidates:
        current = best.get(row[0])
        if current is None or rank.get(row[3], 3) < rank.get(current[3], 3):
            best[row[0]] = row
    base_start, base_season, base_lines, base_source = best[max(best)]
    if start <= base_start:
        return _error(season, _missing_error(season))
    steps = start - base_start
    factor = (1 + CAP_GROWTH_ASSUMPTION) ** steps
    lines = {key: int(round(value * factor)) for key, value in base_lines.items()}
    basis = {"season": base_season, "source": base_source,
             "growth_assumption": CAP_GROWTH_ASSUMPTION, "steps": steps}
    return _ok(season, lines, "growth_extrapolation", True, False,
               approximation_basis=basis)


def projection_cap_lines(con, season: str) -> dict[str, Any]:
    resolved = resolve_cap_lines(con, season, allow_extrapolation=True)
    if not resolved["ok"]:
        return {"ok": False, "lines": None, "projected": False, "source": None,
                "exact": False, "approximation_basis": None,
                "error": resolved["error"]}
    basis = resolved.get("approximation_basis")
    disclosure = None
    if basis and not resolved["exact"]:
        steps = basis["steps"]
        disclosure = (
            f"{int(CAP_GROWTH_ASSUMPTION * 100)}% annual growth for "
            f"{steps} season{'s' if steps != 1 else ''} from the "
            f"{basis['season']} lines in {basis['source']}; not an official "
            "league figure")
    return {"ok": True, "lines": dict(resolved["lines"]),
            "projected": bool(resolved["projected"]),
            "source": resolved["source"], "exact": bool(resolved["exact"]),
            "approximation_basis": disclosure, "error": None}
