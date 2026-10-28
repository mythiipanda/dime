"""Season encoding metadata shared by declared SQL schemas and SQL results."""

from __future__ import annotations

import re
from typing import Any, Mapping

CANONICAL_LABEL = "canonical_label"
END_YEAR_NUMERIC = "end_year_numeric"
NBA_SEASON_ID = "nba_season_id_start_year"
SEASON_PHASE = "season_phase"
UNKNOWN = "unknown"

_LABEL_RE = re.compile(r"^(\d{4})-(\d{2})$")
_SEASON_NAMES = frozenset({"_season", "season", "season_id", "season_type"})

_ENCODINGS: dict[str, dict[str, str]] = {
    CANONICAL_LABEL: {
        "unit": "season_label",
        "format": "YYYY-YY",
        "anchor": "start_year",
        "note": "canonical warehouse season label; the leading year is the start year",
        "source": "shared/store.py save_frame writes FetchMeta.season; "
                  "scripts/seed_history.py season_label(end_year)",
    },
    END_YEAR_NUMERIC: {
        "unit": "season_end_year",
        "format": "4-digit end year",
        "anchor": "end_year",
        "note": "numeric end year; 2025 means the 2024-25 season",
        "source": "scripts/seed_historical_playoffs.py reads numeric season "
                  "from silver_hist_gamelogs; shared/tools/history.py season_label",
    },
    NBA_SEASON_ID: {
        "unit": "nba_season_id",
        "format": "'2' + 4-digit start year",
        "anchor": "start_year",
        "note": "NBA season id; '22025' means the 2025-26 season",
        "source": "scripts/seed_2023_24_playoffs.py SEASON_ID='22023' with "
                  "SEASON='2023-24'; scripts/seed_bbref_gamelogs.py SEASON_ID='22025'",
    },
    SEASON_PHASE: {
        "unit": "season_phase",
        "format": "category",
        "anchor": "none",
        "note": "row phase, not a season key; filter rows with it",
        "source": "scripts/seed_2025_26_warehouse.py season_type='regular-season'; "
                  "scripts/seed_historical_playoffs.py season_type='playoffs'",
    },
    UNKNOWN: {
        "unit": "unknown",
        "format": "unknown",
        "anchor": "unknown",
        "note": "table-specific season encoding is not established by source; "
                "do not infer it from digit count",
        "source": "no source-backed mapping",
    },
}

_TABLE_COLUMNS: dict[str, dict[str, str]] = {
    "silver_hist_standings": {
        "season": END_YEAR_NUMERIC,
        "season_id": NBA_SEASON_ID,
        "season_type": SEASON_PHASE,
    },
    "silver_hist_gamelogs": {
        "season": END_YEAR_NUMERIC,
        "season_type": SEASON_PHASE,
    },
    "silver_hist_player_seasons": {"season": END_YEAR_NUMERIC},
    "silver_playoffs": {"season_id": NBA_SEASON_ID},
}

_GRAIN: dict[str, str] = {
    "silver_hist_standings": "one team-season row",
    "silver_hist_gamelogs": "one team-game row",
    "silver_hist_player_seasons": "one player-season row",
    "silver_playoffs": "one playoff team-game row",
}


def _column_encoding(table: str, column: str) -> str | None:
    name = str(column or "").lower()
    if name == "_season":
        return CANONICAL_LABEL
    mapped = _TABLE_COLUMNS.get(str(table or "").lower(), {})
    if name in mapped:
        return mapped[name]
    if name in {"season", "season_id"}:
        return UNKNOWN
    return None


def _annotation(table: str, column: str) -> dict[str, Any] | None:
    encoding = _column_encoding(table, column)
    if encoding is None:
        return None
    entry = dict(_ENCODINGS[encoding])
    entry["encoding"] = encoding
    entry["row_grain"] = _GRAIN.get(str(table or "").lower(), "table grain not declared")
    if encoding == UNKNOWN:
        entry["ambiguous"] = True
        entry["requires_label_evidence"] = True
    return entry


def annotate_schema(schema: Mapping[str, Any] | None) -> dict[str, Any]:
    tables = (schema or {}).get("tables")
    if not isinstance(tables, Mapping):
        return {"tables": {}}
    return {"tables": {
        table: {
            column: _annotated_column(str(table), column, metadata)
            for column, metadata in columns.items()
        } if isinstance(columns, Mapping) else columns
        for table, columns in tables.items()
    }}


def _annotated_column(table: str, column: str, metadata: Any) -> dict[str, Any]:
    item = dict(metadata) if isinstance(metadata, Mapping) else {"value": metadata}
    semantics = _annotation(table, column)
    if semantics is not None:
        item["season_semantics"] = semantics
    return item


def decode_season_value(encoding: str, value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if encoding == CANONICAL_LABEL:
        match = _LABEL_RE.match(text)
        if match is None:
            return None
        start, tail = int(match.group(1)), int(match.group(2))
        return f"{start:04d}-{tail:02d}" if tail == (start + 1) % 100 else None
    if encoding == END_YEAR_NUMERIC:
        if not text.isdigit() or len(text) != 4:
            return None
        end = int(text)
        return f"{end - 1:04d}-{end % 100:02d}" if 1900 <= end <= 2200 else None
    if encoding == NBA_SEASON_ID:
        if len(text) != 5 or text[0] != "2" or not text[1:].isdigit():
            return None
        start = int(text[1:])
        return f"{start:04d}-{(start + 1) % 100:02d}"
    return None


def _row_value(row: Mapping[str, Any], column: str) -> tuple[bool, Any]:
    if column in row:
        return True, row[column]
    lower = column.lower()
    for key, value in row.items():
        if str(key).lower() == lower:
            return True, value
    return False, None


def _unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out = []
    for value in values:
        key = repr(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _parse_sql(sql: object) -> tuple[Any, Any] | str:
    if not isinstance(sql, str) or not sql.strip():
        return "missing SQL text"
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return "sqlglot unavailable"
    try:
        tree = sqlglot.parse_one(sql, read="duckdb")
    except Exception as error:
        return f"SQL projection inspection failed: {type(error).__name__}"
    if not isinstance(tree, exp.Select) or tree.args.get("with"):
        return "CTE, union, or non-simple SELECT"
    return tree, exp


def _single_source(tree: Any, exp: Any, table: str) -> tuple[bool, str]:
    if tree.args.get("joins"):
        return False, ""
    from_clause = tree.args.get("from") or tree.args.get("from_")
    source = from_clause.this if from_clause is not None else None
    if not isinstance(source, exp.Table) or not source.name:
        return False, ""
    if str(source.name).lower() != table.lower():
        return False, ""
    return True, str(source.alias or source.name).lower()


def _store_column(columns: dict[str, dict[str, Any]], key: str,
                  entry: dict[str, Any]) -> None:
    if key in columns:
        columns[key] = {
            "column": entry["column"],
            "supported": False,
            "reason": "duplicate output column name",
        }
    else:
        columns[key] = entry


def _projection_columns(tree: Any, exp: Any, table: str,
                        alias: str) -> tuple[dict[str, dict[str, Any]], bool, bool]:
    columns: dict[str, dict[str, Any]] = {}
    star_seen = False
    for expression in tree.expressions:
        if isinstance(expression, exp.Star) or (
                isinstance(expression, exp.Column)
                and isinstance(expression.this, exp.Star)):
            star_seen = True
            continue
        if isinstance(expression, exp.Alias):
            output_name, inner = str(expression.alias or ""), expression.this
        elif isinstance(expression, exp.Column):
            output_name, inner = str(expression.name or ""), expression
        else:
            continue
        if not output_name:
            continue
        key = output_name.lower()
        if not isinstance(inner, exp.Column):
            _store_column(columns, key, {
                "column": output_name, "supported": False,
                "reason": "expression or literal alias is not a direct column",
            })
            continue
        if output_name.lower() != inner.name.lower():
            _store_column(columns, key, {
                "column": output_name, "supported": False,
                "reason": "renamed direct alias; output name is not source column identity",
            })
            continue
        qualifier = str(inner.table or "").lower()
        if qualifier and qualifier not in {table.lower(), alias}:
            _store_column(columns, key, {
                "column": output_name, "supported": False,
                "reason": "projection references an unknown table alias",
            })
            continue
        _store_column(columns, key, {
            "column": output_name, "supported": True, "table": table,
        })
    supported = any(item["supported"] for item in columns.values())
    return columns, supported, star_seen


def _attribution(sql: object, tables: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mode": "unresolved",
        "reason": "",
        "columns": {},
        "lineage_proven": False,
    }
    if not tables:
        result["reason"] = "no result table metadata"
        return result
    if len(tables) != 1:
        result["reason"] = "multi-table query; output lineage unresolved"
        return result
    if not isinstance(sql, str) or not sql.strip():
        result["mode"] = "fallback_single_table"
        result["reason"] = (
            "missing SQL text; single-table fallback is not projection proof")
        return result
    parsed = _parse_sql(sql)
    if isinstance(parsed, str):
        result["reason"] = parsed
        return result
    tree, exp = parsed
    table = tables[0]
    ok, alias = _single_source(tree, exp, table)
    if not ok:
        result["reason"] = "multi-table, join, or subquery source; lineage unresolved"
        return result
    columns, supported, star_seen = _projection_columns(tree, exp, table, alias)
    if star_seen:
        result["reason"] = "star projections are unresolved"
        return result
    result["columns"] = columns
    result["lineage_proven"] = supported
    if supported:
        result["mode"] = "partial" if any(
            not item["supported"] for item in columns.values()) else "supported"
    else:
        result["reason"] = "no direct output column lineage was supported"
    return result


def _declared_column_semantics(
    schema: Mapping[str, Any] | None,
    attribution: Mapping[str, Any],
) -> dict[str, dict[str, str]]:
    """Carry source-backed units only for proven direct output columns."""
    tables = (schema or {}).get("tables") or {}
    lineage = attribution.get("columns") or {}
    declared: dict[str, dict[str, str]] = {}
    for item in lineage.values():
        if not isinstance(item, Mapping) or not item.get("supported"):
            continue
        table = item.get("table")
        column = item.get("column")
        if not isinstance(table, str) or not isinstance(column, str):
            continue
        table_schema = next(
            (value for name, value in tables.items()
             if str(name).casefold() == table.casefold()), {})
        metadata = next(
            (value for name, value in table_schema.items()
             if str(name).casefold() == column.casefold()), {})
        if not isinstance(metadata, Mapping):
            continue
        unit = metadata.get("unit")
        note = metadata.get("note")
        semantics = {"table": table, "column": column}
        if isinstance(unit, str) and unit.strip():
            semantics["unit"] = unit
        if isinstance(note, str) and note.strip():
            semantics["note"] = note
        if "unit" in semantics or "note" in semantics:
            declared[column] = semantics
    return declared


def _schema_candidates(schema: Mapping[str, Any] | None,
                       tables: list[str]) -> dict[str, list[dict[str, Any]]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    for table in tables:
        columns = ((schema or {}).get("tables") or {}).get(table) or {}
        if not isinstance(columns, Mapping):
            continue
        for column, metadata in columns.items():
            if isinstance(metadata, Mapping):
                entry = metadata.get("season_semantics")
                if isinstance(entry, Mapping):
                    candidates.setdefault(str(column).lower(), []).append({
                        "table": table,
                        "column": str(column),
                        "encoding": str(entry.get("encoding") or UNKNOWN),
                        "entry": dict(entry),
                    })
    return candidates


def _output_names(result: Mapping[str, Any], rows: list[Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for name in (result.get("columns") or []):
        if isinstance(name, str) and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    for row in rows:
        if isinstance(row, Mapping):
            for name in row:
                if isinstance(name, str) and name.lower() not in seen:
                    seen.add(name.lower())
                    names.append(name)
    return names


def _select_columns(season_columns: list[str],
                    candidates: dict[str, list[dict[str, Any]]],
                    attribution: dict[str, Any]
                    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    supported: list[dict[str, Any]] = []
    unresolved: dict[str, dict[str, Any]] = {}
    lineage = attribution.get("columns") or {}
    for output_name in season_columns:
        key = output_name.lower()
        matches = candidates.get(key, [])
        item = lineage.get(key)
        if isinstance(item, Mapping) and item.get("supported"):
            table = item.get("table")
            selected = [entry for entry in matches if entry["table"] == table]
            if selected:
                supported.extend(selected)
                continue
            reason = "lineage table has no season metadata for this output"
        elif isinstance(item, Mapping):
            reason = str(item.get("reason") or "lineage unresolved")
        else:
            reason = attribution.get("reason") or "output column lineage is not supported"
        unresolved[key] = {
            "column": output_name,
            "candidate_tables": [entry["table"] for entry in matches],
            "reason": reason,
        }
    return supported, unresolved


def _resolved_rows(rows: list[Any], supported: list[dict[str, Any]]
                   ) -> tuple[list[dict[str, Any]], list[tuple[int, list[str]]]]:
    resolved: list[dict[str, Any]] = []
    row_labels: list[tuple[int, list[str]]] = []
    for row_index, row in enumerate(rows):
        labels: list[str] = []
        if isinstance(row, Mapping):
            for candidate in supported:
                present, value = _row_value(row, candidate["column"])
                if not present or value is None:
                    continue
                if candidate["encoding"] in {SEASON_PHASE, UNKNOWN}:
                    continue
                label = decode_season_value(candidate["encoding"], value)
                if label is not None:
                    labels.append(label)
                    item = {
                        "table": candidate["table"],
                        "column": candidate["column"],
                        "encoding": candidate["encoding"],
                        "observed": value,
                        "season_label": label,
                    }
                    if item not in resolved:
                        resolved.append(item)
        row_labels.append((row_index, _unique(labels)))
    return resolved, row_labels


def _observed(rows: list[Any], column: str) -> list[Any]:
    values = []
    for row in rows:
        if isinstance(row, Mapping):
            present, value = _row_value(row, column)
            if present and value is not None:
                values.append(value)
    return _unique(values)


def _season_column_entries(supported: list[dict[str, Any]],
                           unresolved: dict[str, dict[str, Any]],
                           rows: list[Any]
                           ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    columns: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []
    for candidate in sorted(supported, key=lambda item: (item["table"], item["column"])):
        entry = candidate["entry"]
        columns.append({
            "table": candidate["table"],
            "column": candidate["column"],
            "attribution_supported": True,
            "encoding": candidate["encoding"],
            "format": entry.get("format"),
            "row_grain": entry.get("row_grain"),
            "source": entry.get("source"),
        })
        observed = _observed(rows, candidate["column"])
        if candidate["encoding"] == UNKNOWN and observed:
            ambiguities.append({
                "table": candidate["table"],
                "column": candidate["column"],
                "observed": observed,
                "requires_label_evidence": True,
                "reason": entry.get("note") or "unknown season encoding",
            })
    for item in unresolved.values():
        observed = _observed(rows, item["column"])
        columns.append({
            "column": item["column"],
            "attribution_supported": False,
            "candidate_tables": item["candidate_tables"],
            "encoding": None,
            "format": None,
            "row_grain": None,
            "source": None,
            "reason": item["reason"],
        })
        if observed:
            ambiguities.append({
                "column": item["column"],
                "candidate_tables": item["candidate_tables"],
                "observed": observed,
                "attribution_supported": False,
                "requires_label_evidence": True,
                "reason": item["reason"],
            })
    return columns, ambiguities


def annotate_result(
    result: Mapping[str, Any],
    schema: Mapping[str, Any] | None,
) -> dict[str, Any]:
    tables = [
        str(table) for table in
        ((result.get("meta") or {}).get("tables") or [])
        if isinstance(table, str)
    ]
    rows = result.get("rows")
    output = dict(result)
    semantics: dict[str, Any] = {
        "tables": tables,
        "query_attribution": {},
        "season_columns": [],
        "resolved_labels": [],
        "ambiguities": [],
        "contradictions": [],
    }
    if not tables or not isinstance(rows, list):
        output["declared_column_semantics"] = {}
        output["season_semantics"] = semantics
        return output
    candidates = _schema_candidates(schema, tables)
    outputs = _output_names(result, rows)
    season_columns = [
        name for name in outputs
        if name.lower() in candidates or name.lower() in _SEASON_NAMES
    ]
    attribution = _attribution(result.get("sql"), tables)
    output["declared_column_semantics"] = _declared_column_semantics(
        schema, attribution)
    semantics["query_attribution"] = {
        key: attribution.get(key) for key in (
            "mode", "reason", "lineage_proven")
    }
    supported, unresolved = _select_columns(season_columns, candidates, attribution)
    # Deduplicate by (table, column), keeping the last match.
    supported = list({(item["table"], item["column"]): item for item in supported}.values())
    semantics["resolved_labels"], row_labels = _resolved_rows(rows, supported)
    columns, ambiguities = _season_column_entries(supported, unresolved, rows)
    semantics["season_columns"] = columns
    semantics["ambiguities"] = ambiguities
    semantics["contradictions"] = [
        {"row": index, "season_labels": distinct}
        for index, labels in row_labels
        if len(distinct := _unique(labels)) > 1
    ]
    output["season_semantics"] = semantics
    return output
