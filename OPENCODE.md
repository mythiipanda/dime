# OpenCode Instructions — Dime Project

You are working on **Dime**, an AI-native NBA analytics product. Read this file first
before doing anything.

## What Dime Is

Dime is a chat interface over a DuckDB data warehouse of NBA stats. Users ask natural
language questions ("who's the most clutch player?"), the agent calls 70+ backend tools,
reasons over the evidence, and answers with cited numbers.

**The thesis:** Every competitor is a database with a query UI, a metric with a dashboard,
or a lookup bot. Nobody is an analyst. Dime is the analyst.

**Status (Sep 10, 2026):** `main` holds the Sep 9 night-shift promotion —
cross-metric adjudication (`compare_metrics` + MetricsView), citable artifacts
(CitePill), text-to-SQL reliability, debate cards, watchlist, ThinkingBlock UI.
`dev` + crew branches (`muse/backend`, `muse/frontend`, `tony/features`) carry the
Sep 10 day shift: DimeBench families, ELO standings, game-log search, impact
estimates, game predictions, rotation/rest/lineup tools, shot finder, nine new
frontend views. 2025-26 full-season data is the top data priority; 2026-27
preseason starts Oct 3.

## Before You Start

1. Read `ROADMAP.md` — product strategy, market positioning, priority stack.
2. Read `research/nba-analyst-market-brief.md` — competitive landscape, pain points.
3. Read `DESIGN.MD` — visual design law (warm stone, no gradients, no emojis).
4. Check `backend/app/tools/__init__.py` — the registered tools. Don't duplicate.

## Repository Rules (non-negotiable)

- Work on your assigned crew branch (`muse/*`, `tony/*`). Never push to `main`
  without Tony's direct approval each time.
- New backend tools require a `decisions.tsv` row first (local-only, gitignored).
- Never commit: `.env`, credentials, DuckDB files (`*.duckdb`), `AGENTS.md`,
  `LEARNINGS.md`, `decisions.tsv`, shift logs.
- Proxy sanitization lives in `backend/app/__init__.py` — don't move or remove it.
- `get_today` uses `shutdown(wait=False)` for real timeouts — don't regress this.
- DuckDB is single-writer. Only one backend server at a time.

## Design Law

- Warm Seline-inspired stone canvas, stone neutrals, one cyan accent.
- Restrained typography. No gradients, no glassmorphism.
- **No emojis anywhere in the UI.** Text-only, minimal like ChatGPT.
- ChatGPT-style agent UI: collapsible ThinkingBlock, inline ToolCallRows, subtle PlanSteps.

## How to Build

### Backend tools
1. Add the tool in `backend/app/tools/<domain>.py`.
2. Register it in `backend/app/tools/__init__.py`.
3. Add a `decisions.tsv` row (repo rule, local-only).
4. Test: `cd backend && .venv/bin/python -m pytest tests/ -q` (full suite green).

### Frontend
1. Follow existing component patterns in `frontend/components/`.
2. Add API helpers to `frontend/lib/api.ts`.
3. Checks: `npx tsc --noEmit` clean, `npm run build` green, screenshot
   spot-check at 1280px and 390px.
4. Don't start the dev server.

### Commits
- One feature per commit. Focused messages.
- Push to your crew branch with `gh-push-commit.py` (Git Data API, one remote
  commit per local commit).

## Priority Order

Work on the highest priority unbuilt item from ROADMAP.md. As of Sep 10:

1. **2026-27 season readiness** — preseason starts Oct 3, 2026. Daily ingestion
   prep, season rollover. See `docs/PRESEASON_2026_27.md`.
2. **Data completeness** — full 2025-26 regular-season + playoff coverage
   (player/team game logs, season stats, shots). Real sources only.
3. **Latency** — agent paths are slow. Profile and cut the worst offenders.
4. **New analyst tools** — full-stack slices (tool + view) an analyst can't
   get from Stathead. Every new tool gets a DimeBench family the same commit.
5. **Consultant tickets** — outside-persona feedback (beat writer, fantasy
   grinder, casual fan) triaged like customer tickets.

Done, don't rebuild: cross-metric adjudication, citable artifacts, SSE
streaming, matchup splits, regression, trade fit, comps, awards/debate,
previews, streaks, lineups, predictions, freshness, head-to-head, shot zones,
impact estimates, game-log search, ELO standings, playoff sim.

## What NOT to Build

- Betting picks or odds integration
- Video/film features
- Social features beyond debate cards
- Replacing EPM/LEBRON — referee them, don't compete

## Testing

- Backend: `cd backend && .venv/bin/python -m pytest tests/ -q` (green)
- DimeBench: spot-check the affected family in `backend/bench/`
- Frontend: `npx tsc --noEmit` + `npm run build` + screenshot spot-check
- All green before committing.

## When Stuck

- Check if the tool already exists before building a new one.
- Check `research/nba-analyst-market-brief.md` for market context.
- The user (Tony) is the product owner. Only ask him about genuinely new or high-impact
  product decisions (new feature direction, killing a feature, monetization). For
  reversible implementation choices, decide yourself and note it in decisions.tsv.
