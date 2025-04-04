# Technical Context: NBA Sports Analytics Platform

## Core Technologies

*   **Frontend Framework:** Next.js (using App Router)
*   **UI Library:** shadcn/ui
*   **Styling:** Tailwind CSS v4 (Configured via `shadcn/ui init`)
*   **Language:** TypeScript
*   **State Management:** React Context (initially), potentially others later.

## Planned Backend

*   **Backend Framework:** Agno (using FastAPI for serving)
*   **Backend Language:** Python

## Data Sources & APIs (Planned / Initial)

*   **Primary Data:** Free NBA Data APIs
    *   BallDontLie (Player stats, game logs - 60 req/min limit)
    *   NBA.js (Play-by-play - Unofficial, rate-limited)
    *   HoopR (Shot charts, lineup stats - Python/R focused, requires workaround)
    *   RapidAPI Free Tier (News/social sentiment - 500 req/month limit)
*   **Initial Data:** Mock data will be used during early development phases.

## Frontend Visualization Libraries (Planned)

*   **Charts/Graphs:** D3.js, Nivo, Visx
*   **Data Grids:** AG Grid, TanStack Table
*   **3D Visuals:** Three.js, React-Three-Fiber
*   **Animations:** Framer Motion, React-Spring

## AI Integration (Planned)

*   **Model:** Google Gemini (or similar)
*   **Execution:** Browser-based AI runtime (e.g., WebAssembly) for client-side processing initially. Prompts designed to interpret stats.

## Development Setup

*   **Frontend Package Manager:** npm (as chosen during `create-next-app`)
*   **Backend Package Manager:** pip (within `.venv`)
*   **Version Control:** Git
*   **Code Editor:** VS Code (Debugging configurations planned)
*   **Backend Structure:** Standard Python project (`nba-analytics-backend`) with virtual environment (`.venv`), `main.py` (FastAPI), `agents.py`, `requirements.txt`, `.env`, `.gitignore`.

## Technical Constraints & Considerations

*   **API Rate Limits:** Need robust caching and potentially fallback mechanisms.
*   **Data Consistency:** Cross-verification needed due to multiple data sources.
*   **Real-time Updates:** Initial approach via polling, potential for WebSockets later.
*   **Visualization Performance:** Progressive rendering and optimization techniques for large datasets.
*   **shadcn/ui Setup:** Initialized with default settings. Created `components.json` and `lib/utils.ts`. Tailwind CSS v4 configured.