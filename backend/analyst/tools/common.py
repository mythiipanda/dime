import asyncio
import concurrent.futures
from datetime import date, datetime
from decimal import Decimal
import math
import sys
import threading
from typing import Any, Callable

import numpy as np

from .errors import enrich_error
from .schemas import LIVE_CALL_TIMEOUT_S, NETWORK_TOOL_SOURCES, PARAM_KINDS, WAREHOUSE_ALTERNATIVES


def _normalize_or_result(name: str, args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from shared.tools.argnorm import ArgMiss, arg_miss_result, normalize_call_args
    try:
        return normalize_call_args(name, args, PARAM_KINDS), None
    except ArgMiss as miss:
        return args, enrich_error(name, arg_miss_result(name, miss))
    except Exception:
        return args, None


def _config_module() -> Any:
    return sys.modules.get("analyst.python_tools") or sys.modules.get("python_tools")


def get_live_timeout_s() -> float:
    mod = _config_module()
    if mod is not None and hasattr(mod, "LIVE_CALL_TIMEOUT_S"):
        return float(mod.LIVE_CALL_TIMEOUT_S)
    return LIVE_CALL_TIMEOUT_S


def _get_network_sources() -> dict[str, str]:
    mod = _config_module()
    if mod is not None and hasattr(mod, "NETWORK_TOOL_SOURCES"):
        return mod.NETWORK_TOOL_SOURCES
    return NETWORK_TOOL_SOURCES


def _get_warehouse_alternatives() -> dict[str, str]:
    mod = _config_module()
    if mod is not None and hasattr(mod, "WAREHOUSE_ALTERNATIVES"):
        return mod.WAREHOUSE_ALTERNATIVES
    return WAREHOUSE_ALTERNATIVES


def sanitize_for_wire(val: Any) -> Any:
    if val is None or isinstance(val, (str, bool, int)):
        return val
    if isinstance(val, (float, np.floating)):
        return None if (math.isnan(val) or math.isinf(val)) else float(val)
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, np.ndarray):
        return sanitize_for_wire(val.tolist())
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return int(val) if val.as_tuple().exponent >= 0 else float(val)
    if isinstance(val, dict):
        return {str(k): sanitize_for_wire(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [sanitize_for_wire(x) for x in val]
    return val


_sanitize_floats = sanitize_for_wire


def wire_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value.as_tuple().exponent >= 0 else float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if (math.isnan(value) or math.isinf(value)) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    raise TypeError(f"Data result is not JSON serializable: {type(value).__name__}")


def _network_meta(name: str) -> tuple[str, str]:
    return _get_network_sources()[name], _get_warehouse_alternatives()[name]


def _live_timeout_error(name: str, source: str, alternative: str) -> str:
    timeout = get_live_timeout_s()
    return (
        f"{name} timed out after {timeout:.1f}s: the upstream "
        f"source is a live {source} call, not the warehouse. Retry later, or "
        f"answer from the warehouse-backed {alternative} tool."
    )


def _timeout_error(name: str) -> str:
    if name in _get_network_sources():
        source, alternative = _network_meta(name)
        return _live_timeout_error(name, source, alternative)
    timeout = get_live_timeout_s()
    return (
        f"{name} timed out after {timeout:.1f}s; "
        "the read did not complete in time; retry later"
    )


def _apply_future(future: asyncio.Future[Any], value: Any, error: Exception | None) -> None:
    if future.done():
        return
    if error is None:
        future.set_result(value)
    else:
        future.set_exception(error)



def disclose_scoped_season(result: Any, normed: dict[str, Any]) -> Any:
    if not isinstance(result, dict) or result.get("ok") is not True:
        return result
    meta = result.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("season"), str) and meta["season"].strip():
        return result
    from shared.tools.argnorm import canonical_season, _FIELD_KINDS
    values = set()
    for field, kind in _FIELD_KINDS.items():
        if kind != "season" or field not in normed:
            continue
        canon = canonical_season(normed[field])
        if canon:
            values.add(canon)
    if len(values) != 1:
        return result
    if not isinstance(meta, dict):
        meta = {}
        result["meta"] = meta
    meta["season"] = sorted(values)[0]
    return result


async def _bounded_live_call(orig: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[Any] = loop.create_future()

    def _worker() -> None:
        try:
            normed, miss = _normalize_or_result(name, args)
            value = miss if miss is not None else orig.invoke(normed)
            err = None
        except Exception as error:
            value = None
            err = error
        try:
            loop.call_soon_threadsafe(_apply_future, future, value, err)
        except RuntimeError:
            return

    threading.Thread(target=_worker, daemon=True).start()
    done, _pending = await asyncio.wait({future}, timeout=get_live_timeout_s())
    if not done:
        future.cancel()
        return enrich_error(name, {"tool": name, "ok": False, "rows": [], "columns": [],
                                   "error": _timeout_error(name)})
    error = future.exception()
    if error is not None:
        return enrich_error(name, {"tool": name, "ok": False,
                                   "error": f"{type(error).__name__}: {error}"})
    raw = future.result()
    if not isinstance(raw, dict):
        return enrich_error(name, {"tool": name, "ok": False, "error": str(raw)})
    return disclose_scoped_season(raw, args)


async def _execute_tool_bounded(tools: dict[str, Any], name: str,
                                arguments: dict[str, Any]) -> dict[str, Any]:
    def _invoke() -> Any:
        normed, miss = _normalize_or_result(name, arguments)
        if miss is not None:
            return miss
        return disclose_scoped_season(asyncio.run(tools[name].ainvoke(normed)), normed)

    if name not in _get_network_sources():
        result = await asyncio.to_thread(_invoke)
        return enrich_error(name, result) if isinstance(result, dict) else result
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_invoke), get_live_timeout_s())
        return enrich_error(name, result) if isinstance(result, dict) else result
    except asyncio.TimeoutError:
        return enrich_error(name, {"tool": name, "ok": False, "rows": [], "columns": [],
                                   "error": _timeout_error(name)})


def call_sync(orig: Any, name: str, args: dict[str, Any], include_exc_type: bool = True) -> dict[str, Any]:
    try:
        normed, miss = _normalize_or_result(name, args)
        if miss is not None:
            return miss
        res = orig.invoke(normed)
        if not isinstance(res, dict):
            return {"tool": name, "ok": False, "error": str(res)}
        return disclose_scoped_season(res, normed)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}" if include_exc_type else str(exc)
        return {"tool": name, "ok": False, "error": msg}


def call_async_in_sync(orig: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        normed, miss = _normalize_or_result(name, args)
        if miss is not None:
            return miss
        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                res = pool.submit(asyncio.run, orig.ainvoke(normed)).result()
        else:
            res = asyncio.run(orig.ainvoke(normed))
        if not isinstance(res, dict):
            return {"tool": name, "ok": False, "error": str(res)}
        return disclose_scoped_season(res, normed)
    except Exception as exc:
        return {"tool": name, "ok": False, "error": str(exc)}


def _section_rows(name: str, value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [{**item, "section": name} if isinstance(item, dict) else {"value": item, "section": name}
                for item in value]
    if isinstance(value, dict):
        return [{**value, "section": name}]
    return [{"value": value, "section": name}]


def _flatten_sections(res: dict[str, Any], default_cols: list[str], name: str = "") -> dict[str, Any]:
    raw_rows = res.get("rows")
    rows: list[dict[str, Any]] = []
    if res.get("ok") and isinstance(raw_rows, dict):
        for sec_name, value in raw_rows.items():
            rows.extend(_section_rows(sec_name, value))
    res["rows"] = rows
    res["columns"] = list(rows[0].keys()) if rows else default_cols
    res["ok"] = bool(res.get("ok", False))
    if not res["ok"]:
        enrich_error(name or str(res.get("tool") or "tool"), res)
    return sanitize_for_wire(res)


async def _sectioned_result(orig: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        res = await orig.ainvoke(args)
        if not isinstance(res, dict):
            res = {"tool": name, "ok": False, "error": str(res)}
    except Exception as exc:
        res = {"tool": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    raw_rows = res.get("rows")
    if res.get("ok") and not isinstance(raw_rows, dict):
        res["ok"] = False
        message = f"{name} returned {type(raw_rows).__name__} rows, expected a section object"
        upstream_error = res.get("error")
        res["error"] = (f"{upstream_error}; {message}"
                        if isinstance(upstream_error, str) and upstream_error
                        else message)
    return _flatten_sections(res, ["section"], name=name)


def _row_list_result(res: dict[str, Any], name: str, default_cols: list[str]) -> dict[str, Any]:
    raw_rows = res.get("rows")
    if res.get("ok") and not isinstance(raw_rows, list):
        res["ok"] = False
        message = f"{name} returned {type(raw_rows).__name__} rows, expected a list"
        upstream_error = res.get("error")
        res["error"] = (f"{upstream_error}; {message}"
                        if isinstance(upstream_error, str) and upstream_error
                        else message)
    if res.get("ok") and isinstance(raw_rows, list):
        rows = [r if isinstance(r, dict) else {"value": r} for r in raw_rows]
    else:
        rows = []
    res["rows"] = rows
    res["columns"] = list(rows[0].keys()) if rows else default_cols
    res["ok"] = bool(res.get("ok", False))
    if not res["ok"]:
        enrich_error(name, res)
    return sanitize_for_wire(res)


def _section_object_result(res: dict[str, Any], name: str, default_cols: list[str]) -> dict[str, Any]:
    raw_rows = res.get("rows")
    if res.get("ok") and not isinstance(raw_rows, dict):
        res["ok"] = False
        message = f"{name} returned {type(raw_rows).__name__} rows, expected a section object"
        upstream_error = res.get("error")
        res["error"] = (f"{upstream_error}; {message}"
                        if isinstance(upstream_error, str) and upstream_error
                        else message)
    return _flatten_sections(res, default_cols, name=name)


def finish_dict_list(res: dict[str, Any], name: str, default_cols: list[str],
                     set_ok: bool = True, sanitize: bool = True,
                     row_filter: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    raw_rows = res.get("rows")
    if res.get("ok") and isinstance(raw_rows, list):
        rows = [r for r in raw_rows if isinstance(r, dict)]
        if row_filter is not None:
            rows = row_filter(rows)
    else:
        rows = []
    res["rows"] = rows
    res["columns"] = list(rows[0].keys()) if rows else default_cols
    if set_ok:
        res["ok"] = bool(res.get("ok", False))
    if not res["ok"]:
        enrich_error(name, res)
    return sanitize_for_wire(res) if sanitize else res


def finish_strict_rows(res: dict[str, Any], name: str, default_cols: list[str],
                       failure_msg: str, build_rows: Callable[[dict[str, Any]], list[dict[str, Any]]],
                       fixed_cols: bool = False,
                       error_cols: list[str] | None = None) -> dict[str, Any]:
    if not res.get("ok"):
        err = res.get("error")
        out = {
            "ok": False,
            "tool": name,
            "rows": [],
            "columns": error_cols if error_cols is not None else default_cols,
            "error": str(err or failure_msg),
        }
        if res.get("recovery_hint"):
            out["recovery_hint"] = res["recovery_hint"]
        return sanitize_for_wire(enrich_error(name, out))
    rows = build_rows(res)
    res["rows"] = rows
    res["columns"] = default_cols if fixed_cols or not rows else list(rows[0].keys())
    res["ok"] = True
    return sanitize_for_wire(res)
