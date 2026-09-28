# Dime eval harness

One command, honest modes, pass/fail report:

```
python3 backend/evals/run.py [options]
```

Options:

| flag | effect |
|---|---|
| `--suite NAME` | run one suite (default: all) |
| `--live-llm` | skill-finder calls Gemini Flash Lite instead of replaying recordings |
| `--live-judge` | judge calls real judges instead of replaying recordings |
| `--live-backend URL` | probe golden questions + frontier candidates against a live backend |
| `--build-fixture` | build (or rebuild) the stable live-eval fixture warehouse at `backend/evals/data/fixture.duckdb` and exit; point the backend at it (`DIME_WAREHOUSE=<path>`) before any `--live-backend` run |
| `--warehouse PATH` | real warehouse file for real-warehouse golden questions (default: `$DIME_WAREHOUSE`) |
| `--record` | capture live LLM/judge prompts+responses into recordings (needs the matching `--live-*` flag) |
| `--list` | list suites and exit |

The default run is fully hermetic: stdlib + DuckDB only, no network, no
LLM, no warehouse file. Suites that need more are skipped with a labeled
reason. A skip is never a pass.

## Suites

| suite | mode default | what it does |
|---|---|---|
| `golden_warehouse` | hermetic | synthetic fixture warehouse (invented teams/players, seed 7); every question's hidden verifier SQL computes truth at runtime; verify-gate: null oracle fails, empty answer fails, fabricated correct passes, fabricated wrong-number/wrong-season fail |
| `skill_finder` | hermetic (recorded) | AST-extracts the real `_select_skills_intent` from `backend/app/graph.py`; scores 15 labeled questions against the v1 catalog; checks fail-closed `([], None)` and catalog staleness |
| `judge` | hermetic (recorded) | cheap judge scores fabricated answers on 5 criteria (1-10, incl. anti-hedging); confidence < 0.7 escalates to a strong judge; calibration buckets reported |
| `frontier` | hermetic | generates warehouse-grounded candidates at 3 difficulty levels, verify-gates oracles; with `--live-backend` probes them and retains misses |
| `regression_protected` | hermetic | re-probes retained misses; open regressions fail |
| `scorer_mirror` | canonical or fallback-only | runs the existing season-consistency mirror; fallback-only results are SKIP, never PASS |
| `benchmark_pack` | hermetic | existing local pack: scenario integrity + assertion engine on fabricated transcripts |
| `eval_prompts` | hermetic | existing 20-prompt structural eval (wrapped) |
| `live_backend` | skipped | golden questions against a live backend (opt-in); grades NOTHING until the warehouse verification passes (see below) |
| `unit_tests` | hermetic | py_compile sweep + stdlib-only import smoke |

## Live-eval warehouse contract

The live suites (`live_backend`, and the live halves of `frontier`
and `regression_protected`) grade a backend ONLY against the fixture
warehouse the harness builds — never against whatever warehouse the
backend happens to point at. The workflow:

```
1. python3 backend/evals/run.py --build-fixture
2. DIME_WAREHOUSE=<printed path> uvicorn app.main:app ...   # real mechanism: backend/shared/store.py reads DIME_WAREHOUSE at startup
3. python3 backend/evals/run.py --live-backend <url>
```

Before grading a single question, the suite fetches
`GET {base}/api/revision` and compares the backend's startup-frozen
warehouse sha256 (v2/api/routes.py) against the sha256 of the fixture
file it will grade against. Match → grade. Anything else
(unreachable endpoint, bad payload, hash mismatch) → every question
fails with `warehouse-unverified`, mode `live-backend-unverified`,
and the report is labeled INVALID. A backend on the canonical
benchmark warehouse or a stale copy can never silently pass.

The fixture lives at a stable path (`data/fixture.duckdb`, git-ignored)
precisely so step 2 can target it before step 3 runs; per-run tempdirs
would make the verification meaningless. The build pre-creates the
`fetch_log` table exactly as the backend's first connect would, so the
file bytes (and sha256) stay stable across runs.

Mutation-tested (`selftest_live_path.py`, hermetic, no LLM): a backend
reporting a different warehouse's sha gets INVALID with zero questions
graded; a poisoned fixture (one game's result flipped) with the backend
relaunched on it passes verification and the stale answer fails
grading — expected values track the fixture file.

## Two ledgers

Every report splits into two ledgers; the second never inherits the
first's credibility:

- **plumbing** — harness integrity: deterministic scoring,
  verify-gates, recordings, opt-in safety. Green plumbing says the
  harness works.
- **answer-quality signal** — live answers graded against ground
  truth. Only verified live probes land here.

Verdict lines are explicit: `NONE` when no verified live probes ran,
`INVALID` when warehouse verification failed, and a graded count only
when verification passed. Plumbing greens never imply answer quality.

## Honesty rules

- Fallback or ported scoring reports `fallback-only` or skip, never passes as canonical verification.
- No grading without warehouse verification: any live report produced without a passing identity check is INVALID, never PASS.
- No player-specific hardcoding, no keyword/regex routing in eval logic (regex is used only for numeric/season parsing in scoring, never for routing).
- Judge and skill-finder prompts are pinned in `data/prompt_manifest.json` (SHA-256); drift fails the suite so weekly numbers stay comparable.
- Recordings live in `data/recorded/`; traces in `traces/` (git-ignored).

## Paper decisions

The harness implements the adopted mechanisms from the paper review
(warehouse-grounded question factory with hidden verifiers, JEV cascade
judge, criteria decomposition, anti-hedging, prompt manifests,
weakness-frontier mining, calibration). It rejects hyper-tau-bench and
LLM self-modeling as wrong-problem for this pipeline, and grades skills
by live pipeline outcome gain (SWE-Skills-Bench rule), not prose
quality. Full rationale: `~/workspace/goals/dime-playground/hidden_files/workstream-evals-note.md`.
