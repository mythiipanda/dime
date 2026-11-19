import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import latency_benchmark as lb


def test_percentile_median_even():
    assert lb.percentile([1, 2, 3, 4], 50) == 2.5


def test_percentile_p95_interpolates():
    assert lb.percentile([1, 2, 3, 4], 95) == 3.85


def test_percentile_median_odd():
    assert lb.percentile([1, 2, 3, 4, 5], 50) == 3.0


def test_percentile_single_value():
    assert lb.percentile([7], 90) == 7.0


def test_percentile_empty_is_none():
    assert lb.percentile([], 50) is None


def test_percentile_sorts_input():
    assert lb.percentile([3, 1, 2], 50) == 2.0


def test_percentile_zero_and_hundred():
    assert lb.percentile([1, 2, 3, 4], 0) == 1.0
    assert lb.percentile([1, 2, 3, 4], 100) == 4.0


def test_extract_numbers_skips_season():
    assert lb.extract_numbers("Trae Young recorded 880 assists in 2024-25") == [880.0]


def test_extract_numbers_decimal():
    assert lb.extract_numbers("net rating of 8.3") == [8.3]


def test_extract_numbers_comma_grouped():
    assert lb.extract_numbers("1,230 games were played") == [1230.0]


def test_extract_numbers_none():
    assert lb.extract_numbers("no digits here") == []


def test_extract_numbers_bare_season_is_none():
    assert lb.extract_numbers("the 2024-25 season") == []


def test_extract_numbers_multiple():
    assert lb.extract_numbers("116.3 points per game over 82 games") == [116.3, 82.0]


def test_score_golden_exact_int():
    assert lb.score_golden(880, "880") is True


def test_score_golden_int_in_sentence():
    assert lb.score_golden(880, "He recorded 880 assists.") is True


def test_score_golden_within_tolerance():
    assert lb.score_golden(8.3, "8.3001") is True


def test_score_golden_outside_tolerance():
    assert lb.score_golden(8.3, "9.0") is False


def test_score_golden_string_casefold():
    assert lb.score_golden("Trae Young", "trae young") is True


def test_score_golden_string_trailing_punct():
    assert lb.score_golden("Trae Young", "Trae Young.") is True


def test_score_golden_string_mismatch():
    assert lb.score_golden("Trae Young", "Nikola Jokic") is False


def test_score_golden_no_numbers_in_answer():
    assert lb.score_golden(1230, "no numbers here") is False


def test_score_golden_numeric_string_expected():
    assert lb.score_golden("880", "880 assists") is True


def test_parse_sse_named_events():
    raw = (
        'event: thought_stream\n'
        'data: {"text": "Working"}\n'
        '\n'
        'event: final_answer\n'
        'data: {"text": "880", "run_id": "abc"}\n'
        '\n'
    )
    events = lb.parse_sse_events(raw)
    assert events == [
        ("thought_stream", {"text": "Working"}),
        ("final_answer", {"text": "880", "run_id": "abc"}),
    ]


def test_parse_sse_bare_data_lines():
    raw = (
        'data: {"run_id": "x", "text": "hi"}\n'
        '\n'
        'data: {"text": "tok"}\n'
        '\n'
    )
    events = lb.parse_sse_events(raw)
    assert events == [
        (None, {"run_id": "x", "text": "hi"}),
        (None, {"text": "tok"}),
    ]


def test_parse_sse_skips_done_and_bad_json():
    raw = (
        'data: [DONE]\n'
        '\n'
        'data: not json\n'
        '\n'
        'event: ping\n'
        'data: {"ok": true}\n'
        '\n'
    )
    assert lb.parse_sse_events(raw) == [("ping", {"ok": True})]


def test_summarize_ttft_answer_tools():
    frames = [
        (0.5, "thought_stream", {"text": "Working"}),
        (1.0, "tool_result", {"name": "get_standings", "ms": 250}),
        (2.0, "final_answer", {"text": "880", "run_id": "r1"}),
    ]
    out = lb.summarize_frames(frames)
    assert out["ttft_s"] == 0.5
    assert out["answer_text"] == "880"
    assert out["tool_durations"] == {"get_standings": 0.25}
    assert out["tool_status"] == "measured"
    assert out["error"] is None


def test_summarize_legacy_schema_answer_selection():
    frames = [
        (0.1, None, {"node": "x", "text": "narr"}),
        (0.2, None, {"text": "tok"}),
        (0.3, None, {"run_id": "r", "text": "final"}),
    ]
    out = lb.summarize_frames(frames)
    assert out["answer_text"] == "final"
    assert out["ttft_s"] == 0.1


def test_summarize_legacy_fallback_concats_tokens():
    frames = [
        (0.1, None, {"text": "he"}),
        (0.2, None, {"text": "llo"}),
    ]
    out = lb.summarize_frames(frames)
    assert out["answer_text"] == "hello"


def test_summarize_carry_run_id_answer():
    frames = [
        (0.4, "x", {"text": "narr"}),
        (1.2, "y", {"text": "ans", "carry": {"run_id": "r9"}}),
    ]
    out = lb.summarize_frames(frames)
    assert out["answer_text"] == "ans"


def test_summarize_tool_ms_summed_per_tool():
    frames = [
        (0.1, "tool_result", {"name": "t", "ms": 100}),
        (0.2, "tool_result", {"name": "t", "ms": 200}),
        (0.3, "tool_result", {"name": "u", "ms": 50}),
    ]
    out = lb.summarize_frames(frames)
    assert out["tool_durations"] == {"t": 0.3, "u": 0.05}
    assert out["tool_status"] == "measured"


def test_summarize_tool_call_without_timing():
    frames = [(0.1, "tool_call", {"name": "t"})]
    out = lb.summarize_frames(frames)
    assert out["tool_durations"] == {}
    assert out["tool_status"] == "measured"


def test_summarize_no_tool_frames_unavailable():
    frames = [(0.1, "thought_stream", {"text": "hi"})]
    out = lb.summarize_frames(frames)
    assert out["tool_durations"] == {}
    assert out["tool_status"] == "unavailable"


def test_summarize_error_event():
    frames = [(0.2, "error", {"message": "The answer didn't finish. Ask again."})]
    out = lb.summarize_frames(frames)
    assert out["error"] == "The answer didn't finish. Ask again."


def test_summarize_empty_stream():
    out = lb.summarize_frames([])
    assert out["answer_text"] == ""
    assert out["ttft_s"] is None
    assert out["error"] == "empty stream"


def _record(task_id, total, ttft, tools, correct, error=None, cost=None, cost_status="unavailable"):
    return {
        "task_id": task_id,
        "question": "q",
        "expected": 1,
        "answer_text": "a",
        "total_s": total,
        "ttft_s": ttft,
        "tool_durations": tools,
        "tool_status": "measured" if tools else "unavailable",
        "golden_correct": correct,
        "error": error,
        "cost_usd": cost,
        "cost_status": cost_status,
    }


def test_scoreboard_aggregates():
    records = [
        _record("a", 10.0, 1.0, {"t": 2.0}, True),
        _record("b", 20.0, 2.0, {"t": 4.0}, True),
        _record("c", 30.0, 3.0, {"t": 6.0, "u": 1.0}, False),
        _record("d", 40.0, 4.0, {"t": 8.0}, True),
    ]
    board = lb.build_scoreboard(records)
    assert board["n"] == 4
    assert board["p50_total_s"] == 25.0
    assert board["p95_total_s"] == 38.5
    assert board["p95_ttft_s"] == 3.85
    assert board["top_tool"] == "t"
    assert board["top_tool_p95_s"] == 7.7
    assert board["golden_acc"] == 0.75
    assert board["errors"] == 0
    assert board["cost_status"] == "unavailable"


def test_scoreboard_counts_errors_and_nulls_times():
    records = [
        _record("a", 10.0, 1.0, {}, True),
        _record("b", None, None, {}, None, error="boom"),
    ]
    board = lb.build_scoreboard(records)
    assert board["errors"] == 1
    assert board["p50_total_s"] == 10.0
    assert board["golden_acc"] == 1.0
    assert board["top_tool"] is None
    assert board["top_tool_p95_s"] is None


def test_scoreboard_all_errored():
    records = [_record("a", None, None, {}, None, error="x")]
    board = lb.build_scoreboard(records)
    assert board["p50_total_s"] is None
    assert board["p95_ttft_s"] is None
    assert board["golden_acc"] is None
    assert board["errors"] == 1


def test_scoreboard_cost_measured_rollup():
    records = [
        _record("a", 10.0, 1.0, {}, True, cost=0.01, cost_status="measured"),
        _record("b", 20.0, 2.0, {}, True, cost=0.03, cost_status="measured"),
    ]
    board = lb.build_scoreboard(records)
    assert board["cost_usd_per_query"] == 0.02
    assert board["cost_status"] == "measured"


def test_regression_latency_breach():
    baseline = {"medians": {"p50_total_s": 10.0, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.9}}
    candidate = {"p50_total_s": 11.5, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.9}
    verdict, reasons = lb.check_regression(baseline, candidate, 10.0)
    assert verdict == "REGRESSION"
    assert any("p50_total_s" in r for r in reasons)


def test_regression_within_threshold_passes():
    baseline = {"medians": {"p50_total_s": 10.0, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.9}}
    candidate = {"p50_total_s": 10.5, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.9}
    verdict, reasons = lb.check_regression(baseline, candidate, 10.0)
    assert verdict == "PASS"
    assert reasons == []


def test_regression_golden_acc_drop():
    baseline = {"medians": {"p50_total_s": 10.0, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.9}}
    candidate = {"p50_total_s": 10.0, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.75}
    verdict, reasons = lb.check_regression(baseline, candidate, 10.0)
    assert verdict == "REGRESSION"
    assert any("golden_acc" in r for r in reasons)


def test_regression_golden_acc_small_drop_passes():
    baseline = {"medians": {"p50_total_s": 10.0, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.9}}
    candidate = {"p50_total_s": 10.0, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.85}
    verdict, _ = lb.check_regression(baseline, candidate, 10.0)
    assert verdict == "PASS"


def test_regression_skips_none_metrics():
    baseline = {"medians": {"p50_total_s": 10.0, "p95_total_s": None, "p95_ttft_s": 2.0, "golden_acc": None}}
    candidate = {"p50_total_s": 10.0, "p95_total_s": 99.0, "p95_ttft_s": 2.0, "golden_acc": 0.0}
    verdict, _ = lb.check_regression(baseline, candidate, 10.0)
    assert verdict == "PASS"


def test_baseline_medians():
    runs = [
        {"scoreboard": {"p50_total_s": 10.0, "p95_total_s": 20.0, "p95_ttft_s": 2.0, "golden_acc": 0.8}},
        {"scoreboard": {"p50_total_s": 12.0, "p95_total_s": 22.0, "p95_ttft_s": 3.0, "golden_acc": 0.9}},
        {"scoreboard": {"p50_total_s": 14.0, "p95_total_s": 24.0, "p95_ttft_s": 4.0, "golden_acc": 1.0}},
    ]
    medians = lb.baseline_medians(runs)
    assert medians == {
        "p50_total_s": 12.0,
        "p95_total_s": 22.0,
        "p95_ttft_s": 3.0,
        "golden_acc": 0.9,
    }


def test_clean_proxy_env_strips_bracketed():
    env = {"NO_PROXY": "localhost,[::1],127.0.0.1", "no_proxy": "[fe80::1],example.com"}
    out = lb.clean_proxy_env(env)
    assert out == {"NO_PROXY": "localhost,127.0.0.1", "no_proxy": "example.com"}


def test_clean_proxy_env_keeps_plain():
    env = {"NO_PROXY": "localhost,127.0.0.1"}
    assert lb.clean_proxy_env(env) == env


def test_load_questions_accepts_numeric_answers(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text('{"task_id": "g-001", "question": "q?", "answer": 880}\n{"task_id": "g-002", "question": "q?", "answer": "x"}\n', encoding="utf-8")
    rows = lb.load_questions(str(path))
    assert [r["answer"] for r in rows] == [880, "x"]


def test_load_questions_rejects_bad_answer(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text('{"task_id": "g-001", "question": "q?", "answer": true}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        lb.load_questions(str(path))


def test_summarize_legacy_run_id_chunks_concatenated():
    frames = [
        (0.1, None, {"run_id": "r", "text": "he"}),
        (0.2, None, {"run_id": "r", "text": "llo"}),
    ]
    out = lb.summarize_frames(frames)
    assert out["answer_text"] == "hello"


def test_main_freeze_requires_three_runs(tmp_path):
    out = tmp_path / "o"
    code = lb.main(["--freeze", "--runs", "1", "--out", str(out)])
    assert code == 2


def test_main_rejects_zero_runs(tmp_path):
    out = tmp_path / "o"
    code = lb.main(["--runs", "0", "--out", str(out)])
    assert code == 2


def test_score_golden_string_expected_with_number_scores_numeric():
    assert lb.score_golden("880 assists", "880") is True


def _fake_record(error=None, kind=None):
    return {
        "task_id": "g-001", "question": "q", "expected": "1", "answer_text": "",
        "total_s": None, "ttft_s": None, "tool_durations": {}, "tool_status": "unavailable",
        "golden_correct": None, "error": error, "_error_kind": kind,
        "cost_usd": None, "cost_status": "unavailable",
    }


def test_run_once_aborts_on_consecutive_transport_errors(monkeypatch):
    calls = []
    def fake(client, url, headers, timeout, row):
        calls.append(row["task_id"])
        return _fake_record(error="Timeout: x", kind="transport")
    monkeypatch.setattr(lb, "run_question", fake)
    monkeypatch.setattr(lb, "REQUEST_PAUSE_S", 0)
    rows = [{"task_id": "g-%03d" % i, "question": "q", "answer": "1"} for i in range(1, 8)]
    with pytest.raises(RuntimeError):
        lb._run_once(None, "u", {}, 1.0, rows, "run-01", None)
    assert len(calls) == 5


def test_run_once_continues_past_sse_errors(monkeypatch):
    def fake(client, url, headers, timeout, row):
        return _fake_record(error="sse error", kind="sse")
    monkeypatch.setattr(lb, "run_question", fake)
    monkeypatch.setattr(lb, "REQUEST_PAUSE_S", 0)
    rows = [{"task_id": "g-%03d" % i, "question": "q", "answer": "1"} for i in range(1, 8)]
    run = lb._run_once(None, "u", {}, 1.0, rows, "run-01", None)
    assert len(run["questions"]) == 7
    assert run["scoreboard"]["errors"] == 7
    assert all("_error_kind" not in r for r in run["questions"])
