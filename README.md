# Dime

Ask NBA questions in plain English. Dime plans the query, runs it
against its own data warehouse, and shows its work.

Live demo: [dime-fawn.vercel.app](https://dime-fawn.vercel.app)

<video src="assets/readme/dime-motion-demo.mp4" controls muted loop playsinline width="100%"></video>

![Dime answering a four-factors question](assets/readme/four-factors-dark.png)

## Features

- Chat that answers with numbers, not vibes. Every stat comes
  out of the warehouse and the reply shows the tables, charts,
  and shot maps behind it.
- Current season (2025-26): scoring, efficiency, true shooting,
  four factors, on/off splits, clutch numbers, shot zones,
  lineups, rest advantage, game predictions, head-to-heads.
  Trade checks against the 2026-27 cap ledger, award races,
  and draft history back to 1996-97.
- History: game logs, shots, possessions, lineups, and
  standings for 2009-10 through 2025-26, play-by-play for
  2020-21 through 2024-25, and RAPTOR back to 1976-77.
- Fixed answers come from code, not recall. Records, four
  factors, Finals results, and rankings are computed from
  warehouse rows. Outside the coverage window, the answer
  says so instead of guessing.
- 101 tools over a local DuckDB warehouse. Chat runs on
  Gemini (default) and NVIDIA NIM behind one interface.
- Streams tokens and live tool activity over SSE, in dark
  and light themes.

![Dime in the light theme](assets/readme/chat-light.png)

## Quickstart

Backend (Python 3.12):

```bash
cd backend
uv venv --python 3.12
uv pip install -r requirements.txt
cp .env.example .env   # add your LLM keys for chat; the server boots without them
# warehouse: download the data pack release and unzip it so that backend/data/warehouse.duckdb exists
# https://github.com/mythiipanda/dime/releases/download/tony-features-pack-20260911/dime_data.zip
python scripts/generate_asset_manifest.py manifest/expected_asset_manifest.json
DIME_EXPECTED_ASSET_MANIFEST=$PWD/manifest/expected_asset_manifest.json \
  uvicorn app.main:app --port 8010
```

The manifest step is required. Without
`DIME_EXPECTED_ASSET_MANIFEST`, the server exits at startup
with `RuntimeError: DIME_EXPECTED_ASSET_MANIFEST is required`.

Frontend:

```bash
cd frontend
npm install
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8010 npm run dev
```

Open http://localhost:3000 and ask: "What are the Thunder's
four factors this season?"

## How it works

```
frontend/   Next.js 16, React 19, Tailwind 4, Recharts.
            Streams tokens and live tool activity over SSE; dark and light themes.
backend/    FastAPI planner with 101 tools over a local DuckDB warehouse.
            Gemini (default) and NVIDIA NIM behind one interface.
infra/      Azure Container Apps, scale-to-zero.
```

You type a question. The planner picks the tools, runs them
against the warehouse, and streams back the answer with the
evidence attached.

Production serves the v1 runtime. The v2 runtime is built,
tested, and wired behind the `DIME_RUNTIME_V2` flag, with
the cutover still pending.

## Data

The warehouse is a DuckDB file baked into the backend Docker
image. On backend changes, CI downloads the data pack
(`tony-features-pack-20260911`, published 2026-09-12),
unzips it into `backend/data/`, builds derived tables at
image time, and pushes
`ghcr.io/mythiipanda/dime-backend:latest`. Nothing queries
a live stats API at answer time.

Coverage in the current pack: 52 tables, 47 of them silver.
The `silver_hist_*` tables span 2009-10 through 2025-26
(game logs, shots, possessions, lineups, standings).
Play-by-play covers 2020-21 through 2024-25. RAPTOR runs
1976-77 through 2021-22. Draft history runs 1996-97
through 2023-24. Current-season tables and the 2026-27 cap
ledger ship with each pack.

## Evals and tests

The benchmark pack lives in the private dime-internal repo
at `evals/benchmark-pack/`. It runs 35 scenarios against a
live backend with expected-answer assertions. From a
dime-internal checkout:

```bash
python evals/benchmark-pack/runner.py --url http://127.0.0.1:8010 --out reports/run.json
```

The pytest suite (`backend/tests/`, 118 test files) covers
routing, the pinned lanes, warehouse contracts, and
streaming:

```bash
cd backend
pytest tests/ -q
```

## Contributing

Push backend changes on `dev` and CI builds the backend
image with the data pack baked in. Run `pytest tests/ -q`
from `backend/` before you open a PR. Deployments go
through `infra/deploy.sh`, which needs `az login` and the
LLM keys in `backend/.env` (pushed as Container App
secrets, never committed).

## License

No license file ships with the repo yet.
