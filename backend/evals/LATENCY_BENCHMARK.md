# Latency benchmark approach (Round 29)

**Rule: no blind latency rewrites.** Round 24 deferred the option-B
select_skills merge because it would revert a deliberate Phase 2 design
decision without measurement to justify it. This doc + the harness in
`latency_bench.py` (same directory) are the measurement arm. Any latency
lever must show a win against these numbers first.

## Where the ~75s goes (code map)

Stages below follow the v1 chat path (`backend/app/graph.py`) and the
v2 chat path (`backend/v2/runtime/`). LLM = one blocking LLM round-trip.

| Stage | SSE node events | LLM calls | Notes |
|---|---|---|---|
| skill selection | inside `data_retrieval` (no own node) | 1 (`_select_skills_intent`, graph.py:262) — picks 0–2 skills + `entity_level` intent | This is the option-B call. Returns `([], None)` on failure. |
| planner | `data_retrieval` | 1 streaming tool-call loop (`_stream_planner`, graph.py:1257) | Thought tokens stream live; tool-call rounds may iterate. |
| tools | `tools` | 0–N delegate desks; each delegate may make its own LLM calls | Already parallelized; per-call ms already tracked in `elapsed[]` (actual_tool_node). |
| analytics | `analytics` | 1 (analytics_agent, graph.py:5322) | Exception path yields `error` then recovers. |
| presentation | `presentation` | 1 (presentation_agent, graph.py:6438) | Composes the final answer from evidence. |
| suggestions | none (fires after answer) | 1 (`_suggest_*`, graph.py:5223) | Post-answer; a candidate for lazy/deferral. |
| SSE/HTTP | none | — | First-token timeout + heartbeat already shipped. |

**What the SSE timeline can and cannot separate:**

- CAN: per-node wall time (`node_update` running/complete), time-to-first
  thought token (`thought_token`), error counts, tool-call counts, total
  wall time. Both runtimes emit these identically.
- CANNOT: skill-selection vs planner-first-token inside `data_retrieval`
  (the skill call finishes before the planner streams its first token, so
  `data_retrieval` start → first thought token is only an upper bound on
  the skill call). Desk-internal LLM time vs SQL time is likewise opaque
  client-side — use the backend's per-call `elapsed[]` logs for that.
- CONCLUSION: the decision for option B rests on **A/B deltas of the
  merged variant vs control** on the same questions, not on dissecting the
  skill call's exact share.

## How to run

On a machine with the backend's real deps. The sandbox has no fixture
warehouse and no generated asset manifest, so the serve/bench steps
below cannot run there — build and serve on a real machine:

```bash
# 1. Stable data: build the fixture, bind a manifest to it, start the backend.
#    Build from the repo root; serve from backend/ (`uvicorn app.main:app`
#    only resolves with cwd=backend/). Paths must be absolute — store.py
#    reads DIME_WAREHOUSE as-is, so a relative path breaks under cwd=backend/.
#    The lifespan preflight refuses to serve without the manifest.
python3 backend/evals/run.py --build-fixture
DIME_WAREHOUSE=$PWD/backend/evals/data/fixture.duckdb \
python3 backend/scripts/generate_asset_manifest.py \
    backend/evals/data/expected_asset_manifest.json
cd backend
DIME_WAREHOUSE=$PWD/evals/data/fixture.duckdb \
DIME_EXPECTED_ASSET_MANIFEST=$PWD/evals/data/expected_asset_manifest.json \
uvicorn app.main:app &
cd ..

# 2. Baseline (control).
python3 backend/evals/latency_bench.py --base http://localhost:8000 \
    --runtime v1 --repeats 3 --out bench_control.json

# 3. Variant: run the same command against the modified backend build.
python3 backend/evals/latency_bench.py --base http://localhost:8000 \
    --runtime v1 --repeats 3 --out bench_variant.json

# 4. Delta table.
python3 backend/evals/latency_bench.py --compare bench_control.json bench_variant.json
```

Controls that make an A/B honest:

- Same warehouse sha (the script labels every report; `--compare` fails
  non-zero on mismatch — a mismatched A/B is INVALID, not a result).
- Same model (`--model`), same question set, warmup on (default 1), ≥3
  repeats, medians compared.
- Run A and B back-to-back; provider latency drifts across hours.

Cost note: the 8-question battery costs one full LLM round-trip per turn
(~60s+). `--questions` subsets it. A 3-repeat full run is ~25–40 minutes.

## Decision criteria for option B (merge select_skills into the planner)

The merge is APPROVED only if ALL of these hold:

1. **Latency win:** p50 `total_s` improves ≥ 15% on the simple-entity +
   leaderboard-rate questions (the ones where the skill call is pure
   overhead), with no question regressing > 5%.
2. **Skill recall preserved:** the hermetic skill-finder suite
   (`python3 backend/evals/run.py --suite skill_finder`, which AST-extracts
   the real `_select_skills_intent` and scores 15 labeled questions) shows
   no regression on the merged prompt variant.
3. **Intent preserved:** the merged prompt must still return the
   `entity_level` signal (`player`/`team`/`mixed`/`unknown`) — it feeds the
   termination gate (`state["answer_entity_level"]`), not just skill names.
4. **Failure surface unchanged:** the standalone skill call fails closed to
   `([], None)`; the merged variant must show the same empty-skill rate on
   the battery (count via `--repeats`, compare `tool_calls`/skill-driven
   behavior), not silently pick garbage skills.

If any criterion fails, option B stays deferred and the next lever is
re-measured, not argued.

These gates are proposed repo-level checks for this measurement round,
not a personal sign-off from Tony, and must not be cited as approval
for a rewrite.

## Levers worth measuring next (in order, each gated on the same A/B)

1. **Defer suggestions** — the follow-up LLM call (graph.py:5223) fires
   after the answer is complete; make it lazy (only on hover/scroll) or
   drop it. Measure: total_s delta on the battery.
2. **Planner tool-loop rounds** — cap or early-exit the ReAct loop on
   evidence sufficiency; measure against deep questions only.
3. **Delegate fan-out** — desks already run parallel; measure whether the
   slowest desk dominates `tools` node time and cache the hot one.
4. **Skill-call parallelism** — run `_select_skills_intent` concurrently
   with planner-stream setup instead of sequentially. Smaller change than
   option B; same A/B gate.

## Sandbox verification of this round's artifacts

- `python3 -m py_compile backend/evals/latency_bench.py` — clean.
- `python3 backend/evals/latency_bench.py --selftest` — 7 fixture groups
  pass (timeline parsing, interval clamping, error counting, repeat-node
  accumulation, unknown-event tolerance, repeat-median math, compare
  warehouse gating). No network.
- stdlib-only import check (AST): no third-party imports.
- Doc step 1 checked in a scrubbed env (`env -i` with only PATH, HOME,
  DIME_WAREHOUSE): `import app.main` passes with cwd=backend/ and fails
  from the repo root, so the `cd backend` is load-bearing; a relative
  DIME_WAREHOUSE breaks for the same reason — use an absolute path.
  Serving stops at the lifespan preflight without
  DIME_EXPECTED_ASSET_MANIFEST, which can only be generated against a
  built fixture warehouse, so boot past import and GET /api/revision
  genuinely cannot run here.
- No product code touched; no routing changes; no regexes added.
