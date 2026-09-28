"""Per-table data coverage dates for the /datasets/freshness endpoint.

`last_fetch` is an INGESTION timestamp: when the warehouse last pulled the
table. It says nothing about what dates the table's data actually covers --
showing it as "Data through <date>" misleads (one fresh table masks stale
ones).

`data_through` is the coverage date: the latest game/event date present in
the table's own rows, parsed defensively from the table's date column.
NULL when the table has no parseable date column (static or snapshot
tables like combine, draft, standings).

Both the v1 (backend/app/datasets.py) and v2 (backend/v2/api/routes.py)
freshness payload builders call `table_data_through()` so the payloads
stay in sync.
"""

# First match wins; checked against PRAGMA column lists.
DATA_DATE_COLUMNS = ("GAME_DATE", "game_date", "DATE", "date")

# Date spellings observed across seeds: "Oct 28, 2025" (nba_api-style) and
# "2025-10-28" (bbref-style). TRY_STRPTIME returns NULL on mismatch, so both
# are tried per row without raising.
_DATE_FORMATS = ("%b %d, %Y", "%Y-%m-%d")

_MIN_COVERAGE = "1990-01-01"
_MAX_COVERAGE = "2100-01-01"


def table_data_through(con, table, cols):
    """Latest data date in `table` as 'YYYY-MM-DD', or None.

    `con` is an open DuckDB connection, `table` a silver_* table name, `cols`
    its PRAGMA column names. Never raises: any parse/query failure means no
    coverage date.
    """
    date_col = next((c for c in DATA_DATE_COLUMNS if c in cols), None)
    if date_col is None:
        return None
    parsed = "COALESCE(" + ", ".join(
        'TRY_STRPTIME("%s", \'%s\')' % (date_col, fmt)
        for fmt in _DATE_FORMATS
    ) + ")"
    try:
        val = con.execute(
            'SELECT MAX(CAST(%s AS DATE)) FROM "%s" '
            "WHERE %s BETWEEN DATE '%s' AND DATE '%s'"
            % (parsed, table, parsed, _MIN_COVERAGE, _MAX_COVERAGE)
        ).fetchone()[0]
    except Exception:
        return None
    return val.isoformat() if val is not None else None
