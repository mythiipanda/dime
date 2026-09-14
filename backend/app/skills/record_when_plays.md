---
name: record_when_plays
description: Team record when a named player plays, read verbatim from game logs.
---
# record_when_plays

Use when the user asks about a team's record when a named player plays, sits, or is out.

Sequence: resolve_entity for the player, then search_game_logs with
that player and no filters. Read rows.record over ALL matches, not the
capped game list.

Output: wins-losses from rows.record verbatim, games counted, one
sentence on what the record covers.

Pitfalls: never tally the returned game list by hand, rows.record
already aggregates every match. Keep filters off unless the user scopes
to home, away, or a date window.
