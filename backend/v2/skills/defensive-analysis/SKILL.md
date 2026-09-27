---
name: defensive-analysis
description: Evaluate player defense across multiple signals with minutes floors and team-context caveats.
---

# Defensive Analysis

## When to use

Questions about a player's defense, best defenders, DPOY-type questions, or defensive matchups.

## Key insights

- Defense is multi-dimensional. No single number defines a defender. Weigh steals and blocks as signals of event creation, not proof of overall value.
- Off-ball positioning, rotations, rim protection, and matchup difficulty all matter and none are fully captured in box scores.
- Signals to combine: steal and block rates (gambling vs discipline), on-court defensive rating with its team context, opponent shooting when available, and role (who they guard matters more than raw output).
- On-court DRTG is team context: it reflects the four teammates sharing the floor, not the individual alone.

## What to fetch

- Steal and block rate leaders with a 500+ minute floor.
- Defensive rating leaders with a 500+ minute floor.
- On/off defensive splits for context when available.
- Rate-stat leaderboards need a minutes floor: the data layer enforces MIN >= 500 on per-game rate boards (state the floor in every output). Do not impose a blanket floor elsewhere — on totals boards, totals need no floor beyond availability (note games played), and on individual player evaluations report the sample size and qualify instead of excluding.
- Small samples produce noisy extremes: a two-way player's 2-game steal burst is not a signal, so always pair small-sample numbers with their sample size.

## Caveats to apply

- Never crown someone "best defender" from on-court DRTG or a steals-per-game total.
- Note the minutes floor, the sample size, the teammate context, and which signals point which way.
- When signals disagree, say so instead of picking the flattering one.

## What NOT to do

- Never rank defenders on one metric.
- Never compare bench specialists to full-game starters without adjusting for role and volume.
- Never present a steals leader as the "best defensive player" — steals are one signal, not a definition.
