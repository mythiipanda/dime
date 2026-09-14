"""Claim-level grounding checks for benchmark transcripts.

Phase 0 measures whether every factual numeral in an answer can be traced to
an evidence envelope emitted in custom_data. It is intentionally separate
from answer-text grading so it can run in shadow mode before becoming a gate.
"""
from __future__ import annotations

import json
import re
from typing import Any

_NUM = re.compile(
    r"(?<![A-Za-z])(?:20\d{2}-\d{2}|[-+]?\$?\d[\d,]*(?:\.\d+)?%?)")


def _walk(value: Any):
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)
    elif value is not None:
        yield value


def _canon(raw: object) -> set[str]:
    """Comparable forms for an evidence scalar, including percent scaling."""
    text = str(raw).strip().replace(",", "").replace("$", "")
    out = {text.lower()}
    try:
        f = float(text.rstrip("%"))
    except ValueError:
        return out
    out |= {f"{f:g}", f"{f:.1f}", f"{f:.2f}"}
    if abs(f) <= 1:
        out |= {f"{f * 100:g}", f"{f * 100:.1f}", f"{f * 100:.2f}"}
    return {x.rstrip("0").rstrip(".") if "." in x else x for x in out}


def evidence_values(tables: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for table in tables:
        for value in _walk(table):
            values |= _canon(value)
            # Qualification notes such as "82+ made threes" carry
            # evidence numerals inside strings rather than scalar cells.
            if isinstance(value, str):
                for raw in _NUM.findall(value):
                    values |= _canon(raw)
    return values


def factual_numerals(text: str) -> list[str]:
    vals = []
    for match in _NUM.finditer(text or ""):
        raw = match.group(0)
        # Markdown list labels ("1.") are structure, not factual claims.
        if raw.isdigit() and match.end() < len(text) and text[match.end()] == ".":
            if match.start() == 0 or text[match.start() - 1] == "\n":
                continue
        vals.append(raw)
    return vals


def check_claim_grounding(text: str, tables: list[dict[str, Any]],
                          allow: list[str] | None = None) -> dict[str, Any]:
    supported = evidence_values(tables)
    allowed = {x for a in (allow or []) for x in _canon(a)}
    claims = factual_numerals(text)
    unsupported = []
    for claim in claims:
        forms = _canon(claim)
        if not (forms & supported or forms & allowed):
            unsupported.append(claim)
    return {"claims": len(claims), "supported": len(claims) - len(unsupported),
            "unsupported": unsupported,
            "coverage": (round((len(claims) - len(unsupported)) / len(claims), 3)
                         if claims else 1.0)}


def evidence_envelope(scenario_id: str, turns: list[dict[str, Any]]) -> dict:
    """Portable replay fixture: no prompts or user traces, only test evidence."""
    return {"version": 1, "scenario_id": scenario_id,
            "turns": [{"tables": t.get("evidence_tables", []),
                       "tool_trace": t.get("tool_trace", [])} for t in turns]}
