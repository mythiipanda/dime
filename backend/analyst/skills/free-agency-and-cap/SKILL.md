---
name: free-agency-and-cap
description: Free-agent valuation, cap-room arithmetic with holds and apron boundaries, contract comparisons, and offer-sheet/extension scenario math — the cap analyst's workflow over the salary tables.
---

# Free Agency & Cap Mechanics Playbook

Use this playbook for free-agent fits, cap-room computations, contract value comparisons, and offer-sheet or extension scenarios. Every cap answer names the salary-cap season (e.g. "2026-27") it is computed under — cap figures are pinned to a cap year, not a calendar.

## 0. Tables and what each answers

| Table | Answers | Use it when |
|---|---|---|
| `silver_cap_room` | Per-team projected room, committed salary, FA holds, roster charges, and the projected cap/tax/apron1/apron2 lines for a `CAP_SEASON`. | "How much room does X have" — always report `PROJECTED_ROOM` alongside `PROJECTED_APRON1`/`PROJECTED_APRON2`; room above an apron is not usable the same way. |
| `silver_cap_players` | Per-player salary by team: contract type, options (`player_option`, `team_option`), guaranteed money. | Team payroll books and option-year treatment. |
| `silver_contracts` | Player contract rows with option flags, qualifying offers, two-way flags. | Individual contract terms; join to cap room for team-level effects. |
| `silver_free_agents` | The FA pool for a `FA_YEAR`: type (unrestricted/restricted/ETO), prior salary, cap-hold estimate. | "Who is available this summer" and what each hold does to room. |
| `silver_transactions` | Executed signings/trades/extensions with dates. | What actually happened, and the date context (July moratorium, trade deadline). |

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_free_agents` | The upcoming FA class by team or league-wide: type, prior salary, estimated cap holds, projected room and exceptions. | "Who is available this summer" — the assembled version of `silver_free_agents` + `silver_cap_room`. |
| `get_fa_plan` | One team's FA class with deterministic keep-vs-renounce scenarios against projected room. | "What should X do with its own free agents" — the scenario table is the answer's backbone. |
| `get_cap_scenario` | Post-move payroll vs cap/tax/aprons for named signings, incoming players, or removed contracts. | "Can they afford Y at $ZM" — the arithmetic trace answers it, not prose. |
| `get_salary_history` | A player's year-by-year salary with cap/tax/apron context, team payroll history, or the league cap table. | Historical contract questions and market anchors for what a comp signed at. |
| `get_trade_legality` | Full multi-team trade verdict: salary matching, apron aggregation, sign-and-trade, TPE/cash, Stepien picks. | Concrete multi-team or sign-and-trade proposals — `get_trade_check` covers the simple two-team case. |

## 1. Cap Room Is an Estimate, Not a Number

- A team's usable room is `PROJECTED_ROOM` from `silver_cap_room` minus what the scenario consumes: cap holds (`FA_HOLDS_EST`), incomplete-roster charges, and any signing you add. Report the components, not just the headline room.
- Cap holds block room until renounced: a team "keeping" a free agent can't count the hold toward new signings. State whether the scenario assumes holds kept or renounced.
- Over-the-cap paths differ qualitatively: exceptions (MLE, room exception, bi-annual where applicable) and Bird rights signings are different mechanisms than cap room — say which mechanism the offer uses, and note the apron consequence (hard-cap triggers where they apply).

## 2. Aprons Are Boundaries, Not Lines

- `PROJECTED_APRON1`/`PROJECTED_APRON2` on `silver_cap_room` are hard behavior boundaries: first-apron teams lose trade/flexibility options, second-apron teams face the harshest restrictions (aggregated salaries, no cash, frozen picks in some windows).
- When a signing or trade pushes a team across an apron, flag it — "this signing hard-caps them at apron 1" is part of the answer, not a footnote.
- Never present apron-restricted moves as freely available.

## 3. Free-Agent Fit Workflow

1. Establish the pool: `silver_free_agents` for the `FA_YEAR` — filter by `FA_TYPE` (unrestricted vs restricted vs option-year) before ranking.
2. Establish the budget: `silver_cap_room` for the cap season — room vs exceptions-only.
3. Match need to profile: pull the player's production (`get_player_ratings`/`get_impact_rank`/`get_raptor_history`/`get_rapm`) and role indicators (usage, on-ball share) — a "fit" claim needs both the money math and the basketball case.
4. State the contract shape implied: max-tier (25/30/35% of cap by service), mid-level band, or minimum — and sanity-check `PRIOR_SALARY` + `CAP_HOLD_EST` as the market anchor.

## 4. Contract & Extension Comparisons

- Compare contracts on guaranteed dollars and flat salary, not raw totals: `silver_cap_players.guaranteed` and option flags (`player_option` kills the tail of a deal's value to the team; `team_option` does the opposite).
- AAV lies across cap eras: a $30M AAV signed under the 2024 cap and under the projected 2026 cap are different percentages of cap — compare as `% of cap` when the seasons differ.
- Extensions carry rule constraints (veteran extension raise limits, supermax eligibility via awards/All-NBA) — flag eligibility dependencies instead of assuming the number.

## 5. Valuation Framing — Percentiles and Prior-Context

- **Percentile-vs-market is the claim.** An ask ("$25M AAV") is priced
  against the market band for the profile: rank the player inside his
  position/type pool (`get_player_ratings`/`get_impact_rank` for level,
  `get_comps` for the profile set) and price the percentile band, not the
  name. "Top-15 center production priced at the MLE band" is a verdict;
  "he averaged 19" is not.
- **Prior-team context discounts.** A free agent's production was earned
  in a specific role: high-usage counting stats on a bad team translate at
  a discount to a contender's third-option role, and catch-and-shoot
  efficiency created by a superstar's gravity may not travel. Check the
  shot-diet composition (`get_shot_zones`/`get_playtype_profile`) and the
  WOWY splits (`get_wowy`, `get_lineup_on_off`) around the teammates who
  created his looks before projecting the fit.
- **Contract context as well as amount.** `PRIOR_SALARY`/`CAP_HOLD_EST`
  are market anchors, not prices; a 120% raise on an under-market prior
  deal can still be a fair band. Compare guaranteed dollars and `% of cap`
  across the contract's life, not headline totals — and for multi-year
  asks remember the warehouse's cap lines are a single projected season
  (see the coverage map; multi-year cap projection is not modeled — say
  so rather than fabricating a year-by-year cap table).

## 6. What the Warehouse Can't Answer

- Exact dead-cap/stretch arithmetic for hypothetical waives, and real-time cap-sheet minutiae (trade exceptions, exact hold formulas) are not fully modeled — say so rather than fabricating a figure.
- Two-way/two-way conversion and Exhibit-10 mechanics have no dedicated table; `silver_contracts.TWO_WAY` flags current two-ways only.
