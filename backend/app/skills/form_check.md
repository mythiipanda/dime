# form_check

Use when the user asks about form, slump, hot streak, or last games.

Sequence: resolve_entity, then get_last_x with n 10, then get_percentiles
for the same id. Compare recent averages against season percentiles.

Output: last 10 averages for PTS, FG_PCT, and 3P, percentile context per
category, one verdict sentence on trend direction.

Pitfalls: ten games is noisy. Say so. Never call a slump before checking
minutes and attempts first.
