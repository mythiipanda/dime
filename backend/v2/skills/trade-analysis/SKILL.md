---
name: trade-analysis
description: Analyze an NBA trade as a basketball, asset-value, market-price, contract, and legality decision for both teams.
---
# Trade analysis

## Frame the decision

Identify the buyer, seller, competitive timeline, control window, and exact trade sides. Resolve every player, team, performance season, contract vintage, and analysis date before planning. Treat a missing identity or vintage as a blocker.

Form at least two competing readings of the deal. State what evidence would support or weaken each reading. One reading must be the strongest case against the likely verdict.

## Evaluate the assets independently

For each player, answer these questions before comparing the swap:

1. What role and possession burden does the player carry?
2. What is the current production and efficiency baseline?
3. What do predictive impact, adjusted lineup evidence, and contextualized on/off say?
4. Which skills explain the impact and transfer to a different role or team?
5. How stable is the profile across seasons, health, minutes, and role changes?
6. What is the projection over the contract-control window?

Use `player_report` and `player_evaluation` for both players. Use `player_comparison` to normalize role, season, minutes, usage, availability, and team context. A higher all-in-one metric does not settle basketball value. For current role, injury, transaction, option, or team-intent claims, use an explicit `web_search` -> `web_fetch` evidence branch. Search snippets are discovery only.

## Measure replaceability and fit

Build a function-by-function inheritance map for the outgoing player. For each function, identify the internal substitute, likely performance drop, external replacement archetype, acquisition cost, and confidence. Use roster, lineup, and on/off evidence where available. Raw on/off is diagnostic, not causal proof.

Explain what each team adds, loses, duplicates, or exposes. Name the likely closing lineup, creation burden, defensive assignments, off-ball fit, and playoff matchup effects when evidence supports them.

## Separate the four trade questions

Keep these conclusions distinct:

- Basketball value is projected contribution in the intended role.
- Surplus value is projected contribution relative to salary and replacement cost.
- Market price reflects scarcity, control, comparable trades, negotiating position, and timing.
- Legality says whether the proposed structure is allowed.

Use `trade_value` for the modeled production-versus-salary estimate. Use `contracts` for salary, payroll, control, and apron context. Run `trades` only after authoritative salary evidence exists. If it fails, preserve the legality gap. A legal trade can be bad. An attractive illegal trade needs a repair path, not a positive verdict.

Every `trade_value` node names both teams and both player sides. Do not issue a one-sided value call.

## Test contradictions before the verdict

Explain conflicts such as strong box production with weak adjusted impact, a positive on/off split driven by bench quality, or a good player whose contract erases surplus value. Distinguish independent confirmation from several reports repeating the same original report.

Stress-test best, base, and downside cases. State the strongest reason each team says no. Include the opportunity cost in players, picks, depth, flexibility, and the next move the team may lose.

## Complete the answer

A complete answer has:

- current basketball delta;
- projected delta over the control window;
- role and closing-lineup fit;
- function-by-function replaceability;
- surplus-value delta;
- market-price range or a named market-data gap;
- flexibility cost;
- legality status and repair options;
- strongest counterargument;
- accept, reject, negotiate, or insufficient-evidence verdict;
- the price or new evidence that changes the verdict.

Keep every fact tied to admitted evidence. Label projections and judgments. Name missing branches instead of filling them with intuition.
