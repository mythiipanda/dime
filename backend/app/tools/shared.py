"""Identity tools. Resolve names to canonical ids before any id tool."""

import re as _re
from typing import Any
from langchain_core.tools import tool


@tool
def resolve_entity(query: str) -> dict[str, Any]:
    """Resolve a player or team name to canonical ids. Call before any id tool."""
    try:
        from nba_api.stats.static import players, teams

        from ._core import NICKNAMES

        raw = NICKNAMES.get(query.strip().lower(), query.strip())
        name = raw.lower()
        p = players.find_players_by_full_name(raw)[:8]
        if not p:
            seen: set[int] = set()
            p = []
            for fn in (players.find_players_by_last_name,
                       players.find_players_by_first_name):
                try:
                    for x in fn(raw)[:8]:
                        if x.get("id") not in seen:
                            seen.add(x.get("id"))
                            p.append(x)
                except Exception:
                    pass
        if not p:
            all_p = players.get_players()
            p = [x for x in all_p if name in x.get("full_name", "").lower()][:8]
        t = teams.find_teams_by_full_name(raw)[:8]
        if not t:
            all_t = teams.get_teams()
            t = [x for x in all_t
                 if name in x.get("full_name", "").lower()
                 or name == x.get("abbreviation", "").lower()][:8]
        exact_p = [x for x in p if x.get("full_name", "").lower() == name]
        exact_t = [x for x in t if x.get("full_name", "").lower() == name]
        return {
            "tool": "resolve_entity",
            "ok": True,
            "rows": {
                "players": exact_p or p,
                "teams": exact_t or t,
                "exact": bool(exact_p or exact_t),
            },
            "meta": {"source": "nba_api_static"},
        }
    except Exception as exc:
        return {"tool": "resolve_entity", "ok": False, "error": str(exc)[:200]}


@tool
def search_nba(query: str) -> dict[str, Any]:
    """Find NBA players or teams matching a name. Input is a plain name."""
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


_CODE_BANNED = (
    "import ", "import(", "__", "os.", "sys.", "open(",
    "exec(", "eval(", "compile(", "subprocess", "socket",
    "pathlib", "shutil", "globals(", "locals(", "vars(",
    "getattr(", "setattr(", "delattr(", "input(",
)


@tool
def run_python(code: str) -> dict[str, Any]:
    """Run read-only Python over the warehouse. Tables: any silver_* table.

    Available: con (read-only DuckDB connection), pl (polars), math,
    statistics. SELECT via con.execute("...").fetchall(). No imports,
    no writes, no network. Print or set `out`. Output capped.
    """
    import io as _io
    import math as _math
    import statistics as _stats
    from contextlib import redirect_stdout as _redir

    import duckdb as _ddb
    import polars as _pl

    from ..store import DB_PATH

    lowered = str(code or "").lower()
    if not code or not code.strip():
        return {"tool": "run_python", "ok": False, "error": "empty code"}
    if any(b in lowered for b in _CODE_BANNED):
        return {"tool": "run_python", "ok": False,
                "error": "blocked construct (imports, IO, and writes banned)"}
    if _re.search(r"\b(insert|update|delete|drop|alter|create|attach|copy)\b",
                   lowered):
        return {"tool": "run_python", "ok": False,
                "error": "writes banned, SELECT only"}
    try:
        con = _ddb.connect(str(DB_PATH), read_only=True)
    except Exception as exc:
        return {"tool": "run_python", "ok": False, "error": str(exc)[:160]}
    buf = _io.StringIO()
    g: dict[str, Any] = {"con": con, "pl": _pl, "math": _math,
                         "statistics": _stats, "out": None}
    try:
        with _redir(buf):
            exec(compile(str(code), "<dime>", "exec"),
                 {"__builtins__": __builtins__}, g)
    except Exception as exc:
        msg = str(exc)
        if "does not exist" in msg or "Catalog" in msg:
            try:
                rows = con.execute("SHOW TABLES").fetchall()
                valid = sorted(str(r[0]) for r in rows
                               if str(r[0]).startswith("silver_"))
            except Exception:
                valid = []
            hint = ", ".join(valid) if valid else "no silver tables available"
            return {"tool": "run_python", "ok": False,
                    "error": f"unknown table. Valid tables: {hint}"}
        return {"tool": "run_python", "ok": False, "error": str(exc)[:300]}
    finally:
        try:
            con.close()
        except Exception:
            pass
    text = buf.getvalue()[:2000]
    out = g.get("out")
    if out is not None:
        try:
            out = str(out)[:2000]
        except Exception:
            out = None
    return {"tool": "run_python", "ok": True,
            "rows": {"printed": text, "out": out},
            "meta": {"source": "warehouse"}}
