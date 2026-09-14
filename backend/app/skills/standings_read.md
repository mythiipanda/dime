---
name: standings_read
description: Standings, playoff races, seeds, and clinch notes.
---
# standings_read

Use when the user asks about standings, races, seeds, or clinching.

Sequence: get_standings once. Read PlayoffRank and ConferenceRecord first.

Output: top four per conference with records, one race worth watching,
one clinch or elimination note. Never invent streaks or magic numbers.

Pitfalls: ranks shift nightly. Date every claim with the fetch date from
provenance.
