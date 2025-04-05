## Key Components

*   **Frontend (`nba-analytics-frontend/`):** Next.js application using App Router, TypeScript, Tailwind CSS, and shadcn/ui. (Development starting).
*   **Backend (`nba-analytics-backend/`):** Python FastAPI application using Agno for agent orchestration.
    *   **`main.py`:** Defines FastAPI app, API endpoints (`/`, `/analyze`, `/fetch_data`), Pydantic request models. `/fetch_data` calls logic directly (now handles dict/list returns). `/analyze` uses agent. `/normalize_data` commented out. JSON extraction helper present but potentially only needed for `/analyze`. Test coverage improved.
    *   **`agents.py`:** Defines Agno agents:
        *   `DataAggregatorAgent`: Uses configured model (`AGENT_MODEL`), equipped with tools (`get_player_info`, `get_player_gamelog`, `get_player_career_stats`, `get_team_info_and_roster`, `find_games`) to fetch data via `nba-api`. Instructions updated (no longer needs to return raw JSON).
        *   `AnalysisAgent`: Uses configured model (`AGENT_MODEL`), equipped with data tools. Instructions updated to handle wrapped JSON input.
        *   `DataNormalizerAgent`: Placeholder definition (currently commented out).
    *   **`teams.py`:** Defines `NBAnalysisTeam` (using configured `AGENT_MODEL`) which coordinates `DataAggregatorAgent` and `AnalysisAgent` to handle user queries requiring both data fetching and analysis. Instructions guide sequential execution for comparisons.
    *   **`tools.py`:** Contains Agno `@tool` decorated wrapper functions for data fetching (`get_player_info`, `get_player_gamelog`, `get_team_info_and_roster`, `get_player_career_stats`, `find_games`). Wrappers now perform JSON serialization on results from logic functions. Handles basic parameter validation.
    *   **`api_tools/`:** Contains the core logic interacting with the `nba-api` library.
        *   `player_tools.py`: Logic for player info, gamelog, career stats. Returns dict/list. Uses config constants and `utils._process_dataframe`. Test coverage improved.
        *   `team_tools.py`: Logic for team info/roster. Returns dict/list. Uses config constants and `utils._process_dataframe`. Test coverage improved.
        *   `game_tools.py`: Logic for finding games (`leaguegamefinder`), results limited. Returns dict. Uses config constants and `utils._process_dataframe`. Test coverage improved.
        *   `utils.py`: (New) Contains shared `_process_dataframe` helper.
    *   **`app.py`:** Cleared of old test logic. (Manual testing moved to `test_agents/verify_team.py`).
    *   **`test_main.py`:** Pytest tests for API endpoints. Includes tests for error handling paths. Test coverage improved.
    *   *(Note: `test_player_tools.py`, `test_team_tools.py`, `test_game_tools.py`, `test_utils.py` do not currently exist on this branch).*
    *   **`test_agents/`:** (New) Directory for manual agent/team verification.
        *   `verify_team.py`: Script to run `NBAnalysisTeam` with example prompts.
        *   `verify_team_output.txt`: Output file for manual verification.
    *   **`.env`:** Stores API keys (e.g., `GOOGLE_API_KEY`).
    *   **`config.py`:** (New) Centralized configuration for constants (TIMEOUT, SEASON, MODEL), API keys, settings.
    *   **`requirements.txt`:** Lists Python dependencies (includes `pytest-cov`).
    *   **`pytest.ini`:** Configures pytest-asyncio.
    *   **`.gitignore`:** Excludes virtual environment, cache files, logs, etc. (Root and backend).
    *   **`agno_storage.db`:** SQLite database for Agno agent session storage.

## Data Flow (Team Workflow Example)

1.  User sends prompt to `test_agents/verify_team.py` (e.g., "Compare KD's career stats per game vs totals").
2.  `verify_team.py` calls `NBAnalysisTeam.run(prompt)`.
3.  `NBAnalysisTeam` (Lead Agent) determines two datasets are needed.
4.  `NBAnalysisTeam` instructs `DataAggregatorAgent` to get "PerGame" stats.
5.  `DataAggregatorAgent` calls `get_player_career_stats` tool (passing "PerGame").
6.  Tool calls `fetch_player_career_stats_logic` which calls `nba-api`.
7.  Logic returns dictionary/list to Tool wrapper.
8.  Tool wrapper serializes result to JSON string and returns it to `DataAggregatorAgent`.
9.  `DataAggregatorAgent` returns JSON string to `NBAnalysisTeam`.
10. `NBAnalysisTeam` passes wrapped JSON and query part to `AnalysisAgent`.
11. `AnalysisAgent` instructions guide it to extract the inner JSON, analyze "PerGame" stats.
12. `AnalysisAgent` returns analysis text to `NBAnalysisTeam`.
13. `NBAnalysisTeam` repeats steps 4-12 for "Totals" stats.
14. `NBAnalysisTeam` synthesizes the two analyses into a final response.
15. `NBAnalysisTeam` returns final response object to `app.py`.
16. `verify_team.py` extracts final message from history and saves to output file.

*(Note: `/fetch_data` endpoint in `main.py` uses similar agent flow but relies on history extraction)*

## External Dependencies

*   `nba-api`: Python client for stats.nba.com.
*   `agno`: Agent framework.
*   `fastapi`: Web framework for API.
*   `uvicorn`: ASGI server.
*   `pydantic`: Data validation.
*   `python-dotenv`: Environment variable loading.
*   `requests`: (Potentially unused now if `app.py` is cleared).
*   `pytest`, `pytest-asyncio`, `pytest-cov`: For testing and coverage.
*   `google-generativeai`: For Gemini model via Agno.

## Recent Significant Changes

*   [2025-04-04] Added `find_games` tool using `leaguegamefinder`.
*   [2025-04-04] Implemented `NBAnalysisTeam` for multi-agent workflow.
*   [2025-04-04] Refined agent instructions for team coordination and JSON handling.
*   [2025-04-04] Implemented workarounds for Agno agent response wrapping (JSON extraction helper).
*   [2025-04-04] Limited `find_games` results to prevent token errors.
*   [2025-04-04] Fixed various tool signature/parameter issues (`playercareerstats`, `find_games`).
*   [2025-04-04] Updated tests (`test_main.py`) and manual test script (`app.py`).
*   [2025-04-04] Updated `.gitignore` (root and backend).
*   [2025-04-04] Commented out `DataNormalizerAgent` and related test due to `ImportError`.
*   [2025-04-04] Fixed `NameError` for `CURRENT_SEASON` in `tools.py`. (Now imported from config).
*   [2025-04-04] Updated `main.py` JSON extraction helper again.
*   [2025-04-05] Refactored backend: centralized config (`config.py`), created `api_tools/utils.py`, moved `_process_dataframe`.
*   [2025-04-05] Refactored `api_tools` logic functions to return dict/list and use config/utils.
*   [2025-04-05] Refactored `tools.py` wrappers to perform JSON serialization.
*   [2025-04-05] Refactored `main.py` `/fetch_data` endpoint to handle direct dict/list returns.
*   [2025-04-05] Refactored `agents.py` and `teams.py` to use configured `AGENT_MODEL`.
*   [2025-04-05] Corrected documentation (`codebaseSummary.md`) regarding file existence (`utils.py`, `shot_tools.py`, test files).
*   [2025-04-04] Fixed type hints in `tools.py` for optional parameters.

## User Feedback Integration

*   Addressed feedback regarding agent usage vs. direct logic calls (reverted to agent calls).
*   Addressed feedback regarding tool access for all agents.
*   Addressed feedback regarding logging output from `app.py` (now `verify_team.py`).
*   Addressed feedback regarding fixing test failures and Git issues.
*   Addressed feedback regarding test coverage improvement.
*   Addressed feedback regarding team verification approach (switched from pytest to script).
*   Addressed feedback regarding season context and model update.