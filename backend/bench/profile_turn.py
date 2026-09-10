"""Per-stage latency profiler for full agent turns.

Streams run_chat for a set of questions, timestamps every SSE event,
and attributes wall time to phases: triage, planner rounds (LLM),
tool windows, desk streaming, analytics, presentation.

Usage: cd backend && .venv/bin/python -m bench.profile_turn
Writes JSON to /tmp/dime_profile_<ts>.json and prints a summary table.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import run_chat  # noqa: E402

QUESTIONS = [
    ("comps", "Which players play most like Anthony Edwards statistically this season?"),
    ("trade_value", "Who wins this trade on production value vs salary: "
                    "Anthony Edwards (MIN) for Luka Doncic (LAL)? Name the winner."),
    ("brief", "Give me the slate briefing for 2025-10-31: how many games "
              "are on and which teams play?"),
]


async def profile_one(name, question):
    events = []
    t0 = time.perf_counter()
    async for ev in run_chat(question, None, []):
        now = time.perf_counter()
        d = ev.get("data") or {}
        events.append({
            "t": round(now - t0, 3),
            "type": ev.get("type"),
            "node": d.get("node", ""),
            "status": d.get("status", ""),
            "name": d.get("name", ""),
            "label": d.get("label", ""),
            "ms": d.get("ms"),
            "agent": d.get("agent", ""),
            "tlen": len(str(d.get("text", ""))),
        })
        if ev.get("type") == "graph_end":
            break
    return events


def analyze(events):
    phases = []
    stack = []  # open (node, start) windows
    for ev in events:
        if ev["type"] != "node_update":
            continue
        st, node, t = ev["status"], ev["node"], ev["t"]
        if st == "running":
            stack.append((node, t))
        elif st == "complete":
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == node:
                    _, s = stack.pop(i)
                    phases.append((node, s, t))
                    break
    for node, s in stack:  # windows still open at end
        phases.append((node, s, events[-1]["t"] if events else s))
    total = events[-1]["t"] if events else 0
    tok_chars: dict[str, int] = {}
    for ev in events:
        if ev["type"] == "thought_token":
            key = f"{ev['node']}/{ev['agent'] or 'planner'}"
            tok_chars[key] = tok_chars.get(key, 0) + ev["tlen"]
    tool_results = [(e["name"], e["ms"], e["status"])
                    for e in events if e["type"] == "tool_result"]
    calls = [e["name"] for e in events if e["type"] == "tool_call"]
    planner_rounds = sum(1 for e in events
                         if e["type"] == "node_update"
                         and e["node"] == "data_retrieval"
                         and e["status"] == "complete")
    ttft = next((e["t"] for e in events
                 if e["type"] in ("thought_token", "tool_call")), None)
    return {
        "total_s": round(total, 2),
        "phases": [(n, round(e - s, 2)) for n, s, e in phases],
        "tool_results": tool_results,
        "tok_chars": tok_chars,
        "call_sequence": calls,
        "planner_rounds": planner_rounds,
        "ttft_s": round(ttft, 2) if ttft else None,
    }


async def main():
    all_res = {}
    for name, q in QUESTIONS:
        print(f"\n=== {name}: {q[:70]} ===", flush=True)
        evs = await profile_one(name, q)
        rep = analyze(evs)
        all_res[name] = rep
        print(f"total {rep['total_s']}s ttft {rep['ttft_s']}s "
              f"planner_rounds {rep['planner_rounds']}", flush=True)
        print(f"phases {rep['phases']}", flush=True)
        print(f"tools(ms): {rep['tool_results']}", flush=True)
        print(f"tok_chars: {rep['tok_chars']}", flush=True)
        print(f"calls: {rep['call_sequence']}", flush=True)
    out = f"/tmp/dime_profile_{int(time.time())}.json"
    Path(out).write_text(json.dumps(all_res, indent=1))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
