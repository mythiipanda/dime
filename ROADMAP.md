# Dime Roadmap: AI-native NBA analyst workbench

Goal: the chat Tyrese Haliburton Twitter nerds and team analysts open daily.
Free public data only. No odds (killed). No deploy until approved.
Each unit ships only after real runs: pytest, eval, scenarios, browser beta.

**Status as of Sep 10, 2026.** `main` = Sep 9 night-shift promotion (P0s shipped).
`dev` + `muse/backend` + `muse/frontend` + `tony/features` = Sep 10 day shift,
integrating ~10pm ET.

## Market Strategy (added 2026-09-09)

**Source:** `research/nba-analyst-market-brief.md` — full competitive analysis.

**Thesis:** Every incumbent is a database with a query UI (Stathead), a metric with a
dashboard (Dunks & Threes, Cleaning the Glass), or a lookup bot (StatMuse). Nobody is
an **analyst**: nobody takes a question, gathers evidence across sources, reasons about
it, and answers with receipts. That's the gap.

**Target:** The Ringer's working NBA writer — 12 tabs open, $25-40/mo across subscriptions.
If Dime answers the CTG question AND the Stathead question AND the EPM question in one
chat, subscriptions lapse.

**Wedges (priority order):**
1. **Cross-metric adjudication** — SHIPPED Sep 10 (`compare_metrics` + MetricsView).
   "EPM says X, LEBRON says Y — who's right and why?"
2. **Citable artifacts** — SHIPPED Sep 10 (CitePill, buildCitation). Every answer
   carries source + timestamp; screenshots work without added context.
3. **Bettor-adjacent Q&A** — SHIPPED Sep 10 (splits finder, opponent-tier matchup
   rows, game predictions). Analysis tool, never picks.
4. **Freshness as feature** — SHIPPED Sep 10 (warehouse freshness registry +
   panel). Real-time feel during season vs opaque update schedules.
5. **Free-tier wedge** — Undercut $25-40/mo subscription fatigue with generous free NL.

**Don't build:** Betting picks, video/film (Synergy owns it), social beyond debate cards,
trying to replace EPM/LEBRON (referee them instead).

**Risks:** Data licensing (BRef scraping policy), NBA+AWS "Inside the Game" coming
downmarket, StatMuse adding LLMs (Dime's window is depth before they move).

## Phase 0 — Done (Sep 9 and earlier)

Chat over DuckDB warehouse, supervisor plus scout/team/league workers,
70+ tools, compare/preview composites, trade checker, draft combine panel,
team ratings, clutch splits, NBA.com watch links, shot charts, heat maps,
threads plus runs plus export, debate cards, watchlist, ThinkingBlock UI,
real SSE streaming.

## Phase 1 — Done Sep 10 (night shift, on `main`)

1. **Cross-metric adjudication** (`compare_metrics` tool + MetricsView UI).
   Registry of metric disagreements, supervisor wiring, eval cases.
2. **Citable artifacts** (CitePill on tables and answers, title-safe stream tables).
3. **text-to-SQL reliability** — synonym expansion, streak SQL examples,
   deterministic streak leaders, warehouse-first game logs.
4. **Splits + matchup history** — opponent-tier matchup rows, warehouse-first splits.
5. Verification: backend suite green, tsc clean, frontend build ok, Playwright
   smoke (load, chat SSE, today/movers/watchlist, no emoji).

## Phase 2 — Day shift Sep 10 (on `dev` + crew branches, integrating 10pm ET)

Backend (`muse/backend`, 11 commits):
- Rest advantage + lineup matchup matrix tools
- Competitive ratings (blowout-excluded MOV, padding delta)
- Conversational shot finder (`search_shots`: zones, late-game, heave-free)
- Freshness registry (hustle, RAPM, shots coverage)
- 2025-26 season data audit; bbref game-log scrape hardening (588-player target)

Frontend (`muse/frontend`, 9 commits):
- GameLogView, RotationCheckView, StreaksView, PredictionView, HeadToHeadView,
  ImpactView, LineupStatsView, RestAdvantageView, LineupMatrixView
- Debate modal polish, CompareView mobile, artifact surfacing, 390px mobile pass,
  loading skeletons, CourtHeatmap routing for shot zones
- 23/23 consultant UX tickets fixed

Data + bench (on `dev`):
- 2025-26: silver_scoreboard (in-warehouse), silver_hustle_team (30 teams),
  team_games + lineups promoted from hist tables, 2024-25 player seasons
- DimeBench families: rotation, ELO, gamelog, search_game_logs, impact_estimate
- `get_elo_standings` (538-style), `search_game_logs`, `get_impact_estimate`,
  `get_game_prediction` + triage fast-paths, rotation check rebuild
- Latency cuts (trade checker, Today endpoint 30s → 8s)
- Docs: `docs/PRESEASON_2026_27.md`, `docs/SEASON_ROLLOVER.md`

## Phase 3 — Next (priority order)

1. **2026-27 season readiness.** Preseason starts Oct 3, 2026. Daily ingestion
   pipelines, season rollover runbook execution. Owner: data desk.
2. **Data completeness.** Full 2025-26 regular-season + playoff coverage:
   player/team game logs, season stats, shots. Real sources only
   (basketball-reference, NBA API). Finish the 588-player bbref scrape.
   Never fabricate; disclose gaps.
3. **Latency.** Agent paths still slow. Profile, cut worst offenders.
4. **New analyst tools.** Full-stack slices (tool + view + DimeBench family
   in the same commit) an analyst can't get from Stathead.
5. **Consultant tickets.** Keep the outside-persona loop running (beat writer,
   fantasy grinder, casual fan); triage like customer tickets.

## Phase 4 — Parked / later

- Historical depth backfill to 2010 (`get_historical_leaders`)
- Multi-season RAPM priors; WPA-by-play leaders from PBP
- Draft model v2 (BartTorvik college stats + classifier)
- Real salaries from BRef contracts (contract value currently honest minimums)
- Synergy play types (only if answerable without subscription)
- Morning-file briefs stay file-only; no push channels, per owner

## Phase 5 — Interface polish (added 2026-09-11)

19. Cleaner chat UI with built-in micro-interactions. Study the
    subtleties in https://tldraw-chat-app-example.tldraw.workers.dev/
    (streaming caret behavior, message transitions, input focus states,
    loading skeletons that match content shape). Do not copy it; adapt
    the calm, text-first feel to DESIGN.MD (stone neutrals, one cyan
    accent, no gradients, no glassmorphism, no emojis).
20. Component library survey before building new views. Candidate
    sources, cheapest-first: https://ui.spectrumhq.in (expensive-looking
    components), http://21st.dev (community library), 
    https://shadcnblocks.com (shadcn blocks), http://reactbits.dev
    (animated React bits), https://8bitcn.com (retro pixel),
    https://evilcharts.com (animated SVG charts), https://coss.com/ui,
    https://rareui.com, https://beui.dev (animated components).
    Adopt patterns, not dependencies: keep the frontend dependency
    footprint flat and every new view behind a screenshot spot-check
    (1280px and 390px).

## Rules of the loop

V1 tools only, new tools need a decision row. Verify each unit before
the next with real runs, not summaries. Crew branches only; no pushes to
`main` without Tony's direct approval each time. Never log keys. Never
fabricate data or proprietary metrics.

## Appendix — Analyst scenarios from public repos and notebooks

Status as of Sep 10, 2026.

1. RAPM player impact. Have RAPM-lite + `get_impact_estimate`. Next: multi-season priors.
2. Win probability plus WPA. Have `get_win_prob`. Next: WPA-by-play leaders from PBP.
3. ELO power ratings. HAVE `get_elo_standings` (538-style).
4. Game predictor via Monte Carlo. HAVE `get_game_prediction`.
5. Playoff simulator. HAVE `get_playoff_sim` (10k best-of-7 sims).
6. Shot hexmaps. Have shot charts and zones. Next: zone efficiency deltas vs league avg.
7. DFS optimizer. Out of scope, gambling-adjacent. Skip.
8. Trade checker. Have v1 with disclaimer + honest-minimum contract values.
   Next: real salaries from BRef contracts.
9. Draft model. Have combine panel + draft board. Next: BartTorvik + classifier.
10. Contract value and referee bias. Value residual fits `get_compare` later.
    Officiating needs L2M reports, no stable feed. Park officiating.
