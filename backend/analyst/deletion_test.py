"""Keep the product import graph free of the replaced conversation owners."""
import ast
from pathlib import Path


def test_product_has_no_legacy_orchestration_imports():
    backend = Path(__file__).resolve().parents[1]
    retired = {"v2.runtime." + name for name in (
        "assembly", "loop", "action_loop", "executor", "presentation", "recording", "ledger",
        "checkpoints", "policy", "fast_path", "budget", "analysis_execution")}
    retired.update({"v2.adapters.models", "v2.adapters.structured", "v2.prompts", "v2.skills"})
    for directory in ("app", "analyst", "shared", "v2", "scripts"):
        for path in (backend / directory).rglob("*.py"):
            if "tests" in path.parts or "node_modules" in path.parts or path.name.startswith("test_") or path.name.endswith("_test.py"):
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module] + [node.module + "." + alias.name for alias in node.names]
                assert not retired.intersection(modules), (path, node.lineno, modules)


def test_catalogue_uses_authoritative_tool_schemas():
    from shared.tools import WAREHOUSE_TOOLS
    from v2.adapters.capabilities import CAPABILITIES, capability_catalog, _structural_schema
    tools = {tool.name: tool for tool in WAREHOUSE_TOOLS}
    catalogue = capability_catalog()
    for name, spec in CAPABILITIES.items():
        tool = tools.get(spec.tool_name)
        schema = tool.args_schema.model_json_schema() if tool and tool.args_schema else {"type":"object","properties":{}}
        assert catalogue[name]["arguments"] == _structural_schema(schema)
