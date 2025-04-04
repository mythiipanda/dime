# System Patterns: NBA Sports Analytics Platform

## Frontend Setup & Architecture

*   **Project Initialization:** Uses `npx create-next-app@latest` for scaffolding the Next.js project.
    *   Configuration: TypeScript, Tailwind CSS, App Router, ESLint.
*   **UI Component Integration:** Uses `npx shadcn-ui@latest init` to integrate shadcn/ui with the Next.js project.
    *   Configures `tailwind.config.ts`, `globals.css`, and utility functions.
    *   Sets up import alias `@/*` via `tsconfig.json` (or `jsconfig.json`).
*   **Component Management:** Uses `npx shadcn-ui@latest add [component]` to add individual UI components and their dependencies. Components are added directly to the codebase (e.g., in a `components/ui` directory) allowing for customization.
*   **Routing:** Leverages Next.js App Router for file-system based routing, layouts, and server/client component architecture.
*   **Styling:** Primarily uses Tailwind CSS utility classes, configured via `tailwind.config.ts`. shadcn/ui components are built with Tailwind. CSS Variables are used for theming (light/dark mode).
*   **Theming:** Dark mode support implemented via `ThemeProvider` component (from shadcn/ui docs or similar) managing CSS variables and local storage persistence.

## Backend Setup & Architecture (Agno)

*   **Project Initialization:** Standard Python project setup (`mkdir`, `python -m venv .venv`, `pip install ...`). No specific Agno CLI command for project scaffolding identified.
*   **Core Components:**
    *   **Agents (`agents.py`):** Defines `DataAggregatorAgent`, `AnalysisAgent`, `DataNormalizerAgent`.
        *   `DataAggregatorAgent`: Uses Gemini. Equipped with tools (`get_player_info`, `get_player_gamelog`, `get_player_career_stats`, `get_team_info_and_roster`, `find_games`) imported from `tools.py`. Instructions guide tool selection. Returns wrapped JSON.
        *   `AnalysisAgent`: Uses Gemini. Also equipped with data tools. Instructions updated to handle wrapped JSON input from `DataAggregatorAgent`.
        *   `DataNormalizerAgent`: Placeholder definition (currently commented out).
     *   **Teams (`teams.py`):**
         *   `NBAnalysisTeam`: Lead agent coordinating `DataAggregatorAgent` and `AnalysisAgent`. Instructions define workflow, including sequential execution for comparisons to manage context size.
     *   **Tools (`tools.py`, `api_tools/`):**
         *   `tools.py`: Contains Agno `@tool` decorated wrappers. `find_games` signature simplified to avoid schema validation errors.
         *   `api_tools/player_tools.py`, `api_tools/team_tools.py`, `api_tools/game_tools.py`: Contain core logic using `nba-api`. Return JSON strings. `game_tools.py` limits `find_games` results. Helpers included.
     *   **API Server (`main.py`):** Uses FastAPI. `/fetch_data` now calls agent but relies on history/extraction helper (`extract_json_string`) due to agent response issues. `/analyze` uses agent. `/normalize_data` commented out.
     *   **Testing (`test_main.py`, `app.py`):** `pytest` tests API endpoints (some fail due to agent/async issues). `app.py` tests `NBAnalysisTeam` directly.
*   **Storage:** Uses `agno.storage.agent.SqliteAgentStorage` (or other `AgentStorage` subclasses) for persisting agent session data locally during development.
*   **Configuration:** Uses `.env` file and `python-dotenv` for managing API keys (e.g., `GOOGLE_API_KEY`) and other secrets.
*   **Dependencies:** Managed via `pip` and listed in `requirements.txt`.
*   **Testing:** Uses `pytest` and `fastapi.testclient.TestClient` for synchronous testing of FastAPI endpoints (`test_main.py`).

## Data Handling

*   **Data Flow:** Frontend -> Backend API (FastAPI) -> Agno Workflow/Agents -> External APIs -> Agents -> Backend API -> Frontend.
*   **Aggregation:** `DataAggregatorAgent` (coordinated by `NBAnalysisTeam`) uses tools (`tools.py` wrappers calling `api_tools/` logic) which call `nba-api`. Supports player info, gamelogs, career stats (default mode only), team info/roster, finding games (limited results, basic filters).
*   **Normalization:** `DataNormalizerAgent` defined but commented out.
*   **Caching:** Not yet implemented. Planned for backend.

## AI Integration (Planned)

*   **Backend Processing:** `AnalysisAgent` (coordinated by `NBAnalysisTeam`) uses Gemini. Receives data (potentially wrapped JSON) from `DataAggregatorAgent` and performs analysis based on the original user query. Instructions updated for JSON extraction.
*   **Prompt Engineering:** Instructions refined for `DataAggregatorAgent` (tool selection), `AnalysisAgent` (JSON extraction), and `NBAnalysisTeam` (workflow coordination, sequential comparisons).

## Code Structure

*   **Monorepo Structure (Implicit):** Separate directories for frontend (`nba-analytics-frontend`) and backend (`nba-analytics-backend`).
*   **Frontend:** Standard Next.js App Router structure.
*   **Backend:** Modular structure: `main.py` (API), `agents.py` (Individual Agents), `teams.py` (Team Coordinator), `tools.py` (Tool Wrappers), `api_tools/` (API Logic), `app.py` (Direct Agent Test Client). Uses `.venv`, `requirements.txt`, `.env`, `pytest.ini`.