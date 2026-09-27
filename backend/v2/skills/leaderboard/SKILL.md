---
name: leaderboard
description: Read and present stat leaderboards with stated minutes qualifications for rate stats.
---

# Leaderboard

## When to use

Questions about who leads the league in a stat, scoring titles, per-game versus totals leaders, or top-N lists.

## Key insights

- Rate stats (per-game, per-36, percentages, ratings) require minutes qualifications. Never present a rate leaderboard without a minutes floor.
- Totals and per-game answer different questions. State which version the user asked for, and name the other version's holder when they differ.
- Per-game leaders need a meaningful sample. Totals leaders need no floor beyond availability, but note games played when the gap is close.
- If the floor changes what the board looks like, show how: the qualified leaders versus the raw sort, with the difference noted.

## What to fetch

- Rate-stat leaders with an explicit minutes floor (default 500+ minutes for per-game stats).
- Totals leaders with games-played context.
- Both per-game and totals versions when they tell different stories.

## Caveats to apply

- Always state the minutes floor used, in the output, every time.
- Never crown an obscure low-minute player as "best" because their per-game line looks gaudy.
- Never multiply a per-game average by games to manufacture a total.

## What NOT to do

- Never list a two-game 40% three-point shooter as a shooting leader.
- Never present a qualified board as raw.
- Never compare totals across different games played without saying so.
