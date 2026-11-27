# History explorer

The History view explores the 29-season warehouse asset (1996-97 through 2024-25): career arcs with era-adjusted trajectory charts, era-relative comp boards, and cross-era leaderboards with within-season z-scores.

## Sub-features

- `history-arc` renders a player's career trajectory as a chart with a data-table alternative.
- `history-comps` shows era-relative statistical comparisons for a player-season.
- `history-leaders` renders era-adjusted leaderboards across all seasons.

## How to get to it (user POV)

- Open `/?tab=history` directly or click History in the Tools sidebar group.

## Driving it with dime-drive

Preconditions:

- Doctor passes. `curl "localhost:9910/api/history/career?player=LeBron%20James"` returns 200 with season rows.

- **Arc.** Load `/?tab=history`, search/select a long-career player (LeBron James). `{wait-text}` for a season label from the 2000s; assert both the chart (a rendered svg/canvas in the arc region) AND the data-table alternative render — the table alternative is a design-system requirement, its absence is a failure. Shot both.
- **Comps.** Select a player-season on the comp board; assert the comp list carries real historical names with similarity context, no placeholder rows.
- **Leaders.** Load the leaderboard; assert seasons spanning the full asset range are selectable and rows carry z-score context. `text` dump for assertions, shot for evidence.
- **Data honesty.** Spot-check one number against the API directly: `curl` the same endpoint and compare — the view must render endpoint values, not derived fiction.

## Gotchas

- The warehouse tops out at the 2024-25 season — current-season history is absent by design, not a defect.
- Career arcs for short-career players legitimately render few points; use long-career players for the canonical proof.
- The history routes once shipped unregistered in production (the mangled-route regression) — a fully empty view with a healthy host means checking route registration first.
- Charts must not animate (design-system rule) — if capturing mid-motion states, that itself is a finding.
