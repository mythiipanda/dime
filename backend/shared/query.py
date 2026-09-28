"""Direct read-only SQL over the warehouse, for the agent.

query_warehouse(sql, ...) runs agent-written SQL under tight guardrails:
only one SELECT/WITH statement, only over the known warehouse tables,
opened read_only, with a statement timeout and a row cap. It returns
columns, rows, and a truncation flag, so the caller can tell when the
cap cut the result short.

Errors are honest about what happened: blocked statements, timeouts,
and syntax failures each get their own message. No write path exists.
"""

import re
import threading
import time

import duckdb

from . import store

ROW_CAP = 500
STATEMENT_TIMEOUT_S = 30

# First keyword of the single statement. Anything else is rejected.
_FIRST_WORD_RE = re.compile(r"(?i)^\s*(select|with)\b")

# Statement-level words that can never appear in a read-only query.
_WRITE_WORDS = (
    "insert", "update", "delete", "drop", "alter", "create", "pragma",
    "attach", "detach", "copy", "vacuum", "install", "load",
    "checkpoint", "export", "import", "grant", "revoke", "truncate",
)
_WRITE_RE = re.compile(r"\b(" + "|".join(_WRITE_WORDS) + r")\b", re.IGNORECASE)

# Table functions that reach the filesystem or the network.
_TABLE_FN_RE = re.compile(
    r"\b(read_csv|read_parquet|read_json|read_ndjson|read_txt|"
    r"read_json_auto|parquet_scan|csv_scan|json_scan|sqlite_scan|"
    r"sqlite_attach|httpfs_read|read_text)\s*\(",
    re.IGNORECASE,
)

# A quoted FROM target that looks like a file path or URL, e.g.
# FROM 's3://bucket/games.parquet' or FROM '/tmp/x.csv'.
_PATHY_FROM_RE = re.compile(
    r"""(?i)\bfrom\s+(['"])([^'"]*(?:/|\\|\.(?:csv|parquet|json|ndjson|tsv|txt|db))\b[^'"]*)\1"""
)

# Unquoted table references: FROM x, JOIN x.
_TABLE_REF_RE = re.compile(
    r"(?i)\bfrom\s+([a-zA-Z_]\w*)|\bjoin\s+([a-zA-Z_]\w*)"
)

# CTE names declared in WITH ... AS (...), so the outer query's
# FROM <cte> is not mistaken for a warehouse table.
_CTE_FIRST_RE = re.compile(r"(?i)\bwith\b\s+([a-zA-Z_]\w*)\s+as\s*\(")
_CTE_REST_RE = re.compile(r"(?i),\s*([a-zA-Z_]\w*)\s+as\s*\(")

# Words that look like table names to the FROM/JOIN pattern but are
# SQL keywords, so they are never treated as table references.
_KEYWORDS = frozenset("""
select from where join on group order by having limit offset with as
and or not in is null like ilike between union all distinct case when
then else end left right inner outer full cross natural using values
into over partition window rows range unbounded preceding following
current row asc desc true false cast extract pivot unpivot
""".split())


def _blank_noncode(sql: str) -> str:
    """Return sql with string literals and comments replaced by spaces.

    All guardrail checks run on this view, so a blocked word inside a
    string literal (WHERE note = 'copy this') is left alone and a
    blocked word hiding inside a comment is still caught. Positions
    are preserved, so later slicing still lines up.
    """
    out = list(sql)
    i, n = 0, len(sql)
    in_str: str | None = None

    def _blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        ch = sql[i]
        if in_str:
            if ch == in_str:
                if i + 1 < n and sql[i + 1] == in_str:
                    out[i] = out[i + 1] = " "
                    i += 2
                    continue
                out[i] = " "
                in_str = None
            else:
                if ch != "\n":
                    out[i] = " "
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            out[i] = " "
            i += 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            _blank(i, j)
            i = j
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            _blank(i, j)
            i = j
            continue
        i += 1
    return "".join(out)


def _split_statements(sql: str) -> list[str]:
    """Split sql at top-level semicolons, ignoring ones inside strings."""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    in_str: str | None = None
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if in_str:
            cur.append(ch)
            if ch == in_str:
                if i + 1 < n and sql[i + 1] == in_str:
                    cur.append(sql[i + 1])
                    i += 1
                else:
                    in_str = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            cur.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            cur.append(sql[i:j])
            i = j
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            cur.append(sql[i:j])
            i = j
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def _cte_names(code: str) -> set[str]:
    """Names bound by WITH ... AS (...) clauses."""
    names = {m.group(1).lower() for m in _CTE_FIRST_RE.finditer(code)}
    names |= {m.group(1).lower() for m in _CTE_REST_RE.finditer(code)}
    return names


def _allowed_tables(con) -> set[str]:
    """Tables the read path may touch: the curated SQL list, confirmed
    present in the warehouse via information_schema."""
    present = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema IN ('main', 'public')"
        ).fetchall()
    }
    try:
        from .tools import league as _league

        curated = set(_league._SQL_TABLES)
    except Exception:
        curated = set()
    if curated:
        return present & curated
    return present


def _check(sql: str, allowed: set[str]) -> str:
    """Validate sql. Returns the normalized statement or raises ValueError
    with a message the caller passes straight to the agent."""
    text = (sql or "").strip()
    if not text:
        raise ValueError("empty SQL")
    stmts = [s for s in _split_statements(text) if s.strip()]
    if len(stmts) > 1:
        raise ValueError("blocked: only one statement per call; "
                         "multiple statements are not allowed")
    stmt = stmts[0].rstrip().rstrip(";").strip()
    code = _blank_noncode(stmt)
    if not _FIRST_WORD_RE.match(code):
        raise ValueError("blocked: only SELECT and WITH queries are allowed")
    if _WRITE_RE.search(code):
        raise ValueError("blocked: write operations are not allowed; "
                         "SELECT/WITH only")
    if _TABLE_FN_RE.search(code):
        raise ValueError("blocked: filesystem and network table "
                         "functions are not allowed")
    if _PATHY_FROM_RE.search(stmt):
        raise ValueError("blocked: raw file paths are not allowed; "
                         "query the warehouse tables")
    refs = {a or b for a, b in _TABLE_REF_RE.findall(code)}
    refs = {r for r in refs
            if r.lower() not in _KEYWORDS and r.lower() not in _cte_names(code)}
    unknown = sorted(r for r in refs if r not in allowed)
    if unknown:
        raise ValueError("blocked: unknown table(s): " + ", ".join(unknown))
    return stmt


def _run_with_timeout(con, sql: str, timeout_s: float,
                      max_rows: int) -> tuple[list[str], list[tuple], bool]:
    """Run sql on con in a worker thread. If it outlives timeout_s, the
    connection is closed to abort it and TimeoutError is raised."""
    out: dict = {}

    def _run() -> None:
        try:
            rel = con.execute(sql)
            cols = [d[0] for d in con.description]
            rows = rel.fetchmany(max_rows + 1)
            out["result"] = (cols, rows, len(rows) > max_rows)
        except Exception as exc:
            out["error"] = exc

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        try:
            con.close()
        except Exception:
            pass
        raise TimeoutError(f"query exceeded {timeout_s:g}s")
    if "error" in out:
        raise out["error"]
    return out["result"]


def query_warehouse(sql: str, max_rows: int = ROW_CAP,
                    timeout_s: float = STATEMENT_TIMEOUT_S) -> dict:
    """Run one read-only SELECT/WITH statement against the warehouse.

    Returns columns, rows (list of dicts), and a truncated flag that is
    True when the row cap cut the result short. Errors are honest:
    blocked statements say what was blocked and why, timeouts say how
    long the query ran, and syntax failures carry the database message.
    """
    try:
        cap = max(1, min(int(max_rows or ROW_CAP), ROW_CAP))
    except (TypeError, ValueError):
        cap = ROW_CAP
    t0 = time.monotonic()
    con = store.connect(read_only=True)
    try:
        allowed = _allowed_tables(con)
        if not allowed:
            return {"tool": "query_warehouse", "ok": False,
                    "error": "warehouse has no queryable tables"}
        try:
            stmt = _check(sql, allowed)
        except ValueError as vexc:
            return {"tool": "query_warehouse", "ok": False,
                    "error": str(vexc)}
        try:
            cols, rows, truncated = _run_with_timeout(con, stmt, timeout_s, cap)
        except TimeoutError:
            return {"tool": "query_warehouse", "ok": False,
                    "error": f"timed out after {timeout_s:g}s"}
        except Exception as exc:
            msg = str(exc)
            kind = ("syntax error"
                    if isinstance(exc, (duckdb.ParserException,
                                       duckdb.BinderException))
                    else "warehouse read error")
            return {"tool": "query_warehouse", "ok": False,
                    "error": f"{kind}: {msg[:300]}"}
    finally:
        try:
            con.close()
        except Exception:
            pass
    ms = int((time.monotonic() - t0) * 1000)
    kept = rows[:cap]
    return {
        "tool": "query_warehouse",
        "ok": True,
        "columns": cols,
        "rows": [dict(zip(cols, r)) for r in kept],
        "truncated": truncated,
        "meta": {"ms": ms, "returned": len(kept), "row_cap": cap,
                 "timeout_s": timeout_s},
    }
