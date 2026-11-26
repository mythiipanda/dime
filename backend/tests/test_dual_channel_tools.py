from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "backend/analyst/runtime.ts").read_text()


def test_core_tools_get_direct_exposure():
    assert 'DIRECT_CHANNEL_TOOLS = new Set([' in SRC
    for name in ["submit_answer", "verify_answer_numbers", "run_status", "load_skill", "sql_exec", "run_python", "warehouse_schema"]:
        assert f'"{name}"' in SRC, f"{name} must be a direct-channel tool"
    assert 'exposure: DIRECT_CHANNEL_TOOLS.has(tool.name) ? "direct" : "codemode"' in SRC


def test_active_set_includes_direct_channel_tools():
    assert 'setActiveToolsByName(["codemode", ...[...DIRECT_CHANNEL_TOOLS]' in SRC
