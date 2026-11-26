---
name: historical-grain-and-time
description: Preserve historical warehouse grain, season/phase filters, clock-minute parsing, canonical lineup keys, shot-zone ordering, and full-outer reconciliation when auditing player, game, lineup, and shot data.
---

# Historical Grain & Time Contracts Playbook

Use this playbook before aggregating across `silver_hist_*`, `silver_boxscores`, `silver_hist_shots`, or `silver_hist_lineups`, especially when a task names an exact season, phase, player cohort, or reconciliation check.

## 1. Resolve Grain Before Aggregating

- Inspect `warehouse_schema` for the exact table and confirm whether rows are player-game, player-season, team-game, shot-event, or lineup-unit grain.
- Keep player rows separate from team rows. When a task compares player sums to a team total, do not assume the team column is a player row or that team minutes already include the same five players.
- For player-season tables, preserve traded-player semantics: `TOT`/`2TM`/`3TM` rows are summaries, not additional stints. Count entities with `COUNT(DISTINCT ...)`, and choose either stint rows or summary rows deliberately before summing.
- For game-level joins, use the warehouse's actual key spellings (`GAME_ID` vs `game_id`, `PLAYER_ID` vs `person_id`, `team` vs `team_abbreviation` vs `team_tricode`) after schema inspection, and report unmatched keys instead of silently dropping them.

## 2. Season, Phase, And Game-ID Scope

- `_season` is the varchar season label (`'YYYY-YY'`): for 2024-25 use `WHERE _season = '2024-25'`. `season` is the integer end-year: for the same 2024-25 season use `WHERE season = 2025`. Never substitute one for the other (`_season = 2025` or `season = '2024-25'`); inspect the schema and filter the column the table actually carries. `season_id` remains the start-year encoded form (`'22024'` for 2024-25); do not mix encodings in one cohort.
- Filter phase explicitly. For NBA game IDs, `001` is preseason, `002` is regular season, and `004` is playoffs; when `season_type` exists, prefer it and use the game-ID prefix as a cross-check.
- Historical tables can carry variant dimensions. For `silver_hist_lineups`, retain only the requested `season_type`, `measure_type`, and `per_mode` before ranking or comparing units; ratings and pace are not interchangeable across variants.
- When comparing seasons, validate every season in the comparison, not only the final one, and state the exact season labels used.

## 3. Clock Minutes Are Text

- Warehouse clock minutes are `MM:SS` strings. Parse them as `minutes + seconds / 60`; never treat `12:30` as `12.30`, `1230`, or a decimal minute value.
- Blank minutes and `DNP` are zero for played-minute cohorts. Verify the sentinel values on the target table before filtering.
- For per-game or per-36 rates, compute exposure from parsed minutes and the game denominator requested by the task; do not borrow per-game columns from a different grain.

## 4. Canonical Lineup Units

- A five-man unit is canonical only after parsing `group_id` into unique player IDs, requiring exactly five, sorting the IDs, and deduplicating to one row per canonical key per team/season/variant.
- DuckDB has no `OVERLAPS` predicate and no `array_overlaps`/`list_overlap` function. Canonicalize player sets with `array_to_string(list_sort(list_distinct(string_split(group_id, ' - '))), ',')`; test membership overlap with `list_has_any`/`list_has_all` or `len(list_intersect(...))`.
- Rank units by the requested measure with deterministic tie-breaks (usually ascending player IDs or lexicographic unit key), and report minutes/possessions next to every rating.
- For continuity or survival questions, intersect canonical unit keys across seasons or windows instead of comparing display names or unsorted `group_id` strings.

## 5. Shot Zones And Reconciliation

- In `silver_hist_shots`, coordinates may be legacy tenths of feet. Use the task's ordered, mutually exclusive zone rules exactly; do not substitute generic court zones or a different distance cutoff.
- `silver_shots` (current-season event feed) is a different schema from `silver_hist_shots`: uppercase `GAME_ID`, `GAME_EVENT_ID`, `LOC_X`, `LOC_Y`, `SHOT_DISTANCE`, `SHOT_ZONE_BASIC`, `SHOT_ATTEMPTED_FLAG`, `SHOT_MADE_FLAG` vs lowercase `game_id`, `x_legacy`, `y_legacy`, `shot_distance`, `shot_value`, `shot_result`. Do not carry column names between them.
- `silver_shots` can carry duplicate shot events — raw rows can be ~2× unique shots unevenly across players. Deduplicate by `(GAME_ID, GAME_EVENT_ID)` before any FGA/FG% aggregation (`COUNT(DISTINCT ...)` or `ROW_NUMBER()` partition), or totals and rates distort differently per player.
- Retain only valid Made/Missed two- or three-point rows for the requested phase, and separate shot quality (zone mix, expected value) from shot making (actual percentages) when the task asks for both.
- For feed reconciliation, full-outer join on game and player keys, count keys with any numerator or denominator discrepancy, and report totals from both feeds plus the maximum absolute per-key difference.

## 6. Interpretation Guardrails

- Report cohort counts, denominators, filters, and unmatched or excluded rows before the headline numbers.
- Do not turn conditioning on an outcome into a causal claim: win/loss splits, survivor cohorts, and post-treatment windows describe selection, not treatment effects.
- If a requested metric or column is absent, audit `information_schema.columns` or `warehouse_schema`, disclose the limitation, and provide only clearly labeled proxies.
