# 2026-27 Preseason Data-Source Readiness

Researched 2026-09-10. Dime's warehouse is complete through 2025-26 (season ended 2026-06-13).

## 1. Calendar

- **Preseason: Sat Oct 3 – Sun Oct 18, 2026.** First game: Toronto Raptors vs Miami Heat in Quebec City, Sat Oct 3.
  - Sources: [NBC Sports key dates](https://www.nbcsportsboston.com/nba/nba-key-dates-2026-27-opening-night-trade-deadline-finals/798846/?os&ref=app), [ESPN Press Room preseason TV slate](https://espnpressroom.com/press-release/espn-tips-off-its-coverage-of-the-2026-nba-preseason-on-thursday-october-8/)
- **Opening night (regular season): Tue Oct 20, 2026** — BOS @ DET, PHI @ NY, OKC @ SA.
  - Sources: [NBC Sports](https://www.nbcsportsboston.com/nba/nba-key-dates-2026-27-opening-night-trade-deadline-finals/798846/?os&ref=app); independently confirmed via the ESPN scoreboard API (`site.api.espn.com/.../scoreboard?dates=20261020` returns all three as STATUS_SCHEDULED on 2026-09-10)

## 2. Source-by-source readiness (tested today unless noted)

### sportsdataverse-data (GitHub releases)
- **Post-season snapshots, not a live/in-season feed.** The two NBA tags Dime uses — [`nba_stats_shots`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_shots) and [`nba_stats_player_season_stats`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_player_season_stats) — were last refreshed **2026-07-24** (post-Finals), covering through `*_2026.csv` (= 2025-26 season). Assets were touched once more 2026-08-13 (likely a re-upload/fix, not new data).
- **Verdict: useless for in-season data.** Expect `shots_2027` / `player_season_stats_2027` around July 2027, not October 2026. No 2026-27 snapshot will exist during the season. (Also note: unlike the tag scheme Dime's docstring assumed, `nba_stats_schedules` is stale since 2023 and isn't maintained.)

### basketball-reference
- [`NBA_2027.html`](https://www.basketball-reference.com/leagues/NBA_2027.html) **already exists** (empty 0-0 standings for all 30 teams, no per-game data yet). b-ref season pages typically populate within a day of opening night.
- **No preseason data from b-ref**: there is no `NBA_2027_games-preseason.html` page (404 as of 2026-09-10) — b-ref doesn't publish preseason pages/stats. Preseason must come from stats.nba.com / ESPN.

### stats.nba.com API
- **Cannot verify from this sandbox**: requests to `stats.nba.com` hang/time out (and `cdn.nba.com` returns 403 here) — consistent with the prior known NBA-CDN block. The API supports `Season=2026-27` with `SeasonType=Pre Season` (a documented season type), so in an unblocked environment the season-string flip is all that's needed — but it **must be re-tested from the environment that actually runs Dime's fetches**, since lazy-refresh runs from this VM.
- **Implication: in this environment, the NBA pipeline is effectively dark.** Any source that routes through stats.nba.com / cdn.nba.com (scoreboard, boxscores, shot charts, schedules) will fail over to whatever fallback the code has.

### ESPN API (site.api.espn.com)
- **Works from here (HTTP 200).** Serving 2026-27 already:
  - `scoreboard?dates=20261003` → MIA @ TOR on Oct 3, STATUS_SCHEDULED (season object: 2027, displayName "2026-27", start 2026-09-30)
  - `standings` defaults to season 2027 ("2026-27") — 0 entries today, will populate as games are played
  - 30 teams endpoint OK
- **Caveats**: ESPN's undocumented API has no preseason player-stat leaders endpoint guarantee; `site.web.api.espn.com` boxscores/injuries endpoints exist (Dime's `sources/espn.py` already uses ESPN for injuries). ESPN is the only reachable live source from this VM, so it should be the backbone of opening-night data.

## 3. Minimum viable data for opening night

Ranked by what actually answers questions on Oct 20:

1. **`silver_scoreboard`** (games, dates, scores) — ESPN scoreboard is available *now*. Without it, "what games are tonight?" and get_today break.
2. **`silver_standings`** — flips from 0-0 on Oct 20 via ESPN standings; b-ref's NBA_2027 page as backup.
3. **`silver_injuries`** — ESPN injuries endpoint; Dime already sources this from ESPN. Free from the b-ref requirement.
4. **`silver_leaders_*` / per-game boxscores** — stats.nba.com dark here; ESPN boxscores are the fallback.
5. **Player gamelogs, lineups, on_off, four_factors, shots** — lag the season by design (need games played; pbpstats updates with ~1-day lag). Nice-to-have week 1, not opening night.

Everything in this table is already season-param driven in Dime's sources — **the blocker is Dime's pinned `"2025-26"` constants, not upstream.** See `docs/SEASON_ROLLOVER.md` for the full cutover checklist (SEASON constants in `app/tools/_core.py`, `app/subagents.py`, ~15 tool defaults, re-running `scripts/seed.py --season 2026-27`).

## 4. Recommendation: what to seed, and when

| When | Action |
|---|---|
| **Oct 1–3** | Preseason gate test: from the fetch environment, (a) call `site.api.espn.com` scoreboard for Oct 3 and confirm games land, (b) retry `stats.nba.com` scoreboardv2 + `cdn.nba.com` schedule — if still blocked, formally fall back to ESPN for scoreboard/boxscores for the season. Do NOT wait until Oct 20 to discover the NBA API is dark. |
| **Oct 3–18 (preseason)** | `SeasonType=Pre Season` is opt-in; preseason stats don't count and b-ref won't carry them. Skip preseason ingestion entirely unless Tony asks — preseason data has near-zero analytical value and risks polluting regular-season aggregates. (ESPN preseason schedule + scores already reachable if he wants "when do the Lakers play?".) |
| **Oct 20 (opening night)** | Bump the season constants per SEASON_ROLLOVER.md §5, then run `python -m scripts.seed --season 2026-27` (standings, leaders, injuries). Smoke-test `get_today` + scoreboard for Oct 20. |
| **Week 1–2** | Player gamelogs accrue lazily per-queried-player (6h TTL) — 2025-26 only covered 57 seeded players, so decide now whether Tony wants league-wide gamelog coverage for 2026-27 (`seed_bbref_gamelogs.py`-style bulk run once b-ref's NBA_2027 gamelogs exist). |
| **Week 3+** | Re-run `seed_on_off_league.py` with the new season once rotations settle (pbpstats needs games played). |
| **Ongoing** | sportsdataverse: check back **once**, mid-season (Feb 2027), for any `nba_stats_shots`/`player_season_stats` refresh — expect nothing until ~July 2027; don't block anything on it. |

## Sources

- [NBC Sports — 2026-27 key dates](https://www.nbcsportsboston.com/nba/nba-key-dates-2026-27-opening-night-trade-deadline-finals/798846/?os&ref=app) (preseason Oct 3–18, opening night Oct 20)
- [ESPN Press Room — 2026 NBA preseason TV schedule](https://espnpressroom.com/press-release/espn-tips-off-its-coverage-of-the-2026-nba-preseason-on-thursday-october-8/)
- [sportsdataverse-data releases](https://github.com/sportsdataverse/sportsdataverse-data/releases) — `nba_stats_shots` / `nba_stats_player_season_stats` last refreshed 2026-07-24; GitHub API checked 2026-09-10
- [b-ref NBA_2027 season page](https://www.basketball-reference.com/leagues/NBA_2027.html) (live, empty)
- ESPN scoreboard/standings/teams APIs — queried live 2026-09-10 (`site.api.espn.com`)
- stats.nba.com / cdn.nba.com — unreachable from this environment 2026-09-10 (hangs / HTTP 403)
