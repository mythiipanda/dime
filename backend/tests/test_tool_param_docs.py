import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))


def _tools():
    from analyst import python_tools
    from analyst import direct_data

    return {**python_tools.catalogue(), **direct_data.internal_catalogue()}


def test_every_tool_param_is_documented():
    missing = []
    for name, tool in _tools().items():
        if tool.args_schema is None:
            continue
        schema = tool.args_schema.model_json_schema()
        for param, spec in schema.get("properties", {}).items():
            if not spec.get("description"):
                missing.append(f"{name}.{param}")
    assert missing == [], f"undocumented params: {missing}"


def test_every_tool_has_a_description():
    missing = [name for name, tool in _tools().items() if not (tool.description or "").strip()]
    assert missing == [], f"tools without descriptions: {missing}"
