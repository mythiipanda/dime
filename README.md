# NBA Agent

An AI-powered tool for analyzing NBA statistics and data. This project combines a Python backend (using FastAPI and Agno) with a Next.js frontend to provide an interactive chat interface for NBA data analysis.

## Project Structure

-   **`backend/`**: Contains the FastAPI application, Agno agent definition, data fetching tools (using `nba_api`), and tests.
    -   `api_tools/`: Modules for interacting with the `nba_api` library.
    -   `routes/`: FastAPI route definitions.
    -   `tests/`: Pytest tests for tools and agent logic.
    -   `agents.py`: Defines the Agno agent, its system message, and tools.
    -   `config.py`: Configuration settings (API keys, defaults).
    -   `main.py`: FastAPI application entry point.
    -   `tools.py`: Wrappers for logic functions, decorated as Agno tools.
    -   `test_runner.py`: Script for running batch prompts against the agent (used by `test_agent.py`).
-   **`nba-analytics-frontend/`**: Contains the Next.js frontend application.
-   **`.env`**: (Required, not committed) Stores API keys (e.g., `GOOGLE_API_KEY`).
-   **`requirements.txt`**: Backend Python dependencies.

## Agent Capabilities

The core of the backend is an AI agent built with Agno and Google Gemini. It can:

-   Fetch and summarize player basic info, career stats, game logs, and awards.
-   Retrieve team info, rosters, and various team statistics (passing, general).
-   Analyze game data, including box scores (traditional, advanced, four factors) and play-by-play.
-   Provide league-wide information like standings, scoreboards, leaders, and draft history.
-   Find games based on team or player ID.
-   Perform multi-step reasoning to answer complex queries (e.g., comparing players, finding specific game matchups).
-   Handle context and dependencies (e.g., finding a player's team before fetching team stats).

## Available Tools (for Agent)

The agent utilizes the following tools (defined in `backend/tools.py`):

-   `get_player_info`
-   `get_player_gamelog`
-   `get_team_info_and_roster`
-   `get_player_career_stats`
-   `find_games`
-   `get_player_awards`
-   `get_boxscore_traditional`
-   `get_league_standings`
-   `get_scoreboard`
-   `get_playbyplay`
-   `get_draft_history`
-   `get_league_leaders`
-   `get_boxscore_advanced`
-   `get_boxscore_fourfactors`
-   `get_team_passing_stats`
-   `get_player_passing_stats`
-   `get_player_clutch_stats`
-   `get_player_rebounding_stats`
-   `get_player_shots_tracking`

## Setup

1.  **Clone the repository.**
2.  **Backend Setup:**
    -   Navigate to the `backend` directory:
        ```bash
        cd backend
        ```
    -   Create a virtual environment (optional but recommended):
        ```bash
        python -m venv .venv
        source .venv/bin/activate # Linux/macOS
        # or .venv\Scripts\activate # Windows
        ```
    -   Install dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    -   Create a `.env` file in the `backend` directory and add your Google API key:
        ```env
        GOOGLE_API_KEY=YOUR_API_KEY_HERE
        # Add other keys if needed
        ```
3.  **Frontend Setup:**
    -   Navigate to the `nba-analytics-frontend` directory:
        ```bash
        cd ../nba-analytics-frontend
        ```
    -   Install dependencies:
        ```bash
        npm install
        ```

## Running the Application

1.  **Start the Backend (FastAPI):**
    -   From the `backend` directory:
        ```bash
        uvicorn main:app --reload
        ```
2.  **Start the Frontend (Next.js):**
    -   From the `nba-analytics-frontend` directory:
        ```bash
        npm run dev
        ```
    -   Open your browser to `http://localhost:3000`.

## Testing

The project includes comprehensive test coverage for the backend tools and agent logic.

### Running Unit/Integration Tests (Pytest)

These tests verify the data fetching logic and utility functions.

1.  Navigate to the `backend` directory:
    ```bash
    cd backend
    ```
2.  Run all tests:
    ```bash
    pytest -v
    ```
    *(Ensure your virtual environment is active if you created one)*

### Running Agent Tests

These tests run predefined prompts against the configured Agno agent to check its reasoning and tool usage.

1.  Navigate to the **project root** directory (the one containing `backend` and `nba-analytics-frontend`).
2.  Run the agent test script as a module:
    ```bash
    python -m backend.tests.test_agent
    ```
    *(This command structure is necessary due to Python's module import system)*

The script will output the agent's thought process, tool calls, and final responses for each test prompt, followed by a summary.