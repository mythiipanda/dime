
DATA_DATE_COLUMNS = ("GAME_DATE", "game_date", "DATE", "date")

_DATE_FORMATS = ("%b %d, %Y", "%Y-%m-%d")

_MIN_COVERAGE = "1990-01-01"
_MAX_COVERAGE = "2100-01-01"

def _column_type(con, table, name):
    try:
        info = con.execute('PRAGMA table_info("%s")' % table).fetchall()
    except Exception:
        return None
    for row in info:
        if row[1] == name:
            return str(row[2]).upper()
    return None

def table_data_through(con, table, cols):
    date_col = next((c for c in DATA_DATE_COLUMNS if c in cols), None)
    if date_col is None:
        return None
    if _column_type(con, table, date_col) == "DATE":
        expr = '"%s"' % date_col
    else:
        expr = "COALESCE(" + ", ".join(
            'TRY_STRPTIME("%s", \'%s\')' % (date_col, fmt)
            for fmt in _DATE_FORMATS
        ) + ")"
    try:
        val = con.execute(
            'SELECT MAX(CAST(%s AS DATE)) FROM "%s" '
            "WHERE CAST(%s AS DATE) BETWEEN DATE '%s' AND DATE '%s'"
            % (expr, table, expr, _MIN_COVERAGE, _MAX_COVERAGE)
        ).fetchone()[0]
    except Exception:
        return None
    return val.isoformat() if val is not None else None
