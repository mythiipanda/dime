---
name: factual-accuracy-and-exactness
description: Lock the requested population, season, grain, denominator, and precision before querying, then verify exact figures, rankings, and derived rates before submitting.
---

# Factual Accuracy & Exactness Playbook

Use this playbook when a prompt asks for exact values, per-entity breakdowns, comparisons, deltas, shares, rates, or rankings.

## 1. Scope Lock Before Querying

Before the first warehouse query, write down the requested scope as a checklist:

- Entity set: players, teams, games, seasons, or league population.
- Season encoding and phase: regular season vs playoffs vs preseason, with the exact season label.
- Grain: player, team, game, possession, shot, season, or stint.
- Denominator: per game, per possession, per attempt, per 100 possessions, or share of a named total.
- Precision: exact counts, rounded rates, rankings, deltas, or ranges only when the prompt allows them.

Every SQL filter, Python aggregation, and submitted figure must map back to one checklist item. If a later answer changes scope, restart the checklist instead of blending populations.

Scope qualifiers are WHERE clauses, not prose decoration. When the request names a phase or prefix (`002% regular-season`, `season_type='regular-season'`, preseason vs playoffs), the executed query must apply it literally — a season filter alone does not exclude playoff games on tables that hold both.

## 2. Use Canonical Warehouse Semantics

- Call `warehouse_schema` and use `warehouse-reconciliation` guidance before inventing columns, season encodings, team codes, or phase filters.
- For shot-location questions, use the warehouse's canonical shot-location fields/classes. Do not infer corner, arc, rim, or paint from distance proxies unless the prompt explicitly asks for a custom definition and you label it as custom.
- For player-season leaderboards, handle traded-player `TOT`/`2TM`/`3TM` rows deliberately: count distinct entities and avoid double-counting stint rows.
- For historical tables, respect `season_semantics`; do not mix integer end-year seasons, `season_id`, and canonical labels.

## 3. Exact Figures, Not Proxies

- If the prompt asks for exact counts or values for each requested entity, report them exactly. Do not replace them with ranges, "about", only the leader, or only the most extreme row.
- If a requested exact figure is unavailable in the warehouse, state which figure is unavailable and why; do not silently substitute a nearby proxy.
- Keep units attached to every number: attempts vs makes, games vs possessions, per-game vs per-100, percentage points vs percent.

## 4. Recompute Rankings and Deltas From Raw Rows

For "strongest", "smallest", "largest", "best", "worst", or delta questions:

1. Pull the raw numerator and denominator rows for every candidate entity.
2. Recompute each candidate's metric in the same grain and denominator.
3. Compute the delta or ranking from those recomputed values.
4. Verify the sign, magnitude, and units before naming the winner.

Do not infer the winner from a narrative, a single season-summary row, or an unverified tool summary. If the answer hinges on a delta, show the two endpoint values that produced it.

## 5. Denominator Discipline for Ratios

Before reporting a share, rate, or percentage:

- Name the denominator in the prose and artifact.
- Ensure the denominator matches the prompt: share of 3PAs uses 3PA, not FGA; rim share uses total FGA only if the prompt asks for FGA share; offensive rating per 100 uses possessions, not games.
- Recompute the denominator independently when the ratio looks extreme; a ratio near 80-90% for a minority category is usually a denominator or classification error.

## 6. Pre-Submission Reconciliation

Before `submit_answer`, check every requested deliverable:

- Every requested entity, season, phase, and grain appears.
- Every exact requested number appears as an exact number, not a range.
- Every ratio names its denominator and uses the requested one.
- Every ranking/delta names the recomputed endpoints.
- Methods/caveats disclose filters, sample size, and any custom classification.
- Every scope qualifier echoed in prose or artifacts corresponds to a filter the executed query actually applied. Re-read the last query before claiming `regular season`, `002%`, or a denominator it never restricted — a claimed-but-unimplemented filter is fabricated methodology, not a rounding issue.

If any item fails, fix the query or disclose the limitation before submitting.
