import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "tool_schema_golden.json"
TS_SOURCE = BACKEND / "analyst" / "python-tools.ts"
SHARED_TOOL_NAMES = ("get_tracking_profile", "get_defensive_matchups", "get_transactions")
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))


def _capture(tools):
    result = {}
    for name, tool in tools.items():
        schema = tool.args_schema.model_json_schema() if tool.args_schema is not None else None
        result[name] = {
            "name": tool.name,
            "description": tool.description,
            "args_schema": schema,
        }
    return result


def _shared_snapshot():
    from shared.tools import WAREHOUSE_TOOLS

    by_name = {tool.name: tool for tool in WAREHOUSE_TOOLS}
    return _capture({name: by_name[name] for name in SHARED_TOOL_NAMES})


def _snapshot():
    from analyst import python_tools
    from analyst import direct_data

    return {
        "catalogue": _capture(python_tools.catalogue()),
        "internal": _capture(direct_data.internal_catalogue()),
        "shared": _shared_snapshot(),
    }


def _serialize(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _typescript_names():
    manifest = json.loads(TS_SOURCE.with_name("tools").joinpath("manifest.json").read_text(encoding="utf-8"))
    return [t["name"] for t in manifest["tools"]]


def _golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_golden_file_is_canonical_serialization():
    assert GOLDEN.read_bytes() == _serialize(_golden())


def test_catalogue_golden_matches_live():
    assert _serialize(_golden()["catalogue"]) == _serialize(_snapshot()["catalogue"])


def test_internal_golden_matches_live():
    assert _serialize(_golden()["internal"]) == _serialize(_snapshot()["internal"])


def test_shared_golden_matches_live():
    assert _serialize(_golden()["shared"]) == _serialize(_snapshot()["shared"])


def test_golden_shared_names():
    golden = _golden()["shared"]
    live = _snapshot()["shared"]
    assert list(golden.keys()) == list(SHARED_TOOL_NAMES)
    for name in SHARED_TOOL_NAMES:
        assert golden[name]["description"] == live[name]["description"]
        assert golden[name]["args_schema"] == live[name]["args_schema"]


def test_live_catalogue_names_match_typescript_list():
    from analyst import python_tools

    assert list(python_tools.catalogue().keys()) == _typescript_names()


def test_golden_catalogue_names_match_typescript_list():
    assert list(_golden()["catalogue"].keys()) == _typescript_names()


def test_snapshot_is_byte_deterministic():
    assert _serialize(_snapshot()) == _serialize(_snapshot())
