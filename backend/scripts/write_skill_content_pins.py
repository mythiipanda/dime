import importlib.util
import sys
from pathlib import Path

if "--write-pins" not in sys.argv[1:]:
    raise SystemExit("pass --write-pins to regenerate backend/tests/skill_content_pins.json")

BACKEND = Path(__file__).resolve().parents[1]
TEST = BACKEND / "tests" / "test_skill_content_pins.py"
spec = importlib.util.spec_from_file_location("skill_content_pins_test", TEST)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.PINS.write_bytes(module._serialize(module._normalized_snapshot()))
print(f"wrote {module.PINS}")
