---
name: defensive_analysis
description: Evaluate player defense across multiple signals with minutes floors and team-context caveats.
---
# Defensive Analysis

Use when the user asks about a player's defense, best defenders, DPOY-type
questions, or defensive matchups.

Defense is multi-dimensional. No single number defines a defender. Weigh
steals and blocks as signals of event creation, not proof of overall value.
Off-ball positioning, rotations, rim protection, and matchup difficulty all
matter and none are fully captured in box scores.

Signals to combine: steal and block rates (gambling vs discipline), on-court
defensive rating with its team context, opponent shooting when available,
and role (who they guard matters more than raw output).
Always apply a 500+ minute floor before evaluating anyone. Small samples
produce noisy extremes and reward players who haven't been exposed.

On-court DRTG is team context: it reflects the four teammates sharing the
floor, not the individual alone. Never crown someone "best defender" from
on-court DRTG or a steals-per-game total.

Caveat every verdict: note the minutes floor, the sample size, the teammate
context, and which signals point which way. When signals disagree, say so
instead of picking the flattering one.

What NOT to do: never rank defenders on one metric; never compare bench
specialists to full-game starters without adjusting for role and volume.
