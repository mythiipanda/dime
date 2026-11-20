---
name: interpretation-and-evidence
description: Turn correct warehouse numbers into correct conclusions. Volunteer the interpretation a number actually supports — bias checks, confounders, and trend context — even when the question only asks for a value.
---

# Interpretation & Evidence Discipline

Numbers alone answer only the literal half of an analytics question. When you report a stat, comparison, ranking, or model output, append the interpretation the data actually supports: what it means, what could be driving it, and what it cannot show. Do not wait for the user to ask "why" or "is that significant".

## What to volunteer

- **Selection and survivorship effects.** Any population defined by a threshold (minutes, possessions, attempts, GP) is biased toward players who earned that volume. "Players with ≥3000 possessions who shoot well" are not a random sample of NBA talent — they are players good enough to keep playing. State which way the bias runs. Same for season filters: a midseason snapshot overstates teams that started hot.
- **Collinearity between candidate drivers.** When two variables move together (usage and assists, height and rim protection, team pace and counting stats), do not attribute an outcome to one without noting the other explains part of it. If the warehouse can't separate them, say so.
- **Confounders the data does carry.** Before crediting a player or scheme, check available context columns: opponent strength, rest, home/away, lineup-mate quality, role change, age. Mention the confounders you could not rule out.
- **Trend versus point estimate.** A single-season or recent-window value answers "what is it now", not "where is it going". When history is available (`get_career_arc`, `get_raptor_history`, `silver_hist_*` tables, trajectory tools), compare the current figure to the player's or team's own prior and to the trajectory — rising, declining, stable, or noisy.
- **Threshold sensitivity.** Results that flip when a qualification cutoff moves slightly are fragile. If a ranking depends on a specific cutoff (≥100 FTA, ≥3000 possessions), note whether the ordering is robust or an artifact of the boundary.
- **Correlation is not mechanism.** A W/L split (eFG% higher in wins) or a correlation between two stats does not establish that one causes the other. Name plausible reverse or third-variable explanations.

## Examples

- Comparing two high-volume free-throw shooters by raw percentage: report the percentages, then add that qualifying at ≥100 FTA selects established rotation guards, that a ~30-attempt gap in volume makes the smaller-sample rate noisier, and that defensive attention on the two players differs — a posterior comparison beats ranking raw percentages.
- A team's win/loss eFG% split: the gap is expected direction (teams that shoot better win more); the informative part is whether the split is wider or narrower than league-typical and whether the TOV split differs — say which, rather than reciting the numbers.
- A metric the warehouse does not contain: after disclosing the gap, interpret the closest proxy you computed and state explicitly that it is a proxy, not the requested metric.
- "Is X having a breakout season?": the season-to-date line plus the career arc — is this level above prior mean, within prior variance, or driven by a new role? Say which.

## Calibrate the claim to the evidence

- Match confidence to sample: full-season ≈ stable, partial season ≈ provisional, single-game or small stint samples ≈ illustrative only.
- "Suggests / is consistent with" when the data can't rule out alternatives; "shows / establishes" only when the confounders were checked.
- End with the one thing that would change the conclusion — more games, a different season window, or a column the warehouse doesn't carry — when the answer is genuinely uncertain.
