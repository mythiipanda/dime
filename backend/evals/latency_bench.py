#!/usr/bin/env python3
"""Latency benchmark for the Dime chat path. No backend changes needed.

Drives a LIVE backend's chat stream and rebuilds a per-stage timing
breakdown from the SSE timeline both runtimes already emit:

    node_update {"node": <stage>, "status": "running"|"complete"} -> per-node wall time
    thought_token / token                                        -> time-to-first-token
    final_answer                                                 -> answer captured
    error                                                        -> counted, never fatal

This is the measurement arm of the latency-reduction work (see
LATENCY_BENCHMARK.md next to this file). It deliberately changes NO
product code: option B (merging select_skills into the planner prompt),
or any other latency lever, must be justified against numbers produced
by this script BEFORE it is implemented.

Stdlib only (mirrors backend/evals/live_backend.py). Cannot run in the
sandbox: it needs a live backend with LLM access and a warehouse. It is
verifiable here only via --selftest (synthetic SSE fixtures, no network).

Usage:
    python3 backend/evals/latency_bench.py --base http://host:8000 --runtime v1
    python3 backend/evals/latency_bench.py --base http://host:8000 --runtime v2 --repeats 3 --out A.json
    python3 backend/evals/latency_bench.py --compare A.json B.json   # A/B delta table
    python3 backend/evals/latency_bench.py --selftest

Report JSON (stdout or --out):
    {
      "base": ..., "runtime": "v1", "started_at": ..., "warehouse_sha256": ...,
      "questions": [
        {"id": ..., "turns": [{"q": ...,
           "total_s": ..., "ttft_s": ..., "node_s": {"entry":.., "data_retrieval":..,
              "tools":.., "analytics":.., "presentation":..},
           "errors": 0, "tool_calls": 0, "answer_chars": 0, "empty_answer": false}]}
      ]
    }
Node durations accumulate across repeated running/complete pairs on the
same node. An interval left open at stream end is clamped at final_answer
(or stream EOF) so a missing "complete" event degrades to a bound, not a gap.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
import uuid
from pathlib import Path


def backend_identity(base: str, timeout_s: float = 15.0) -> tuple[str | None, str]:
    """Record the backend's warehouse identity without grading.

    GET /api/revision and return (sha256, detail). Unlike
    live_backend.verify_warehouse this never invalidates anything: the
    bench measures timing, not correctness, but both runs of an A/B must
    serve the same warehouse, so the sha is labeled on every report.
    """
    url = f"{base.rstrip('/')}/api/revision"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return None, f"identity endpoint unreachable ({exc})"
    identity = (payload.get("warehouse") or {}) if isinstance(payload, dict) else {}
    sha = identity.get("sha256")
    if not sha:
        return None, "identity endpoint answered but reported no warehouse sha256"
    wid = identity.get("warehouse_id", "?")
    return sha, f"backend serves warehouse_id={wid} sha256={sha[:16]}…"

#: Nodes both runtimes emit via node_update events.
NODES = ("entry", "data_retrieval", "tools", "analytics", "presentation")

#: Question battery. Each item is (id, [turn, ...]); a two-turn item runs both
#: turns on one thread so the second turn exercises the follow-up/carry path.
#: Keep the battery small: each turn costs a full LLM round-trip (~60s+).
QUESTIONS: list[tuple[str, list[str]]] = [
    ("simple-entity",
     ["What team does Luka Dončić play for?"]),
    ("leaderboard-rate",
     ["Who leads the league in 3P% this season?"]),
    ("leaderboard-defense",
     ["Who are the best defensive players this season?"]),
    ("team-offense",
     ["What is the best offense this season?"]),
    ("compare",
     ["Compare Luka Dončić and Shai Gilgeous-Alexander"]),
    ("standings",
     ["Show me the current standings"]),
    ("followup-2turn",
     ["Who leads the league in scoring this season?",
      "What about last season?"]),
    ("deep",
     ["Which teams improved most defensively over the last three seasons?"]),
]


def stream_path(runtime: str) -> str:
    return {"v1": "/api/v1/chat/stream", "v2": "/api/v2/chat/stream"}[runtime]


def ask_timed(base: str, runtime: str, thread: str, question: str,
              model: str | None = None, timeout_s: float = 420.0) -> dict:
    """POST one question; return the parsed timeline + wall-clock timings."""
    body: dict = {"q": question, "thread": thread}
    if model:
        body["model"] = model
    req = urllib.request.Request(
        f"{base.rstrip('/')}{stream_path(runtime)}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    node_open: dict[str, float] = {}
    node_s: dict[str, float] = {n: 0.0 for n in NODES}
    ttft_s: float | None = None
    answer_chars = 0
    errors = 0
    tool_calls = 0
    ended = False
    ev_name: str | None = None
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        for raw in resp:
            now = time.time() - t0
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if not line:
                ev_name = None
                continue
            if line.startswith("event: "):
                ev_name = line[7:].strip()
                continue
            if line.startswith("data: ") and ev_name:
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    data = {}
                name = ev_name
                ev_name = None
                if name == "node_update":
                    node = str(data.get("node", ""))
                    status = str(data.get("status", ""))
                    if node in node_s and status == "running" and node not in node_open:
                        node_open[node] = now
                    elif node in node_s and status in ("complete", "error"):
                        start = node_open.pop(node, None)
                        if start is not None:
                            node_s[node] += now - start
                elif name in ("thought_token", "token"):
                    if ttft_s is None and str(data.get("text", "")):
                        ttft_s = now
                elif name == "final_answer":
                    answer_chars = len(str(data.get("text", "")))
                    clamp_at = now
                    for node, start in list(node_open.items()):
                        node_s[node] += clamp_at - start
                    node_open.clear()
                elif name == "tool_call":
                    tool_calls += 1
                elif name == "error":
                    errors += 1
                elif name == "graph_end":
                    ended = True
    total_s = time.time() - t0
    for node, start in node_open.items():  # stream EOF with node still open
        node_s[node] += total_s - start
    return {
        "q": question,
        "total_s": round(total_s, 2),
        "ttft_s": round(ttft_s, 2) if ttft_s is not None else None,
        "node_s": {n: round(v, 2) for n, v in node_s.items()},
        "errors": errors,
        "tool_calls": tool_calls,
        "answer_chars": answer_chars,
        "empty_answer": answer_chars == 0,
        "stream_ended": ended,
    }


def run_bench(base: str, runtime: str, model: str | None, repeats: int,
              warmup: int, question_ids: list[str] | None,
              fixture_sha: str | None) -> dict:
    items = [q for q in QUESTIONS if not question_ids or q[0] in question_ids]
    if warmup:
        wid, wturns = items[0]
        for i in range(warmup):
            thread = f"bench-warmup-{i}-{uuid.uuid4().hex[:8]}"
            for turn in wturns:
                ask_timed(base, runtime, thread, turn, model=model)
    questions = []
    for qid, turns in items:
        rep_turns = []
        for r in range(repeats):
            thread = f"bench-{qid}-r{r}-{uuid.uuid4().hex[:8]}"
            for turn in turns:
                res = ask_timed(base, runtime, thread, turn, model=model)
                rep_turns.append(res)
                print(f"  [{qid} r{r}] {res['total_s']:7.1f}s "
                      f"ttft={res['ttft_s']} errs={res['errors']} "
                      f"answer_chars={res['answer_chars']}", flush=True)
        questions.append({"id": qid, "turns": rep_turns})
    return {
        "base": base,
        "runtime": runtime,
        "model": model,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "warehouse_sha256": fixture_sha,
        "repeats": repeats,
        "questions": questions,
    }


def summarize(report: dict) -> dict:
    """Median per question across repeats (per turn index)."""
    out: dict[str, dict] = {}
    for q in report["questions"]:
        n_turns = max((len(t) for t in [q["turns"]]), default=0)
        turns = []
        for ti in range(n_turns):
            group = [t for i, t in enumerate(q["turns"]) if i % n_turns == ti]
            turns.append({
                "total_s": statistics.median(t["total_s"] for t in group),
                "ttft_s": statistics.median(t["ttft_s"] for t in group
                                            if t["ttft_s"] is not None)
                if any(t["ttft_s"] is not None for t in group) else None,
                "node_s": {n: statistics.median(t["node_s"][n] for t in group)
                           for n in NODES},
                "errors": sum(t["errors"] for t in group),
                "tool_calls": statistics.median(t["tool_calls"] for t in group),
                "empty_answers": sum(1 for t in group if t["empty_answer"]),
            })
        out[q["id"]] = {"turns": turns}
    return out


def print_table(title: str, summary: dict) -> None:
    print(f"\n== {title} ==")
    hdr = (f"{'question':<20}{'turn':<5}{'total':>8}{'ttft':>8} "
           + " ".join(f"{n[:8]:>8}" for n in NODES)
           + f"{' errs':>6}")
    print(hdr)
    print("-" * len(hdr))
    for qid, q in summary.items():
        for ti, t in enumerate(q["turns"]):
            ttft = f"{t['ttft_s']:.1f}" if t["ttft_s"] is not None else "-"
            row = (f"{qid:<20}{ti:<5}{t['total_s']:>8.1f}{ttft:>8} "
                   + " ".join(f"{t['node_s'][n]:>8.1f}" for n in NODES)
                   + f" {t['errors']:>5}")
            print(row)


def cmd_compare(a_path: str, b_path: str) -> int:
    a = json.loads(Path(a_path).read_text())
    b = json.loads(Path(b_path).read_text())
    sa, sb = summarize(a), summarize(b)
    print(f"A: {a_path}  (runtime={a['runtime']}, warehouse={str(a['warehouse_sha256'])[:12]})")
    print(f"B: {b_path}  (runtime={b['runtime']}, warehouse={str(b['warehouse_sha256'])[:12]})")
    if a["runtime"] != b["runtime"]:
        print("WARNING: runtimes differ; deltas mix v1/v2 path differences.")
    if a["warehouse_sha256"] and b["warehouse_sha256"] \
            and a["warehouse_sha256"] != b["warehouse_sha256"]:
        print("WARNING: warehouse identity differs; deltas are INVALID.")
    hdr = (f"{'question':<20}{'turn':<5}{'Δtotal':>8}{'Δttft':>8} "
           + " ".join(f"Δ{n[:7]:>7}" for n in NODES))
    print("\n" + hdr)
    print("-" * len(hdr))
    for qid in sa:
        if qid not in sb:
            print(f"{qid:<20}  (missing in B)")
            continue
        for ti, (ta, tb) in enumerate(zip(sa[qid]["turns"], sb[qid]["turns"])):
            d_tot = tb["total_s"] - ta["total_s"]
            d_ttft = ((tb["ttft_s"] - ta["ttft_s"])
                      if ta["ttft_s"] is not None and tb["ttft_s"] is not None
                      else None)
            row = (f"{qid:<20}{ti:<5}{d_tot:>+8.1f}"
                   + (f"{d_ttft:>+8.1f}" if d_ttft is not None else f"{'-':>8}")
                   + " "
                   + " ".join(f"{tb['node_s'][n] - ta['node_s'][n]:>+8.1f}"
                              for n in NODES))
            print(row)
    print("\nΔ = B - A. Negative is faster. 'total' includes SSE/HTTP overhead "
          "both ends pay.")
    return 0


# ---------------------------------------------------------------------------
# --selftest: parse synthetic SSE streams through the real timeline code.
# ---------------------------------------------------------------------------

def _fake_stream(pairs: list[tuple[str, dict]], start_t0: float = 1000.0,
                 step: float = 0.5):
    """Yield SSE lines while advancing a fake clock.

    `pairs` is a list of (event_name, data) frames; the clock advances
    `step` seconds per frame (not per line), so expected durations are
    exact. The real ask_timed parses these through its normal line path.
    """
    clock = {"t": start_t0}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            for name, data in pairs:
                clock["t"] += step
                yield f"event: {name}\n".encode()
                yield f"data: {json.dumps(data)}\n".encode()
                yield b"\n"

    def fake_urlopen(req, timeout=None):
        return Resp()

    import urllib.request as _u
    orig_urlopen, orig_time = _u.urlopen, time.time
    _u.urlopen = fake_urlopen
    time.time = lambda: clock["t"]
    try:
        res = ask_timed("http://x", "v1", "t", "q")
    finally:
        _u.urlopen, time.time = orig_urlopen, orig_time
    return res


def selftest() -> int:
    fails = []

    def check(label: str, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        else:
            print(f"  ok: {label}")

    # 1. Normal run: entry + data_retrieval + tools + analytics + presentation,
    #    first thought token, final answer. 15 frames * 0.5s = 7.5s total.
    frames = [
        ("node_update", {"node": "entry", "status": "running"}),
        ("node_update", {"node": "entry", "status": "complete"}),
        ("node_update", {"node": "data_retrieval", "status": "running"}),
        ("thought_token", {"node": "data_retrieval", "text": "planning"}),
        ("node_update", {"node": "data_retrieval", "status": "complete"}),
        ("node_update", {"node": "tools", "status": "running"}),
        ("tool_call", {"name": "get_leaders"}),
        ("tool_result", {"name": "get_leaders", "status": "ok"}),
        ("node_update", {"node": "tools", "status": "complete"}),
        ("node_update", {"node": "analytics", "status": "running"}),
        ("node_update", {"node": "analytics", "status": "complete"}),
        ("node_update", {"node": "presentation", "status": "running"}),
        ("node_update", {"node": "presentation", "status": "complete"}),
        ("final_answer", {"text": "SGA leads at 61.6%."}),
        ("graph_end", {}),
    ]
    r = _fake_stream(frames)
    check("total_s", r["total_s"], 7.5)   # 15 frames * 0.5s
    check("ttft_s", r["ttft_s"], 2.0)     # 4 frames in
    check("entry", r["node_s"]["entry"], 0.5)
    check("data_retrieval", r["node_s"]["data_retrieval"], 1.0)
    check("tools", r["node_s"]["tools"], 1.5)
    check("tool_calls", r["tool_calls"], 1)
    check("errors", r["errors"], 0)
    check("empty_answer", r["empty_answer"], False)
    check("ended", r["stream_ended"], True)

    # 2. Missing "complete" on tools: interval clamps at final_answer.
    frames = [
        ("node_update", {"node": "tools", "status": "running"}),
        ("final_answer", {"text": "ok"}),
    ]
    r = _fake_stream(frames)
    check("clamp tools", r["node_s"]["tools"], 0.5)

    # 3. Error events counted; status=error closes the node interval.
    frames = [
        ("node_update", {"node": "analytics", "status": "running"}),
        ("error", {"node": "analytics", "message": "boom"}),
        ("node_update", {"node": "analytics", "status": "error"}),
        ("final_answer", {"text": ""}),
    ]
    r = _fake_stream(frames)
    check("error count", r["errors"], 1)
    check("error closes node", r["node_s"]["analytics"], 1.0)
    check("empty answer flagged", r["empty_answer"], True)

    # 4. Duplicate running events on one node accumulate, not double-start.
    frames = [
        ("node_update", {"node": "tools", "status": "running"}),
        ("node_update", {"node": "tools", "status": "complete"}),
        ("node_update", {"node": "tools", "status": "running"}),
        ("node_update", {"node": "tools", "status": "complete"}),
        ("final_answer", {"text": "ok"}),
    ]
    r = _fake_stream(frames)
    check("repeated node accumulates", r["node_s"]["tools"], 1.0)

    # 5. Malformed data line + unknown event: ignored, stream survives.
    frames = [
        ("node_update", {"node": "entry", "status": "running"}),
        ("bogus_event", {"x": 1}),
        ("node_update", {"node": "entry", "status": "complete"}),
        ("final_answer", {"text": "ok"}),
    ]
    r = _fake_stream(frames)
    check("unknown event ignored", r["node_s"]["entry"], 1.0)

    # 6. compare() math on two fabricated reports.
    def _rep(sha, totals):
        return {"base": "b", "runtime": "v1", "warehouse_sha256": sha,
                "questions": [
                    {"id": qid,
                     "turns": [{"q": qid, "total_s": v, "ttft_s": 1.0,
                                "node_s": {n: 0.0 for n in NODES},
                                "errors": 0, "tool_calls": 0,
                                "answer_chars": 5, "empty_answer": False}]}
                    for qid, v in totals.items()]}
    a = _rep("sha", {"q1": 60.0, "q2": 90.0})
    b = _rep("sha", {"q1": 45.0, "q2": 95.0})
    sa, sb = summarize(a), summarize(b)
    check("compare delta q1", sb["q1"]["turns"][0]["total_s"]
          - sa["q1"]["turns"][0]["total_s"], -15.0)
    check("compare delta q2", sb["q2"]["turns"][0]["total_s"]
          - sa["q2"]["turns"][0]["total_s"], 5.0)

    if fails:
        print("\nSELFTEST FAILURES:")
        for f in fails:
            print(" -", f)
        return 1
    print(f"\nselftest: all {6} fixture groups pass")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost:8000",
                    help="backend base URL")
    ap.add_argument("--runtime", choices=["v1", "v2"], default="v1")
    ap.add_argument("--model", default=None, help="force chat model")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--warmup", type=int, default=1,
                    help="warmup turns before timing (default 1)")
    ap.add_argument("--questions", default=None,
                    help="comma-separated question ids (default: all)")
    ap.add_argument("--out", default=None, help="write report JSON here")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"),
                    help="print A/B delta table instead of running")
    ap.add_argument("--skip-warehouse-check", action="store_true",
                    help="do not verify /api/revision identity")
    ap.add_argument("--selftest", action="store_true",
                    help="run synthetic-SSE selftest, no network")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.compare:
        return cmd_compare(*args.compare)

    fixture_sha: str | None = None
    if not args.skip_warehouse_check:
        fixture_sha, detail = backend_identity(args.base)
        print(f"warehouse identity: {detail}")
        if fixture_sha is None:
            print("WARNING: cannot label this report with a warehouse sha; "
                  "A/B deltas against it are unreliable.")
    qids = args.questions.split(",") if args.questions else None
    report = run_bench(args.base, args.runtime, args.model, args.repeats,
                       args.warmup, qids, fixture_sha)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"report written to {args.out}")
    print_table(f"{args.base} runtime={args.runtime} "
                f"(medians over {args.repeats} repeat(s))",
                summarize(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
