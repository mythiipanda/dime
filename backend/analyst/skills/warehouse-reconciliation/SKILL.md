---
name: warehouse-reconciliation
description: Inspect warehouse_schema, reconcile season encodings, regular-season vs playoff scope, traded-player TOT/2TM row deduplication, and empty/0-row warehouse evidence.
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

## 3. Traded Players & Entity-Level Deduplication

In player-season tables, a traded player often has one combined row (`TEAM_ABBREVIATION IN ('TOT', '2TM', '3TM')`) PLUS one row per stint team:
- **Counting distinct players**: Use `COUNT(DISTINCT player_id)` (or `COUNT(DISTINCT PLAYER_NAME)` if ID is absent), never `COUNT(*)`.
- **Avoiding double-counting totals**: When summing across the league, exclude `TOT`/`2TM`/`3TM` summary rows (or keep ONLY `TOT`/`2TM`/`3TM` for single-row player-season leaderboards, falling back to single-team rows when a player was not traded).
- **Weighted vs unweighted averages**: Compute league or team efficiency from summed numerators and denominators (`SUM(PTS) / (2.0 * (SUM(FGA) + 0.44 * SUM(FTA)))`), never by averaging player-level percentages (`AVG(TS_PCT)`).

## 4. Handling 0-Row Observations & False Premises

`sql_exec` returns `ok: true, rows: [], row_count: 0, meta: { empty_observation: true }` when a valid query matches zero rows:
- Do **not** treat a 0-row result as a tool crash. First verify your filter literals (spelling, case, season encoding) against `warehouse_schema` or a broader `SELECT DISTINCT` probe.
- Once filters are verified, a 0-row observation is affirmative evidence that no entity or event satisfied those criteria in the covered warehouse scope (e.g., resolving a false-premise question). Report the exact verified scope and the 0-row finding transparently.

## 5. Cross-Table Joins

- Join players and teams on IDs whenever both sides carry them.
- When only names are shared, normalize both sides before joining: strip accents, punctuation, and suffixes (Jr., Sr., II, III), collapse whitespace, lowercase.
- Report matched and unmatched counts. If more than a few percent of rows fail to match, inspect the unmatched names and fix the join before computing anything from it.
