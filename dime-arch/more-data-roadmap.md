# More-data roadmap

Grounded 2026-09-13 from a live warehouse inventory
(backend/data/warehouse.duckdb, read_only counts).

## Current coverage (verified)

Current season (2025-26): player season (551), gamelogs (26,488 rows
across 22024+22025), boxscores (2,204), playoffs (170 series rows +
1,949 playoff gamelogs), standings (90), lineups (20,058), on/off
(7,476), zone splits (3,500), salaries (464 players), cap figures
(315), RAPM (490 + 1,882 priors), RAPTOR (19,159 player rows).

Historical depth: gamelogs, shots (3.7M), pbp (3.2M), possessions
(4.5M), standings all run 2009-10 through 2025-26 (17 seasons);
player-season aggregates run 2014-15 onward (11 seasons).

## Gaps, ranked by question impact

1. silver_four_factors: 2 rows - should be 30 teams per season. Team
   identity questions ("why are the Thunder good?") can't cite eFG/TOV/
   ORB/FT-rate. Seed script pattern exists (backend/scripts/seed_*).
2. silver_wowy: 1 row - WOWY ("how do the Knicks do with vs without
   Brunson?") is a one-row stub. record-when-plays works (43-22 canon)
   but true on/off splits per star are missing.
3. hist_player_seasons starts 2014-15 while gamelogs start 2009-10 -
   five seasons of aggregate history (peak Rose, Kobe's last years,
   early Curry) can't answer season-aggregate questions.
4. silver_injuries: 27 rows - injury-context questions ("with X out")
   are thin.
5. watchlists: 0 rows - the Today tab Watchlist card is an empty
   feature end-to-end.
6. silver_combine: 79 rows (one class) - draft-comparison questions
   only work for one class.

## Constraints

- $0 spend: all sources must be free tiers (nba_api, bbref scraping
  within rate limits, existing seed-script patterns).
- stats.nba.com is unreachable from this sandbox (8 test_shots.py
  failures stand); seeds that need it must run where it is reachable.
- Every new table needs: seed script, dataset registration in
  backend/app/datasets.py, at least one benchmark scenario that fails
  without it.
