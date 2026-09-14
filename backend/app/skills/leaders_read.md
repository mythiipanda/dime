---
name: leaders_read
description: League leaders in a stat, totals and per-game from one table.
---
# leaders_read

Use when the user asks who leads the league in a stat, scoring title, or per-game versus totals leaders.

Sequence: get_leaders once per stat category. The rows carry totals
and per-game columns together, so one call answers both versions.

Output: top five with totals and per-game values side by side, one line
on who holds each version of the lead. Values verbatim from rows.

Pitfalls: never multiply a per-game average by GP to build a total.
Never compare totals across different games played without saying so.
Season defaults to 2025-26.
