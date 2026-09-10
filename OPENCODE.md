# OpenCode Instructions — Dime Project

You are working on **Dime**, an AI-native NBA analytics product. Read this file first
before doing anything.

## What Dime Is

Dime is a chat interface over a DuckDB data warehouse of NBA stats. Users ask natural
language questions ("who's the most clutch player?"), the agent calls 63+ backend tools,
reasons over the evidence, and answers with cited numbers.

**The thesis:** Every competitor is a database with a query UI, a metric with a dashboard,
or a lookup bot. Nobody is an analyst. Dime is the analyst.

## Before You Start

1. Read `ROADMAP.md` — product strategy, market positioning, priority stack.
2. Read `research/nba-analyst-market-brief.md` — competitive landscape, pain points.
3. Read `DESIGN.MD` — visual design law (warm stone, no gradients, no emojis).
4. Check `backend/app/tools/__init__.py` — the 63 registered tools. Don't duplicate.

## Repository Rules (non-negotiable)

- Work on branch `muse/features`. Never push to main without approval.
- New backend tools require a `decisions.tsv` row first.
- Never commit: `.env`, DuckDB files (`*.duckdb`), `AGENTS.md`, `LEARNINGS.md`, `decisions.tsv`.
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
3. Add a `decisions.tsv` row (repo rule).
4. Test: `cd backend && .venv/bin/python -m pytest tests/ -q` (should be 17 passed).

### Frontend
1. Follow existing component patterns in `frontend/components/`.
2. Add API helpers to `frontend/lib/api.ts`.
3. Build: `cd frontend && npm run build` (must pass with no errors).
4. Don't start the dev server.

### Commits
- One feature per commit. Focused messages.
- Local commits only. Never push without explicit approval.

## Priority Order

Work on the highest priority unbuilt item from ROADMAP.md:

1. **P0 — Cross-metric adjudication** (`compare_metrics` tool + UI)
2. **P0 — Citable artifacts** (copy citation buttons, prominent source/timestamp)
3. **P1 — Bettor-adjacent splits** (`get_splits` expansion, matchup history)
4. **P1 — Freshness** (auto-refresh, live indicators, stale warnings)
5. **P2 — Historical depth** (backfill to 2010, `get_historical_leaders`)
6. **P2 — Mobile polish** (375px audit, touch targets, keyboard handling)

## What NOT to Build

- Betting picks or odds integration
- Video/film features
- Social features beyond debate cards
- Replacing EPM/LEBRON — referee them, don't compete

## Testing

- Backend: `cd backend && .venv/bin/python -m pytest tests/ -q`
- Frontend: `cd frontend && npm run build`
- Both must pass before committing.

## When Stuck

- Check if the tool already exists before building a new one.
- Check `research/nba-analyst-market-brief.md` for market context.
- The user (Tony) is the product owner. Ask him for product decisions, not technical ones.
