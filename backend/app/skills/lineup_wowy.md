---
name: lineup_wowy
description: Best lineups and with-or-without-you pairs with minutes context.
---
# lineup_wowy

Use when the user asks who plays well together, best lineup, on-off, or Wowy.

Sequence: resolve_entity for the team, then get_lineups once, then get_wowy
for the key pair. Read lineups sorted by minutes first.

Output: top three lineups by plus-minus with minutes, the requested pair
split, one warning when minutes sit under 100.

Pitfalls: small samples lie. Always state minutes next to plus-minus.
Never rank a 20 minute lineup above a 500 minute one without saying so.
