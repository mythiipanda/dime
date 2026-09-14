---
name: impact_check
description: On-off impact and value, which factors move with a player on court.
---
# impact_check

Use when the user asks about impact, value, on-off, or carrying a team.

Sequence: resolve_entity, then get_on_off plus get_four_factors together.
Read TS% and eFG% deltas first, then the four factor rows.

Output: on-court versus off-court efficiency deltas, which factors move,
one sentence on how the impact happens. Never reduce impact to points.

Pitfalls: on-off confounds teammates. Name the biggest confound you see,
usually the co-star sharing minutes.
