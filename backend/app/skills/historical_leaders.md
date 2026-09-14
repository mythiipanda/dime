---
name: historical_leaders
description: Multi-season or all-time leaders by end-year season range.
---
# historical_leaders

Use when the user asks about multi-season, all-time, decade, or best single-season leaders.

Sequence: get_historical_leaders with the category and the requested
range. Seasons are end-years, 2025 means 2024-25.

Output: leaders per season or best single seasons depending on mode,
values verbatim, coverage range dated.

Pitfalls: coverage runs 2015 to 2025. Out-of-range seasons return
empty, report that honestly and never fabricate. Values are per-game
warehouse estimates, not totals.
