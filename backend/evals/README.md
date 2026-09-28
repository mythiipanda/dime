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
| `live_backend` | skipped | golden questions against a live backend (opt-in) |
| `unit_tests` | hermetic | py_compile sweep + stdlib-only import smoke |

## Honesty rules

- Fallback or ported scoring reports `fallback-only` or skip, never passes as canonical verification.
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
