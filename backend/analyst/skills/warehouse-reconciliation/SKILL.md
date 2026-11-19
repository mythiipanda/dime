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

## 4. Handling 0-Row Observations & False Premises

`sql_exec` returns `ok: true, rows: [], row_count: 0, meta: { empty_observation: true }` when a valid query matches zero rows:
- Do **not** treat a 0-row result as a tool crash. First verify your filter literals (spelling, case, season encoding) against `warehouse_schema` or a broader `SELECT DISTINCT` probe.
- When the named table lacks the requested season, phase, or team, say so, then keep the requested scope: list coverage (`SELECT DISTINCT _season, ...`) in other tables that hold the same measure and verify each requested scope has rows there before switching. Never substitute an adjacent season or shift the comparison window to fit the first table's coverage. If no table covers a requested scope, report that gap for that part.
- Once filters are verified, a 0-row observation is affirmative evidence that no entity or event satisfied those criteria in the covered warehouse scope (e.g., resolving a false-premise question). Report the exact verified scope and the 0-row finding transparently.
