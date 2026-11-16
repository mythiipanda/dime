import importlib.util
import sys
from pathlib import Path

if "--write-golden" not in sys.argv[1:]:
    raise SystemExit("pass --write-golden to regenerate backend/tests/tool_schema_golden.json")

BACKEND = Path(__file__).resolve().parents[1]
TEST = BACKEND / "tests" / "test_tool_schema_golden.py"
spec = importlib.util.spec_from_file_location("tool_schema_golden_test", TEST)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.GOLDEN.write_bytes(module._serialize(module._snapshot()))
print(f"wrote {module.GOLDEN}")
