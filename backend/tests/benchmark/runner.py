"""Live benchmark runner. Stdlib only (urllib SSE client).

Usage:
  python3 runner.py --url https://dime-backend...azurecontainerapps.io \
      --out reports/run-$(date +%s).json [--scenario canon-finals]

Each scenario gets a fresh thread id; chain turns share it (context
carry under test). Records per turn: final text, wall seconds, tool
calls, streamed chars. Writes JSON report + prints a markdown summary.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

from assertions import evaluate_scenario, load_pack

HERE = Path(__file__).resolve().parent


def stream_turn(base: str, question: str, thread: str,
                timeout_s: float = 200.0) -> dict:
    body = json.dumps({"q": question, "thread": thread}).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/api/v1/chat/stream", data=body,
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    text, tool_calls, streamed = "", 0, 0
    tool_trace: list[dict[str, str]] = []
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        event = None
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event: "):
                event = line[7:]
                continue
            if line.startswith("data: ") and event:
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    data = {}
                if event == "final_answer":
                    text = str(data.get("text", ""))
                elif event == "tool_call":
                    tool_calls += 1
                    tool_trace.append({
                        "name": str(data.get("name", "")),
                        "agent": str(data.get("agent", "")),
                    })
                elif event in ("token", "thought_token"):
                    streamed += len(str(data.get("text", "")))
                event = None
            if text and event is None and line == "":
                # final_answer seen; keep reading until stream closes
                pass
    return {"text": text, "seconds": round(time.time() - t0, 2),
            "tool_calls": tool_calls, "tool_trace": tool_trace,
            "streamed_chars": streamed}


def run_pack(base: str, pack: dict, only: str | None) -> dict:
    results = []
    banned = pack.get("banned_everywhere", [])
    for s in pack["scenarios"]:
        if only and s["id"] != only:
            continue
        thread = f"bench-{uuid.uuid4().hex[:10]}"
        turns = []
        for q in s["chain"]:
            try:
                turns.append(stream_turn(base, q, thread))
            except Exception as exc:  # network/timeout: record, grade as fail
                turns.append({"text": f"<runner error: {exc}>",
                              "seconds": 0.0, "tool_calls": 0,
                              "tool_trace": [], "streamed_chars": 0})
                break
        results.append(evaluate_scenario(s, turns, banned))
        results[-1]["thread"] = thread
        results[-1]["answers"] = [t["text"] for t in turns]
        mark = ("PASS" if results[-1]["pass"]
                else ("XFAIL" if results[-1]["xfail"] else "FAIL"))
        print(f"[{mark}] {s['id']} "
              f"({results[-1].get('seconds', 0)}s)", flush=True)
    graded = [r for r in results if not r["xfail"]]
    known = [r for r in results if r["xfail"]]
    return {
        "base": base, "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "capability": {
            "passed": sum(1 for r in graded if r["pass"]),
            "total": len(graded),
            "xfail_now_passing": [r["id"] for r in known if r["pass"]],
        },
        "efficiency": {
            "seconds_total": round(sum(r.get("seconds", 0) for r in results), 1),
            "tool_calls_total": sum(r.get("tool_calls", 0) for r in results),
            "streamed_chars_total": sum(r.get("streamed_chars", 0) for r in results),
        },
        "results": results,
    }


def markdown(report: dict) -> str:
    lines = [f"# Benchmark {report['ran_at']}", "",
             f"Capability: {report['capability']['passed']}/"
             f"{report['capability']['total']} passed "
             f"(xfail-now-passing: {report['capability']['xfail_now_passing']})",
             f"Efficiency: {report['efficiency']['seconds_total']}s total, "
             f"{report['efficiency']['tool_calls_total']} tool calls, "
             f"{report['efficiency']['streamed_chars_total']} streamed chars", ""]
    for r in report["results"]:
        mark = "PASS" if r["pass"] else ("XFAIL" if r["xfail"] else "FAIL")
        lines.append(f"- [{mark}] {r['id']} ({r.get('seconds', 0)}s, "
                     f"{r.get('tool_calls', 0)} calls)")
        for f in r["fails"]:
            lines.append(f"  - {f}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--pack", default=str(HERE / "scenarios.json"))
    args = ap.parse_args()
    pack = load_pack(args.pack)
    report = run_pack(args.url, pack, args.scenario)
    md = markdown(report)
    print(md)
    out = Path(args.out) if args.out else (
        HERE / "reports" / f"run-{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    out.with_suffix(".md").write_text(md)
    print(f"\nreport: {out}")
    failed = [r for r in report["results"] if not r["pass"] and not r["xfail"]]
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
