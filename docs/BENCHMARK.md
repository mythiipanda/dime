# DimeBench

Runtime-generated benchmark for the Dime NBA analyst agent. Inspired by
BFCL (tool-call correctness) and tau-bench (multi-turn task success), but
every task is generated at runtime from live warehouse data. There are zero
hardcoded test cases: entities, stat categories, games, and salaries are
sampled fresh on each run.

## Methodology

The agent entry point is `app.graph.run_chat(question, model_id, history)`,
an async generator yielding `node_update`, `thought_stream`, `tool_call`,
`token`, `final_answer`, `suggestions`, `graph_end`, `error`, and
`custom_data` events. The driver collects these events per task, records
tool-call names from exact `tool_call` events, captures the final answer text, and stops at `graph_end`.

Ground truth is computed from `app.store` (read-only DuckDB reads) and
`app.sources` only. The benchmark never calls `app.tools` wrappers to build
expected values. This anti-circularity rule is the load-bearing design
choice: if ground truth came from the same code the agent uses, the
benchmark would reward the agent for agreeing with itself.

Each generator takes `(rng, ctx)` and returns `(Task, GroundTruth)`.
`rng` is seeded per `(seed, family, index)` so runs are reproducible for a
fixed warehouse snapshot; the warehouse itself moves, so scores drift as
the season moves. That drift is signal, not noise.

## Task families

1. `lookup` — single-entity fact. Samples a random top-50 scorer for
   context, asks who leads the league in a random stat category
   (PTS/REB/AST/STL/BLK). Gold: `get_leaders`.
2. `compare` — two random players from the top 80 of a random category,
   head-to-head on that stat. Gold: `get_compare`.
3. `chain` — two hops. Samples a random player with cached gamelogs, takes
   his latest game, then asks for that game's boxscore top scorer. Gold:
   `get_player_intel`/`get_last_x` plus `get_boxscore`.
4. `adjudicate` — one player present in both leaders and on/off tables.
   Asks whether percentile rank and on/off net agree. Gold:
   `get_percentiles`/`get_on_off`.
5. `trade` — two random players on different teams with real salaries from
   the salary sheet. Asks if a one-for-one swap is legal. Ground truth
   recomputes the 125pct-plus-250k rule from raw salary rows, below-apron
   form only, no apron aggregation logic. Gold: `get_trade_check`.
6. `brief` — slate briefing for a random cached scoreboard date. Ground
   truth is game count plus team abbreviations. Scores mainly coverage
   and latency. Gold: `get_today`/`get_morning_briefing`.
7. `finder` — random team streak question from history tables. If no
   history tables exist, the task is skipped gracefully (`ok=False`,
   `error=skipped: ...`) instead of failing. Gold: `get_finder`.

## Scoring formulas

- `tool_f1` — each observed tool call maps to a family bucket through a
  small static `TOOL_FAMILY` table in `bench/scoring.py` (config, not a
  test case). Plumbing calls (`resolve_entity`, `search_nba`,
  `run_python`, `text_to_sql`, watchlist tools) are excluded. F1 of the
  observed family set against the gold family set. Observed calls are
  captured from exact `tool_call` SSE events with arg summaries;
  inference from progress text is removed. Empty observation
  scores 0.
- `numeric_acc` — for each numeric ground-truth fact, 1 if the rounded
  value (int, 1-decimal, comma, or raw form) appears in the final answer
  with digit-boundary guards, so value 5 does not match inside 25.
  The entity last-name fallback is removed: a name alone never counts
  as a numeric hit. Season-shaped tokens (e.g. 2025-26) are stripped
  before matching. Fraction matched over numeric facts. Tasks with no
  numeric facts score 1.
- `groundedness` — season-shaped tokens are excluded from numeric
  extraction on both answer and payload sides. Remaining answer numbers
  match payload numbers after comma/percent normalization, plus a
  rounding-tolerant float comparison (|a - p| <= 0.051, covering
  one-decimal rounding like 25.5 vs 25.47) and a reverse percent
  conversion (non-percent answer number also tries cand*100, so 0.452
  matches a 45.2% payload). No numbers in the answer scores 1;
  numbers with no payload evidence score 0.
- `latency_ms` — wall clock per task. `ttft_ms` — time to the first tool
  call event; falls back to `latency_ms` when the agent calls no tools.

Failed tasks (`ok=False`) score 0 on all three metrics.

## How to run

From `backend/`:

```
.venv/bin/python -m bench.run_benchmark --per-family 2 --seed 7 --timeout 180
.venv/bin/python -m bench.run_benchmark --families lookup,compare --per-family 1
.venv/bin/python -m bench.run_benchmark --families trade --model mistral:ministral-8b-2512
```

Flags: `--families` (comma subset, default all), `--per-family` (default
2), `--seed` (default 7), `--timeout` seconds per task (default 180),
`--model` (passed to `run_chat`, default None resolves to the configured
provider).

Output goes to `backend/bench/results/`: `bench_<timestamp>.jsonl` (one
RunResult per line) and `bench_<timestamp>.md` (per-family mean scores,
latency p50/p95, ok/failed/skipped counts). The markdown is also printed
to stdout.

## How to read the report

Each row is one family: task count, ok count, mean `tool_f1`,
`numeric_acc`, `groundedness`, and latency p50/p95 over ok tasks.
`tool_f1` below 1 usually means the supervisor routed through a delegate
(`delegate_scout` counts as `chain`, `delegate_team` as `brief`) rather
than calling the gold tool directly — check the `tool_calls` column in
the JSONL before treating it as a failure. `numeric_acc` below 1 with
high `groundedness` means the answer cited real evidence but missed the
specific fact. Skipped rows (finder without history tables) are
environment gaps, not agent failures.

## Known limits

- The supervisor speaks mostly through delegates, so family attribution
  for delegate calls is approximate by construction.
- Trade ground truth uses the simplified below-apron rule and ignores
  apron state, aggregation bans, and exceptions — same simplification as
  the tool, recomputed independently from raw rows.
- Scores depend on the warehouse snapshot and the live LLM provider, so
  cross-run comparison needs the same seed plus a fresh warehouse.
- The benchmark issues real LLM calls and can take minutes; it never
  writes to the warehouse itself (ground truth uses read-only
  connections), but the agent under test may fetch-and-cache normally.
