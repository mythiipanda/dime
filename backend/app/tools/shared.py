"""Identity tools. Resolve names to canonical ids before any id tool."""

import re as _re
from typing import Any
from langchain_core.tools import tool


@tool
def resolve_entity(query: str) -> dict[str, Any]:
    """Resolve a player or team name to canonical ids. Call before any id tool.

    Scored general matcher from _core plus Wikipedia suggestions
    when nothing in static tables scores above 0.5.
    """
    try:
        from nba_api.stats.static import teams

        from ._core import _norm_name, score_player_candidates

        raw = (query or "").strip()
        nq = _norm_name(raw)
        ranked = score_player_candidates(raw)
        p = [{**r, "score": s} for s, r in ranked[:8]]
        t = teams.find_teams_by_full_name(raw)[:8]
        if not t:
            all_t = teams.get_teams()
            t = [x for x in all_t
                 if nq and (nq in _norm_name(x.get("full_name", ""))
                            or nq == (x.get("abbreviation", "") or "").lower())][:8]
        suggestions: list[str] = []
        top = ranked[0][0] if ranked else 0.0
        return {
            "tool": "resolve_entity",
            "ok": True,
            "rows": {
                "players": [{**x, "score": s} for s, x in ranked],
                "teams": t,
                "exact": top >= 0.95,
                "suggestions": suggestions,
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
                "error": "That code pattern is unavailable. "
                         "con, pl, math, statistics are already preloaded; "
                         "imports/IO/writes are unavailable. "
                         "Query with e.g. "
                         "rows = con.execute(\"SELECT * FROM silver_standings "
                         "LIMIT 5\").fetchall(); print(rows)"}
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
        if ("does not exist" in msg or "Catalog" in msg
                or "Referenced column" in msg or "Binder" in msg):
            try:
                rows = con.execute("SHOW TABLES").fetchall()
                valid = sorted(str(r[0]) for r in rows
                               if str(r[0]).startswith("silver_"))
            except Exception:
                valid = []
            hint = ", ".join(valid) if valid else "no silver tables available"
            col_hint = ""
            try:
                import re as _re2

                for t in valid:
                    if _re2.search(r"\b" + _re2.escape(t) + r"\b", code,
                                   _re2.IGNORECASE):
                        cols = con.execute(
                            f"PRAGMA table_info({t})").fetchall()
                        names = [str(c[1]) for c in cols
                                 if not str(c[1]).startswith("_")]
                        col_hint = f" Columns of {t}: " + ", ".join(names[:25]
                                                                     )
                        break
            except Exception:
                pass
            return {"tool": "run_python", "ok": False,
                    "error": f"unknown table or column.{col_hint} "
                             f"Valid tables: {hint}"}
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
