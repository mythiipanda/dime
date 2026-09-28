---
name: draft-prospects
description: Evaluate NBA draft prospects with limited college or international data, focusing on translatable skills, age, production context, and the pitfalls of mock-draft consensus.
---
# Draft prospects

## Frame the question

Prospect evaluation asks which skills transfer to an NBA role, at what developmental cost, and how certain the read is. Data is thin by design: one college season, uneven competition, roles that will not exist in the NBA. The skill's job is to separate what the prospect has shown from what the evaluator is projecting.

Start by naming the prospect's age, listed measurements, team, league, role, and usage. An unknown here is a gap, not a guess.

## Gather the production evidence

Use the prospect's rate production with minutes and games played, not raw totals: per-possession or per-minute scoring, true shooting, assist and turnover rates, steal and block rates, rebounding rates. Small samples need their size stated next to every number.

Put production in context. Competition level matters: production in a major conference means something different than the same line in a weaker league or against buy-game opponents. Split the read between performance against real competition and the rest when the schedule allows.

Use `rookie_leaders` to see how comparable profiles performed as NBA rookies. This is a base-rate check, not a comp. For scouting consensus, reported measurements, and workout news, run a `web_search` -> `web_fetch` branch across several independent sources. Search snippets are discovery only. Mock drafts are one data point about consensus, never evidence about the player.

## Reason about translation

Ask which skills transfer independent of role. Shooting mechanics, passing reads, defensive instincts, and footwork travel. Raw percentages in a new role, highlight finishes, and counting stats built on being the best athlete on the floor do not necessarily travel.

Weigh age against production. A 19-year-old producing at the same rate as a 22-year-old is a different bet because the younger player's curve has more room. This is about the slope of development, not a rule that young always beats old.

Test the profile against the likely NBA role, not the college role. A college primary creator may project as a secondary handler; a college rim protector may project as a switchable four. Name the role you are evaluating and the skills that role actually requires.

## Pitfalls

Mock-draft groupthink is the main one. Mocks converge on each other, so five outlets ranking a prospect the same is one consensus, not five independent evaluations. Treat consensus as a market price to be questioned, not a measurement.

Highlight scouting reverses the sampling: a reel shows the best plays of a season, not the median possession. Judge the prospect by full-game and season data, not the edited version.

Tournament games are tiny samples played under odd conditions. A two-game run moves nobody's real evaluation; a two-game slump should not either.

Physical measurements are a ceiling, not a floor. Wingspan and vertical numbers describe what is possible, not what the player does.

Ignore the draft slot when evaluating the player. "He's projected 8th" is about the market, not the prospect.

## Complete the answer

A complete answer has:

- age, size, league, role, usage, and sample size;
- rate production with the sample stated;
- which skills transfer to the projected NBA role and why;
- the age-versus-production read;
- best-case, typical, and downside NBA roles;
- the open questions that would change the read;
- an explicit uncertainty statement.

Keep the consensus read and your own read separate. Never present a mock rank as an evaluation.
