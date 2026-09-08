# SPEC-003: Preview composite tool

Problem: previews scatter across hub, lineups, standings, and win
probability. Second highest demand at 6 of 40 questions.

Change: `get_preview(team_a, team_b)` composes hub records, top lineups
by plus-minus, seeding, rest splits, and Elo-lite probability into one
payload with per-team sections.

Surface: one call feeds the preview answer plus tables. Suggestions
offer boxscore and shot follow-ups.

Verify: scenario asserts Thunder versus Celtics payload names both teams
with records, lineups, and a probability that sums to one.
