import difflib
from typing import Any

from langchain_core.tools import tool

from .common import (
    call_sync,
    finish_strict_rows,
    sanitize_for_wire,
)
from .errors import enrich_error
from .sql_hints import schema_hint_for_sql_failure


def _normalize_sql_result(res: dict[str, Any]) -> dict[str, Any]:
    rows = res.get("rows")
    if not res.get("ok"):
        res["rows"] = []
        res["columns"] = []
    elif not isinstance(rows, list):
        res["ok"] = False
        message = f"sql_exec returned {type(rows).__name__} rows, expected a list"
        upstream_error = res.get("error")
        res["error"] = (
            f"{upstream_error}; {message}"
            if isinstance(upstream_error, str) and upstream_error
            else message
        )
        res["rows"] = []
        res["columns"] = []
    else:
        res["rows"] = [r if isinstance(r, dict) else {"value": r} for r in rows]
        cols = res.get("columns")
        res["columns"] = (
            cols if isinstance(cols, list)
            else list(res["rows"][0].keys()) if res["rows"] else []
        )
    res["ok"] = bool(res.get("ok", False))
    if not res["ok"]:
        enrich_error("sql_exec", res)
    return sanitize_for_wire(res)


def _select_schema_tables(columns: dict[str, Any], tables: list[str] | None) -> tuple[list[str], dict[str, Any] | None]:
    if tables is None:
        return list(columns), None
    selected: list[str] = []
    unknown: list[str] = []
    for name in dict.fromkeys(tables):
        if name in columns:
            selected.append(name)
        else:
            unknown.append(name)
    if unknown:
        suggestions = {
            name: difflib.get_close_matches(name, list(columns), n=3, cutoff=0.5)
            for name in unknown
        }
        suggestions = {k: v for k, v in suggestions.items() if v}
        return [], sanitize_for_wire(enrich_error("warehouse_schema", {
            "tool": "warehouse_schema",
            "ok": False,
            "error": (
                "unknown declared table(s) in tables selection: "
                f"{', '.join(unknown)}; omit tables for the full declared schema"
            ),
            "tables": {},
            "columns": [],
            "did_you_mean": suggestions,
        }))
    if not selected:
        return [], sanitize_for_wire(enrich_error("warehouse_schema", {
            "tool": "warehouse_schema",
            "ok": False,
            "error": (
                "tables selection must name at least one declared table; "
                "omit tables for the full declared schema"
            ),
            "tables": {},
            "columns": [],
        }))
    return selected, None


def _wrap_dict_or_list(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        return [raw_rows]
    return []


def _python_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        return [raw_rows]
    return [{"printed": str(raw_rows or ""), "out": None}]


def register() -> dict[str, Any]:
    from shared.tools.sql_exec import sql_exec as _orig_sql_exec, TABLES
    from shared.tools.league import (
        _get_warehouse_schema,
        get_warehouse_freshness as _orig_get_warehouse_freshness,
    )
    from shared.tools.season_semantics import annotate_schema
    try:
        from shared.tools.watchlist import get_watchlist
    except ImportError:
        from backend.shared.tools.watchlist import get_watchlist

    declared_catalog = ", ".join(TABLES)
    schema_description = (
        "Read declared warehouse columns, source units and season encodings. "
        "Pass tables to return only those declared tables (avoiding full catalog payloads). "
        f"Declared table allowlist: {declared_catalog}. "
        "This allowlist names declared tables, not proof of actual table content, "
        "complete warehouse inventory or data freshness. "
        "catalog_scope covers the returned declared tables and columns only, not the full warehouse "
        "inventory; a name absent here is not evidence it is absent everywhere."
    )

    @tool("sql_exec", description=_orig_sql_exec.description)
    async def sql_exec(sql: str) -> dict:
        try:
            res = await _orig_sql_exec.ainvoke({"sql": sql})
            if not isinstance(res, dict):
                res = {"tool": "sql_exec", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "sql_exec", "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        hint = schema_hint_for_sql_failure(sql, res)
        if hint is not None:
            res["schema_hint"] = hint
        return _normalize_sql_result(res)

    @tool("warehouse_schema", description=schema_description)
    def warehouse_schema(tables: list[str] | None = None) -> dict:
        try:
            _, columns = _get_warehouse_schema()
        except Exception as exc:
            return sanitize_for_wire(enrich_error("warehouse_schema", {
                "tool": "warehouse_schema",
                "ok": False,
                "error": f"warehouse unavailable: {exc}",
                "tables": {},
                "columns": [],
                "catalog_scope": {
                    "kind": "declared_read_only_tables",
                    "exhaustive_warehouse_inventory": False,
                    "available_table_count": 0,
                    "returned_table_count": 0,
                    "negative_claim_scope": "warehouse unavailable",
                },
            }))
        selected, err = _select_schema_tables(columns, tables)
        if err is not None:
            return err
        annotated = annotate_schema({"tables": {name: columns[name] for name in selected}})
        if 'silver_hist_lineups' in selected:
            annotated['lineup_variant_policy'] = (
                "Filter season_type (regular-season/playoffs), measure_type "
                "(base/advanced/defense/misc/opponent/scoring/usage), per_mode (totals/pergame). "
                "Default regular-season/base/totals; never sum across variants. "
                "Ratings/pace require matching advanced row on group_id, team_id, _season, season_type, per_mode.")
        annotated["catalog_scope"] = {
            "kind": "declared_read_only_tables",
            "exhaustive_warehouse_inventory": False,
            "available_table_count": len(columns),
            "returned_table_count": len(selected),
            "negative_claim_scope": "returned declared tables and columns only",
        }
        try:
            from shared.tools.data_dictionary import dictionary_for_tables
            dictionary = dictionary_for_tables(selected)
        except Exception:
            dictionary = None
        if dictionary is not None:
            annotated["data_dictionary"] = dictionary
        annotated["tool"] = "warehouse_schema"
        annotated["ok"] = True
        return sanitize_for_wire(annotated)

    @tool("get_warehouse_freshness", description=_orig_get_warehouse_freshness.description)
    def get_warehouse_freshness() -> dict:
        res = call_sync(_orig_get_warehouse_freshness, "get_warehouse_freshness", {})
        default_cols = ["table", "rows", "last_fetch", "stale"]
        if not res.get("ok"):
            res["rows"] = []
            res["columns"] = default_cols
            res["ok"] = False
            return sanitize_for_wire(enrich_error("get_warehouse_freshness", res))
        rows = _wrap_dict_or_list(res.get("rows"))
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = True
        return sanitize_for_wire(res)

    @tool("get_dataset", description="Query the Dime Data Engine for standardized silver analytical datasets (standings, leaders, ratings, injuries, player_gamelogs, team_games, scoreboard, shots, lineups, on_off, wowy, four_factors, hustle, combine, playoffs, draft, raptor, player_seasons).")
    def get_dataset(
        name: str,
        season: str = "2026-27",
        player_id: int = 0,
        team_id: int = 0,
        game_id: str = "",
        game_date: str = "",
        stat: str = "PTS",
        ids: str = "",
        player_a: str = "",
        player_b: str = "",
        fmt: str = "json",
    ) -> dict:
        from analyst.dataset_engine import dataset as _run_dataset
        try:
            res = _run_dataset(
                name=name, season=season, player_id=player_id, team_id=team_id,
                game_id=game_id, game_date=game_date, stat=stat, ids=ids,
                player_a=player_a, player_b=player_b, fmt=fmt,
            )
            if not isinstance(res, dict) or res.get("ok") is False:
                err = res.get("error") if isinstance(res, dict) else res
                return sanitize_for_wire(enrich_error("get_dataset", {
                    "ok": False, "tool": "get_dataset", "rows": [], "columns": [],
                    "error": str(err or "Dataset query failed"),
                }))
        except Exception as exc:
            return sanitize_for_wire(enrich_error("get_dataset", {
                "ok": False, "tool": "get_dataset", "rows": [], "columns": [],
                "error": str(exc),
            }))
        rows = res.get("data") if isinstance(res.get("data"), list) else res.get("rows", [])
        if not isinstance(rows, list):
            rows = []
        columns = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
        return sanitize_for_wire({
            "ok": True, "tool": "get_dataset", "name": name, "season": season,
            "rows": rows, "columns": columns, "meta": res.get("meta", {}),
        })

    @tool("get_dataset_freshness", description="Query current ingestion freshness and coverage timestamps across all Dime Data Engine silver warehouse tables.")
    def get_dataset_freshness() -> dict:
        from analyst.dataset_engine import datasets_freshness as _run_freshness
        cols = ["table", "rows", "last_fetch", "data_through"]
        try:
            res = _run_freshness()
            if not isinstance(res, dict) or res.get("ok") is False:
                err = res.get("error") if isinstance(res, dict) else res
                return sanitize_for_wire(enrich_error("get_dataset_freshness", {
                    "ok": False, "tool": "get_dataset_freshness", "rows": [],
                    "columns": cols, "error": str(err or "Dataset freshness check failed"),
                }))
        except Exception as exc:
            return sanitize_for_wire(enrich_error("get_dataset_freshness", {
                "ok": False, "tool": "get_dataset_freshness", "rows": [],
                "columns": cols, "error": str(exc),
            }))
        rows = res.get("rows") if isinstance(res.get("rows"), list) else []
        return sanitize_for_wire({
            "ok": True, "tool": "get_dataset_freshness", "rows": rows, "columns": cols,
        })

    @tool("run_python", description="Execute read-only Python code over the warehouse DuckDB connection (con), polars (pl), numpy (np), math, and statistics. Useful for ad-hoc statistical modeling, linear algebra, shrinkage, and aggregations.")
    def run_python(code: str) -> dict:
        from shared.tools.shared import run_python as _orig_run_python
        res = call_sync(_orig_run_python, "run_python", {"code": code})
        default_cols = ["printed", "out"]
        return finish_strict_rows(
            res, "run_python", default_cols, str(res.get("error") or "Python execution failed"),
            _python_rows,
        )

    return {
        "sql_exec": sql_exec,
        "warehouse_schema": warehouse_schema,
        "get_warehouse_freshness": get_warehouse_freshness,
        "get_watchlist": get_watchlist,
        "get_dataset": get_dataset,
        "get_dataset_freshness": get_dataset_freshness,
        "run_python": run_python,
    }
