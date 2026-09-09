# compare_players

Use when the user names two or more players with compare, versus, better, or rank.

Sequence: resolve_entity for each name, then get_compare once for the
box-score base, then one delegate per player for shot diet via
get_shot_compare, clutch via get_clutch, and advanced depth via get_rapm
plus get_raptor_history. Then delegate_team per side for record and rating
context. Never compare without both id sets.

Output: one row per player with PTS, REB, AST, FG_PCT, plus-minus story, and
on-off delta. Name the winner per dimension covering scoring, efficiency,
shot diet, clutch, impact, and team context, then one overall verdict.

Pitfalls: nicknames need resolve first. Never use memorized ids. Season
defaults to 2025-26. RAPM-lite and RAPTOR are estimates. EPM, PER, BPM, WS,
VORP, and LEBRON are unavailable, never quote them.
