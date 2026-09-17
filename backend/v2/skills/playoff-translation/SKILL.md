---
name: playoff-translation
description: Test whether a team's regular-season profile will translate to the playoffs using separate performance, rotation, availability, and late-game evidence.
---
# Playoff translation

## Frame competing hypotheses

Treat translation as a decision with at least two live hypotheses: the regular-season profile is portable, or a playoff-specific weakness will compress it. State what evidence would change the conclusion. Do not treat regular-season net rating, record, or one playoff result as sufficient by itself.

## Keep populations separate

Pin every season and season type. Use `team_ratings` for the regular-season baseline and `playoff_team_ratings` for completed playoff-game ratings. Never blend them into one sample. A cross-population change is derived and requires a declared calculation over the two evidence envelopes.

Use `clutch` for late-game execution with its sample visible. Use `injuries` or `injury_impact` for current availability, and `roster`, `team_splits`, or lineup evidence for rotation durability and role concentration when available. Do not use roster membership as injury evidence. Keep historical playoff performance separate from current availability.

## Test mechanisms and contradictions

Cover offense, defense, late-game execution, rotation durability, and availability risk. Test at least one mechanism that could fail under playoff conditions, such as half-court creation concentration, shooting dependence, foul pressure, defensive matchup exposure, or lineup depth, but only when an available capability measures it.

Actively look for disagreement between record, regular-season ratings, playoff ratings, clutch results, and availability. Explain whether the disagreement reflects population, sample, role, or missing evidence. Do not turn correlation or raw on/off into a cause.

## Complete the briefing

Separate observed facts from inference. Give the likely translation outcome, confidence and its limiting evidence, strongest counterargument, and the signal that would change the call. If a material branch is unavailable, name it and keep the outcome partial rather than filling it with a nearby metric.
