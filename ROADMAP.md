# Dime Roadmap: AI-native NBA analyst workbench

Goal: the chat Tyrese Haliburton Twitter nerds and team analysts open daily.
Free public data only. No odds (killed). No deploy until approved.
Each unit ships only after real runs: pytest, eval, scenarios, browser beta.

## Phase 0 — Done

Chat over DuckDB warehouse, supervisor plus scout/team/league workers,
34 tools, compare/preview composites, trade checker, draft combine panel,
team ratings, clutch splits, NBA.com watch links, shot charts, heat maps,
threads plus runs plus export. Suites: 10 + 27 + 16, browser 5/5.

## Phase 1 — Trust (team-buyer blockers)

1. Verification surfacing. Every insight shows SQL or tool args, row
   count, source, fetch timestamp. UI already shows source plus date.
   Missing: SQL text for text_to_sql answers.
2. Sample floors. Lineups and on/off hide units under 100 possessions
   and flag blowout-heavy minutes. No more +12 in 40 minutes as signal.
3. Cap honesty. Trade output labeled estimate, lists omitted CBA rules,
   links source and salary date.
4. Freshness panel. Explore tab table: every warehouse table, row
   count, last fetch, stale flag.

## Phase 2 — Analyst currency (unused nba_api depth, 274 endpoints)

5. Splits finder. General/game/last-N/shooting splits per player and
   team. Partly exists (get_splits) — widen coverage, force-route it.
6. Shot locations league-wide. LeagueDashPlayerShotLocations and
   TeamShotLocations for zone diet tables.
7. Stathead core. Streak finders plus PlayerVsPlayer and TeamVsPlayer
   head-to-head. One game-log search tool over DuckDB logs.
8. Estimated metrics. Player and TeamEstimatedMetrics for
   EPM-adjacent efficiency numbers.
9. Draft depth. DraftBoard plus DraftHistory enrich the combine panel
   with pick slots and past classes.
10. Play types. SynergyPlayTypes if it answers without a subscription,
    else cut it fast.

## Phase 3 — New sources (ranked, free)

11. NBA CDN liveData. No key, no Akamai pain. Live scores, boxscore
    and play-by-play JSON. Replaces fragile stats.nba.com paths.
12. hoopR and sportsdataverse. Full-season history in one pull for
    multi-season depth.
13. Real salaries. Basketball-Reference contracts at low rate plus
    cache. Turns the cap ledger from estimated to sourced.
14. RAPTOR historical CSV. Frozen 2023, fine as model priors.
15. DARKO and EPM boards. UI-only, scrape-hostile. Park unless a
    stable path appears.

## Phase 4 — Loop polish

16. Canned briefs. Next-opponent scout and rotation check as one-call
    composites plus skills, not generic chat.
17. Eval growth. Every new tool gets eval and scenario cases the same
    commit it lands.
18. Morning file brief stays file-only. No push channels, per owner.

## Rules of the loop

V1 tools only, new tools need a decision row. Verify each unit before
the next with real runs, not summaries. Local commits only, no pushes,
no deploys without approval. Never log keys.
