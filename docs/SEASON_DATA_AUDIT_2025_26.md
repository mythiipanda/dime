# 2025-26 Season Data Audit (excluding player game logs)

Audited 2026-09-10 by the data desk. All counts read from `backend/data/warehouse.duckdb`.
Every table below is seeded from REAL sources only (nba_api, sportsdataverse-data
releases, Basketball-Reference). Nothing was fabricated; no rows were added or changed
by this audit.

## Verdicts

| Table | Rows | Expected | Source | Verdict |
|---|---|---|---|---|
| `silver_lineups` | 48,188 | full hist slice | sportsdataverse-data `nba_stats_lineups` (via `silver_hist_lineups`, seasons 2021-22→2025-26) | **COMPLETE** — 30 teams, 4,309 distinct 5-man groups. Row duplication (~7/14/21/28 rows per group) is the 7 LeagueDash measure types × regular/playoff variants, all real. The old "~16 games partial" note is stale. |
| `silver_salaries` | 461 | 30 × ~15 | Basketball-Reference `/contracts/` (bref_contracts, scraped 2026-09-10) | **COMPLETE** — all 30 teams, 12–19 players each (avg 15.4). Spot-checked names are real current figures (Curry $62.6M, Jokić $59.0M, Tatum $58.5M; Giannis listed at MIA, AD at WAS). |
| `silver_shots` | 233,632 | full season | sportsdataverse-data `nba_stats_shots` (via `silver_hist_shots`) | **COMPLETE per source** — 1,315 games: 1,230 regular-season (219,159 shots) + 85 playoff (14,473 shots). `GAME_DATE`/`TEAM_NAME` are NULL because the upstream CSV has no date/team-name columns (only `team_tricode` in hist) — cosmetic, matches hist. |
| `silver_hustle_player` | 581 | ~500–600 | nba_api `LeagueHustleStatsPlayer` (2026-09-09) | **COMPLETE** — 30 teams represented, regular season. |
| `silver_hustle_team` | 30 | 30 | nba_api `LeagueHustleStatsTeam` (2026-09-10) | **COMPLETE**. |

## Known gaps (documented, not seedable)

1. **Play-in games missing everywhere.** The 6 play-in games (game-id prefix `005`) appear
   in NO table: not in `silver_shots`, not in `silver_team_games` (2,460 rows = 1,230
   regular-season games only), not in `silver_hist_gamelogs`. This is an upstream-source
   limitation — the sportsdataverse-data releases and the hist seeding both scope to
   regular-season + playoffs. Backfilling would require nba_api shot-chart calls in a
   different schema than `silver_shots` uses, so it stays out of scope rather than
   mixing schemas or fabricating rows.
2. **Salary season label.** `silver_salaries._season` = `2026-27` and the figures are
   2026-27 (current) salaries, but the column is named `SALARY_2025_26`. This is the
   documented spec-column convention in `app/sources/salaries.py` ("kept under spec
   column SALARY_2025_26") — intentional, not a seeding error. Downstream consumers
   should treat the column as "current season salary".
3. **`_source` stamping noise.** `seed_2025_26_warehouse.py` stamps `silver_lineups` and
   `silver_team_games` rows as `_source='sportsdataverse'` at promote time even though
   the hist rows came from sportsdataverse-data releases and nba_api respectively.
   Cosmetic; the per-season slices in the `silver_hist_*` tables carry the true source.

## Scripts written

None — every table above is already complete against its real source, so there was
nothing seedable. Re-running any seed script would only re-fetch identical data.
If play-in coverage is ever wanted, the source of truth would need to be extended
upstream (sportsdataverse-data release) first.
