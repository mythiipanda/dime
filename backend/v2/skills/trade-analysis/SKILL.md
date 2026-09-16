---
name: trade-analysis
description: Analyze an NBA trade, including player role and value, team fit, replaceability, contracts, and legality. Use for proposed swaps, trade targets, trade winners, or whether a team should move a player.
---
# Trade analysis

## Plan
- Resolve each player, team, season, and analysis date before comparing value.
- Establish current role and box-score production with `player_report`, and tier/value context with `player_evaluation`. Test replaceability with `roster`, `lineups`, `on_off`, and `player_comparison` where the available evidence fits the question.
- For follow-up trades, carry prior resolved entities and evidence needs forward. Add the incoming player's same-season `player_report` and `player_evaluation`, then use `player_comparison` for the direct swap rather than restarting from a generic trade check.
- Separate player value, basketball fit, replaceability, money, contract terms, trade legality, and each team's preference into distinct branches.
- Use `trade_value` for the production-versus-salary estimate. Check incoming and outgoing salary with `contracts` before `trades`; make the `trades` legality node depend on that contract evidence so its salary season is used for matching. Without authoritative salary evidence, name the legality gap instead of declaring the trade legal.
- Compare what each team gains and loses, including lineup fit, creation burden, defensive assignments, and internal replacements when evidence supports them.
- Use warehouse evidence for measured production and impact. For current role, injury, contract-option, transaction, or team-intent context, plan explicit `web_search` -> `web_fetch` pairs. Search snippets are discovery only. Prefer an official or primary source, then an independent reputable report when it can confirm or challenge a decision-relevant claim.

## Answer
- State the strongest case for each team and the largest downside.
- Keep facts tied to evidence. Label projections and judgments.
- Reconcile source and vintage conflicts explicitly. Do not treat several reports repeating the same original report as independent confirmation.
- Do not turn a metric edge into a universal value ranking.
- Every `trade_value` node must name both teams and both player sides. Do not
  call it with one team, even when the swap wording makes the other side seem
  implicit.
