---
name: warehouse-guide
description: What each warehouse table can and cannot answer — cap/salary, injuries, combine, tracking, hustle, PBP, on-off, draft, standings and schedule — so coverage gaps route to the right table instead of retries or fabricated numbers.
---

# Warehouse Table Guide

Use this guide when a coverage gap, usage error, or schema question arises: find the table that actually holds the answer, check its grain and coverage below, then `warehouse_schema` for exact columns before `sql_exec`. If a table is listed as missing or thin, say the data is unavailable — do not substitute a different season or invent the figure.

A requested metric or dataset may not exist in the warehouse at all (for example a proprietary tracking metric the warehouse never ingested). The correct answer then is the verdict itself: state that the metric does not exist in the warehouse, and back the verdict with the verification evidence — the tables and columns you checked via `warehouse_schema`/`sql_exec`, and the closest related tables that do exist. That verdict, with its evidence, is a complete honest answer. Never substitute proxies (nearest boxscore stats, invented composites) and never narrate the submission instead of writing the verdict.

## Canonical spelling and grain

- `_season` is the season string (`'2025-26'`) on most `silver_*` tables; `silver_hist_*` uses `_season` too but some legacy columns use a start-year int. Confirm on the table itself via `warehouse_schema`.
- `_source`/`_fetched_at`/`_entity` are provenance columns — ignore them in analysis; check `_source` only when diagnosing stale data.
- Two row-encodings recur: uppercase-sport columns (`PLAYER_NAME`, `TEAM_ABBREVIATION`) on API-shaped tables vs lowercase snake_case on curated tables. Never assume one spelling.

## Cap, contracts & roster

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_cap_room` | Projected room, committed salary, holds, and projected cap/tax/apron1/apron2 per `CAP_SEASON`. | Exact live cap-sheet minutiae (trade exceptions, stretch math). |
| `silver_cap_players` | Per-player team salary, contract type, options, guaranteed — cap-sheet rows only, narrower coverage than silver_salaries. | Historical salary; league-average contract distributions. |
| `silver_salaries` | The complete player-salary table — one row per player with TEAM and season-tagged columns SALARY_2025_26 (current year), SALARY_2026_27 and forward. This is the table for trade matching-band math, salary lookups, and any current-or-forward salary figure. | Contract-type/option detail (use silver_cap_players/silver_contracts); historical salaries before 2022 (use silver_hist_salaries). |
| `silver_contracts` | Contract rows: options, qualifying offers, two-way flags. | Dead-cap after waives; extension rule checks. |
| `silver_free_agents` | FA pool by year with type, prior salary, hold estimate. | Bird-rights details; market predictions beyond hold anchor. |
| `silver_rosters` | Current roster membership. | Historical rosters (use `silver_boxscores`/`silver_hist_gamelogs` for who played). |
| `silver_transactions` | Executed moves with dates. | Rumors, agreed-but-unofficial deals. |

## Injuries & availability

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_injury_entries` | Per-entry injury reports: status, injury, return estimate, report date. | Games actually missed (join to boxscores/gamelogs for that). |
| `silver_injuries` | Player-level injury payloads by person. | Team-level inactive lists per game — use `silver_playoff_inactive` or boxscore DNPs. |

## Draft & prospects

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_draft_boards` | Stored board orders (ESPN, etc.) with measurements per prospect. | "Consensus" beyond the boards actually ingested. |
| `silver_prospect_stats` | Recent-class counting stats (PTS/REB/AST/TS/USG). | Full historical college data; defense/film traits. |
| `silver_combine` | ~72-column anthropometrics (heights, wingspan, agility). | Shooting drills context; position-group percentiles need computing in SQL. |
| `silver_future_picks` | Traded picks: owner, protection, conditional status, summary text. | Pick odds before standings resolve; swap-conveyance needs scenario logic. |
| `silver_draft_value_curve` | Expected value by slot for trade math. | Class-depth adjustment — pair with `silver_hist_draft` outcomes. |
| `silver_hist_draft` | Historical draft results by pick. | Prospect-level college profiles. |

## Player tracking & hustle

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_tracking_pt_stats` | Player-tracking aggregates: catch-shoot, pull-up, drives, touches, passes by player. | Possession-level sequencing (use `silver_hist_possessions`/`silver_hist_pbp`). |
| `silver_tracking_pt_shot` | Defender-distance shot splits (tight/open/wide-open) per player. | Shot-maker quality vs shot difficulty fully decomposed. |
| `silver_tracking_pt_defend` | Closest-defender rows: defended FGA, D_FG%, normal FG%, +/- diff. | Scheme attribution; help rotations. |
| `silver_hustle_player` / `silver_hustle_team` | Deflections, charges, contested shots, loose balls, screen assists. | Non-hustle defensive value (pair with impact tables). |
| `silver_hist_hustle` | Multi-season hustle rows at player-season grain. | Playoff hustle (coverage is regular-season rows). |

## Play-by-play, stints & on/off

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_hist_pbp` | Event-level plays: clock, action, shooter, shot result/distance, coordinates. | Lineups on floor per event — join `silver_hist_possessions`/`silver_stints`. |
| `silver_hist_possessions` | Possession boundaries: offense/defense teams, duration, points, start type. | Shot-by-shot detail (join `silver_hist_pbp`). |
| `silver_stints` | Lineup stints per game: in/out clock, duration, team ids. | Aggregate ratings — compute from `silver_hist_possessions` or use `silver_hist_lineups`. |
| `silver_on_off` | Single-player on/off splits. | WOWY differentials — `silver_wowy_derived`. |
| `silver_wowy_derived` | Canonical pre-aggregated WOWY/on-off surface: one row per player-season (`_season`, player_id, player_name, team_id) with games_on, games_played, on_minutes, on_net_per48, off_net_per48, and wowy_diff_per48 (team net per 48 with the player on minus off — positive is good). Covers 2009-10 through 2025-26; current-season 2026-27 is absent because stint coverage lags — that is a coverage lag, not missing data to retry. Use this table for any WOWY/on-off ask; always filter on on_minutes — tiny-minute players produce extreme noise values. | Anything per-game or per-stint granularity (use `silver_stints`); 2026-27 rows. |
| `silver_wowy` | Raw unparsed JSON blobs — do not use; query `silver_wowy_derived` instead. | Everything — superseded by `silver_wowy_derived`. |
| `silver_hist_lineups` | Five-man unit season aggregates (see `lineups-and-rotations` for variant columns). | Per-game lineup minutes (use `silver_stints`). |

## Shots, zones & playtypes

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_shots` / `silver_hist_shots` | Shot events with zone/distance; hex/zone aggregates. | Playtype tags (spot-up, P&R ball-handler) — use playtype tables. |
| `silver_zone_splits` | Player/team shooting by zone. | Below-zone distance detail (query shots). |
| Playtype PPP/frequency (spot-up, P&R ball-handler) | Not currently warehoused — no playtype or synergy table exists in the runtime warehouse; do not probe `silver_playtypes`/`silver_synergy`, they are absent. The correct answer for a playtype ask is the verified-unavailability verdict with the schema checks as evidence. | `silver_playtype_profile` does not exist as a table either — it is a named tool, not a table. |
| `silver_clutch` | Clutch-window stats — filter `GROUP_SET='Players'` for player rows (the table multiplexes group sets; without the filter the player pool reads near-empty). | Custom time-window filters (compute from `silver_hist_pbp`/`silver_stints`). |

## Impact, ratings & four factors

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_rapm` | Raw regularized plus-minus: one row per player (player_id, name, rapm, possessions) for 2025-26 only. | Prior seasons; blended priors (use `silver_rapm_prior`). |
| `silver_impact` | BPM, OBPM, DBPM, VORP, WS/WS48 per player-season (uppercase PLAYER_NAME/TEAM columns), 2021-22 through 2024-25. | Current-season impact — not yet ingested for 2025-26. |
| `silver_raptor_player` / `silver_raptor_team` | Historical RAPTOR/PREDATOR ratings and WAR per player — the season column is `SEASON` as a start-year integer (1977 through 2022), not `_season`. | Current seasons — ingest ends at start-year 2022. |
| `silver_four_factors_team` | Team four-factors per season: EFG_PCT, TOV_PCT, ORB_PCT, FT_RATE plus opponent counterparts, keyed by TEAM + `_season`, 2025-26 and 2026-27. | Historical four-factors before 2025-26. |
| `silver_four_factors` | Thin experimental table (2 rows) of on/off four-factor results — not a general source. | Anything beyond its two rows — prefer `silver_four_factors_team`. |

## Game logs & team games

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_player_gamelogs` | Per-player game lines (MIN, PTS, REB, AST, PLUS_MINUS, uppercase columns) for 2024-25 onward. | Older game logs — use `silver_hist_gamelogs`. |
| `silver_playoff_gamelogs` | Same shape for playoff games, 2010-11 onward. | Regular-season games. |
| `silver_playoffs` | Team-level playoff game results (TEAM_ID, GAME_ID, MATCHUP, PTS, plus/minus) for 2025-26. | Player lines — use `silver_playoff_gamelogs`. |
| `silver_team_games` | Team game results with shooting splits, 2021-22 onward. | Player-level lines (use `silver_player_gamelogs`). |
| `silver_boxscores_ext` | Extended per-player-per-game boxscores including ADV_ advanced columns (offensive/defensive rating, pace, pie) covering 2015-16 through 2024-25 — large table, always filter by season/game; no current-season rows. | Anything needing playtype tags or possession context. |

## Cap history & league financials

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_cap_history` | League cap/tax/apron lines by season: season, salary_cap, luxury_tax, apron_1, apron_2, max-salary tier percentages, cba_era — one row per season at league grain. | Team-level cap positions (use `silver_cap_room`/`silver_cap_players`). |

## Award voting & category leaderboards

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_bbref_awards` | Historical award voting: SEASON, AWARD, RANK, PLAYER, POINTS_WON, AWARD_SHARE, VOTES_FIRST — 1976-77 onward. | Winners before 1976-77; current-season projections. |
| `silver_leaders_pts` / `_reb` / `_ast` / `_stl` / `_blk` / `_dreb` / `_fg_pct` | Per-category season leaderboards (RANK, PLAYER, TEAM, counting stats) spanning 2019-20 through 2026-27 including the current season. | Custom per-game floors or blends — compute from `silver_hist_player_seasons` instead. |

## Seasons, standings & schedule

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_player_season` | Current/recent-season per-game counting lines: PPG/RPG/APG/SPG/BPG, MPG, GP/GS, AGE, TEAM, FG_PCT/FG3_PCT/FT_PCT/TS_PCT, keyed by PLAYER_ID + `_season`. TS-only current scoring-efficiency screens (PPG with TS_PCT cutoffs, ranks, percentiles, comparisons) are one aggregate query over this table. | Usage and impact columns — USG_PCT/ratings/other advanced-only columns are not here; use `silver_advanced` when the screen needs them. |
| `silver_advanced` | Season usage/impact metrics per player: USG_PCT, OFF/DEF/NET_RATING, AST_PCT, REB_PCT, EFG_PCT — join to `silver_player_season` on PLAYER_ID + `_season` (same-season rows only) when a screen mixes those columns with production or TS_PCT. Mixed efficiency+usage/ratings screens are ALWAYS this join, one grouped query. | Shot locations, playtypes, salary — those live in their own tables. |
| `silver_hist_player_seasons` / `silver_hist_team_seasons` | Multi-season player/team totals and rates — performance stats only, no salary columns. | Current-season rows — use `silver_player_season`/`silver_team_ratings`; salaries never live here, use `silver_salaries`. |
| `silver_standings` / `silver_hist_standings` | Standings snapshots. | Tie-breaker resolution logic — state when tied records need them. |
| `silver_schedule` / `silver_scoreboard` | Upcoming/recent game slate, results. | Historical full schedules before ingest coverage — check `_season`. |
| `silver_preseason_projections` | Stored projection inputs. | Actuals vs projections needs a join, not a single table. |

## Leaderboards & qualifying pools

- A "top N" or "how many qualify" ask resolves in ONE aggregate query — `GROUP BY` the entity over the full table with `HAVING` on the cutoff — never per-player loops or sampled subsets. The qualifying pool size is `COUNT(*)` of qualifying rows in that same query; report it exactly.
- Shot-zone cuts (`silver_hist_shots`) aggregate at league scale — group on the zone geometry (e.g. corner-3 `ABS(x_legacy)>=220 AND y_legacy<=92.5`) rather than enumerating players.

## When a table can't answer

- Check `silver_news` for report context (rumors, quotes) — it is text, not stats; never cite it for a number a stats table should hold.
- If the data genuinely isn't warehoused, name the missing table/coverage in the answer instead of substituting a different season, a different player pool, or a remembered figure.
