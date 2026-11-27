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
| `silver_cap_players` | Per-player salary by team: contract type, options (`player_option`, `team_option`), guaranteed flag. | Team payroll books and option-year treatment. |
| `silver_contracts` | Player contract rows with option flags, qualifying offers, two-way flags. | Individual contract terms; join to cap room for team-level effects. |
| `silver_free_agents` | The FA pool for a `FA_YEAR`: type (`ufa`, `rfa`, `player_option`, `team_option`, `early_termination`, `two_way`), prior salary, cap-hold estimate. | "Who is available this summer" and what each hold does to room. |
| `silver_transactions` | Executed signings/trades/extensions with dates. | What actually happened, and the date context (July moratorium, trade deadline). |

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_free_agents` | The upcoming FA class by team or league-wide: type, prior salary, estimated cap holds, projected room and exceptions. | "Who is available this summer" — the assembled version of `silver_free_agents` + `silver_cap_room`. |
| `get_fa_plan` | One team's FA class with deterministic keep-vs-renounce scenarios against projected room. | "What should X do with its own free agents" — the scenario table is the answer's backbone. |
| `get_cap_scenario` | Post-move payroll vs cap/tax/aprons for named signings, incoming players, or removed contracts. | "Can they afford Y at $ZM" — the arithmetic trace answers it, not prose. |
| `get_salary_history` | A player's year-by-year salary with cap/tax/apron context, team payroll history, or the league cap table. | Historical contract questions and market anchors for what a comp signed at. |
| `get_trade_legality` | Full multi-team trade verdict: salary matching, apron aggregation, sign-and-trade, TPE/cash, Stepien picks. | Concrete multi-team or sign-and-trade proposals — `get_trade_check` covers the simple two-team case. |

### League-wide scans are one query

Any all-30-team sweep, league-wide scan, payroll-tier count, or cross-team ranking is ONE `sql_exec` over `silver_cap_room` or `silver_salaries` (as appropriate), never 30 per-team tool calls. Use `silver_cap_room` for committed-salary, projected-room, cap/tax/apron scans; use `silver_salaries` only when the ask is explicitly salary-ledger payroll, aggregated from the correct season-tagged salary column. Per-team cap tools are for single-team depth after the scan, not for assembling the league table.

```sql
SELECT CAP_SEASON, payroll_tier, COUNT(*) AS teams
FROM (
    SELECT TEAM,
           CAP_SEASON,
           CASE
               WHEN COMMITTED_SALARY > PROJECTED_APRON2 THEN 'over apron 2'
               WHEN COMMITTED_SALARY > PROJECTED_APRON1 THEN 'over apron 1'
               WHEN COMMITTED_SALARY > PROJECTED_TAX THEN 'over tax line'
               WHEN COMMITTED_SALARY > PROJECTED_CAP THEN 'over cap line'
               ELSE 'at or below cap line'
           END AS payroll_tier
    FROM silver_cap_room
    WHERE CAP_SEASON = (SELECT MAX(CAP_SEASON) FROM silver_cap_room)
) AS team_tiers
GROUP BY CAP_SEASON, payroll_tier
ORDER BY CAP_SEASON, teams DESC, payroll_tier;
```

Pin the `CAP_SEASON` filter to the asked cap season; the subquery form is only for an unqualified current-scan ask. When the answer needs team rows rather than tier counts, select the team rows from the same one filtered query and order them there.

## 1. Cap Room Is an Estimate, Not a Number

- A team's usable room is `PROJECTED_ROOM` from `silver_cap_room` minus the cap holds the scenario keeps and any signing you add; `PROJECTED_ROOM` is already net of incomplete-roster charges. Report the components, not just the headline room.
- Cap holds block room until renounced: a team "keeping" a free agent can't count the hold toward new signings. State whether the scenario assumes holds kept or renounced.
- Cap-hold field contract: `cap_hold` is the effective planning estimate used in arithmetic and `cap_hold_est` is its compatibility alias; both are null when the hold is unknown, never zero-filled. `legacy_cap_hold_est` and raw `CAP_HOLD_EST` are the unvalidated warehouse seed estimate retained for comparison. When derivation inputs are unavailable, the effective estimate may be a clearly labeled legacy-seed fallback rather than a calculator-derived value.
- `get_fa_plan` scenario rows disclose unknown-hold arithmetic. When `unknown_holds_retained_count` is positive, `projected_room` is null because exact room cannot be computed; `projected_room_upper_bound` is only a ceiling that excludes those unknown amounts, never an exact zero-cost assumption. `cap_holds_retained` and `cap_holds_renounced` are exact only when their semantics say `exact`; `known_amounts_partial_sum` means unknown-dollar amounts are excluded and the corresponding unknown count is emitted. Renounced unknown holds do not affect exact room after renunciation, but their unknown amounts still make the renounced-dollar total partial.
- Over-the-cap paths differ qualitatively: exceptions (MLE, room exception, bi-annual where applicable) and Bird rights signings are different mechanisms than cap room — say which mechanism the offer uses, and note the apron consequence (hard-cap triggers where they apply).

## 2. Aprons Are Boundaries, Not Lines

- `PROJECTED_APRON1`/`PROJECTED_APRON2` on `silver_cap_room` are hard behavior boundaries: first-apron teams lose trade/flexibility options, second-apron teams face the harshest restrictions (aggregated salaries, no cash, frozen picks in some windows).
- When a signing or trade pushes a team across an apron, flag it — "this signing hard-caps them at apron 1" is part of the answer, not a footnote.
- Never present apron-restricted moves as freely available.

## 3. Free-Agent Fit Workflow

1. Establish the pool: `silver_free_agents` for the `FA_YEAR` — filter by exact `FA_TYPE` code before ranking.
2. Establish the budget: `silver_cap_room` for the cap season — room vs exceptions-only.
3. Match need to profile: pull the player's production (`get_player_ratings`/`get_impact_rank`/`get_raptor_history`/`get_rapm`) and role indicators (usage, on-ball share) — a "fit" claim needs both the money math and the basketball case.
4. State the contract shape implied: max-tier (25/30/35% of cap by service), mid-level band, or minimum — and sanity-check `PRIOR_SALARY` + `CAP_HOLD_EST` as the market anchor.

## 4. Contract & Extension Comparisons

- Compare contracts on guaranteed dollars and flat salary, not raw totals: `silver_salaries.GUARANTEED` and `silver_cap_players` option flags (`player_option` kills the tail of a deal's value to the team; `team_option` does the opposite).
- AAV lies across cap eras: a $30M AAV signed under the 2024 cap and under the projected 2026 cap are different percentages of cap — compare as `% of cap` when the seasons differ.
- Extensions carry rule constraints (veteran extension raise limits, supermax eligibility via awards/All-NBA) — flag eligibility dependencies instead of assuming the number.

## 5. Max-Contract Tier Math

The three max-salary tiers are percentages of the salary cap for the contract's first season, set by the player's years of service: 0-6 years -> 25% of cap, 7-9 years -> 30%, 10+ years -> 35%. To compute a max figure: use the target season's cap line from the cap history table via get_salary_history only when that exact season exists in cap history (coverage ends at 2025-26). For a later target season, use the authoritative current/projected source for that exact season: for 2026-27, the official constants backing the cap tools (`CAP` in `backend/shared/tools/league/cba_cap.py`, exposed as `meta.cap` by `get_cap_table`); for a projected `CAP_SEASON` such as 2027-28, the league-wide `PROJECTED_CAP` carried on `silver_cap_room` rows marked `ESTIMATED`. When neither source covers the target season, declare it unavailable rather than substituting another cap year. Multiply the resolved exact-season cap by the tier percentage and report the dollar amount with the cap season pinned. A "max-contract math" ask wants all three tier amounts computed from the same cap number, each labeled with its service band — never compute only the tier the question's example player falls in.

## 6. What the Warehouse Can't Answer

- Exact dead-cap/stretch arithmetic for hypothetical waives, and real-time cap-sheet minutiae (trade exceptions, exact hold formulas) are not fully modeled — say so rather than fabricating a figure.
- Two-way/two-way conversion and Exhibit-10 mechanics have no dedicated table; `silver_contracts.TWO_WAY` is a row-season flag.
