---
name: warehouse-guide
description: What each warehouse table can and cannot answer — cap/salary, injuries, combine, tracking, hustle, PBP, on-off, draft, standings and schedule — so coverage gaps route to the right table instead of retries or fabricated numbers.
---

# Warehouse Table Guide

Use this guide when a coverage gap, usage error, or schema question arises: find the table that actually holds the answer, check its grain and coverage below, then `warehouse_schema` for exact columns before `sql_exec`. If a table is listed as missing or thin, say the data is unavailable — do not substitute a different season or invent the figure.

## Canonical spelling and grain

- `_season` is the season string (`'2025-26'`) on most `silver_*` tables; `silver_hist_*` uses `_season` too but some legacy columns use a start-year int. Confirm on the table itself via `warehouse_schema`.
- `_source`/`_fetched_at`/`_entity` are provenance columns — ignore them in analysis; check `_source` only when diagnosing stale data.
- Two row-encodings recur: uppercase-sport columns (`PLAYER_NAME`, `TEAM_ABBREVIATION`) on API-shaped tables vs lowercase snake_case on curated tables. Never assume one spelling.

## Cap, contracts & roster

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_cap_room` | Projected room, committed salary, holds, and projected cap/tax/apron1/apron2 per `CAP_SEASON`. | Exact live cap-sheet minutiae (trade exceptions, stretch math). |
| `silver_cap_players` | Per-player team salary, contract type, options, guaranteed. | Historical salary; league-average contract distributions. |
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
| `silver_on_off` | Single-player on/off splits. | WOWY two-player matrices — `get_wowy`/`silver_wowy`. |
| `silver_wowy` | With/without-you payloads. | Three-plus-player combos — compute from stints. |
| `silver_hist_lineups` | Five-man unit season aggregates (see `lineups-and-rotations` for variant columns). | Per-game lineup minutes (use `silver_stints`). |

## Shots, zones & playtypes

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_shots` / `silver_hist_shots` | Shot events with zone/distance; hex/zone aggregates. | Playtype tags (spot-up, P&R ball-handler) — use playtype tables. |
| `silver_zone_splits` | Player/team shooting by zone. | Below-zone distance detail (query shots). |
| `silver_playtypes` | Synergy-style playtype PPP/frequency per player/team where ingested. | Defense-side playtype suppression unless defensive playtype rows exist — verify with `warehouse_schema` first. |
| `silver_synergy` | Seeded synergy aggregates (2015-16→2026-27 per seed). | Coverage varies by season; confirm rows exist for the asked season before quoting. |
| `silver_clutch` | Clutch-window stats — filter `GROUP_SET='Players'` for player rows (the table multiplexes group sets; without the filter the player pool reads near-empty). | Custom time-window filters (compute from `silver_hist_pbp`/`silver_stints`). |

## Seasons, standings & schedule

| Table | Can answer | Cannot answer |
|---|---|---|
| `silver_hist_player_seasons` / `silver_hist_team_seasons` | Multi-season player/team totals and rates. | Current-season rows — use `silver_player_season`/`silver_team_ratings`. |
| `silver_standings` / `silver_hist_standings` | Standings snapshots. | Tie-breaker resolution logic — state when tied records need them. |
| `silver_schedule` / `silver_scoreboard` | Upcoming/recent game slate, results. | Historical full schedules before ingest coverage — check `_season`. |
| `silver_preseason_projections` | Stored projection inputs. | Actuals vs projections needs a join, not a single table. |

## Leaderboards & qualifying pools

- A "top N" or "how many qualify" ask resolves in ONE aggregate query — `GROUP BY` the entity over the full table with `HAVING` on the cutoff — never per-player loops or sampled subsets. The qualifying pool size is `COUNT(*)` of qualifying rows in that same query; report it exactly.
- Shot-zone cuts (`silver_hist_shots`) aggregate at league scale — group on the zone geometry (e.g. corner-3 `ABS(x_legacy)>=220 AND y_legacy<=92.5`) rather than enumerating players.

## When a table can't answer

- Check `silver_news` for report context (rumors, quotes) — it is text, not stats; never cite it for a number a stats table should hold.
- If the data genuinely isn't warehoused, name the missing table/coverage in the answer instead of substituting a different season, a different player pool, or a remembered figure.
