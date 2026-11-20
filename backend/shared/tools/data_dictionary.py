import json as _json
from pathlib import Path
from typing import Any

from .. import store as _store

_cache: dict[str, Any] = {"path": None, "mtime_ns": None, "doc": None}


def dictionary_path() -> Path:
    return Path(_store.DB_PATH).parent / "data_dictionary.json"


def load_data_dictionary() -> dict[str, Any] | None:
    path = dictionary_path()
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        _cache.update({"path": None, "mtime_ns": None, "doc": None})
        return None
    if (_cache["path"] == path and _cache["mtime_ns"] == mtime_ns
            and _cache["doc"] is not None):
        return _cache["doc"]
    try:
        doc = _json.loads(path.read_text())
    except (OSError, ValueError):
        _cache.update({"path": None, "mtime_ns": None, "doc": None})
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("tables"), dict):
        _cache.update({"path": None, "mtime_ns": None, "doc": None})
        return None
    _cache.update({"path": path, "mtime_ns": mtime_ns, "doc": doc})
    return doc


def dictionary_for_tables(names: list[str]) -> dict[str, Any] | None:
    doc = load_data_dictionary()
    if doc is None:
        return None
    tables = doc["tables"]
    out = {name: tables[name] for name in names if name in tables}
    if not out:
        return None
    return {
        "warehouse_sha256": doc.get("warehouse_sha256"),
        "generated_at": doc.get("generated_at"),
        "entries": out,
    }


def clear_data_dictionary_cache() -> None:
    _cache.update({"path": None, "mtime_ns": None, "doc": None})
