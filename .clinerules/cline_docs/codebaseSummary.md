## Key Components

*   **Frontend (`nba-analytics-frontend/`):** Next.js application using App Router, TypeScript, Tailwind CSS, and shadcn/ui. (Development currently paused).
*   **Backend (`nba-analytics-backend/`):** Python FastAPI application using Agno for agent orchestration.
    *   **`main.py`:** Defines FastAPI app, API endpoints (`/`, `/analyze`, `/fetch_data`), Pydantic request models. `/fetch_data` currently calls tool logic directly due to agent testing issues. Includes JSON extraction helper for agent responses.
    *   **`agents.py`:** Defines Agno agents:
        *   `DataAggregatorAgent`: Uses Gemini, equipped with tools (`get_player_info`, `get_player_gamelog`, `get_player_career_stats`, `get_team_info_and_roster`, `find_games`) to fetch data via `nba-api`.
        *   `AnalysisAgent`: Uses Gemini, currently analyzes mock data provided via API request, but has data tools available. Instructions updated to handle potentially wrapped JSON input.
        *   `DataNormalizerAgent`: Placeholder definition (currently commented out).
    *   **`teams.py`:** Defines `NBAnalysisTeam` which coordinates `DataAggregatorAgent` and `AnalysisAgent` to handle user queries requiring both data fetching and analysis. Instructions guide sequential execution for comparisons.
    *   **`tools.py`:** Contains Agno `@tool` decorated wrapper functions for the data fetching logic. Handles basic parameter validation.
    *   **`api_tools/`:** Contains the core logic interacting with the `nba-api` library.
        *   `player_tools.py`: Logic for player info, gamelog, career stats. Includes helper `_find_player_id`.
        *   `team_tools.py`: Logic for team info/roster. Includes helper `_find_team_id` and `CURRENT_SEASON` constant.
        *   `game_tools.py`: Logic for finding games (`leaguegamefinder`), results limited.
    *   **`app.py`:** Script for manually testing the `NBAnalysisTeam` workflow directly, logging results to `app_test_output.log`.
    *   **`test_main.py`:** Pytest tests for API endpoints. `/fetch_data` tests currently validate direct logic calls. `/normalize_data` test commented out.
    *   **`.env`:** Stores API keys (e.g., `GOOGLE_API_KEY`).
    *   **`requirements.txt`:** Lists Python dependencies.
    *   **`pytest.ini`:** Configures pytest-asyncio.
    *   **`.gitignore`:** Excludes virtual environment, cache files, logs, etc.
    *   **`agno_storage.db`:** SQLite database for Agno agent session storage.

## Data Flow (Team Workflow Example)

1.  User sends prompt to `app.py` (e.g., "Compare KD's career stats per game vs totals").
2.  `app.py` calls `NBAnalysisTeam.run(prompt)`.
3.  `NBAnalysisTeam` (Lead Agent) determines two datasets are needed.
4.  `NBAnalysisTeam` instructs `DataAggregatorAgent` to get "PerGame" stats.
5.  `DataAggregatorAgent` calls `get_player_career_stats` tool (passing "PerGame").
6.  Tool calls `fetch_player_career_stats_logic` which calls `nba-api`.
7.  Logic returns JSON string to Tool.
8.  Tool returns JSON string to `DataAggregatorAgent`.
9.  `DataAggregatorAgent` returns wrapped JSON string to `NBAnalysisTeam`.
10. `NBAnalysisTeam` passes wrapped JSON and query part to `AnalysisAgent`.
11. `AnalysisAgent` instructions guide it to extract the inner JSON, analyze "PerGame" stats.
12. `AnalysisAgent` returns analysis text to `NBAnalysisTeam`.
13. `NBAnalysisTeam` repeats steps 4-12 for "Totals" stats.
14. `NBAnalysisTeam` synthesizes the two analyses into a final response.
15. `NBAnalysisTeam` returns final response object to `app.py`.
16. `app.py` extracts final message from history and logs/prints it.

*(Note: `/fetch_data` endpoint currently bypasses steps 3-15 and calls logic directly)*

## External Dependencies

*   `nba-api`: Python client for stats.nba.com.
*   `agno`: Agent framework.
*   `fastapi`: Web framework for API.
*   `uvicorn`: ASGI server.
*   `pydantic`: Data validation.
*   `python-dotenv`: Environment variable loading.
*   `requests`: For `app.py` client.
*   `pytest`, `pytest-asyncio`: For testing.
*   `google-generativeai`: For Gemini model via Agno.

## Recent Significant Changes

*   [2025-04-04] Added `find_games` tool using `leaguegamefinder`.
*   [2025-04-04] Implemented `NBAnalysisTeam` for multi-agent workflow.
*   [2025-04-04] Refined agent instructions for team coordination and JSON handling.
*   [2025-04-04] Implemented workarounds for Agno agent response wrapping (JSON extraction helper).
*   [2025-04-04] Limited `find_games` results to prevent token errors.
*   [2025-04-04] Fixed various tool signature/parameter issues (`playercareerstats`, `find_games`).
*   [2025-04-04] Updated tests (`test_main.py`) and manual test script (`app.py`).
*   [2025-04-04] Updated `.gitignore`.
*   [2025-04-04] Commented out `DataNormalizerAgent` and related test due to `ImportError`.

## User Feedback Integration

*   Addressed feedback regarding agent usage vs. direct logic calls.
*   Addressed feedback regarding tool access for all agents.
*   Addressed feedback regarding logging output from `app.py`.
*   Addressed feedback regarding fixing test failures.