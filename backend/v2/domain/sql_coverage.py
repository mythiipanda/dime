"""Pure SQL coverage comparison shared by planning and admission.

Planning-time requirement coverage and runtime binding admission must agree on
what "the same SQL" means.  The rule is exact normalized equality plus one
conservative extension: a single-table plain SELECT may add direct source-column
projections (optionally aliased or duplicated) as long as every source column
projected by the requirement is still projected at least once and every
non-projection clause is identical.

Anything this extension does not positively recognize keeps exact normalized
equality, so aggregates, expressions, wildcards, joins, CTEs, subqueries, set
operations, and any filter/group/order/limit/distinct drift stay rejected.

Canonicalization only normalizes what the SQL grammar makes insignificant:
identifier case and keyword spelling.  Every literal value keeps its exact
text, the only exception being the pre-existing ``regular season`` /
``regular-season`` literal normalization.  In particular a filter such as
``PLAYER = 'PlayerA'`` never matches ``PLAYER = 'playera'``.
"""
from __future__ import annotations

from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

_DIALECT = "duckdb"
_REGULAR_SEASON_LITERALS = frozenset({"regular season", "regular-season"})


def _normalize_regular_season(ast: exp.Expression) -> exp.Expression:
    for literal in ast.find_all(exp.Literal):
        if (literal.is_string
                and literal.this.strip("'\"").casefold()
                in _REGULAR_SEASON_LITERALS):
            literal.replace(exp.Literal.string("regular-season"))
    return ast


def _normalize_identifiers(ast: exp.Expression) -> exp.Expression:
    """Lowercase identifiers without touching literal values.

    Identifier case is not significant in the duckdb dialect, but string
    literal case is, so only ``exp.Identifier`` nodes are rewritten.
    """
    for identifier in ast.find_all(exp.Identifier):
        identifier.set("this", identifier.this.casefold())
    return ast


def _parse(sql: Any) -> exp.Expression | None:
    if not (isinstance(sql, str) and sql.strip()):
        return None
    try:
        ast = parse_one(sql, read=_DIALECT)
    except ParseError:
        return None
    _normalize_regular_season(ast)
    return _normalize_identifiers(ast)


def _direct_column(projection: exp.Expression, allowed: frozenset[str]) -> str | None:
    inner = projection.this if isinstance(projection, exp.Alias) else projection
    if not isinstance(inner, exp.Column):
        return None
    if inner.name == "*" or any(
            isinstance(node, exp.Star) for node in inner.walk()):
        return None
    if inner.table and inner.table.casefold() not in allowed:
        return None
    return inner.name.casefold()


def _direct_source_columns(ast: exp.Expression) -> list[str] | None:
    """Return projected source columns for a plain single-table SELECT.

    ``None`` marks any shape this extension does not positively understand, so
    the caller keeps exact equality.
    """
    if not isinstance(ast, exp.Select):
        return None
    if ast.args.get("with") is not None:
        return None
    if ast.args.get("joins") or any(True for _ in ast.find_all(exp.Join)):
        return None
    if any(True for _ in ast.find_all(exp.Subquery)):
        return None
    if any(True for _ in ast.find_all(exp.SetOperation)):
        return None
    tables = list(ast.find_all(exp.Table))
    if len(tables) != 1:
        return None
    table = tables[0]
    allowed = frozenset(
        name.casefold() for name in (table.name, table.alias_or_name) if name)
    columns = []
    for projection in ast.expressions:
        column = _direct_column(projection, allowed)
        if column is None:
            return None
        columns.append(column)
    return columns


def _scope_sql(ast: exp.Expression) -> str:
    stripped = ast.copy()
    stripped.set("expressions", [])
    return stripped.sql(dialect=_DIALECT)


def _projection_extension_covers(
    expected_ast: exp.Expression, actual_ast: exp.Expression,
) -> bool:
    expected_columns = _direct_source_columns(expected_ast)
    actual_columns = _direct_source_columns(actual_ast)
    if expected_columns is None or actual_columns is None:
        return False
    if _scope_sql(expected_ast) != _scope_sql(actual_ast):
        return False
    return set(expected_columns) <= set(actual_columns)


def sql_covers(expected_sql: Any, actual_sql: Any) -> bool:
    """Return whether ``actual_sql`` covers ``expected_sql``."""
    if not (isinstance(actual_sql, str) and actual_sql.strip()):
        return False
    if not isinstance(expected_sql, str):
        return False
    if expected_sql.strip() == actual_sql.strip():
        return True
    expected_ast = _parse(expected_sql)
    actual_ast = _parse(actual_sql)
    if expected_ast is None or actual_ast is None:
        return False
    if (expected_ast.sql(dialect=_DIALECT)
            == actual_ast.sql(dialect=_DIALECT)):
        return True
    return _projection_extension_covers(expected_ast, actual_ast)
