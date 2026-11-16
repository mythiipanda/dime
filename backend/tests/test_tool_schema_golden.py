import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "tool_schema_golden.json"
TS_SOURCE = BACKEND / "analyst" / "python-tools.ts"
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


def _snapshot():
    from analyst import python_tools
    from analyst import direct_data

    return {
        "catalogue": _capture(python_tools.catalogue()),
        "internal": _capture(direct_data.internal_catalogue()),
    }


def _serialize(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _typescript_names():
    source = TS_SOURCE.read_text(encoding="utf-8")
    block = source.split("export const ANALYST_TOOL_NAMES: readonly PythonToolName[] = [", 1)[1]
    block = block.split("] as const;", 1)[0]
    return re.findall(r'"([^"]+)"', block)


def _golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_golden_file_is_canonical_serialization():
    assert GOLDEN.read_bytes() == _serialize(_golden())


def test_catalogue_golden_matches_live():
    assert _serialize(_golden()["catalogue"]) == _serialize(_snapshot()["catalogue"])


def test_internal_golden_matches_live():
    assert _serialize(_golden()["internal"]) == _serialize(_snapshot()["internal"])


def test_live_catalogue_names_match_typescript_list():
    from analyst import python_tools

    assert list(python_tools.catalogue().keys()) == _typescript_names()


def test_golden_catalogue_names_match_typescript_list():
    assert list(_golden()["catalogue"].keys()) == _typescript_names()


def test_snapshot_is_byte_deterministic():
    assert _serialize(_snapshot()) == _serialize(_snapshot())
