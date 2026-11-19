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
- **Phase is not season**: `GAME_ID LIKE '002%'` selects the regular season of every season a table holds. Multi-season tables (`silver_hist_shots`, `silver_hist_gamelogs`, `silver_advanced`, ...) also need a `_season` filter. When `sql_exec` returns `meta.season_scope_warning`, add the filter and rerun before using the rows.
- **Bound check**: a shooting percentage, eFG%, or TS% above 100%, or a single-season game count above 1,230, means the population or formula is wrong; fix it before reporting.

## 3. Traded Players & Entity-Level Deduplication

In player-season tables, a traded player often has one combined row (`TEAM_ABBREVIATION IN ('TOT', '2TM', '3TM')`) PLUS one row per stint team:
- **Counting distinct players**: Use `COUNT(DISTINCT player_id)` (or `COUNT(DISTINCT PLAYER_NAME)` if ID is absent), never `COUNT(*)`.
- **Avoiding double-counting totals**: When summing across the league, exclude `TOT`/`2TM`/`3TM` summary rows (or keep ONLY `TOT`/`2TM`/`3TM` for single-row player-season leaderboards, falling back to single-team rows when a player was not traded).
- **Weighted vs unweighted averages**: Compute league or team efficiency from summed numerators and denominators (`SUM(PTS) / (2.0 * (SUM(FGA) + 0.44 * SUM(FTA)))`), never by averaging player-level percentages (`AVG(TS_PCT)`).

## 4. Handling 0-Row Observations & False Premises

`sql_exec` returns `ok: true, rows: [], row_count: 0, meta: { empty_observation: true }` when a valid query matches zero rows:
- Do **not** treat a 0-row result as a tool crash. First verify your filter literals (spelling, case, season encoding) against `warehouse_schema` or a broader `SELECT DISTINCT` probe.
- Once filters are verified, a 0-row observation is affirmative evidence that no entity or event satisfied those criteria in the covered warehouse scope (e.g., resolving a false-premise question). Report the exact verified scope and the 0-row finding transparently.

## 5. Duplicate Rows
- When an audit finds duplicate rows by the event key, build one deduplicated CTE (`QUALIFY row_number() OVER (PARTITION BY <key> ORDER BY _fetched_at DESC) = 1`) and run every later aggregate on that CTE, never on the raw table.
- Reconcile before reporting: the deduplicated attempt total must equal the unique-key count from the audit. A total that still equals the raw row count means the aggregate read duplicated rows.
- Explain what duplication does to each metric: uniform k-fold duplication multiplies counts (FGA, FGM, possessions) by k but leaves ratios (FG%, eFG%, per-possession rates) unchanged, because numerator and denominator scale together. Non-uniform duplication biases ratios too.

## 6. Joining Tables on Player Names

Name-keyed tables spell the same player differently: accents (`Nikola Jokić` vs `Nikola Jokic`), punctuation (`A.J. Green` vs `AJ Green`), and suffixes (`Larry Nance Jr.` vs `Larry Nance Jr`). A raw `ON a.PLAYER_NAME = b.name` join silently drops those players.
- Join on `name_key(a.PLAYER_NAME) = name_key(b.name)`. `name_key` is built into every `sql_exec` and `run_python` connection; it strips accents, punctuation, and generational suffixes, and returns NULL for rows whose name holds no letters.
- Prefer `player_id` joins whenever both tables carry an ID.
- Before ranking or aggregating, count unmatched rows on each side with an anti-join and report the count and the names.
- Compute team-level totals (payroll, wins) from each source table on its own, then join teams on the team key. Never derive a team total from a player-level join, because every unmatched player shrinks that team's total and can drop the team entirely.

## 7. Call Economy: Fewer Turns, Faster Answers

Every codemode turn costs model latency, so spend calls deliberately:

- Inspect schema once per table with `warehouse_schema({ tables: [...] })` and reuse the result via `store`/`load`; never re-fetch the full catalog or repeat a freshness check within a run.
- `get_warehouse_freshness` and `get_dataset_freshness` report overlapping coverage; one freshness check per run is enough unless you specifically need Data Engine ingestion timestamps.
- When `sql_exec` fails, read the error's candidate bindings and `schema_hint` (the referenced tables' real columns, and which tables actually contain a missing column) and correct the query on the next call; call `warehouse_schema` again only when no hint was returned.
- Prefer one comprehensive `run_python` script (loops and intermediate variables inside Python) over many small one-row probe calls, and batch independent `sql_exec`/`run_python` calls with `Promise.all` inside codemode.

## 8. Current Season vs Completed Seasons (Stale Premises)

Warehouse coverage lags the calendar: production and game tables (`silver_leaders_*`, `silver_team_games`, `silver_player_season`, box scores, play-by-play) hold completed seasons only, while contract and roster tables (`silver_salaries`, `silver_cap_players`) describe the current league and are labelled with the current season in `_season`. Consequences:

- **"Current" questions**: pass the current NBA season to contract, trade and roster tools. They pair current salary/roster data with the latest production season and report both in `meta` (`production_season` vs `salary_season`). Stat-only tools that have no rows for the current season fall back to the latest season with data and set `meta.season_fallback` / `meta.requested_season` — always quote the season each figure actually covers.
- **Team attribution is season-dependent**: a player who changed teams has one team in past-season production rows and another in the current salary sheet (for example a star traded in the offseason). Resolve "who is on team X" against the season the question is about before answering.
- **Stale premise handling**: when a tool reports that a player's team differs from the question's premise (trade guard errors name the season and the listed team), say the premise is stale, then answer for the player's current team or re-run with the historical season the user meant. Do not force the question's teams through.
