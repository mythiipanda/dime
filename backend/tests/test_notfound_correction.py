from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "backend/analyst/pi-execution.ts").read_text()


def test_correction_fires_per_occurrence_in_subscribe_not_turn_end_only():
    sub = SRC.index("session.subscribe(event =>")
    handler = SRC[sub:sub + 2400]
    assert "scannedToolResults" in handler, "the per-occurrence scan must live in the subscribe handler"
    assert "notFoundCorrections < 3" in SRC, "per-occurrence firing capped at 3, not single-use"


def test_correction_names_direct_tool_call_channel():
    assert "submit_answer is a direct tool you invoke as a tool_call in your response" in SRC
    assert "never JavaScript, never inside codemode" in SRC


def test_correction_drops_full_tool_list():
    seg_start = SRC.index("Correction: nothing is missing")
    seg = SRC[seg_start:seg_start + 900]
    assert "The same holds for sql_exec, verify_answer_numbers and the warehouse tools" in seg
    assert "Available right now:" not in seg, "no full bridge tool enumeration in the correction"
