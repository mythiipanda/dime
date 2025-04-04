# Codebase Summary: NBA Sports Analytics Platform (Initial)

## Project Structure Overview

*   **Frontend (`nba-analytics-frontend/`)**: Standard Next.js App Router structure.
    *   `app/`: Core routing and UI components (`layout.tsx`, `page.tsx`).
    *   `components/ui/`: Contains shadcn/ui components (e.g., `button.tsx`).
    *   `lib/`: Utility functions (`utils.ts` from shadcn).
    *   `public/`: Static assets.
    *   Configuration files: `next.config.ts`, `tailwind.config.ts`, `tsconfig.json`, `components.json`.
*   **Backend (`nba-analytics-backend/`)**: Standard Python project structure.
    *   `.venv/`: Python virtual environment.
    *   `main.py`: FastAPI application entry point.
    *   `agents.py`: Placeholder for Agno agent definitions.
    *   `requirements.txt`: Python dependencies.
    *   `.env`: Environment variables (API keys, etc.).
    *   `.gitignore`: Specifies files/directories ignored by Git.

## Key Components (Planned/Initial)

*   **Frontend:**
    *   `app/layout.tsx`: Root layout (currently default Next.js).
    *   `app/page.tsx`: Main landing page (currently default Next.js).
    *   `components/ui/button.tsx`: Added via `shadcn/ui`.
    *   `lib/utils.ts`: Created by `shadcn/ui`.
*   **Backend:**
    *   `main.py`: Basic FastAPI app structure.
    *   `agents.py`: Placeholder for future Agno agents.
*   *Application-specific components and agents are planned but not yet created.*

## Data Flow (Initial)

*   **Frontend:** Currently, no external data flow. Will use mock data. Planned: Fetching from backend API / external NBA APIs.
*   **Backend:** Currently, no data flow. Planned: Fetching from external NBA APIs, processing data, serving data/insights via FastAPI endpoints.

## External Dependencies (Initial)

*   **Frontend:** `next`, `react`, `react-dom`, `typescript`, `tailwindcss`, `shadcn-ui` related libs (`class-variance-authority`, `clsx`, etc.).
*   **Backend:** `agno`, `fastapi`, `uvicorn`, `python-dotenv`, `sqlalchemy`, `psycopg[binary]`, `google-generativeai`.

## Recent Significant Changes

*   [2025-04-04] Frontend project bootstrapped (`nba-analytics-frontend`).
*   [2025-04-04] `shadcn/ui` initialized in frontend.
*   [2025-04-04] Backend project structure created (`nba-analytics-backend`) with Python venv and core dependencies installed.

## User Feedback Integration

*   N/A at this stage.