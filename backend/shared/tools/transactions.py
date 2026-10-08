from typing import Any

from langchain_core.tools import tool

from .. import store
from ._core import coerce_team_id

_TABLE = "silver_transactions"

_VALID_TXN_TYPES = (
    "Signing",
    "Waive",
    "Trade",
    "ContractConverted",
    "AwardOnWaivers",
)

_COLUMNS = (
    "txn_date",
    "txn_type",
    "player",
    "player_id",
    "team",
    "team_id",
    "detail",
)


def _canonical_txn_type(raw: object) -> str | None:
    text = "" if raw is None else str(raw).strip()
    if not text:
        return ""
    lowered = text.lower()
    for name in _VALID_TXN_TYPES:
        if name.lower() == lowered:
            return name
    return None


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _season_for_date(date: object) -> str | None:
    try:
        text = str(date).strip()[:10]
        year = int(text[:4])
        month = int(text[5:7])
    except (TypeError, ValueError, IndexError):
        return None
    if month < 1 or month > 12:
        return None
    if month >= 10:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"


def _requested_seasons(start: str, end: str) -> list[str]:
    seasons: list[str] = []
    first = _season_for_date(start) if start else None
    last = _season_for_date(end) if end else None
    if first is None and last is None:
        return seasons
    if first is None:
        seasons.append(str(last))
        return seasons
    if last is None:
        seasons.append(first)
        return seasons
    try:
        low = int(first[:4])
        high = int(last[:4])
    except (TypeError, ValueError):
        return sorted({first, last})
    step = 1 if high >= low else -1
    out: list[str] = []
    year = low
    while True:
        if year >= 10:
            out.append(f"{year}-{str(year + 1)[2:]}")
        if year == high:
            break
        year += step
    return sorted(set(out))


def _no_coverage(start: str, end: str, txn_type: str, team: str) -> dict[str, Any]:
    from v2.adapters.coverage import table_seasons

    available = sorted(table_seasons(_TABLE))
    span = start or end
    if start and end:
        span = start + ".." + end
    if available:
        asked = (
            f"Transactions data for {span or 'that range'} is not available. "
            f"Available seasons: {', '.join(available)}. "
            "Which range should be used instead?"
        )
    else:
        asked = (
            f"Transactions data for {span or 'that range'} is not available. "
            "No seasons are on hand for transactions data right now. "
            "Which range should be used instead?"
        )
    return {"tool": "get_transactions", "ok": False, "rows": [], "error": asked,
            "meta": {"source": f"warehouse:{_TABLE}", "team": team,
                     "start": start, "end": end, "txn_type": txn_type,
                     "available_seasons": available,
                     "deterministic_answer": asked}}


def _slim(row: dict[str, Any]) -> dict[str, Any]:
    return {col: row.get(col) for col in _COLUMNS if col in row}


@tool
def get_transactions(team: str = "", start: str = "", end: str = "",
                     txn_type: str = "") -> dict[str, Any]:
    """Team transactions: signings, waivers, trades by team and date range."""
    want_team = "" if team is None else str(team).strip()
    want_start = "" if start is None else str(start).strip()
    want_end = "" if end is None else str(end).strip()
    canonical = _canonical_txn_type(txn_type)
    if canonical is None:
        valid = ", ".join(_VALID_TXN_TYPES)
        return {"tool": "get_transactions", "ok": False, "rows": [],
                "error": f"Unknown txn_type {str(txn_type).strip()!r}. "
                         f"Use one of: {valid}.",
                "meta": {"source": f"warehouse:{_TABLE}",
                         "team": want_team.upper() if want_team else "",
                         "start": want_start, "end": want_end,
                         "txn_type": "" if txn_type is None else str(txn_type).strip()}}
    tid: int | None = None
    if want_team:
        try:
            tid = coerce_team_id(want_team)
        except ValueError:
            return {"tool": "get_transactions", "ok": False, "rows": [],
                    "error": f"unknown team: {want_team}",
                    "meta": {"source": f"warehouse:{_TABLE}",
                             "team": want_team,
                             "start": want_start, "end": want_end,
                             "txn_type": canonical}}
    requested = _requested_seasons(want_start, want_end)
    if requested:
        from v2.adapters.coverage import table_seasons

        available = set(table_seasons(_TABLE))
        if not any(season in available for season in requested):
            return _no_coverage(want_start, want_end, canonical,
                                want_team.upper() if want_team else "")
    clauses: list[str] = []
    params: list[object] = []
    if want_start:
        clauses.append("txn_date >= ?")
        params.append(want_start)
    if want_end:
        clauses.append("txn_date <= ?")
        params.append(want_end)
    where = " AND ".join(clauses)
    frame = store.read_frame(_TABLE, where, params)
    raws: list[dict[str, Any]] = []
    if frame is not None and frame.height > 0:
        try:
            raws = frame.to_dicts()
        except Exception:
            raws = []
    rows: list[dict[str, Any]] = []
    for raw in raws:
        day = str(raw.get("txn_date") or "")
        if want_start and day < want_start:
            continue
        if want_end and day > want_end:
            continue
        if tid is not None:
            same_id = _as_int(raw.get("team_id")) == tid
            same_abbr = (str(raw.get("team") or "").strip().upper()
                         == want_team.upper())
            if not (same_id or same_abbr):
                continue
        if canonical:
            if str(raw.get("txn_type") or "") != canonical:
                continue
        rows.append(_slim(raw))
    rows.sort(key=lambda r: str(r.get("txn_date") or ""), reverse=True)
    if not rows:
        subject = want_team.upper() if want_team else "the league"
        bounds = want_start or want_end
        if want_start and want_end:
            bounds = want_start + ".." + want_end
        label = canonical if canonical else "transactions"
        if bounds:
            error = f"No {label} rows for {subject} in {bounds}."
        else:
            error = f"No {label} rows for {subject}."
        return {"tool": "get_transactions", "ok": False, "rows": [],
                "error": error,
                "meta": {"source": f"warehouse:{_TABLE}",
                         "team": want_team.upper() if want_team else "",
                         "start": want_start, "end": want_end,
                         "txn_type": canonical}}
    display = want_team.upper() if want_team else ""
    return {"tool": "get_transactions", "ok": True, "rows": rows,
            "meta": {"source": f"warehouse:{_TABLE}",
                     "team": display, "start": want_start, "end": want_end,
                     "txn_type": canonical,
                     "coverage": "Team transactions by date range "
                                 "for seasons on file; a range outside "
                                 "coverage is reported, never swapped.",
                     **store.warehouse_identity()}}
