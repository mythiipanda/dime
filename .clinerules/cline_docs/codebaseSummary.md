## Overview
A full-stack AI-powered NBA analytics platform. The backend is built with Python (FastAPI) and uses the `nba_api` library for data retrieval, potentially augmented by a Gemini AI agent. The frontend is a Next.js application using TypeScript, Tailwind CSS, and shadcn/ui components. Communication between frontend and backend for AI interactions is handled via Server-Sent Events (SSE).

## Key Components

### Backend (`backend/`)
- **`main.py`**: FastAPI application entry point.
- **`config.py`**: Handles application configuration, likely including API keys and constants.
- **`api_tools/`**: Contains modules for interacting with the `nba_api` and processing data.
    - `player_tools.py`: Logic for fetching various player-specific data (info, gamelog, career stats, profile, shotchart, defense, hustle, awards).
    - `player_tracking.py`: Logic for fetching player tracking statistics (clutch, passing, rebounding, shots).
    - `game_tools.py`: Logic for fetching game-specific data (box scores, play-by-play, shot charts, win probability, league games).
    - `league_tools.py`: Logic for fetching league-wide data (standings, draft history, league leaders).
    - `live_game_tools.py`: Logic for fetching live game scoreboard data.
    - `matchup_tools.py`: Logic for fetching player vs. player matchup statistics.
    - `odds_tools.py`: Logic for fetching betting odds for games.
    - `search.py`: Logic for searching players, teams, and games.
    - `synergy_tools.py`: Logic for fetching Synergy play type statistics.
    - `team_tools.py`: Logic for fetching team information, roster, and general team statistics.
    - `team_tracking.py`: Logic for fetching specific team tracking statistics (passing, rebounding, shooting).
    - `trending_team_tools.py`: Logic for identifying top-performing teams.
    - `trending_tools.py`: Logic for identifying top-performing players.
    - `analyze.py`: Contains logic for more complex analysis, possibly involving AI.
    - `scoreboard/scoreboard_tools.py`: Contains logic for fetching scoreboard data (live and static).
- **`routes/`**: Defines the API endpoints for the FastAPI application.
    - `sse.py`: Handles Server-Sent Event streaming for AI agent responses.
    - Other route files correspond to different data categories (players, games, teams, league, search, etc.).
- **`smoke_tests/`**: Scripts to perform basic tests on the `api_tools` functions.

### Frontend (`nba-analytics-frontend/`)
- **`app/`**: Core Next.js App Router directory.
    - `(app)/ai-assistant/page.tsx`: Main page for the AI chat interface.
    - Other subdirectories like `games/`, `players/`, `teams/` for specific feature pages.
- **`components/`**: Reusable React components.
    - `agent/`: Components specific to the AI chat interface (e.g., `ChatMessageDisplay.tsx`, `PromptInputForm.tsx`).
    - `ui/`: shadcn/ui components.
    - `layout/`: Components for overall page structure (e.g., `SidebarNav.tsx`).
- **`lib/`**: Utility functions and custom hooks.
    - `hooks/useAgentChatSSE.ts`: Custom hook for managing SSE communication for the chat.

## Data Flow (Typical AI Query)
1. User interacts with the AI chat interface on the frontend.
2. Frontend (`useAgentChatSSE.ts`) sends the user's prompt to a backend SSE endpoint (e.g., `/ask` handled by `routes/sse.py`).
3. The backend AI agent (defined in `agents.py` or similar) processes the request.
4. The agent may use tools defined in `api_tools/` (which wrap `nba_api` calls) to fetch necessary data.
5. The agent streams responses (intermediate thoughts, progress, final answer) back to the frontend via SSE.
6. Frontend components update in real-time to display the agent's output.

## Implemented NBA Data Functions (Core Logic in `api_tools/`)

**Player Specific (`player_tools.py`):**
- `fetch_player_info_logic(player_name: str) -> str`
- `fetch_player_gamelog_logic(player_name: str, season: str, season_type: str) -> str`
- `fetch_player_career_stats_logic(player_name: str, per_mode: str) -> str`
- `fetch_player_profile_logic(player_name: str, per_mode: Optional[str]) -> str`
- `fetch_player_shotchart_logic(player_name: str, season: str, season_type: str) -> str`
- `fetch_player_defense_logic(player_name: str, season: str, season_type: str, per_mode: str, opponent_team_id: int, date_from: Optional[str], date_to: Optional[str]) -> str`
- `fetch_player_hustle_stats_logic(season: str, season_type: str, per_mode: str, player_name: Optional[str], team_id: Optional[int], league_id: str, date_from: Optional[str], date_to: Optional[str]) -> str`
- `fetch_player_awards_logic(player_name: str) -> str`
- `fetch_player_stats_logic(player_name: str, season: str, season_type: str) -> str` (Composite function)

**Player Tracking (`player_tracking.py`):**
- `fetch_player_clutch_stats_logic(player_name: str, season: str, season_type: str, measure_type: str, per_mode: str, plus_minus: str, pace_adjust: str, rank: str, clutch_time_nullable: Optional[str], ahead_behind_nullable: Optional[str], point_diff_nullable: Optional[int], game_scope_nullable: Optional[str], player_experience_nullable: Optional[str], player_position_nullable: Optional[str], starter_bench_nullable: Optional[str], outcome_nullable: Optional[str], location_nullable: Optional[str], month: int, season_segment_nullable: Optional[str], date_from_nullable: Optional[str], date_to_nullable: Optional[str], opponent_team_id: int, vs_conference_nullable: Optional[str], vs_division_nullable: Optional[str], game_segment_nullable: Optional[str], period: int, last_n_games: int) -> str`
- `fetch_player_passing_stats_logic(player_name: str, season: str, season_type: str, per_mode: str) -> str`
- `fetch_player_rebounding_stats_logic(player_name: str, season: str, season_type: str, per_mode: str) -> str`
- `fetch_player_shots_tracking_logic(player_name: str, season: str, season_type: str, opponent_team_id: int, date_from: Optional[str], date_to: Optional[str]) -> str`

**Game Specific (`game_tools.py`):**
- `fetch_boxscore_traditional_logic(game_id: str, start_period: int, end_period: int, start_range: int, end_range: int, range_type: int) -> str`
- `fetch_boxscore_advanced_logic(game_id: str, end_period: int, end_range: int, start_period: int, start_range: int) -> str`
- `fetch_boxscore_four_factors_logic(game_id: str, start_period: int, end_period: int) -> str`
- `fetch_boxscore_usage_logic(game_id: str) -> str`
- `fetch_boxscore_defensive_logic(game_id: str) -> str`
- `fetch_playbyplay_logic(game_id: str, start_period: int, end_period: int) -> str`
- `fetch_shotchart_logic(game_id: str) -> str` (Game-wide shot chart)
- `fetch_league_games_logic(player_or_team_abbreviation: str, player_id_nullable: Optional[int], team_id_nullable: Optional[int], season_nullable: Optional[str], season_type_nullable: Optional[str], league_id_nullable: Optional[str], date_from_nullable: Optional[str], date_to_nullable: Optional[str]) -> str`
- `fetch_win_probability_logic(game_id: str, run_type: str) -> str`

**League Specific (`league_tools.py`):**
- `fetch_league_standings_logic(season: Optional[str], season_type: str) -> str`
- `fetch_draft_history_logic(season_year_nullable: Optional[str], league_id_nullable: str, team_id_nullable: Optional[int], round_num_nullable: Optional[int], overall_pick_nullable: Optional[int]) -> str`
- `fetch_league_leaders_logic(season: str, stat_category: str, season_type: str, per_mode: str, league_id: str, scope: str, top_n: int) -> str`

**Live Game Data (`live_game_tools.py` / `scoreboard_tools.py`):**
- `fetch_league_scoreboard_logic(bypass_cache: bool) -> str` (from `live_game_tools.py`)
- `fetch_scoreboard_data_logic(game_date: Optional[str], league_id: str, day_offset: int, bypass_cache: bool) -> str` (from `scoreboard_tools.py`, handles live and static)

**Matchups (`matchup_tools.py`):**
- `fetch_league_season_matchups_logic(def_player_identifier: str, off_player_identifier: str, season: str, season_type: str, bypass_cache: bool) -> str`
- `fetch_matchups_rollup_logic(def_player_identifier: str, season: str, season_type: str, bypass_cache: bool) -> str`

**Odds (`odds_tools.py`):**
- `fetch_odds_data_logic(bypass_cache: bool) -> str`

**Search (`search.py`):**
- `find_players_by_name_fragment(name_fragment: str, limit: int) -> List[Dict[str, Any]]` (Used by player search route)
- `search_players_logic(query: str, limit: int) -> str` (For generic search endpoint)
- `search_teams_logic(query: str, limit: int) -> str` (For generic search endpoint)
- `search_games_logic(query: str, season: Optional[str], season_type: Optional[str], limit: int) -> str` (For generic search endpoint)

**Synergy (`synergy_tools.py`):**
- `fetch_synergy_play_types_logic(league_id: str, per_mode: str, player_or_team: str, season_type: str, season: str, play_type_nullable: Optional[str], type_grouping_nullable: Optional[str], bypass_cache: bool) -> str`

**Team Specific (`team_tools.py`):**
- `fetch_team_info_and_roster_logic(team_identifier: str, season: str, season_type: str, league_id: str) -> str`
- `fetch_team_stats_logic(team_identifier: str, season: str, season_type: str, per_mode: str, measure_type: str, opponent_team_id: int, date_from: Optional[str], date_to: Optional[str], league_id: str) -> str`
- `fetch_team_passing_stats_logic(team_identifier: str, season: str, season_type: str, per_mode: str) -> str` (Also present in `team_tracking.py`, this one is in `team_tools.py`)

**Team Tracking (`team_tracking.py`):**
- `fetch_team_passing_stats_logic(team_identifier: str, season: str, season_type: str, per_mode: str) -> str` (Duplicate name, but specific to tracking context)
- `fetch_team_rebounding_stats_logic(team_identifier: str, season: str, season_type: str, per_mode: str, opponent_team_id: int, date_from: Optional[str], date_to: Optional[str]) -> str`
- `fetch_team_shooting_stats_logic(team_identifier: str, season: str, season_type: str, per_mode: str, opponent_team_id: int, date_from: Optional[str], date_to: Optional[str]) -> str`

**Trending - Teams (`trending_team_tools.py`):**
- `fetch_top_teams_logic(season: str, season_type: str, league_id: str, top_n: int, bypass_cache: bool) -> str`

**Trending - Players (`trending_tools.py`):**
- `fetch_top_performers_logic(category: str, season: str, season_type: str, per_mode: str, scope: str, league_id: str, top_n: int, bypass_cache: bool) -> str`

**Analysis (`analyze.py`):**
- `analyze_player_stats_logic(player_name: str, season: str, season_type: str, per_mode: str, league_id: str) -> str`

## Recent Significant Changes
- [2025-05-10] Resolved `ImportError` and `TypeError` in `player_tracking.py` and `smoke_test_player_tools.py`.
- [2025-05-10] Corrected `per_mode` handling in `fetch_player_profile_logic` to use default when `None` is passed.
- [2025-05-10] Added robust dataset checking in `fetch_player_profile_logic` to handle potential API inconsistencies.
- [2025-05-10] Fixed `TypeError` in `backend/routes/standings.py` by not passing `league_id` to `fetch_league_standings_logic`.
- [2025-05-10] Corrected player search suggestion URL in frontend (`PlayerSearchBar.tsx`) from `/players/search` to `/player/search`.

## User Feedback Integration
- (To be documented as feedback is received and integrated)