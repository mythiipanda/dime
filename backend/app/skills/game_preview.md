---
name: game_preview
description: Preview a matchup between two teams with records, form, and a pick.
---
# game_preview

Use when the user names two teams with preview, matchup, tonight, or who wins.

Sequence: resolve_entity for each team, then delegate_team per id in one
block. Add get_standings once for seeding context.

Output: records, recent form from game logs, best lineup by plus-minus,
one edge per team, one pick with reason. Never predict without tables.

Pitfalls: team ids differ across sources. Use returned ids verbatim.
Injuries change picks, check the injury table first.
