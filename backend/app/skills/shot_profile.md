# shot_profile

Use when the user asks about shooting, shot chart, zones, or efficiency.

Sequence: resolve_entity, then get_player_intel, then the shots dataset
through get_player_intel context or a direct shots fetch. Split makes and
attempts into rim, midrange, and three.

Output: zone shares plus zone efficiency, best zone, weakest zone, one
sentence on shot diet. Plot coordinates back the story.

Pitfalls: zone edges need consistent definitions. Rim means under 8 feet.
Corner threes stay separate from above break threes when data allows.
