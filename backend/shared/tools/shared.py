import json as _json
import os as _os
from pathlib import Path as _Path
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
from typing import Any
from langchain_core.tools import tool

@tool(description='Resolve a player or team name to canonical ids. Call before any id tool.\n\nScored general matcher from _core plus Wikipedia suggestions\nwhen nothing in static tables scores above 0.5.')
def resolve_entity(query: str) -> dict[str, Any]:
    try:
        from nba_api.stats.static import teams

        from ._core import (_norm_name, coerce_player_id,
                            score_player_candidates)

        raw = (query or "").strip()
        nq = _norm_name(raw)
        ranked = score_player_candidates(raw)
        p = [{**r, "score": s} for s, r in ranked[:8]]

        if p and _norm_name(p[0].get("full_name", "")) == nq:
            try:
                canonical_id = coerce_player_id(raw)
            except ValueError:
                canonical_id = p[0].get("id")
            if canonical_id != p[0].get("id"):
                p[0]["static_id"] = p[0].get("id")
                p[0]["id"] = canonical_id
                p[0]["identity_source"] = "warehouse_exact_name"
        t = teams.find_teams_by_full_name(raw)[:8]
        if not t:
            all_t = teams.get_teams()
            t = [x for x in all_t
                 if nq and (nq in _norm_name(x.get("full_name", ""))
                            or nq == (x.get("abbreviation", "") or "").lower())][:8]

        exact_team = any(
            nq in {
                _norm_name(x.get("full_name", "")),
                _norm_name(x.get("nickname", "")),
                _norm_name(x.get("abbreviation", "")),
            }
            for x in t
        )
        if exact_team and not (ranked and ranked[0][0] >= 0.95):
            ranked = []
            p = []
        suggestions: list[str] = []
        top = ranked[0][0] if ranked else 0.0
        out = {
            "tool": "resolve_entity",
            "ok": True,
            "rows": {
                "players": p,
                "teams": t,
                "exact": top >= 0.95,
                "suggestions": suggestions,
            },
            "meta": {"source": "nba_api_static"},
        }

        if " " in raw.strip():
            return out
        _act = [(sc, r.get("full_name", "")) for sc, r in ranked
                if r.get("is_active") and r.get("full_name")]
        _exact_full = any(sc >= 0.99 for sc, _ in _act)
        if len(_act) >= 2 and not _exact_full and _act[0][0] >= 0.6:
            names = ", ".join(n for _, n in _act[:3])
            out["ambiguity_note"] = (
                f"'{raw}' loosely matches several active players "
                f"({names}).")
        return out
    except Exception as exc:
        return {"tool": "resolve_entity", "ok": False, "error": str(exc)[:200]}

@tool(description='Find NBA players or teams matching a name. Input is a plain name.')
def search_nba(query: str) -> dict[str, Any]:
    try:
        from nba_api.stats.static import players, teams

        name = query.strip()
        return {
            "tool": "search_nba",
            "ok": True,
            "rows": {
                "players": players.find_players_by_full_name(name)[:8],
                "teams": teams.find_teams_by_full_name(name)[:8],
            },
            "meta": {"source": "nba_api_static"},
        }
    except Exception as exc:
        return {"tool": "search_nba", "ok": False, "error": str(exc)[:200]}

_BOOTSTRAP_SCRIPT = """
import datetime
import decimal
import io
import json
import math
import os
import re
import statistics
import sys
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"

import duckdb
import numpy as np
import polars as pl


def _json_safe(value, depth=0):
    if depth > 6:
        return str(value)[:2000]
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        num = float(value)
        return num if math.isfinite(num) else None
    if isinstance(value, decimal.Decimal):
        num = float(value)
        return num if math.isfinite(num) else None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist(), depth + 1)
    if isinstance(value, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, depth + 1) for item in value]
    return str(value)[:2000]


def _table_hint(con, code):
    if con is None:
        return "", ""
    try:
        rows = con.execute("SHOW TABLES").fetchall()
        valid = sorted(str(r[0]) for r in rows if str(r[0]).startswith("silver_"))
    except Exception:
        valid = []
    hint = ", ".join(valid) if valid else "no silver tables available"
    col_hint = ""
    try:
        for t in valid:
            if re.search(r"\\b" + re.escape(t) + r"\\b", code, re.IGNORECASE):
                cols = con.execute(f"PRAGMA table_info({t})").fetchall()
                names = [str(c[1]) for c in cols if not str(c[1]).startswith("_")]
                col_hint = f" Columns of {t}: " + ", ".join(names[:25])
                break
    except Exception:
        pass
    return col_hint, hint


def _exc_lineno(exc):
    lineno = getattr(exc, "lineno", None)
    if lineno is not None:
        return lineno
    tb = exc.__traceback__
    found = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == "<dime>":
            found = tb.tb_lineno
        tb = tb.tb_next
    return found


def _code_context(code, lineno):
    lines = code.splitlines()
    if lineno is None or not (1 <= lineno <= len(lines)):
        return None
    lo = max(1, lineno - 2)
    hi = min(len(lines), lineno + 2)
    out = []
    for n in range(lo, hi + 1):
        mark = ">>" if n == lineno else "  "
        out.append(f"{mark} {n:4d}| {lines[n - 1][:160]}")
    return "\\n".join(out)


def _serialize_out(out):
    if isinstance(out, pl.DataFrame):
        return _json_safe(out.head(500).to_dicts()), None
    if isinstance(out, list) and all(isinstance(x, dict) for x in out):
        return _json_safe(out[:500]), None
    if isinstance(out, dict):
        safe = _json_safe(out)
        encoded = json.dumps(safe)
        if len(encoded) > 16000:
            return None, encoded[:16000]
        return None, safe
    if isinstance(out, (int, float, bool, np.integer, np.floating)):
        return None, _json_safe(out)
    if out is not None:
        return None, str(out)[:16000]
    return None, None


def _main():
    result_path = Path(os.environ["DIME_PY_RESULT_PATH"])
    db_path = os.environ.get("DIME_WAREHOUSE", "")
    code = sys.stdin.read()
    con = None
    try:
        if db_path:
            con = duckdb.connect(db_path, read_only=True)
    except Exception as exc:
        result_path.write_text(json.dumps({
            "ok": False,
            "error": str(exc)[:300],
            "recovery_hint": "Verify DIME_WAREHOUSE path and warehouse availability.",
        }), encoding="utf-8")
        return
    buf = io.StringIO()
    old_stdout = sys.stdout
    ns = {
        "__builtins__": __builtins__,
        "con": con,
        "pl": pl,
        "np": np,
        "math": math,
        "statistics": statistics,
        "out": None,
    }
    try:
        sys.stdout = buf
        exec(compile(code, "<dime>", "exec"), ns, ns)
    except Exception as exc:
        sys.stdout = old_stdout
        msg = str(exc) or type(exc).__name__
        hints = ("does not exist", "Catalog", "Referenced column", "Binder")
        recovery = "Check Python syntax, variable names, and warehouse column names via warehouse_schema."
        if isinstance(exc, SyntaxError):
            recovery = "Fix the syntax on the marked line of the submitted code, then rerun run_python."
            js_ish = re.search(
                r"`|=>|\\$\\{|\\bconst\\b|\\blet\\b|^return\\s", code, re.M)
            if js_ish:
                recovery = ("run_python executes Python, not JavaScript: replace "
                            "backticks and ${...} with string literals, const/let "
                            "with plain assignment, => with def/lambda, and "
                            "assign the result to `out` or print it instead of "
                            "returning.")
            elif re.match(r"\\s*(SELECT|WITH)\\b", code, re.I):
                recovery = ("run_python executes Python code; raw SQL is not "
                            "valid here. Pass the query as a string to "
                            "con.execute or call sql_exec instead.")
        elif isinstance(exc, NameError) and re.search(r"\\b(store|load)\\s*\\(", code):
            recovery = ("store()/load() exist only in codemode, not in "
                        "run_python: run_python is Python executed fresh per "
                        "call, so keep intermediate results in Python "
                        "variables within the call or write them to files "
                        "under the workspace dir.")
        elif ("Cannot open database" in msg or "duckdb" in msg.lower()) and re.search(r"\\bduckdb\\.connect\\s*\\(", code):
            recovery = ("Do not open warehouse files by guessed path — the "
                        "warehouse is reachable only through the preloaded "
                        "`con` (con.execute(...)). Re-run without "
                        "duckdb.connect().")
        elif any(h in msg for h in hints):
            col_hint, valid_hint = _table_hint(con, code)
            recovery = f"Unknown table or column.{col_hint} Valid tables: {valid_hint}"
            if "sqlite_" in msg and re.search(r"\\bduckdb\\.connect\\s*\\(", code):
                recovery = ("duckdb.connect with a relative or new file path "
                            "(including ':memory:') opens an empty database, so "
                            "no warehouse tables exist on that connection; use "
                            "the preloaded `con` for the warehouse instead of "
                            f"opening a new file. Valid tables: {valid_hint}")
        lineno = _exc_lineno(exc)
        context = _code_context(code, lineno)
        error_text = f"{type(exc).__name__}: {msg}"
        if context:
            error_text += "\\ncode around line " + str(lineno) + ":\\n" + context
        payload = {
            "ok": False,
            "error": error_text[:1200],
            "error_type": type(exc).__name__,
            "stdout": buf.getvalue()[:16000],
            "recovery_hint": recovery,
        }
        if lineno is not None:
            payload["error_line"] = lineno
        if context:
            payload["code_context"] = context
        result_path.write_text(json.dumps(payload), encoding="utf-8")
        return
    finally:
        sys.stdout = old_stdout
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
    text = buf.getvalue()[:16000]
    structured_rows, out_val = _serialize_out(ns.get("out"))
    workspace_files = sorted(
        str(p.relative_to(".")).replace("\\\\", "/")
        for p in Path(".").rglob("*")
        if p.is_file()
    )[:200]
    payload = {
        "ok": True,
        "structured_rows": structured_rows,
        "out_val": out_val,
        "stdout": text,
        "workspace_files": workspace_files,
    }
    if con is not None and ns.get("con") is not con:
        payload["warning"] = (
            "Your code rebound `con` to a different DuckDB connection; a bare "
            "duckdb.connect() (or ':memory:'/new file) opens an empty database "
            "with no warehouse tables. The warehouse is only reachable through "
            "the preloaded `con`: do not reassign it, re-run with con.execute(...) "
            "against the provided connection."
        )
    result_path.write_text(json.dumps(payload), encoding="utf-8")


_main()
"""

_SAFE_ENV_KEYS = (
    "SystemRoot",
    "WINDIR",
    "PATH",
    "LANG",
    "LC_ALL",
    "PYTHONPATH",
    "PYTHONNOUSERSITE",
    "CONDA_PREFIX",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)

def _workspace_dir() -> tuple[_Path, bool]:
    configured = _os.environ.get("DIME_THREAD_WORKSPACE", "").strip()
    if configured:
        path = _Path(configured)
        path.mkdir(parents=True, exist_ok=True)
        return path, False
    return _Path(_tempfile.mkdtemp(prefix="dime-py-")), True

def _clean_subprocess_env(workspace: _Path, db_path: _Path, result_path: _Path) -> dict[str, str]:
    env = {k: _os.environ[k] for k in _SAFE_ENV_KEYS if _os.environ.get(k)}
    env.update({
        "HOME": str(workspace),
        "USERPROFILE": str(workspace),
        "TEMP": str(workspace),
        "TMP": str(workspace),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "POLARS_MAX_THREADS": "1",
        "MPLBACKEND": "Agg",
        "PYTHONDONTWRITEBYTECODE": "1",
        "DIME_WAREHOUSE": str(db_path),
        "DIME_THREAD_WORKSPACE": str(workspace),
        "DIME_PY_RESULT_PATH": str(result_path),
    })
    return env

def _format_subprocess_result(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("ok"):
        out: dict[str, Any] = {
            "tool": "run_python",
            "ok": False,
            "error": str(payload.get("error") or "Python execution failed")[:1200],
        }
        for key in ("error_type", "error_line", "code_context"):
            if payload.get(key) is not None:
                out[key] = payload[key]
        if payload.get("recovery_hint"):
            out["recovery_hint"] = str(payload["recovery_hint"])
        if payload.get("stdout"):
            out["stdout"] = str(payload["stdout"])[:16000]
        return out
    structured_rows = payload.get("structured_rows")
    text = str(payload.get("stdout") or "")[:16000]
    workspace_files = list(payload.get("workspace_files") or [])
    if structured_rows is not None:
        rows_payload: Any = structured_rows
    else:
        rows_payload = {
            "printed": text,
            "out": payload.get("out_val"),
            "workspace_files": workspace_files,
        }
    out_ok: dict[str, Any] = {
        "tool": "run_python",
        "ok": True,
        "rows": rows_payload,
        "stdout": text,
        "workspace_files": workspace_files,
        "meta": {"source": "warehouse", "workspace_files": workspace_files},
    }
    if payload.get("warning"):
        out_ok["warning"] = str(payload["warning"])
    return out_ok

@tool(description='Run isolated Python in the thread workspace with read-only DuckDB warehouse access.\n\nPreloaded: con (read-only DuckDB connection), pl (polars), np (numpy), math, statistics. Standard scientific imports (scipy, statsmodels, sklearn, matplotlib, duckdb, polars, json, pathlib) are allowed and workspace files persist across turns for identified threads. Print to stdout or assign `out`. Each call runs up to 240 seconds; aggregate and filter large tables in SQL first so Python iterates over compact arrays, and split resampling loops across calls when a single pass would exceed the cap.')
def run_python(code: str) -> dict[str, Any]:
    from ..store import DB_PATH

    if not code or not str(code).strip():
        return {"tool": "run_python", "ok": False, "error": "empty code"}
    workspace, ephemeral = _workspace_dir()
    fd, raw_result_path = _tempfile.mkstemp(prefix="dime-py-res-", suffix=".json")
    _os.close(fd)
    result_path = _Path(raw_result_path)
    try:
        env = _clean_subprocess_env(workspace, _Path(DB_PATH), result_path)
        try:
            proc = _subprocess.run(
                [_sys.executable, "-B", "-c", _BOOTSTRAP_SCRIPT],
                input=str(code),
                cwd=str(workspace),
                env=env,
                capture_output=True,
                text=True,
                timeout=240,
            )
        except _subprocess.TimeoutExpired:
            return {
                "tool": "run_python",
                "ok": False,
                "error": "run_python timed out after 240s",
                "recovery_hint": "Filter rows in SQL before Python modeling or reduce iteration count.",
            }
        raw = result_path.read_text(encoding="utf-8") if result_path.exists() else ""
        if not raw.strip():
            err = (proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
            return {
                "tool": "run_python",
                "ok": False,
                "error": err[:500],
                "recovery_hint": "Check script imports, memory usage, or stderr output.",
            }
        return _format_subprocess_result(_json.loads(raw))
    finally:
        try:
            result_path.unlink(missing_ok=True)
        except Exception:
            pass
        if ephemeral:
            _shutil.rmtree(workspace, ignore_errors=True)
