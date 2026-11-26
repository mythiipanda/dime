---
name: lineups-and-rotations
description: Analyze 5-man lineup net ratings with sample-size caveats, possession-weighted aggregation, 2-man WOWY matrices, non-star survival minutes, within-season rotation breadth and concentration (top-8 share, HHI, effective players), lineup continuity across seasons, and playoff rotation tightening.
---

# Lineups, WOWY & Rotation Analytics Playbook

Use this playbook for 5-man lineup evaluation, two-player With-Or-Without-You (WOWY) synergy splits, bench survival analysis, and playoff rotation tightening.


## Single-pass lineup screens

A "every five-man unit with at least N minutes, ranked" ask resolves in ONE aggregate query against `silver_hist_lineups` — never enumerate teams or players in a loop. The table is variant-row grain: filter one `season_type`/`measure_type`/`per_mode` variant; `min` and `net_rating` are available on `measure_type='advanced'` rows per `_season`/`team_abbreviation`:

```sql
SELECT group_name, ROUND(min, 1) AS mins, ROUND(net_rating, 1) AS net
FROM silver_hist_lineups
WHERE _season = '2024-25'
  AND season_type = 'regular-season'
  AND measure_type = 'advanced'
  AND per_mode = 'totals'
  AND min >= 100
ORDER BY net_rating DESC
```

(verified executable — returns league-best units directly; add `team_abbreviation = 'DEN'` for one team. Units can appear in up to 28 variant rows, so the three variant filters are required; `SELECT DISTINCT` does not collapse non-identical variants). If the result looks thin, lower the minutes cutoff in the SAME query — do not start per-team follow-up loops; each round trip costs budget the write-up phase needs.

## 0. Tools and when they matter

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_lineups` / `get_lineup_stats` | One team's five-man units by minutes and their ratings. | Rotation-structure questions — closing unit, starters, most-used combinations. `get_lineups` takes `season_type`, `measure_type`, `per_mode`; `get_lineup_stats` takes `min_possessions`. |
| `get_lineup_leaders` | Best/worst qualifying units league-wide. | "Their best five" or league context for one unit's rating. Respect `min_minutes` — the floor already prunes noise. |
| `get_lineup_matchup_matrix` | Two teams' five-man units head-to-head on shared minutes. | "How does our best lineup fare against theirs" — cells carry sample flags. |
| `get_wowy` | Two players' four-state with/without-you splits. | The 2-man matrix in §2 — it returns all four quadrants directly. |
| `get_on_off` | One player's on/off possession-level splits on a team. | Individual impact within a rotation; attribute carefully (teammate context matters). |
| `get_lineup_on_off` | On/off splits for an arbitrary 2-5 player unit — together vs all other team possessions; with exactly two players it also carries the four-way split. | "How does the team do when these three share the floor" — the generalized version of pair WOWY for any unit size. |
| `get_availability_impact` | Game-level played-vs-missed splits: team record, win pct, and margin when a player sits vs plays; optional `teammate` per-game conditioning; blank `player` = league win-drop ranking. | "How do they do without X" / games-missed questions — the game-grain complement to on/off's possession grain. |
| `get_on_off_leaders` | Stint-level on/off splits: league board (on-minus-off net gap, possession floors), team board by on-court possessions, single-player split, or `pair` 2x2. | On-off net-rating gaps and stint-based with/without asks — the stint-source answer where `get_on_off`/`get_wowy` disagree with official numbers. |
| `get_rotation_check` / `get_stint_timeline` | Rotation patterns, closing units, stint order per game. | Staggering and substitution-pattern questions; playoff-tightening checks in §4. |
| `get_scout_pack` | Compact opponent dossier: record, ratings, top lineups, injuries. | First pass before drilling into unit-level detail. |

## 1. Sample-Size Caveats on 5-Man Lineups

Raw 5-man unit net ratings are dominated by shooting luck (especially opponent 3P% variance) at small minute or possession counts:
- **Minimum qualification floors**: Treat 5-man lineups under `100` minutes (~200 possessions) as exploratory noise; require `>= 200` minutes (or `>= 400` possessions) for strong regular-season conclusions, and report exact minutes/possessions alongside every lineup rating.
- **Possession-weighted aggregation**: Never take an unweighted mean of lineup net ratings across units. Weight offensive, defensive, and net ratings by possessions:
  $$\text{NetRtg}_{\text{agg}} = 100 \times \left(\frac{\sum \text{PTS}_{\text{for}}}{\sum \text{Poss}_{\text{off}}} - \frac{\sum \text{PTS}_{\text{against}}}{\sum \text{Poss}_{\text{def}}}\right)$$
- **Opponent 3P% luck check**: When a lineup posts an extreme DRTG, check opponent 3P% and rim frequency allowed before attributing it solely to scheme or personnel.

## 2. 2-Man WOWY Matrix Construction

When evaluating fit between two focal players $A$ and $B$, construct the full $2 \times 2$ partition of team possessions:

| State | Meaning | Key Question |
|---|---|---|
| **$A \text{ ON}, B \text{ ON}$** | Shared minutes | Do their usage profiles and spacing amplify each other? |
| **$A \text{ ON}, B \text{ OFF}$** | $A$ leads solo / staggered | Can $A$ sustain offensive creation without $B$'s gravity? |
| **$A \text{ OFF}, B \text{ ON}$** | $B$ leads solo / staggered | **Non-star survival check**: does the offense collapse or survive? |
| **$A \text{ OFF}, B \text{ OFF}$** | Deep bench / garbage time | Baseline noise filter; check score-margin leverage. |

Use `get_wowy` for lineup-row four-state ratings; for possession-level four-state splits, use `get_on_off_leaders` pair mode or query stint/possession tables in `run_python` for Net Rating, ORTG, and DRTG.

When a task asks for a WOWY matrix or star-off split from `silver_hist_possessions` itself, the relevant columns are: `game_id`, `period`, `possession_number`, `offense_team_id`/`defense_team_id` (numeric TEAM_IDs), `off_player_1..5`/`def_player_1..5` (player IDs in each on-court lineup), `points`, `possession_start_type`, `count_as_possession`, `garbage`, `season`. There are no `player_name`, `possession_id`, `opportunity_id` or `team_id_offense` columns — a player is ON for a team's offense when their ID is in `off_player_1..5` on a row where `offense_team_id` is the team, and the 2-man state is the pair's joint presence across the team's off/def player slots. Filter `count_as_possession='true'` and `garbage=0`, then `100*AVG(points)` is the team's ORTG over its offensive rows.

## 3. Non-Star Survival Minutes & Staggering

- Evaluate how a team performs in the **star-off** and **second-star-stagger** segments (`A ON, B OFF` and `A OFF, B ON`) excluding garbage time.
- Identify which role players bridge offensive creation (assists per 100, rim pressure) and defensive floor (DRTG, defensive rebounding %) when the primary initiator sits.

## 4. Playoff Rotation Tightening

Regular-season depth often masks playoff vulnerabilities:
- Top rotations compress from 9–10 players in the regular season to **7–8 core players** in competitive playoff series, with star minutes rising from ~34–36 MPG to ~39–43 MPG.
- Compare regular-season vs playoff lineup concentration (top-3 lineup share of total minutes, starter vs bench minute split) using variant-filtered `silver_hist_lineups` rows for units and playoff boxscore rows for player minutes.
- Present 5-man lineup comparisons in a `table` artifact (including `MIN`, `POSS`, `ORTG`, `DRTG`, `NET_RTG`) and 2-man WOWY splits in a `compare` or `table` artifact.

## 5. Canonical `group_id` Keys

`group_id` strings in `silver_lineups` and `silver_hist_lineups` often carry leading or trailing dashes (`-201950-202083-...-`), so `string_split(group_id, '-')` produces empty elements that break `CAST` to int and corrupt dedupe keys:

- Canonicalize in Python: `tuple(sorted(int(p) for p in group_id.split('-') if p))`.
- In SQL, filter before casting: `list_filter(string_split(group_id, '-'), x -> x <> '')` — DuckDB evaluates a list comprehension's transform for every element before applying its `IF`, so `[CAST(x AS BIGINT) FOR x IN string_split(...) IF x <> '']` still casts `''` and errors.

## 6. Windowed Rotation Breadth & Concentration

Asks that track how a rotation stretches or tightens *within* a season ("first N vs last N games", "early vs late") are window-comparison problems, not season aggregates:

- **Window selection**: rank the team's regular-season games (`silver_hist_gamelogs`, `GAME_ID LIKE '002%'`) by `game_date` then `game_id`; the first-N and last-N windows are positional slices of that ordering, and the season must contain enough unique games to fill both windows without overlap.
- **Minutes grain**: join `silver_boxscores` on team/season/game; keep one row per game-player. Boxscore minutes come as `MM:SS` text — split on `:` and take `minutes + seconds/60`; a blank/`DNP` cell is `0`, not NULL-excluded.
- **Shares and concentration**: aggregate each player's minutes inside the window, take `share_i = min_i / total_minutes` over *all* positive-minute players (no per-player floor — the denominator is total actual player-minutes including overtime). Report `top8_share = Σ` of the 8 largest shares, `HHI = Σ share_i²`, and `effective_players = 1/HHI`. Compare the two windows' deltas; concentration rising means HHI up and effective players down.
- **Unit concentration**: for 5-man concentration asks, filter `silver_hist_lineups` to one variant (`season_type`, `measure_type='advanced'`, `per_mode='totals'`), group it by the canonical key of §5 with the stated minute/possession floors, then report unit count, total possessions, the possession-weighted mean `net_rating` *and* the simple mean, the most-used unit's minute share, and the weighted mean recomputed without it.

## 7. Lineup Continuity Across Seasons

"Continuity" asks measure carryover of qualifying units between a season and its predecessor, not roster overlap:

- A unit *qualifies* in a season when its `silver_hist_lineups` row clears the stated floors (`season_type='regular-season'`, `measure_type='advanced'`, `per_mode='totals'`, `min >=` floor, positive `poss`, non-null `net_rating`, exactly five unique player IDs after §5 canonicalization, one row per canonical unit per season).
- **Retained** = qualifies in both seasons; **newly qualifying** = qualifies now but did not qualify previously (it may still have played together below the floor).
- Report prior/current qualifying counts, retained count, retained units' share of *current* qualifying minutes, and the possession-weighted current `net_rating` computed separately for retained vs newly qualifying units.
