"""Cheap, fail-closed count evidence and returned-row profile for sql_exec.

Additive metadata only. Nothing here executes SQL, reads the warehouse, or
claims entities or grains. Basis indexes are 0-based ordinals aligned with the
result's ``columns`` list, correlated positionally. All doubt fails closed to
``status="unavailable"`` and the caller's payload passes through untouched.
"""

from __future__ import annotations

from typing import Any

import sqlglot
from sqlglot import exp

def _unavailable() -> dict[str, Any]:
    return {"status": "unavailable"}

def _clean_column_names(columns: Any) -> list[str] | None:
    if not isinstance(columns, list) or not columns:
        return None
    names: list[str] = []
    for name in columns:
        if not isinstance(name, str) or not name.strip():
            return None
        names.append(name)
    return names

def _has_duplicate_names(names: list[str]) -> bool:
    lowered = [name.lower() for name in names]
    return len(set(lowered)) != len(lowered)

def _star_ok(node: exp.Expression) -> bool:
    for star in node.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            return False
    return True

def _direct_count(core: exp.Expression) -> tuple[str, exp.Count | None]:
    if isinstance(core, exp.Count):
        if core.args.get("filter") is not None or core.args.get("over") is not None:
            return "wrapped", None
        return "ok", core
    return "none", None

def _distinct_parts(distinct: exp.Distinct) -> list[exp.Expression]:
    parts = list(distinct.expressions)
    if len(parts) == 1 and isinstance(parts[0], exp.Tuple):
        parts = list(parts[0].expressions)
    return parts

def _classify(index: int, count: exp.Count) -> dict[str, Any] | None:
    this = count.this
    if this is None:
        return None
    if isinstance(this, exp.Star):
        return {"index": index, "kind": "count_star"}
    if isinstance(this, exp.Distinct):
        parts = _distinct_parts(this)
        if not parts:
            return None
        args = [part.sql(dialect="duckdb") for part in parts]
        if len(parts) == 1 and isinstance(parts[0], exp.Column):
            return {"index": index, "kind": "count_distinct", "column": args[0]}
        return {"index": index, "kind": "count_distinct", "argument": args}
    argument = this.sql(dialect="duckdb")
    if isinstance(this, exp.Column):
        return {"index": index, "kind": "count_column", "column": argument}
    return {"index": index, "kind": "count_expr", "argument": [argument]}

def basis_for(query: str, columns: Any) -> dict[str, Any]:
    try:
        names = _clean_column_names(columns)
        if names is None or _has_duplicate_names(names):
            return _unavailable()
        if not isinstance(query, str):
            return _unavailable()
        tree = sqlglot.parse_one(query, read="duckdb")
    except Exception:
        return _unavailable()
    if not isinstance(tree, exp.Select):
        return _unavailable()
    projections = list(tree.expressions)
    if len(projections) != len(names):
        return _unavailable()
    aggregates: list[dict[str, Any]] = []
    for index, node in enumerate(projections):
        if not _star_ok(node):
            return _unavailable()
        core = node.this if isinstance(node, exp.Alias) else node
        state, count = _direct_count(core)
        if state == "wrapped":
            return _unavailable()
        if count is not None:
            aggregate = _classify(index, count)
            if aggregate is None:
                return _unavailable()
            aggregates.append(aggregate)
        elif core.find(exp.Count) is not None:
            return _unavailable()
    return {"status": "ok", "aggregates": aggregates}

def profile_for(columns: Any, rows: Any) -> dict[str, Any]:
    try:
        names = _clean_column_names(columns)
        if names is None or _has_duplicate_names(names):
            return _unavailable()
        if not isinstance(rows, list):
            return _unavailable()
        counts = dict.fromkeys(names, 0)
        for row in rows:
            if not isinstance(row, dict):
                return _unavailable()
            for name in names:
                if row.get(name) is not None:
                    counts[name] += 1
        return {
            "returned_rows": len(rows),
            "scope": "returned_post_cap",
            "columns": {name: {"non_null": count} for name, count in counts.items()},
        }
    except Exception:
        return _unavailable()

def count_evidence_meta(query: str, columns: Any, rows: Any) -> dict[str, Any]:
    try:
        basis = basis_for(query, columns)
    except Exception:
        basis = _unavailable()
    try:
        profile = profile_for(columns, rows)
    except Exception:
        profile = _unavailable()
    return {"basis": basis, "profile": profile}
