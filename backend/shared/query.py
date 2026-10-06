
import threading
import time

import duckdb
import sqlglot
from sqlglot import exp

from . import store

ROW_CAP = 500
STATEMENT_TIMEOUT_S = 30

_READ_STMTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)

_SAFE_FUNCTIONS = frozenset("""
case if coalesce nullif ifnull greatest least
cast try_cast
count sum avg mean min max median quantile quantile_cont quantile_disc
mode stddev stddev_pop stddev_samp var_pop var_samp variance
string_agg group_concat listagg list_agg array_agg bool_and bool_or
approx_count_distinct arg_max arg_min corr covar_pop covar_samp
regr_slope regr_intercept regr_count regr_r2 regr_avgx regr_avgy
regr_sxx regr_syy regr_sxy first last any_value min_by max_by
product histogram approx_quantile skewness kurtosis list
row_number rank dense_rank percent_rank cume_dist ntile
lag lead first_value last_value nth_value
abs ceil ceiling floor round trunc sqrt cbrt pow power exp
ln log log10 log2 sign mod div gcd lcm factorial
degrees radians sin cos tan asin acos atan atan2 pi
even isinf isfinite isnan random uuid
lower upper length len char_length character_length
trim ltrim rtrim btrim substr substring left right
reverse repeat replace concat concat_ws starts_with ends_with
contains position strpos str_position instr split_part string_split
regexp_matches regexp_replace regexp_extract
lpad rpad chr ascii unicode md5 sha256 format printf
overlay translate levenshtein
now current_date current_timestamp current_time
year month day hour minute second week quarter dow doy epoch
date_part datepart date_trunc datediff date_diff dateadd date_add
age make_date make_time make_timestamp strftime monthname dayname
extract
array list_value struct struct_pack row
list_contains list_has typeof
""".split())

def _split_statements(sql: str) -> list[str]:
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

def _parse_one(stmt: str) -> exp.Expression:
    try:
        trees = [t for t in sqlglot.parse(stmt, read="duckdb")
                 if t is not None]
    except Exception as exc:
        raise ValueError(f"syntax error: could not parse SQL ({exc})")
    if not trees:
        raise ValueError("blocked: only SELECT and WITH queries are allowed")
    if len(trees) > 1:
        raise ValueError("blocked: only one statement per call; "
                         "multiple statements are not allowed")
    return trees[0]

def _func_name(fn: exp.Func) -> str:
    if isinstance(fn, exp.Anonymous):
        return fn.name.lower()
    return fn.sql_name().lower()

def _allowed_tables(con) -> set[str]:
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

_READ_SCHEMAS = frozenset({"main", "public", "memory"})

def _resolve_table(tbl: exp.Table, allowed: set[str],
                   scope: dict[str, bool]) -> None:
    name = (tbl.name or "").lower()
    if not name:
        raise ValueError("blocked: table functions are not allowed; "
                         "query the warehouse tables")
    db = (tbl.db or "").lower()
    catalog = (tbl.catalog or "").lower()
    if db or catalog:
        if db not in _READ_SCHEMAS and db != "":
            raise ValueError("blocked: unknown table(s): " + tbl.name)
        if catalog not in _READ_SCHEMAS and catalog != "":
            raise ValueError("blocked: unknown table(s): " + tbl.name)
        if name not in allowed:
            raise ValueError("blocked: unknown table(s): " + tbl.name)
        return
    if name not in allowed and name not in scope:
        raise ValueError("blocked: unknown table(s): " + tbl.name)

def _walk_tables(node: exp.Expression, allowed: set[str],
                 scope: dict[str, bool]) -> None:
    if isinstance(node, exp.Table):
        _resolve_table(node, allowed, scope)
        return
    local = dict(scope)
    with_node = node.args.get("with", node.args.get("with_"))
    if isinstance(with_node, exp.With):
        if with_node.args.get("recursive"):
            for cte in with_node.expressions:
                if cte.alias:
                    local[cte.alias.lower()] = True
        for cte in with_node.expressions:
            _walk_tables(cte.this, allowed, dict(local))
            if cte.alias:
                local[cte.alias.lower()] = True
    for child in node.args.values():
        if isinstance(child, exp.Expression):
            _walk_tables(child, allowed, local)
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, exp.Expression):
                    _walk_tables(item, allowed, local)

def _check(sql: str, allowed: set[str]) -> str:
    text = (sql or "").strip()
    if not text:
        raise ValueError("empty SQL")
    stmts = [s for s in _split_statements(text) if s.strip()]
    if len(stmts) > 1:
        raise ValueError("blocked: only one statement per call; "
                         "multiple statements are not allowed")
    stmt = stmts[0].rstrip().rstrip(";").strip()
    tree = _parse_one(stmt)
    if not isinstance(tree, _READ_STMTS):
        raise ValueError("blocked: only SELECT and WITH queries are allowed")
    for sel in tree.find_all(exp.Select):
        if sel.args.get("into") is not None:
            raise ValueError("blocked: SELECT ... INTO is not allowed; "
                             "it creates a table")
    cte_names = {c.alias.lower() for c in tree.find_all(exp.CTE)
                 if c.alias}
    ok_tables = {t.lower() for t in allowed}
    shadowed = sorted(cte_names & ok_tables)
    if shadowed:
        raise ValueError("blocked: CTE name shadows warehouse table(s): "
                         + ", ".join(shadowed))
    _walk_tables(tree, ok_tables, {})
    for src in list(tree.find_all(exp.From)) + list(tree.find_all(exp.Join)):
        node = src.args.get("this")
        while isinstance(node, exp.Lateral):
            node = node.this
        if isinstance(node, exp.Func):
            raise ValueError("blocked: table functions are not allowed; "
                             "query the warehouse tables")
    for fn in tree.find_all(exp.Func):
        fname = _func_name(fn)
        if fname not in _SAFE_FUNCTIONS:
            raise ValueError("blocked: function not allowed: " + fname)
    return stmt

def _run_with_timeout(con, sql: str, timeout_s: float,
                      max_rows: int) -> tuple[list[str], list[tuple], bool]:
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
