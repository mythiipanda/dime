---
name: morning_briefing
description: Overnight recaps, finals, top scorers, and one surprise.
---
# morning_briefing

Use when the user asks for a briefing, recap, last night, or standouts.

Sequence: get_briefing once. It carries games plus top scorers already.
Add get_standings only if the user asks about races.

Output: every final with score, top three scorers with lines, one surprise
worth knowing. Short sentences. Numbers from tables only.

Pitfalls: offseason dates return empty scoreboards. Say so plainly and
offer the latest finals instead of inventing games.
