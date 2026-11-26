---
name: player-evaluation
description: Evaluate NBA players and contracts — multi-season trends, impact rank, shot splits, production-versus-salary value, aging curves — with explicit current-versus-historical framing from the warehouse.
---

# Player & Contract Evaluation Playbook

This playbook is guidance for reasoning about player evaluation and
contract value, not a fixed procedure. Use whichever tools answer the
question; skip the rest. Every number is warehouse-sourced — never a live
endpoint at question time — and each tool reports its own sources, so
cite them.

## 1. Tools and when they matter

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_career_arc` | A player's season-by-season trajectory — production, efficiency, minutes across all seasons. | Any "is he getting better/worse", "prime year", or trajectory question. The backbone of multi-season claims. |
| `get_impact_rank` | Where a player ranks by WS, VORP, BPM for a season. | Calibrating "is he actually a star" and comparing players to each other or to replacement level. |
| `get_raptor_history` | Multi-season RAPM-family impact ratings. | A trend view on impact that `get_impact_rank` gives for one season — use it to see the slope, not just the level. |
| `get_shot_zones` / `get_shot_compare` / `search_shots` | Where shots come from, eFG by zone, player-vs-player or player-vs-league shot diets. | Skill-profile and "is the shooting real" questions; splits like wins/losses, home/away are also reachable via `sql_exec` on `silver_hist_shots`. |
| `get_splits` / `get_situational_splits` | A player's stats split by context (clutch, opponent, situation). | "How does he perform when it matters" or matchup-dependent claims. |
| `get_contract_value` | Production-vs-salary surplus per player — who outperforms or underperforms their contract. | Any value/contract question; also the fastest way to rank a team's books. |
| `get_comps` | Similar players by profile. | Reasonable-projections and aging arguments — comps show what typically happens to this profile. |
| `get_regression_check` / `get_last_x` | Is a hot/cold stretch sustainable vs the season base rate? | "Career year?" or small-sample jumps — separates a breakout from a heater. |
| `get_scouting_report` / `get_scout_pack` | Assembled single-player profile. | A broad "tell me about X" before drilling into a specific claim. |
| `get_rapm` / `get_rapm_prior` / `get_ratings` / `get_player_ratings` | RAPM-family impact and composite player ratings for a season. | Single-season impact claims — `get_impact_rank` ranks across WS/VORP/BPM; these give the model-based level. |
| `get_era_comps` | Cross-era comparisons with pace/era adjustment. | "How does he compare to players from the 90s" — raw comps mislead across eras. |
| `get_rookie_leaders` / `get_young_player_usage` / `get_player_risers` / `get_risers` | Rookie leaderboards, young-player usage/development reads, and league risers. | "Which rookies/young players are breaking out" — the named answer, not a hand-built SQL list. |
| `get_historical_leaders` / `get_leaderboard_deltas` | All-time/career leaderboards and week-over-week leaderboard movement. | "Most X ever" and "who's climbing the leaderboard" asks. |
| `sql_exec` | Ad-hoc warehouse queries. | Anything the named tools don't cover — e.g. custom splits, age curves across `silver_impact`, year-over-year deltas. |

## 2. Multi-season evaluation

A single-season number is a snapshot; the trend is usually the claim.

- Start with `get_career_arc` for the shape: which season was the prime,
  whether the last 2–3 seasons are rising, flat, or declining, and whether
  minutes or efficiency is driving the change. Then use `get_impact_rank`
  per season (pass `season` explicitly) or `get_raptor_history` for the
  impact-metric view of the same arc.
- Distinguish *role change* from *skill change*: production dips that
  track minutes are different from dips that track efficiency. The arc
  data usually shows which — say which it is rather than calling it
  "decline".
- Shot-profile changes often precede scoring changes. Compare shot diets
  across seasons with `get_shot_zones`/`get_shot_compare` (or a
  `sql_exec` split on `silver_hist_shots` by season): a player trading
  mid-range for rim/threes can hold efficiency while usage drops — that
  is adaptation, not loss of skill.
- Breakouts need confirmation, not just the number. `get_regression_check`
  tests whether a current stretch is unusual against the player's own
  baseline; a confirmed breakout plus an upward multi-season impact slope
  is real development; either alone is weaker.

## 3. Contract value vs production

- `get_contract_value` computes production-vs-salary surplus for a season.
  It grades the *contract*, not the *player*: a max player graded
  "negative" can still be the team's best player — the contract just
  leaves no surplus. Cross-check with `get_impact_rank`: surplus-negative
  + top-20 rank = expensive star; surplus-negative + rank ~150 = the
  actual problem contract.
- Young players on rookie-scale deals dominate surplus rankings almost by
  construction — say so when a value list is presented, since "best
  contracts" reads like "best players" otherwise.
- Declining veterans show the aging tail early: compare the current
  `get_contract_value` grade against `get_career_arc`'s slope. A mildly
  negative grade on a steepening decline curve projects worse than the
  same grade on a flat one — the forward-looking read matters for
  extension and trade questions, and comps (`get_comps`) give the
  empirical shape of how this profile ages.
- For aging specifically, an `sql_exec` pass over `silver_impact` by age
  bucket is a grounded way to state league aging curves instead of
  asserting them.

## 4. Shot splits as evidence

Shot splits answer "where does his value come from" and "is it
transferable":

- Zone profiles (`get_shot_zones`) separate self-created offense from
  offense a system generates — a player whose efficiency lives on
  assisted corner threes travels differently than one whose eFG holds on
  above-the-break pull-ups.
- Win/loss and home/away splits via `sql_exec` on `silver_hist_shots`
  joined to `silver_hist_gamelogs` show whether a player's efficiency is
  scoreboard-sensitive — a real, citable way to test "he only scores when
  it doesn't matter".
- `get_splits`/`get_situational_splits` cover clutch and situational
  performance — use them for "does he produce in leverage" rather than
  asserting it from totals.

## 5. Qualified-pool analytics (scouting-desk asks)

Asks like "against the qualified pool", "closest statistical matches",
"percentile profile", or "rank the under-23 core" define an eligible pool
then rank or measure each player inside it. Compute every one of these in
`sql_exec` against the season-appropriate pool table —
`silver_hist_player_seasons` for historical or multi-season pools,
`silver_player_season` for the current snapshot when its columns cover the
screen — never pull the pool into context with
`get_leaders`/`get_dataset` dumps; a whole-pool payload (~570 rows) burns the
turn budget and the context window.

Efficiency screens are single-table first: `silver_player_season` carries
`TS_PCT` beside GP/MPG/PPG and the shooting percentages, so a current
scoring-efficiency cutoff, rank, percentile, or comparison that needs only
true shooting belongs in one aggregate query over that table.
Join `silver_advanced` on `PLAYER_ID` + `_season` only when the screen needs an
advanced-only column (`USG_PCT`, `OFF_RATING`, `DEF_RATING`, `NET_RATING`,
`AST_PCT`, `REB_PCT`, or `EFG_PCT`); for historical or multi-season pools,
use `silver_hist_player_seasons`, whose lowercase `ts_pct` and usage/rating
columns already cover the same computation without a second table.

Grain facts that trip these queries:

- `season` is the int start year (2025 = '2024-25'); `_season` carries the
  'YYYY-YY' string. `min` and the counting stats (`pts`, `reb`, `ast`,
  `stl`, `blk`, `tov`) are per-game already — do not divide by `gp`.
  There is no `season_type` on the player table; that column lives on
  `silver_hist_team_seasons` (value 'regular-season').
- "Qualified" means `gp >= 41 AND min >= 24.0` unless the ask overrides
  the cutoffs; that pool is ~180 players for 2025.
- Percentile = share of the pool below the player's value. One query:
  cross join the target row(s) to the pool and `COUNT(*) FILTER (pool.x <
  t.x) * 100.0 / COUNT(*)`, or `percent_rank() OVER (ORDER BY x)` for a
  full board.
- "Closest statistical matches" = z-score each named stat across the pool
  (`(x - avg(x) OVER ()) / stddev(x) OVER ()`), then Euclidean distance —
  one `sql_exec`, ordered by distance, excluding the player himself.
- Team ranks need no computation: `silver_hist_team_seasons` carries one
  row per team × `measure_type` × `per_mode` — filter
  `measure_type='advanced'` (or the metric's table) and read the `*_rank`
  column (`reb_pct_rank`, `net_rating_rank`, ...).

## 6. Current vs historical — always stated

Contract, roster and trade tools default to the current 2026-27 season;
stat/leaderboard tools fall back to the latest season with data. While
2026-27 is early and partial, an unspecified season-long total or
leaderboard ask ("who leads the league in corner threes") wants the latest
completed season — query `_season = '2025-26'` rows and label that season
in the answer; only an explicit "this season" or "in 2026-27" means the
in-progress partial data. Historical asks must pass `season` explicitly,
and the answer must name which season each number belongs to. Two failure
modes to avoid:

- Mixing eras silently: never put stats from different seasons in the same
  comparison without labeling each. When citing a player's
  current team, verify it in the season's data — a player traded mid-
  season has rows under more than one team.
- Present-tense claims on historical data: "averages 24" for a player
  whose last season was 2023-24 needs the season attached. The
  warehouse's `silver_leaders_pts` coverage runs 2019-20 through 2025-26,
  so multi-season comparisons are well covered — use them rather than
  generalizing from memory.

## 6. Warehouse-grounded examples

*"Is the extension candidate actually worth a max?"*
`get_career_arc` → trajectory and prime season; `get_impact_rank` for
the last three seasons → whether he's top-15 by impact or lower;
`get_contract_value` → current surplus (rookie/max context stated);
`get_comps` → what his profile typically does after the extension starts;
`get_regression_check` if the case rests on a breakout season. Verdict
states value per season with the trend direction, not a single number.

*"Two guards being compared for a trade target."*
`get_impact_rank` both, same season → level; `get_career_arc` both →
trend; `get_shot_compare` → whose shooting profile fits the buying team's
gap; `get_contract_value` → surplus on each contract. The report names
the better player, the better contract, and when those differ, why.

*"He's washed" claims.*
`get_career_arc` → is the slope real or a minutes/role artifact;
`get_impact_rank` latest season vs prior → rank movement, not just raw
stats; `get_shot_zones` or a shots-split query → whether the scoring dip
is diet-driven (fixable) or across-the-board; `get_comps` → how the
profile historically ages. Answer says which evidence supports decline
and which doesn't, with seasons labeled.

## 7. Reporting

- Lead with the claim, then the trend evidence, then the single-season
  calibration — never a bare season line as the whole answer to an eval
  question.
- Name the season on every stat; keep current-season and historical
  claims in separate sentences or rows.
- Cite each tool's `meta.sources`/per-row sources; disclose the tools'
  own approximations (estimated values, partial seasons) in one line.
- Where evidence conflicts (strong impact rank, weak contract value),
  report both — that tension is usually the answer.
