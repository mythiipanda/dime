---
name: draft-and-prospects
description: Draft-board ranking with stated weights, prospect comps by explicit distance metric, draft-capital value curves, pick-swap/protection resolution, and combine-measurement reading — the prospect-eval workflow a real draft analyst runs.
---

# Draft & Prospect Scouting Playbook

Use this playbook for big boards, prospect comps, draft-capital valuation, pick-swap math, and combine/body-tool reads. Every draft answer states its source year and its ranking rule up front — "top-10" means nothing until the board and the weighting are named.

## 0. Tools and when they matter

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_draft_board` | A top-30 production-plus-measurements slice for a draft year, sorted by an ad-hoc blend — not a named board ordering. | Not board-rank asks; query `silver_draft_boards` via `sql_exec` and say which board and year the row came from. |
| `get_draft_model` | In-sample `STAR_P` star probabilities from college production for a class. | Production-proxy star-probability reads. |
| `get_prospect` / `get_combine` | One prospect's profile or anthropometric combine numbers. | Wingspan-to-height and no-shoe height vs position norms. |
| `get_draft_capital` / `get_trade_value` | A team's pick inventory or pick equity within a player trade. | Pick-plus-player trade-value questions. |
| `silver_draft_value_curve` (via `sql_exec`) | Expected value by pick slot from committed data: `SLOT`, `VALUE_INDEX` (plus `MEDIAN_CAREER_WAR`, `HIT_RATE`). | Weighting pick trades: value(pick_n) - value(pick_m) from the curve, not vibes. |
| `silver_prospect_stats` | College counting lines (GP, PTS, REB, AST, TS_PCT, USG). | Stats-based prospect reads; thin coverage — verify a player exists before ranking him. |
| `silver_hist_draft` | Historical draft rows (pick, player, team). | Comp-by-draft-position claims. |
| `silver_combine` | Combine anthropometrics and spot-shooting table (~72 cols: heights with/without shoes, wingspan, hand size, shooting drills). | Positional measurement comps; note TEMP_PLAYER_ID vs PLAYER_ID joins. |
| `silver_future_picks` | Every traded future pick: owner, protection, conditional, summary. | Pick-swap and protection-resolution questions (§3). |

## 1. Big-Board Ranking With Stated Weights

- Say which board(s) you are using before you rank anyone: a media board order is an opinion input, not ground truth; `silver_draft_boards.BOARD` names the board type per row.
- Board-plus-production blends, cohort sizes and pool asks are `sql_exec` over `silver_draft_boards` joined or filtered against `silver_prospect_stats` — `get_draft_board` returns a top-30 ad-hoc production blend, not a board slice, so cohorts built from it drop members and land the wrong counts.
- When the task gives weights ("rank by 60% talent, 40% fit"), implement them literally — order by the weighted score and show both component ranks, never blend silently.
- Tier beats ordinal: consecutive picks (4 vs 6) inside one tier are closer than a tier boundary (8 vs 10). Where the model/board exposes tiers, report the tier cut before the raw order.
- Class depth is part of every pick answer: "pick 9 in a shallow class" and "pick 9 in 2021" are different assets — compare against the slot's expected value or hit rate from `silver_draft_value_curve`.
- Value-curve arithmetic is one query, not a pipeline: `SELECT SLOT, VALUE_INDEX FROM silver_draft_value_curve WHERE _season = (SELECT MAX(_season) FROM silver_draft_value_curve)` returns all 60 slots (~4 KB), then sums, shares, deltas and biggest-drop reads are prose-level math — reaching for `run_python` on these burns calls on code that only needs addition.

## 2. Prospect Comps — Explicit Distance Metric

- Comps are a distance computation, not a name pulled from memory: define the feature vector first (production profile — PTS/REB/AST/TS/USG — plus body tools — wingspan, no-shoe height — plus age and position), then rank candidates by it.
- Use `get_comps` for established-player similarity; for draft prospects pull the candidate pool from `silver_prospect_stats` and compute the distance in `run_python` — state the metric ("euclidean over z-scored PTS/REB/AST/TS_PCT/USG within position group") in the answer.
- Never present a comp as a projection: report it as "closest available profile", and name the dimension where the fit breaks (age, shooting, defensive role).
- A comps answer is a ranked list — the honesty audit rejects stat lines that live only in prose blocks. Emit a `table` artifact whose rows carry every figure the blocks state (comp name, team, distance, and the target's own stat line), then keep the same figures verbatim in the blocks.

## 3. Pick Swaps, Protections & Resolution

- `silver_future_picks` is the ledger: `ORIG_TEAM`, `HELD_BY`, `PROTECTION`, `CONDITIONAL`, `SUMMARY`. A swap is not a pick — read `STATUS`/`CONDITIONAL` before valuing it.
- Resolve protections by scenario: a top-8-protected 2026 first conveys or rolls; state both branches with the trigger, then value the pick under the likeliest standings outcome (use `get_standings` for current standings evidence, never assume).
- A swap's value is `value(better_of_two_slots) - value(own_slot)` on the curve — a swap from a team projected 4th is worth almost nothing; a swap from a fringe playoff team is a real asset. Say which regime applies.

## 4. Combine & Tools Reads

- Position-normalize every measurement: a 7'1" wingspan is ordinary for a center and extreme for a point guard. Compare within position buckets (`POSITION` on `silver_combine`) before calling a trait elite.
- Height sources differ: `HEIGHT_WO_SHOES` vs `HEIGHT_W_SHOES` — say which you used (scouts quote with-shoes).
- Translate tools to role: length + lateral quickness -> switchable defense; standing reach + strength -> rim protection vs finishing; hand size -> ball security. Name the translation, don't recite measurements.

## 5. What the Warehouse Can't Answer

- No full historical college/intl box scores — `silver_prospect_stats` covers recent classes at counting-stat level; defensive and film-based evaluations are outside the data.
- Boards are the stored sources' opinions — do not claim "the consensus" if only some boards are ingested; name the boards actually present.
- Flag genuinely non-computable asks as unavailable rather than substituting a proxy silently.
