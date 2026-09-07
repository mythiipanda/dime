# Dime — NBA analyst workbench

An agent assistant for NBA data analysts. Chat over a DuckDB warehouse of
five seasons plus live APIs, with provenance on every table.

## Layout

`backend/` owns the FastAPI service. FastAPI plus LangGraph plus DuckDB.
`frontend/` owns the Next.js workbench. Next 16 plus Tailwind v4.
`infra/` owns Azure deploy scripts. Container Apps consumption plan.
`DESIGN.MD` owns the Seline visual spec.

## Quickstart

Backend first. Copy `backend/.env.example` to `backend/.env` and fill keys.
Install with `pip install -r backend/requirements.txt`.
Seed with `python -m scripts.seed_history` from `backend/`.
Serve with `uvicorn app.main:app` from `backend/`.

Frontend next. Set `NEXT_PUBLIC_BACKEND_URL` in `frontend/.env.local`.
Install with `npm install` in `frontend/`. Serve with `npm run dev`.

## Checks

`python -m scripts.eval` runs the tool eval set.
`python -m scripts.scenarios` runs daily analyst cases.
`python -m scripts.validate` gates warehouse hygiene.

## Rules

`LEARNINGS.MD`, `AGENTS.md`, `decisions.tsv`, and any `.env` file stay
local. They never commit. CI enforces this.
