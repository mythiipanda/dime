# Dime Roadmap: AI-native NBA analyst workbench

Goal: the chat Tyrese Haliburton Twitter nerds and team analysts open daily.
Free public data only. No odds (killed). No deploy until approved.
Each unit ships only after real runs: pytest, eval, scenarios, browser beta.

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
1. **Cross-metric adjudication** — "EPM says X, LEBRON says Y — who's right and why?"
   No tool does this. Most differentiated query class.
2. **Citable artifacts** — Analysts' currency is credibility. Every answer needs
   source + timestamp. Screenshots should work without added context.
3. **Bettor-adjacent Q&A** — "Last 15 vs top-10 defenses" in seconds, not hours of
   `nba_api` wrangling. Analysis tool, never picks.
4. **Freshness as feature** — Real-time feel during season vs opaque update schedules.
5. **Free-tier wedge** — Undercut $25-40/mo subscription fatigue with generous free NL.

**Don't build:** Betting picks, video/film (Synergy owns it), social beyond debate cards,
trying to replace EPM/LEBRON (referee them instead).

**Risks:** Data licensing (BRef scraping policy), NBA+AWS "Inside the Game" coming
downmarket, StatMuse adding LLMs (Dime's window is depth before they move).

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

## Appendix — Analyst scenarios from public repos and notebooks

Each scenario maps to a tool or workflow. Status as of this writing.

1. RAPM player impact (Dianjeol stint-data, rd11490 tutorials). Ridge
   on stint differentials. Have RAPM-lite. Next: multi-season priors.
2. Win probability plus WPA (tbukic, colekev). Have get_win_prob.
   Next: WPA-by-play leaders from PBP.
3. ELO power ratings (538 nba-elo). Missing. Tool: standings
   extension with ELO, win-equiv, Elo-implied spread.
4. Game predictor via Monte Carlo (norrisja, badariayush). Missing.
   Tool: preview extension with win percent, projected total,
   confidence interval from ratings plus injuries.
5. Playoff simulator (PRODHOSH, NHX87). Missing. Workflow: bracket
   plus net ratings, 10k best-of-7 sims, series and title odds.
6. Shot hexmaps (hkair, ManoSegr). Have shot charts and zones. Next:
   zone efficiency deltas vs league average.
7. DFS optimizer (owenauch). Out of scope, gambling-adjacent. Skip.
8. Trade checker (HP2324). Have v1-simplified with disclaimer. Next:
   real salaries from BRef contracts (Phase 3.13).
9. Draft model (JasonG7234, AggieSportsAnalytics). Have combine
   panel. Next: BartTorvik college stats plus classifier.
10. Contract value and referee bias (dribbleanalytics, kpelechrinis).
    Value residual fits get_compare later. Officiating needs L2M
    reports, no stable feed. Park officiating, keep value residual.
