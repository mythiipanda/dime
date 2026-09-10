"""Async driver. Runs tasks sequentially against app.graph.run_chat."""

import asyncio
import json
import re
import time

from app.graph import run_chat, tool_label
from app.tools import TOOL_NAMES

from . import ground
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


_PRED_ARGS_RX = re.compile(
    r"(?:^|[,\s])a\s*=\s*([^,]+?)\s*,\s*b\s*=\s*([^,]+?)"
    r"(?:\s*,|\s*$)")


def _resolve_pred_abbr(token: str, teams: dict) -> str | None:
    tok = str(token or "").strip()
    if tok.upper() in teams:
        return tok.upper()
    low = tok.lower()
    for abbr, t in teams.items():
        if str(t.get("full_name", "")).lower() == low:
            return abbr
    return None


def _observed_pred_args(tool_calls: list) -> tuple[str, str] | None:
    # Recover the agent's get_game_prediction arg order from the captured
    # arg summaries (raw args are not emitted by the stream). Last
    # parseable call wins.
    teams = ground._pred_team_table()
    for call in reversed(tool_calls):
        if call.get("name") != "get_game_prediction":
            continue
        summary = str((call.get("args") or {}).get("summary", ""))
        m = _PRED_ARGS_RX.search(summary)
        if not m:
            continue
        a = _resolve_pred_abbr(m.group(1), teams)
        b = _resolve_pred_abbr(m.group(2), teams)
        if a and b and a != b:
            return a, b
    return None


def _rescored_pred_facts(task: Task, truth: GroundTruth,
                         tool_calls: list) -> dict:
    # Prediction-family-only score-time rescore: recompute facts from the
    # replica with the agent's observed arg order. The tool assigns the
    # neutral-site home/away roles by caller order (injury-penalty sides
    # plus the away tie-break noise draw), so facts recomputed with the
    # observed order match the tool's real output; the canonical
    # (sorted) facts drift on flipped calls. Falls back to the
    # precomputed canonical facts when the agent never called the tool,
    # or asked about a different matchup.
    facts = truth.facts
    observed = _observed_pred_args(tool_calls)
    if observed is None:
        return facts
    teams = ground._pred_team_table()
    full2abbr = {str(t.get("full_name", "")).lower(): abbr
                 for abbr, t in teams.items()}
    task_pair = {full2abbr.get(str(e).strip().lower())
                 for e in (task.entities or [])}
    if set(observed) != task_pair or None in task_pair:
        return facts
    try:
        recomputed = ground._pred_facts(*observed, preserve_order=True)
    except ground.SkipTask:
        return facts
    return ground.pred_truth_facts(recomputed)


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
        facts = (truth.facts if task.family != "prediction"
                 else _rescored_pred_facts(task, truth, tool_calls))
        scores = {
            "tool_f1": tool_f1(
                [c["name"] for c in tool_calls], task.gold_tool_families),
            "numeric_acc": numeric_acc(facts, answer),
            "groundedness": groundedness(answer, payloads),
            "name_recall": name_recall(facts, answer),
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
