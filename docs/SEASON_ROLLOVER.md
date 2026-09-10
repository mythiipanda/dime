# Season Rollover Ops Guide — 2025-26 → 2026-27

Audited 2026-09-10 against `muse/features`. Documentation only — no ingestion
logic was changed. 2025-26 ended 2026-06-13; 2026-27 tips off ~mid-October 2026.

## 1. How data gets into the warehouse today

There is **no scheduler and no cron**. Data enters two ways:

**A. Manual seed scripts** (`backend/scripts/`, run from `backend/`). Two flavors:

| Script | Type | What it does |
|---|---|---|
| `seed.py --season 2025-26` | per-season, re-runnable | standings, leaders PTS, injuries — the only "current season" refresher |
| `seed_expansion.py` | coverage expansion, idempotent | lineups (→30 teams), gamelogs (→50 players), on_off |
| `seed_on_off_league.py` | one-shot, gentle (sleeps) | full-league `silver_on_off` via pbpstats, 2025-26 |
| `seed_2025_26_warehouse.py` | **one-time, season-hardcoded** | promotes 2025-26 hist slices → current-season `silver_*` tables |
| `seed_bbref_gamelogs.py` | one-time, 2025-26 only | full-season player gamelogs from basketball-reference (57 players) |
| `seed_sportsdataverse.py --seasons 2025` | rolling historical | shots + player season stats from sportsdataverse releases |
| `seed_history.py`, `seed_draft.py`, `seed_raptor.py`, `seed_player_season_stats.py`, `seed_salaries.py` | one-time historical | frozen history; salaries already on **2026-27** |

**B. Lazy live refresh on read.** Agent tools call `_warehouse_or_live()`
(`app/tools/_core.py`): serve from warehouse if rows exist and are within TTL,
else fetch live from stats.nba.com / ESPN / pbpstats / cdn.nba.com and save.
Refresh therefore happens **only when someone asks a question** — never
overnight, never on a schedule.

`/datasets/{name}` is warehouse-first with **live on miss only** — it applies no
TTL, so a cached 2025-26 row is served forever via this endpoint. (Entity-scoped
datasets like `player_gamelogs` are an exception: the endpoint clears the cached
frame, forcing a live fetch every call.)

## 2. What `/datasets/freshness` actually reports

Per `silver_*` table: row count and `MAX(_fetched_at)`. That's it. It does **not**
report a `stale` flag, knows nothing about TTLs, and has no per-entity
(player/team/date) granularity. A table seeded once in June shows a June
timestamp; nothing marks it stale. (The string `"stale": true` does exist, but
only in per-tool response metadata when a live fetch *fails* and old rows are
served — `app/tools/_core.py:273`.)

## 3. The TTLs (in `app/tools/_core.py`)

| Constant | Value | Applies to |
|---|---|---|
| `TTL_SCOREBOARD_PAST` | 12h | scoreboard for past dates |
| `TTL_GAMELOG` | 6h | player/team gamelogs |
| `TTL_PBPSTATS` | 24h | on_off, four_factors, lineups |
| `TTL_ROSTER` | 24h | rosters |
| `TTL_BOX` | 1h | box scores by game_id |
| `TTL_LEADERS` | 12h | league leaders |

Today's scoreboard (not a past date) gets no TTL — each date is its own entity,
so new dates always miss cache and fetch live.

## 4. Tables that need in-season updates, and their feeds

| Table | Daily? | Live source (all season-param driven) |
|---|---|---|
| `silver_scoreboard` | yes | `nba_stats.scoreboard` (stats.nba.com) |
| `silver_team_games` | yes | `nba_stats.team_gamelog` |
| `silver_player_gamelogs` | yes | `nba_stats.player_gamelog` |
| `silver_lineups` | yes | `nba_stats.lineups` / pbpstats |
| `silver_standings` | yes | `nba_stats.standings` (+ `espn` fallback) |
| `silver_injuries` | yes | `espn.injuries` |
| `silver_leaders_*` | yes | `nba_stats.leaders` |
| `silver_on_off`, `silver_four_factors` | yes-ish | pbpstats API |
| `silver_shots` | on demand | `nba_stats.shot_chart` + sportsdataverse `nba_stats_shots` release |
| `silver_hist_shots`, `silver_hist_player_seasons` | no (final) | sportsdataverse releases — **rolling snapshots, not nightly dumps**: `nba_stats_shots` / `nba_stats_player_season_stats` were last refreshed 2026-07-24 (post-season). They update during the season; verify cadence at cutover and treat as supplemental. |

All live sources take a season string and will serve 2026-27 as soon as it
exists upstream — **the blocker is Dime's pinned season constants, not the
sources.** `cdn.nba.com`'s schedule (`sources/cdn.py`) follows the league's
current season automatically.

## 5. Cutover checklist (run ~opening week, mid-Oct 2026)

1. **Bump season constants.** The canonical ones:
   - `app/tools/_core.py: SEASON = "2025-26"` → `"2026-27"`
   - `app/subagents.py: SEASON = "2025-26"` → `"2026-27"` (duplicate — consolidate someday)
   - ~15 API/tool defaults `Query("2025-26")` / `season: str = "2025-26"`:
     `app/datasets.py:127`, `app/routes.py:227,235,245,276,286,297`,
     `app/tools/league.py:1833,1983`, `app/tools/sim.py:73`
   - Agent prompt pins: `app/graph.py:119,982,1077`, `app/subagents.py:330,358,362`,
     `app/skills/compare_players.md`
   - Cosmetic docstrings: `app/sources/cdn.py`, `app/sources/pbpstats.py`
   - Coverage notes in tool docstrings that say "2025-26 only" (`headtohead.py`,
     `gamelog.py`, `player.py:582`, `zone.py`, `team.py:613,637`) — update as new
     coverage lands, or they mislead.
   - `app/tools/league.py` contract/trade tooling already targets 2026-27
     salaries (`SAL_SEASON = "2026-27"`) — leave alone.
2. **Re-run the per-season seed:** `python -m scripts.seed --season 2026-27`
   (standings, leaders, injuries).
3. **Decide on the hist→current promotion.** `seed_2025_26_warehouse.py` is
   hardcoded to 2025-26. Either parametrize it or write the 2026-27 equivalent
   before needing `silver_team_games`/`silver_lineups` for the new season.
   sportsdataverse end-year-2026 assets (`shots_2026.csv`) won't exist until
   the season progresses — don't block cutover on them.
4. **Start in-season gamelog coverage.** 2025-26 gamelogs cover only the 57
   seeded players; there is no full-league gamelog refresher. For 2026-27,
   gamelogs accrue lazily per-queried-player (6h TTL). If Tony wants
   league-wide game-log answers early in the season, someone must extend
   `seed_bbref_gamelogs.py`-style coverage or add a bulk refresher.
5. **Re-run full-league on_off** (`seed_on_off_league.py`) once rotations settle
   (a few weeks in), with the season param bumped.
6. Sanity check: hit `/datasets/freshness` and confirm `silver_standings` /
   `silver_injuries` show October `_fetched_at` values.

## 6. What happens if nobody runs anything

Nothing crashes. The tools keep answering with `season="2025-26"` defaults, so
answers silently describe last season; `/datasets/freshness` keeps showing June
timestamps. Lazy refresh keeps working — but only for the pinned 2025-26
season, and only for entities someone actually queries. Injuries, standings,
and leaders freeze at their last manual `seed.py` run.

## 7. Known gaps (be honest)

1. **No scheduled ingestion.** "Daily refresh" does not exist as a job; it is
   lazy, pull-driven, and query-dependent. Overnight, nothing refreshes.
2. **Freshness endpoint can't see staleness.** No TTLs, no `stale` flag, no
   per-entity view — ops must eyeball `_fetched_at` timestamps.
3. **Season constants are sprayed across ~20 files** with two duplicate `SEASON`
   constants. A missed bump = mixed-season answers. `app/config.py` has no
   season setting; there is no single switch.
4. **Patchy write coverage.** No bulk gamelog refresher; lineups/on_off refresh
   per-team on query (24h TTL); full-league refreshes are manual scripts with
   hand-tuned rate limiting.
5. **sportsdataverse is a snapshot feed, not a live one** (last NBA refresh
   2026-07-24). Fine for history/shots backfill; not a daily driver.
