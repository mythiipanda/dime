"""Deterministic metric coverage registry.

Which impact metrics the warehouse backs and which are unavailable.
No warehouse query: coverage is declared here and available metrics name
their backing table.
"""
from __future__ import annotations

import re
from typing import Any

UNAVAILABLE_METRICS = ("EPM", "LEBRON", "DARKO", "DRIP", "PER", "BPM",
                       "WS", "VORP")

AVAILABLE_METRICS = {
    "RAPM": {"label": "RAPM-lite", "table": "silver_rapm",
             "note": "ridge on stint differentials; estimate"},
    "ONOFF": {"label": "on-off net", "table": "silver_on_off",
              "note": "lineup splits, noisy"},
    "PIE": {"label": "PIE", "table": "silver_advanced",
            "note": "box-score share"},
    "TRUESHOOTING": {"label": "true shooting", "table": "silver_advanced",
                     "note": "scoring efficiency"},
    "RAPTOR": {"label": "RAPTOR", "table": "silver_raptor_player",
               "note": "box plus on-off; historical vintage, estimate"},
    "WAR": {"label": "WAR", "table": "silver_raptor_player",
            "note": "wins above replacement; historical vintage, estimate"},
}

_ALIASES = {
    "RAPMLITE": "RAPM",
    "TS": "TRUESHOOTING",
    "TSPCT": "TRUESHOOTING",
    "ONOFFNET": "ONOFF",
    "WARTOTAL": "WAR",
}


def _key(metric: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (metric or "").upper())


def _classify(metric: str) -> dict[str, str]:
    key = _ALIASES.get(_key(metric), _key(metric))
    for prop in UNAVAILABLE_METRICS:
        if key == _key(prop):
            return {"metric": prop, "status": "unavailable",
                    "note": "not in warehouse, never estimated"}
    known = AVAILABLE_METRICS.get(key)
    if known:
        return {"metric": known["label"], "status": "available",
                "note": f"{known['note']} ({known['table']})"}
    return {"metric": metric, "status": "unknown",
            "note": "not in the coverage registry"}


def metric_coverage(
    metrics: str | list[str],
    player: str = "",
    season: str | None = None,
) -> dict[str, Any]:
    """Report warehouse coverage for named metrics, for at most one player.

    EPM, LEBRON, DARKO, DRIP, PER, BPM, WS and VORP are unavailable
    and never estimated.
    """
    if isinstance(metrics, str):
        metrics = [m.strip() for m in re.split(r"[,;&]|\band\b", metrics)
                 if m.strip()]
    rows = []
    for raw in metrics:
        row = _classify(raw)
        if player:
            row["player"] = player
        rows.append(row)
    unavailable = [r["metric"] for r in rows if r["status"] == "unavailable"]
    subject = f" for {player}" if player else ""
    warnings: list[str] = []
    if unavailable:
        joined = " and ".join(unavailable)
        verb = "are" if len(unavailable) > 1 else "is"
        warnings.append(
            f"{joined} {verb} not available in the warehouse{subject}; "
            "Dime never estimates missing proprietary metrics. Available "
            "current impact context includes RAPM-lite, on-off net, PIE, "
            "and true shooting.")
    unknown = [r["metric"] for r in rows if r["status"] == "unknown"]
    for name in unknown:
        warnings.append(f"{name} is not a recognized metric{subject}.")
    available = [r["metric"] for r in rows if r["status"] == "available"]
    parts = []
    if unavailable:
        parts.append(warnings[0])
    if available:
        parts.append(f"Available in the warehouse{subject}: "
                     + ", ".join(available) + ".")
    if not parts:
        parts.append(f"No recognized metrics requested{subject}.")
    meta: dict[str, Any] = {
        "source": "warehouse coverage",
        "coverage": "declared coverage registry; unavailable metrics are "
                    "constants, available metrics name their silver table",
        "deterministic_answer": " ".join(parts),
        "warnings": warnings,
    }
    if season:
        meta["season"] = str(season)
    return {"tool": "metric_coverage", "ok": True, "rows": rows, "meta": meta}
