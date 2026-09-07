# compare_players

Use when the user names two or more players with compare, versus, better, or rank.

Sequence: resolve_entity for each name, then get_player_intel per id in one
block, then get_on_off per id in one block. Never compare without both id sets.

Output: one row per player with PTS, REB, AST, FG_PCT, plus-minus story, and
on-off delta. Name the winner per category, then one verdict sentence.

Pitfalls: nicknames need resolve first. Never use memorized ids. Season
defaults to 2025-26.
