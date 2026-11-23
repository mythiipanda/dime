import json
from pathlib import Path

LIVE_CALL_TIMEOUT_S = 12.0

_MANIFEST = json.loads((Path(__file__).resolve().parent / "manifest.json").read_text())
_TOOLS = _MANIFEST["tools"]

TOOL_ORDER = tuple(t["name"] for t in _TOOLS)

TOOL_DESCRIPTIONS = {t["name"]: t["description"] for t in _TOOLS if "description" in t}

NETWORK_TOOL_SOURCES = {
    t["name"]: t["network_source"] for t in _TOOLS if "network_source" in t
}

LIVE_ONLY_TOOLS = {
    t["name"]: t["live_only_fallback"] for t in _TOOLS if "live_only_fallback" in t
}

WAREHOUSE_QUERY_TOOL = _MANIFEST["warehouse_query_tool"]
WAREHOUSE_FALLBACK_TOOL = _MANIFEST["warehouse_fallback_tool"]

WAREHOUSE_ALTERNATIVES = {
    name: (
        LIVE_ONLY_TOOLS[name] if name in LIVE_ONLY_TOOLS
        else WAREHOUSE_FALLBACK_TOOL if name == WAREHOUSE_QUERY_TOOL
        else WAREHOUSE_QUERY_TOOL
    )
    for name in NETWORK_TOOL_SOURCES
}

TOOL_SCHEMA_DESCRIPTIONS = {
    t["name"]: t["schema_description"] for t in _TOOLS if "schema_description" in t
}

PARAM_SCHEMA_DESCRIPTIONS = _MANIFEST["shared_params"]

TOOL_PARAM_DESCRIPTIONS = {
    (t["name"], field): doc
    for t in _TOOLS
    for field, doc in t.get("params", {}).items()
}

PARAM_KINDS = {
    tool: dict(fields)
    for tool, fields in _MANIFEST.get("param_kinds", {}).items()
}
