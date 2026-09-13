# Dime

An AI basketball analyst that answers NBA questions with real data, not
vibes. Ask in plain English; Dime plans the work, queries a local DuckDB
warehouse of NBA history, and streams back an answer with the numbers it
actually pulled — tables, charts, shot maps, and the coverage window named
out loud.

![Dime answering a four-factors question](assets/readme/four-factors-dark.png)

<video src="assets/readme/dime-motion-demo.mp4" controls muted loop playsinline width="100%"></video>

## What it does

- **Ask anything NBA.** Season averages, head-to-heads, clutch splits, trade
  checks, award races, draft models, lineup matrices, shot zones, win
  probability, rest advantage, prediction, and more — 93 tools behind one
  chat box.
- **History, not just this week.** 17 seasons of game logs, shot charts,
  and standings (2009-10 through 2025-26), plus this season's full team box
  scores with four factors computed offline from the games themselves.
- **Honest about coverage.** Every answer that touches history names its
  window ("This data covers 2009-10 through 2025-26"). A question outside
  coverage says so instead of guessing.
- **Deterministic where it matters.** Record questions (highest-scoring
  game, four factors, finals results) are answered straight from the
  warehouse payload — the model composes prose, it never invents numerals.
- **Streaming UI.** Token-streamed answers, live tool activity, skeleton
  loaders, dark and light themes.

![Dime in the light theme](assets/readme/chat-light.png)

## Architecture

```
frontend/   Next.js 16 + React 19 + Tailwind 4 + Recharts
            Streaming chat, tool-activity rail, artifact canvas
backend/    FastAPI + LangGraph-style planner
            93 tools over a DuckDB warehouse (backend/data/warehouse.duckdb)
            Multi-provider LLM fan-out on free tiers:
            Mistral (ministral-8b), OpenRouter free models,
            Inception (mercury-2.5), Groq (gpt-oss-20b)
infra/      Azure Container Apps, consumption plan, scale-to-zero
research/   Architecture notes, rivals scan, data roadmap
dime-arch/  Architecture docs and diagrams
```

The warehouse is the source of truth. Seeders under `backend/scripts/` pull
from stats.nba.com, Basketball-Reference, ESPN, and pbpstats into silver
tables; derived tables (like `silver_four_factors_team`) are computed from
those rows locally, no network needed.

## Cost stance

Dime is built to run on $0 of model spend: every provider in the fan-out is
a free tier, and the Azure deploy uses a student subscription with
scale-to-zero consumption pricing.

## Quality gates

- **Benchmark pack** (`backend/tests/benchmark/`): 23 scenario chains with
  expected-answer assertions and per-scenario latency budgets. Run it
  against a live backend:

  ```bash
  cd backend
  python tests/benchmark/runner.py --url http://127.0.0.1:8010 --out reports/run.json
  ```

- **Test suite**: ~75 test files covering routing, pins, warehouse
  contracts, streaming, and trade logic.

  ```bash
  cd backend
  pytest tests/ -q
  ```

## Run it locally

Backend (Python 3.12):

```bash
cd backend
uv venv --python 3.12
uv pip install -r requirements.txt
cp .env.example .env   # add your LLM keys
uvicorn app.main:app --port 8010
```

Frontend (Node 22):

```bash
cd frontend
npm install
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8010 npm run dev
```

Open http://localhost:3000 and ask: "What are the Thunder's four factors
this season?"

## Deploy

`infra/deploy.sh` builds and pushes the backend image to Azure Container
Registry and updates a scale-to-zero Container App. Requires `az login` on
the student subscription and `backend/.env` with the LLM keys (pushed as
Container App secrets, never committed).
