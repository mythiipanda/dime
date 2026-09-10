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
   head-to-head on that stat. Ground truth is per-game from cached
   gamelogs, `round(sum / gp, 1)`, exactly what `get_compare` reports
   (not season totals). Gold: `get_compare`.
3. `chain` — two hops. Finds players whose latest gamelog game has a
   cached boxscore, takes his latest game, then asks for that game's
   boxscore top scorer. Gold:
   `get_player_intel`/`get_last_x` plus `get_boxscore`.
4. `adjudicate` — one player present in both leaders and on/off tables.
   Asks whether percentile rank and on/off net agree. Gold:
   `get_percentiles`/`get_on_off`.
5. `trade` — two random players on different salary-sheet teams with
   real salaries. Asks if a one-for-one swap is legal. Ground truth
   recomputes the tool's salary-matching rule from raw salary rows:
   125pct-plus-250k below the first apron ($209,661,000 payroll),
   100pct above it. A 1-for-1 never trips the second-apron
   aggregation ban. Teams come from the salary sheet so the tool's
   payroll matching accepts them. Gold: `get_trade_check`.
6. `brief` — slate briefing for a random cached scoreboard date. Ground
   truth is game count plus team abbreviations. Scores mainly coverage
   and latency. Gold: `get_games_on_date` (the date-slate tool;
   `get_today`/`get_morning_briefing` only cover the current day and
   cannot answer arbitrary cached dates).
7. `finder` — random team streak question from history tables. If no
   history tables exist, the task is skipped gracefully (`ok=False`,
   `error=skipped: ...`) instead of failing. Gold: `get_finder`.
8. `comps` — nearest statistical neighbors of a top-50 scorer (400+
   minutes) over the same 18-feature pipeline as `get_comps`: 8 counting
   stats per-36, FG3%/FT%, 8 advanced; z-scored with mean-imputation for
   missing values, zero-variance features dropped. Similarity is
   round(100/(1+dist/20), 1). Ground truth is verified to match the
   tool exactly. Gold: `get_comps`.
9. `splits` — last-15 PPG split by top-10 defenses (lowest DEF_RATING)
   for a player with 20+ gamelogs. Gold: `get_matchup_splits`.
10. `trade_value` — which side wins a one-for-one trade on production
    value vs salary. Ground truth replicates `get_trade_value`'s value
    model exactly: production_score = round(sum(per-game stat *
    weight), 2) with weights PTS 1.0 / REB 1.2 / AST 1.5 / STL 2.0 /
    BLK 2.0 / TOV -1.5; dollars-per-point over qualified (GP>=20,
    salaried) players; est_market_value_m = round(score * dpp / 1e6, 1);
    winner by side delta >= 0.5. Players are sampled from the
    salary-sheet roster so the tool's payroll matching accepts them.
    Ground truth is verified to match the tool exactly.
    Gold: `get_trade_value`.
11. `awards` — top-3 MVP candidates by the same z-score model as
    `get_award_race`: components PPG .35 / team win% .20 / net rating
    .15 / APG .15 / RPG .15 over qualified candidates (GP>=20,
    MIN>=500); candidate score = round(total, 2). Ground truth is
    verified to match the tool exactly. Gold: `get_award_race`.
12. `streaks` — longest streak question sampled from five configs:
    30+ point / 10+ rebound / 10+ assist / 4+ three-pointer games
    (player scope, from cached gamelogs) or win streak (team scope,
    regular-season only from history tables). Ground truth mirrors
    `get_streaks`' ranking exactly: per-holder runs, longest-run
    tie-break to the later end date, cross-holder sort by streak
    desc, end_date desc, holder name asc. Mode is always longest;
    active streaks have multiple winners and are ungradeable.
    Streaks under 2 games and unresolved holder names are skipped.
    Gold: `get_streaks`.
13. `lineups` — best net rating per 100 possessions among a random
    team's five-man lineups (minimum 100 possessions). Ground truth
    mirrors `get_lineup_stats` exactly: play-level possession
    aggregates with reconstructed blowout margins, the MIN*2
    estimated fallback when possession data is missing, ratings
    round(x, 1), the 100-possession sample floor, sort by poss desc.
    Ground truth is the best net rating over ALL floor-passing units
    (the tool's default limit=10 is a display slice; the agent can page
    deeper). Teams with fewer than 2 qualifying units or a tied
    best net rating are skipped. No `names` dict: five-man GROUP_NAMEs
    share surnames across units, so last-token name_recall
    false-positives on wrong lineups; the four numeric facts (net/off/
    def rating, possessions) uniquely identify the unit and carry the
    grade. Gold: `get_lineup_stats` (the floor-aware tool; the older
    `get_lineups` maps to `chain` and does not satisfy the sample-floor
    requirement).

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
- `name_recall` — name-based families (comps, trade_value, awards)
  score expected-name coverage: fraction of `names` values whose last
  token appears in the answer, case-insensitive on word boundaries.
  Families without a `names` dict score 1.
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

Failed tasks (`ok=False`) score 0 on all four metrics.

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
latency p50/p95, ttft p50/p95, ok/failed/skipped counts). The markdown is also printed
to stdout.

## How to read the report

Each row is one family: task count, ok count, mean `tool_f1`,
`numeric_acc`, `groundedness`, `name_recall`, and latency p50/p95 over ok tasks.
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
- Trade ground truth recomputes the tool's salary-matching rule from raw
  rows, including the first-apron 100pct form and ignoring exceptions —
  same rule as the tool. A 1-for-1 never trips the aggregation ban.
- Scores depend on the warehouse snapshot and the live LLM provider, so
  cross-run comparison needs the same seed plus a fresh warehouse.
- The benchmark issues real LLM calls and can take minutes; it never
  writes to the warehouse itself (ground truth uses read-only
  connections), but the agent under test may fetch-and-cache normally.
