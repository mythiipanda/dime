# Preseason Ops: 2026-27 Season Rollover Runbook

Audited 2026-09-10 on branch `muse/backend`. Docs only — no ingestion logic
was changed. Companions: `docs/SEASON_ROLLOVER.md` (what breaks), 
`docs/PRESEASON_2026_27.md` (source readiness). This doc is the ops plan:
what runs when, who runs it, what's manual vs automatable.

## 1. The reality in one paragraph

There is **no scheduler and no cron**. Data enters the warehouse two ways:
(1) manual seed scripts run from `backend/` (`backend/scripts/seed.py` etc.),
and (2) lazy live refresh on read — agent tools call `_warehouse_or_live()`
in `app/tools/_core.py`, which serves warehouse rows if fresh (per-table TTL)
and otherwise fetches live from stats.nba.com / ESPN / pbpstats / cdn.nba.com.
So **"daily refresh" does not exist as a job**. In-season freshness is
query-driven: anything nobody asks about freezes at its last manual seed.
Anything that matters league-wide (standings, injuries, leaders, scoreboard)
therefore needs a person — or a new cron — to touch it.

Key dates (verified in `docs/PRESEASON_2026_27.md`): preseason Oct 3–18, 2026
(first game Sat Oct 3); **opening night Tue Oct 20, 2026** (BOS @ DET,
PHI @ NY, OKC @ SA). 2025-26 ended 2026-06-13.

## 2. Ops calendar: what runs when

| Window | Action | How | Owner |
|---|---|---|---|
| Now → Sep 30 | Prep only. Prepare the season-bump change (constant list in §3). Nothing to ingest; 2026-27 has no games. | code review | agent |
| **Oct 1–3: preseason gate test** | Decide whether stats.nba.com works from the fetch environment. Retry `nba_stats` scoreboard + `cdn.nba.com` schedule from the VM that runs Dime's fetches — unreachable from this sandbox on 2026-09-10 (`docs/PRESEASON_2026_27.md` §2). If still dark, **formally fall back to ESPN** for scoreboard/boxscores for the whole season. Also confirm ESPN scoreboard for Oct 3 lands in `silver_scoreboard` via the ESPN path. | manual test | agent |
| **Oct 20 (opening day): cutover** | 1. Bump season constants (§3). 2. `python -m scripts.seed --season 2026-27` (standings, leaders, injuries). 3. Smoke-test `get_today` + `/datasets/freshness` — `silver_standings` / `silver_injuries` should show October `_fetched_at`. | manual run | agent |
| Oct 21 – Nov 3 | Re-run `scripts.seed --season 2026-27` **daily-ish** while standings/injuries churn. Gamelogs accrue lazily per queried player (6h TTL, `TTL_GAMELOG`); lineups/on_off accrue per team on query (24h TTL). | manual run | agent / Tony |
| Week 1–2 | Decide on league-wide 2026-27 gamelog coverage. 2025-26 only covers the 57 players seeded by `seed_bbref_gamelogs.py`; there is no full-league gamelog refresher. If Tony wants league-wide game-log answers early, port `seed_bbref_gamelogs.py` to 2026-27 once b-ref's `NBA_2027` gamelog pages exist (~a day after opening night). | decision + one-shot script | agent |
| Week 3+ | `seed_on_off_league.py` with season bumped — full-league `silver_on_off` once rotations settle. pbpstats lags games by ~1 day; the script self-rate-limits. | manual run | agent |
| Ongoing in-season | `scripts.seed --season 2026-27` on a cadence (see §5: weekly is enough after Nov). Monitor `/datasets/freshness`; nothing else refreshes overnight. | manual / cron if built | agent |
| Post-season (~Jun 2027) | Freeze 2026-27: promote slices into `silver_hist_*` (the `promote_2025_26.py` / `seed_2025_26_warehouse.py` equivalents — both are hardcoded to 2025-26 today and will need to be parametrized or rewritten). | manual run | agent |

### Preseason games (Oct 3–18): skip ingestion on purpose
`SeasonType=Pre Season` is opt-in; preseason stats don't count and b-ref
publishes no preseason data. Ingesting preseason into regular-season tables
risks polluting aggregates. If Tony asks "when do the Lakers play?",
answer from ESPN schedule — don't write preseason rows into `silver_scoreboard`
unless he's explicitly opted in.

## 3. What breaks at cutover (file + line list)

Audited today; read-only. `SEASON_ROLLOVER.md` §5 has the full checklist;
this is the executable core of it:

**Canonical season constants** (both must flip, and the duplication is the
main risk):
- `backend/app/tools/_core.py:9` — `SEASON = "2025-26"` (drives every tool
  through `_warehouse_or_live()` / `season()` at `_core.py:36`)
- `backend/app/subagents.py:17` — `SEASON = "2025-26"` (duplicate; subagent
  prompts at `subagents.py:177,179,237`)

**API/tool defaults** (miss one → mixed-season answers):
- `backend/app/datasets.py:127`, `backend/app/routes.py:227,235,245,276,286,297`,
  `backend/app/tools/league.py:1833,1983`, `backend/app/tools/sim.py:73`
- Agent prompt pins: `backend/app/graph.py:119,982,1077`,
  `backend/app/subagents.py:330,358,362`, `backend/app/skills/compare_players.md`
- `backend/app/tools/league.py` contract/trade tooling is already on
  `SAL_SEASON = "2026-27"` (salaries are 2026-27 already) — **leave alone**.

**Scripts that die with 2025-26** (each has `SEASON = "2025-26"` hardcoded or
is season-named): `seed_2025_26_warehouse.py:25`,
`promote_2025_26.py:27`, `seed_scoreboard_2025_26.py:29`,
`seed_bbref_gamelogs.py:38`, `seed_expansion.py:18`,
`seed_on_off_league.py:19`, `seed_hustle_team.py:21,37`.
`seed.py` takes `--season` but **defaults to `2025-26`** (`seed.py:19`) —
run without the flag and it silently re-seeds last season. Either always pass
the flag or change the default at cutover.

**Tests** — the blind spot. ~20 files in `backend/tests/` hardcode
`"2025-26"` (e.g. `test_streaks.py:178`, `test_text_to_sql.py`,
`test_elo_standings.py`, `test_game_prediction.py`, `test_shot_zones.py`).
The season bump breaks these fixtures/assertions unless they get a pass too.
Any cutover PR that doesn't include `backend/tests/` will turn CI red.

**Read-path gotchas**:
- `/datasets/{name}` is warehouse-first with **live on miss only** — no TTL.
  A cached 2025-26 frame is served forever via this endpoint. Entity-scoped
  datasets (e.g. `player_gamelogs`) clear the cached frame and re-fetch live
  every call — good for 2026-27, but verify each new-season table's behavior.
- `/datasets/freshness` reports only row counts and `MAX(_fetched_at)` per
  `silver_*` table — no `stale` flag, no TTL awareness, no per-entity view.
  Ops monitoring = eyeballing timestamps.

## 4. Manual vs automatable

| Task | Today | Automatable? | Path |
|---|---|---|---|
| standings / injuries / leaders refresh | manual: `python -m scripts.seed --season 2026-27` | yes, trivial | cron: daily 6am ET `seed.py` (after the NBA-vs-ESPN decision in §2, so the sources are known-good) |
| scoreboard nightly | none — accrues lazily on query (`TTL_SCOREBOARD_PAST` 12h) | yes, moderate | cron hitting a refresh path that exercises `_warehouse_or_live` for the day's games |
| player/team gamelogs league-wide | none beyond 57 seeded players; lazy per queried player (`TTL_GAMELOG` 6h) | yes, moderate | bulk refresher ported from `seed_bbref_gamelogs.py` (b-ref populates NBA_2027 gamelogs ~day 1) |
| on_off / four_factors league refresh | manual `seed_on_off_league.py` (self rate-limits) | yes, moderate | cron, weekly, after rotations settle (Nov) |
| freshness monitoring | eyeball `/datasets/freshness` | yes, trivial | cron hitting `/datasets/freshness`, alert if any table's `MAX(_fetched_at)` is older than its intended cadence |
| sportsdataverse hist backfill | manual spot-check | keep manual | tags (`nba_stats_shots`, `nba_stats_player_season_stats`) are post-season snapshots — last touched 2026-07-24; check once mid-season, expect nothing until ~Jul 2027 |
| season-constant bump | manual ~20-file edit | yes, later | single `CURRENT_SEASON` in `app/config.py` (no season setting there today); tests need the same treatment |
| promotion 2026-27 → hist tables | `promote_2025_26.py` / `seed_2025_26_warehouse.py` are 2025-26-hardcoded | needs a rewrite first | parametrize both scripts before Jun 2027 |

## 5. What "daily refresh" would actually take

Be honest about the gap: there is **zero cron/scheduling infrastructure** in
this repo (nothing matches `cron|schedule|scheduler` outside NBA "schedule"
references). Building daily refresh means:

1. **A cron host.** This VM's cron (or Tony's scheduler of choice) running
   `python -m scripts.seed --season 2026-27` daily ~6am ET. That covers
   standings, injuries, and PTS leaders — the three tables that rot fastest
   when nobody asks questions.
2. **Known-good sources first.** From this sandbox, stats.nba.com hangs and
   cdn.nba.com 403s (`docs/PRESEASON_2026_27.md` §2). A cron that silently
   429s/hangs overnight is worse than no cron. The Oct 1–3 gate test decides
   the source mapping (ESPN fallback vs NBA) *before* automating.
3. **Weekly is probably enough.** Lazy refresh already covers anything Tony
   actually asks about (6h–24h TTLs by table). Cron only matters for
   *unqueried* entities. Daily buys nothing over weekly except for standings/
   injuries/leaders in the first two weeks — and `seed.py` is a one-command
   manual run until then.

Recommendation: keep it manual through November, then decide based on how
often Tony's questions hit stale rows. Don't build the cron in October to
solve a problem lazy refresh already handles.

## 6. Risk register

1. **Silent mixed-season answers** — a missed constant (one of the ~20 files)
   means the agent confidently describes last season. Mitigation: bump from
   the §3 checklist, and include `backend/tests/` in the same pass.
2. **The NBA API is dark from this environment** — scoreboard, boxscores, shot
   charts, and schedules route through stats.nba.com / cdn.nba.com. If the
   Oct gate test fails, those tables are ESPN-or-nothing for the season.
   `get_today` and scoreboard live or die on this decision.
3. **`seed.py` default lies** — bare `python -m scripts.seed` writes
   `2025-26` rows without warning. Pass `--season` every time, or change the
   default at cutover.
4. **Preseason pollution** — keep Oct 3–18 games out of regular-season tables.
5. **Staleness is invisible to the API** — `/datasets/freshness` can't flag a
   June `_fetched_at` as stale. Until a `stale` flag or TTL-aware monitoring
   exists, freshness checks are manual eyeballing after every manual seed.

## 7. Cutover command sheet (copy-paste on Oct 20)

```bash
cd ~/workspace/dime/backend
# 1. bump SEASON constants per §3 (incl. tests) and restart the app
# 2. re-seed current-season tables
python -m scripts.seed --season 2026-27
# 3. smoke test
#    - hit /datasets/freshness: silver_standings + silver_injuries show October _fetched_at
#    - ask get_today about Oct 20 games (scoreboard path)
# 4. leave for later: gamelog coverage (week 1-2), seed_on_off_league.py (week 3+)
```

## Sources

- This repo, read-only audit 2026-09-10: `backend/app/tools/_core.py`
  (SEASON, `_warehouse_or_live`, TTLs), `backend/app/store.py`
  (`save_frame`/`read_frame`), `backend/app/datasets.py`, `backend/scripts/seed*.py`
- `docs/SEASON_ROLLOVER.md`, `docs/PRESEASON_2026_27.md` (calendar, source
  readiness, ESPN verification 2026-09-10)
