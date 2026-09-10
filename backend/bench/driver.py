"""Async driver. Runs tasks sequentially against app.graph.run_chat."""

import asyncio
import json
import time

from app.graph import run_chat, tool_label
from app.tools import TOOL_NAMES

from .schemas import GroundTruth, RunResult, Task
from .scoring import groundedness, name_recall, numeric_acc, tool_f1

_DELEGATES = ["delegate_scout", "delegate_team", "delegate_league"]


def _label_to_name() -> dict[str, str]:
    table: dict[str, str] = {}
    for name in list(TOOL_NAMES) + _DELEGATES:
        table.setdefault(tool_label(name), name)
    return table


_LABEL_TO_NAME = _label_to_name()


async def _collect(task: Task, model: str | None) -> tuple[
        list, str, str, int | None]:
    tool_calls: list = []
    payloads: list[str] = []
    answer = ""
    ttft_ms: int | None = None
    t0 = time.perf_counter()

    def _mark_ttft() -> None:
        nonlocal ttft_ms
        if ttft_ms is None:
            ttft_ms = int((time.perf_counter() - t0) * 1000)

    async for event in run_chat(task.question, model, []):
        kind = event.get("type", "")
        data = event.get("data", {}) or {}
        # Stream carries exact tool names via tool_call events; arg
        # summaries only (raw args are not emitted).
        if kind == "tool_call":
            name = data.get("name") or _LABEL_TO_NAME.get(
                data.get("label", ""), data.get("label", ""))
            if name:
                tool_calls.append({"name": name, "args": {
                    "summary": str(data.get("summary", ""))}})
                _mark_ttft()
        elif kind == "node_update" and data.get("node") == "tools":
            _mark_ttft()
        elif kind == "custom_data" and data.get("tables") is not None:
            try:
                payloads.append(json.dumps(data["tables"], default=str))
            except (TypeError, ValueError):
                pass
        elif kind == "final_answer":
            answer = str(data.get("text", "") or "")
        elif kind == "graph_end":
            break
    return tool_calls, answer, " ".join(payloads), ttft_ms


async def run_task(task: Task, truth: GroundTruth,
                   model: str | None) -> RunResult:
    t0 = time.perf_counter()
    try:
        tool_calls, answer, payloads, ttft = await asyncio.wait_for(
            _collect(task, model), timeout=task.timeout_s)
        ok, error = True, ""
    except asyncio.TimeoutError:
        tool_calls, answer, payloads, ttft = [], "", "", None
        ok, error = False, "timeout"
    except Exception as exc:
        tool_calls, answer, payloads, ttft = [], "", "", None
        ok, error = False, str(exc)[:200]
    latency_ms = int((time.perf_counter() - t0) * 1000)
    if ok:
        scores = {
            "tool_f1": tool_f1(
                [c["name"] for c in tool_calls], task.gold_tool_families),
            "numeric_acc": numeric_acc(truth.facts, answer),
            "groundedness": groundedness(answer, payloads),
            "name_recall": name_recall(truth.facts, answer),
        }
    else:
        scores = {"tool_f1": 0.0, "numeric_acc": 0.0, "groundedness": 0.0,
                  "name_recall": 0.0}
    return RunResult(
        task_id=task.task_id, ok=ok, error=error, tool_calls=tool_calls,
        final_answer=answer, latency_ms=latency_ms,
        ttft_ms=ttft if ttft is not None else latency_ms, scores=scores,
    )


async def run_all(pairs: list[tuple[Task, GroundTruth]],
                  model: str | None) -> list[RunResult]:
    results = []
    for task, truth in pairs:
        if truth.facts.get("__skipped__"):
            results.append(RunResult(
                task_id=task.task_id, ok=False,
                error=str(truth.facts.get("__skipped__", "skipped") or
                          "skipped")[:200],
                scores={"tool_f1": 0.0, "numeric_acc": 0.0,
                        "groundedness": 0.0, "name_recall": 0.0},
            ))
            continue
        results.append(await run_task(task, truth, model))
    return results


def _pct(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(pct / 100 * len(ordered)))]


def summarize(results: list[RunResult]) -> tuple[str, dict]:
    scored = [r for r in results if r.ok]
    skipped = [r for r in results
               if not r.ok and r.error.startswith("skipped")]
    failed = [r for r in results
              if not r.ok and not r.error.startswith("skipped")]
    by_family: dict[str, list[RunResult]] = {}
    for r in results:
        by_family.setdefault(r.task_id.split("-")[0], []).append(r)
    lines = ["# DimeBench report", "",
             f"tasks: {len(results)} ok: {len(scored)} "
             f"failed: {len(failed)} skipped: {len(skipped)}", "",
              "| family | n | ok | tool_f1 | numeric_acc | groundedness | "
              "name_recall | lat_p50 | lat_p95 | ttft_p50 | ttft_p95 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | "
              "--- | --- |"]
    for family in sorted(by_family):
        rows = by_family[family]
        ok_rows = [r for r in rows if r.ok]
        lat = [r.latency_ms for r in ok_rows]
        ttft = [r.ttft_ms for r in ok_rows]
        mean = lambda k: (round(sum(r.scores.get(k, 0.0)
                                    for r in ok_rows) / len(ok_rows), 3)
                          if ok_rows else 0.0)
        lines.append(
            f"| {family} | {len(rows)} | {len(ok_rows)} | "
            f"{mean('tool_f1')} | {mean('numeric_acc')} | "
            f"{mean('groundedness')} | {mean('name_recall')} | "
            f"{int(_pct(lat, 50))} | {int(_pct(lat, 95))} | "
            f"{int(_pct(ttft, 50))} | {int(_pct(ttft, 95))} |")
    stats = {
        "tasks": len(results), "ok": len(scored),
        "failed": len(failed), "skipped": len(skipped),
    }
    return "\n".join(lines) + "\n", stats
