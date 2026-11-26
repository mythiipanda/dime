from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = (ROOT / "backend/analyst/runtime.ts").read_text()
EXEC = (ROOT / "backend/analyst/pi-execution.ts").read_text()


def test_submit_answer_taught_as_direct_tool_everywhere():
    assert "await tools.submit_answer" not in RUNTIME, "system prompt must not teach the codemode form"
    assert "call tools.submit_answer" not in EXEC, "steers must not teach the prefixed form"
    assert "tools.submit_answer is available" not in EXEC
    assert "no tools. prefix" in RUNTIME


def test_verify_answer_taught_as_direct_tool():
    assert "await tools.verify_answer_numbers" not in RUNTIME
