---
name: warehouse-reconciliation
description: Inspect warehouse_schema, reconcile season encodings and salary column years, regular-season vs playoff scope, traded-player TOT/2TM row deduplication, player-name join normalization, and empty/0-row warehouse evidence.
---

# Warehouse SQL Reconciliation & Data Integrity Playbook

Use this playbook before writing non-trivial `sql_exec` or `run_python` queries over Dime's DuckDB warehouse.

## 1. Schema Inspection First

Never guess table or column names:
1. Call `await tools.warehouse_schema({})` (or filter the returned `tables` dictionary in JS inside `codemode`) to confirm exact column spellings, types, `unit` annotations, and `season_semantics`.
2. Inspect `season_semantics` on every returned query result (`declared_column_semantics` and `season_semantics`) before stating units (e.g., `points_per_game` vs `total_points`) or season labels.

## 2. Season Format & Phase Conventions

Different `silver_*` tables encode seasons differently:
- **`_season` (`canonical_label`)**: `YYYY-YY` string such as `'2024-25'` or `'2025-26'`.
- **`season` (`end_year_numeric`)** in historical tables (`silver_hist_standings`, `silver_hist_gamelogs`, `silver_hist_player_seasons`): 4-digit integer end year (`2025` means the `2024-25` season).
- **`season_id` (`nba_season_id_start_year`)**: `'2' + start_year` (e.g., `'22024'` means regular-season `2024-25`).
- **`season_type` (`season_phase`)**: Filter explicitly between `'regular-season'` and `'playoffs'` (or `GAME_ID` prefixes `'002'` regular season vs `'004'` playoffs vs `'001'` preseason). Never mix preseason or playoff rows into regular-season totals unless requested.
- **`silver_hist_gamelogs` is team-grain**: every game produces two rows — one per team — so `COUNT(*)` doubles game counts. Deduplicate with `GROUP BY game_id` (or `COUNT(DISTINCT game_id)`) for game-level questions, resolve venue with `matchup LIKE '%vs.%'` (home) vs `'@'` (away) — pair them via `h.game_id = a.game_id AND h.team_abbreviation <> a.team_abbreviation` — and pin a team whenever you join per-game event tables on `game_id`, or the join fans out 2×.

## 3. Traded Players & Entity-Level Deduplication

In player-season tables, a traded player often has one combined row (`TEAM_ABBREVIATION IN ('TOT', '2TM', '3TM')`) PLUS one row per stint team:
- **Counting distinct players**: Use `COUNT(DISTINCT player_id)` (or `COUNT(DISTINCT PLAYER_NAME)` if ID is absent), never `COUNT(*)`.
- **Avoiding double-counting totals**: When summing across the league, exclude `TOT`/`2TM`/`3TM` summary rows (or keep ONLY `TOT`/`2TM`/`3TM` for single-row player-season leaderboards, falling back to single-team rows when a player was not traded).
- **Stint rows vs season rows**: `silver_hist_player_seasons` is already one row per player-season; `silver_player_season` is not — it has no `TOT` marker rows, and traded players carry one row per team stint (hundreds of multi-row players across seasons). A season-level aggregate or ranking on `silver_player_season` must `GROUP BY PLAYER_ID` and sum the stints, or a traded player's partial rows can both enter a top-N and undersell their total. Never read a stint row as a full-season stat line.
- **Weighted vs unweighted averages**: Compute player, team, or league efficiency from summed numerators and denominators, never by averaging percentages. For player PPG and TS%, use a `player_games` CTE filtered to the requested scope, with one row per player and game:

```sql
SELECT player_id,
       COUNT(*) AS gp,
       SUM(PTS) AS pts,
       SUM(FGA) AS fga,
       SUM(FTA) AS fta,
       SUM(PTS) / COUNT(*) AS ppg,
       SUM(PTS) / NULLIF(2.0 * (SUM(FGA) + 0.44 * SUM(FTA)), 0) AS ts_pct
FROM player_games
GROUP BY player_id
```

- **Comparable rates**: Use the same formula, scale, and grain for both sides. If only a stored rate is available on one side, verify its definition and scope before comparing it with a derived rate. Subtract the fractions, then multiply by 100 for a percentage-point delta. TS% above 100% can occur in a small sample; check the `2.0 *` denominator, fraction vs 0–100 scale, and that points and attempts cover the same player, games, and phase. Do not clamp the result.

## 4. Person-Name Joins: Normalize Before Matching

Player-name spellings differ across `silver_*` tables: stat/tracking tables carry accented forms (`Hugo González`, `Moussa Diabaté`, `Nikola Jokić`) while `silver_salaries` and box-score tables often store ASCII (`Hugo Gonzalez`). An exact `name = PLAYER_NAME` join silently drops those rows — and in a filtered top-N ranking the dropped players can be exactly the ones that matter, so a result can look verified while a slice of the population is missing.

- Join on `player_id`/`PLAYER_ID` when both sides carry one; IDs skip name normalization entirely.
- Otherwise normalize both sides before comparing: strip diacritics, lowercase, drop punctuation, collapse whitespace, and remove generational suffixes:

```sql
STRIP_ACCENTS(REPLACE(LOWER(name_col), '.', ''))
```

In Python: `unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()` plus punctuation/suffix cleanup.

- After any name join, audit the match count (matched vs total rows on each side) and skim the unmatched names before trusting ranked output. If the join drops qualifying rows, fix the normalization; if some remain unmatched after normalization, disclose the shortfall rather than presenting a partial ranking as complete.
- Exploring normalization and then shipping the exact join anyway is a known failure: once you have seen unmatched names, the partial result is not the answer — apply the normalized join or state explicitly that coverage excludes those entities.

## 5. Handling 0-Row Observations & False Premises

`sql_exec` returns `ok: true, rows: [], row_count: 0, meta: { empty_observation: true }` when a valid query matches zero rows:
- Do **not** treat a 0-row result as a tool crash. First verify your filter literals (spelling, case, season encoding) against `warehouse_schema` or a broader `SELECT DISTINCT` probe.
- When the named table lacks the requested season, phase, or team, say so, then keep the requested scope: list coverage (`SELECT DISTINCT _season, ...`) in other tables that hold the same measure and verify each requested scope has rows there before switching. Never substitute an adjacent season or shift the comparison window to fit the first table's coverage. If no table covers a requested scope, report that gap for that part.
- Once filters are verified, a 0-row observation is affirmative evidence that no entity or event satisfied those criteria in the covered warehouse scope (e.g., resolving a false-premise question). Report the exact verified scope and the 0-row finding transparently.

## 5. Current Season vs Completed Seasons (Stale Premises)

Warehouse coverage lags the calendar: production and game tables (`silver_leaders_*`, `silver_team_games`, `silver_player_season`, box scores, play-by-play) hold completed seasons only, while contract and roster tables (`silver_salaries`, `silver_cap_players`) describe the current league and are labelled with the current season in `_season`. `silver_player_season` carries only the latest season; for earlier seasons join `silver_hist_player_seasons`, which stores per-game averages and per-season rows. Consequences:

- **"Current" questions**: pass the current NBA season to contract, trade and roster tools. They pair current salary/roster data with the latest production season and report both in `meta` (`production_season` vs `salary_season`). Stat-only tools that have no rows for the current season fall back to the latest season with data and set `meta.season_fallback` / `meta.requested_season` — always quote the season each figure actually covers.
- **Unspecified season-long totals and leaderboards resolve to the latest completed season while the current one is early**: an ask like "who leads the league in corner threes" with no season named wants complete-season volume, not the partial in-progress rows — query the latest completed `_season` (2025-26) and label it in the answer. Only an explicit "this season" or "in 2026-27" means the in-progress partial data, and then the small-sample caveat applies.
- **Team attribution is season-dependent**: a player who changed teams has one team in past-season production rows and another in the current salary sheet (for example a star traded in the offseason). Resolve "who is on team X" against the season the question is about before answering.
- **Salary columns carry year semantics**: in `silver_salaries`, `SALARY` is the cap hit for the row's `_season`; the `SALARY_20XX_YY`/`OPTION_20XX_YY` columns are per-contract-year values and shift every rollover. For "20XX-YY payroll / cap hit", sum `SALARY` on `_season = '20XX-YY'` rows (or the matching `SALARY_20XX_YY` column) — never a different year column. A frozen column such as `SALARY_2025_26` on 2026-27 rows silently returns last year's payroll, and the result can look verified because the schema accepts it. When the prompt's year differs from any column you plan to sum, reconcile it against `SUM(SALARY)` first.
- **Stale premise handling**: when a tool reports that a player's team differs from the question's premise (trade guard errors name the season and the listed team), say the premise is stale, then answer for the player's current team or re-run with the historical season the user meant. Do not force the question's teams through.

## 6. Call Economy: Fewer Turns, Faster Answers

Every codemode turn costs model latency, so spend calls deliberately:

- Inspect schema once per table with `warehouse_schema({ tables: [...] })` and reuse the result via `store`/`load`; never re-fetch the full catalog or repeat a freshness check within a run.
- `get_warehouse_freshness` and `get_dataset_freshness` report overlapping coverage; one freshness check per run is enough unless you specifically need Data Engine ingestion timestamps.
- When `sql_exec` fails, read the error's candidate bindings and `schema_hint` (the referenced tables' real columns, and which tables actually contain a missing column) and correct the query on the next call; call `warehouse_schema` again only when no hint was returned.
- Prefer one comprehensive `run_python` script (loops and intermediate variables inside Python) over many small one-row probe calls, and batch independent `sql_exec`/`run_python` calls with `Promise.all` inside codemode.
