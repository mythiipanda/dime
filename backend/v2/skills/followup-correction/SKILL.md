---
name: followup-correction
description: Handle correction openers by inheriting prior context, but reset entities when the new question is league-wide.
---

# Followup Correction

## When to use

The user opens with a correction phrase — "no i mean", "i meant", "actually", "sorry", "correction:" — indicating the previous answer missed their intent.

## Key insights

- A correction opener signals the user is refining or redirecting, not starting fresh. Inherit the prior turn's context (season, stat, comparison frame) unless the correction explicitly changes it.
- Entity reset rule: if the corrected question is league-wide ("best defensive players in the league", "who leads the league in..."), DROP any player or team entities carried from the prior turn. A league-wide ask names no player — carrying one forward (e.g., Wembanyama from a prior player question) suppresses the league route and steers to the wrong analysis.
- If the correction names a specific player or team, bind to the new entity and drop the old one.
- If the correction is ambiguous about scope, prefer the narrower reading and state the assumption.

## What to fetch

- Reuse the prior turn's fetched data when the correction only reframes the same entities.
- Fetch fresh when the correction changes entities, scope (player-wide to league-wide), or the stat in question.

## Caveats to apply

- State what context was inherited ("using the same 2024-25 season as before").
- State when entities were reset ("treating this as a league-wide question, not about any single player").

## What NOT to do

- Never carry a named player into a league-wide question.
- Never drop the season or stat context silently — if you keep it, say so.
- Never treat "actually" as a full reset; it is a correction, not a new conversation.
