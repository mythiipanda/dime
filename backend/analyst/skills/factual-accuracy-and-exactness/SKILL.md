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
- Never compress or round a figure in prose: write "$4,446,789" or whatever the tool result shows verbatim, never "$4.447M", "$750M-ish", "about $290M" or "exceeding $290M". The submission audit matches figures verbatim against tool results and artifact payloads — a compressed or rounded rendering is unbacked even when the underlying computation is exact, and "exceeding X" phrases an approximation as a comparison the evidence never made.
- Keep units attached to every number: attempts vs makes, games vs possessions, per-game vs per-100, percentage points vs percent.

## 4. Recompute Rankings and Deltas From Raw Rows

For "strongest", "smallest", "largest", "best", "worst", or delta questions:

1. Pull the raw numerator and denominator rows for every candidate entity.
2. Recompute each candidate's metric in the same grain and denominator.
3. Compute the delta or ranking from those recomputed values.
4. Verify the sign, magnitude, and units before naming the winner.

Do not infer the winner from a narrative, a single season-summary row, or an unverified tool summary. If the answer hinges on a delta, show the two endpoint values that produced it.

Compute every derived figure — deltas, differences from a threshold or cap line, sums across rows, shares, percentage-point gaps — inside `sql_exec` itself (`SELECT team, payroll, 221200000 - payroll AS apron_room ...`), never by mental arithmetic on tool results. The submission audit rejects any narrated figure that does not appear verbatim in a tool result: a mentally computed delta is unbacked even when both endpoints are backed, and the rejection loop costs the run. One query that emits the endpoints and the derived column together backs every number the answer will cite.

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
- Every derived figure (delta, gap to a threshold, share, total) appears verbatim in a tool result; if it does not, recompute it inside sql_exec before submitting.
- Before every submission or resubmission, re-check ALL prose figures against the audit criteria — exact, tool-backed, present in an artifact — not only the figure the last rejection flagged. Rejections arrive one figure at a time; fixing only the flagged one guarantees another rejection cycle, and each cycle burns budget the answer needs.
- When the run budget is nearly spent, stop verifying and fixing: compose and submit immediately with whatever is already backed. A partial deliverable inside budget is the only thing the evaluator can score — a perfect answer cut mid-composition delivers nothing.
- Never compute any arithmetic in prose at composition time. Adding two salaries for a trade total, subtracting one rating from another for a decline, dividing payroll by wins for cost-per-win — every one of these must be computed inside sql_exec or the artifact payload BEFORE writing the answer. If you find yourself typing arithmetic into prose ("$18,102,000 + $10,449,421 = ..." or "74.4 - 68.1 = 6.3"), stop and compute it in SQL instead; prose-typed arithmetic is invisible to the audit and fails unsupported_claims every time.
- Derived figures must be computed INTO the artifact rows themselves, not just into sql_exec output or prose: when the answer cites a ratio (cost per win), a difference (payroll minus apron), a total across rows, or a per-100 rating, the artifact carries that derived value as its own column or row — add the derivation to the SQL or reshape step that builds the artifact rows (SELECT payroll / wins AS cost_per_win, payroll - 207800000 AS over_second_apron), so each artifact row is self-backing. A derived figure that exists only in prose fails unsupported_claims even when every input is backed, because the audit matches figures against artifact payloads and tool results, not against arithmetic the reader could redo.
- Counts, cohort sizes, and summary statistics (n=108, league means, qualifying totals) are figures too: give them a labeled summary row in the table artifact or a footnote on it — they have no natural entity row, and unstored they fail missing_in_artifacts like any other number.
- Never present data as a prose markdown table. Every tabulated figure must live in the artifact rows themselves: a markdown table in prose is invisible to the audit whenever the submission also carries artifacts, so its figures all fail missing_in_artifacts even though they look tabulated to you.
- Every figure stated in the prose blocks also lives in an artifact row. The submission audit rejects any prose figure missing from the artifact payloads with missing_in_artifacts — prose-only numbers are undeliverable no matter how correct. When a key comparison figure exists only in your sentences, add it to the table/compare/memo artifact rows before submitting; the artifact is the backing exhibit, not decoration, so a figure the reader must trust must appear in both places.
- Echo every methodological stipulation the ask makes — stipulated salary treatments, scenario assumptions, resampling or join instructions, data-source restrictions — and name how your queries implemented each one. A stipulation you followed silently reads as unaddressed: the audit flags it as an uncovered ask when the submission never shows the constraint being applied.
- Methods/caveats disclose filters, sample size, and any custom classification.
- Every scope qualifier echoed in prose or artifacts corresponds to a filter the executed query actually applied. Re-read the last query before claiming `regular season`, `002%`, or a denominator it never restricted — a claimed-but-unimplemented filter is fabricated methodology, not a rounding issue.

If any item fails, fix the query or disclose the limitation before submitting.
