from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "backend/analyst/pi-execution.ts").read_text()


def test_correction_fires_per_occurrence_in_subscribe_not_turn_end_only():
    sub = SRC.index("session.subscribe(event =>")
    handler = SRC[sub:sub + 2400]
    assert "scannedToolResults" in handler, "the per-occurrence scan must live in the subscribe handler"
    assert "notFoundCorrections < 6" in SRC, "per-occurrence firing capped at 6, not single-use"
    assert "correctedNotFoundNames.has" in SRC, "dedupe by malformed name so startup clusters do not burn the cap"


def test_correction_names_direct_tool_call_channel():
    assert "submit_answer is a direct tool you invoke as a tool_call in your response" in SRC
    assert "never JavaScript, never inside codemode" in SRC


def test_correction_drops_full_tool_list():
    seg_start = SRC.index("Correction: nothing is missing")
    seg = SRC[seg_start:seg_start + 900]
    assert "The same holds for sql_exec and verify_answer_numbers" in seg
    assert "they are never direct tool_calls" in seg, "warehouse tools must not be instructed as direct calls — they are codemode-exposure only"
    assert "await tools.<name>" in seg, "the correction names the real codemode invocation form"
    assert "invoke them as direct tool_calls by bare name. Retry" not in seg, "the old impossible-instruction form must be gone"
    assert "Available right now:" not in seg, "no full bridge tool enumeration in the correction"



def test_correction_events_carry_malformed_name():
    assert 'args: { malformed: notFound[1] }' in SRC, "correction tool_call event must carry the malformed name for archive observability"
    assert 'corrected malformed tool name: ${notFound[1]}' in SRC, "correction tool_result must name the malformed tool"
