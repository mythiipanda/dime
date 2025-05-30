from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from typing import List
# Assuming your project structure allows this import path
from backend.api_tools.game_boxscore_matchups import fetch_game_boxscore_matchups_logic as fetch_game_boxscore_matchups_data
from backend.api_tools.scoreboard_tools import fetch_scoreboard_data_logic as fetch_scoreboard_data
from backend.api_tools.win_probability_pbp import (
    fetch_win_probability_pbp_logic,
    _VALID_RUN_TYPES
)
class GameBoxscoreMatchupsInput(BaseModel):
    """Input schema for the NBA Game Boxscore Matchups tool."""
    game_id: str = Field(
        description="The ID of the game to fetch matchup data for (e.g., '0022300001')."
    )

@tool("get_nba_game_boxscore_matchups", args_schema=GameBoxscoreMatchupsInput)
def get_nba_game_boxscore_matchups(game_id: str) -> str:
    """Fetches player matchup data for a given NBA game, including time matched up, points scored, field goal percentages, assists, turnovers, and blocks in the matchup. Requires a game ID."""
    json_response = fetch_game_boxscore_matchups_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic as fetch_boxscore_traditional_data,
    fetch_boxscore_advanced_logic as fetch_boxscore_advanced_data,
    fetch_boxscore_four_factors_logic as fetch_boxscore_four_factors_data,
    fetch_boxscore_usage_logic as fetch_boxscore_usage_data,
    fetch_boxscore_defensive_logic as fetch_boxscore_defensive_data,
    fetch_boxscore_summary_logic as fetch_boxscore_summary_data,
    fetch_boxscore_misc_logic as fetch_boxscore_misc_data,
    fetch_boxscore_playertrack_logic as fetch_boxscore_playertrack_data,
    fetch_boxscore_scoring_logic as fetch_boxscore_scoring_data,
    fetch_boxscore_hustle_logic as fetch_boxscore_hustle_data
)

class BoxscoreTraditionalInput(BaseModel):
    """Input schema for the NBA Traditional Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")
    start_period: Optional[int] = Field(default=0, description="Starting period number (0 for full game).")
    end_period: Optional[int] = Field(default=0, description="Ending period number (0 for full game).")
    start_range: Optional[int] = Field(default=0, description="Starting range in seconds.")
    end_range: Optional[int] = Field(default=0, description="Ending range in seconds.")
    range_type: Optional[int] = Field(default=0, description="Type of range (0 for full game).")

@tool("get_nba_boxscore_traditional", args_schema=BoxscoreTraditionalInput)
def get_nba_boxscore_traditional(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    start_range: int = 0,
    end_range: int = 0,
    range_type: int = 0
) -> str:
    """Fetches traditional box score data for a given NBA game, including player and team statistics like points, rebounds, assists, etc. Allows filtering by period and time range."""
    json_response = fetch_boxscore_traditional_data(
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        start_range=start_range,
        end_range=end_range,
        range_type=range_type,
        return_dataframe=False
    )
    return json_response

class BoxscoreAdvancedInput(BaseModel):
    """Input schema for the NBA Advanced Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")
    start_period: Optional[int] = Field(default=0, description="Starting period number (0 for full game).")
    end_period: Optional[int] = Field(default=0, description="Ending period number (0 for full game).")
    start_range: Optional[int] = Field(default=0, description="Starting range in seconds.")
    end_range: Optional[int] = Field(default=0, description="Ending range in seconds.")

@tool("get_nba_boxscore_advanced", args_schema=BoxscoreAdvancedInput)
def get_nba_boxscore_advanced(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    start_range: int = 0,
    end_range: int = 0
) -> str:
    """Fetches advanced box score data for a given NBA game, including player and team advanced statistics like true shooting percentage, effective field goal percentage, etc. Allows filtering by period and time range."""
    json_response = fetch_boxscore_advanced_data(
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        start_range=start_range,
        end_range=end_range,
        return_dataframe=False
    )
    return json_response

class BoxscoreFourFactorsInput(BaseModel):
    """Input schema for the NBA Four Factors Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")
    start_period: Optional[int] = Field(default=0, description="Starting period number (0 for full game).")
    end_period: Optional[int] = Field(default=0, description="Ending period number (0 for full game).")

@tool("get_nba_boxscore_four_factors", args_schema=BoxscoreFourFactorsInput)
def get_nba_boxscore_four_factors(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0
) -> str:
    """Fetches Four Factors box score data for a given NBA game, including effective field goal percentage, turnover percentage, offensive rebound percentage, and free throw rate. Allows filtering by period."""
    json_response = fetch_boxscore_four_factors_data(
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        return_dataframe=False
    )
    return json_response

class BoxscoreUsageInput(BaseModel):
    """Input schema for the NBA Usage Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")

@tool("get_nba_boxscore_usage", args_schema=BoxscoreUsageInput)
def get_nba_boxscore_usage(game_id: str) -> str:
    """Fetches usage box score data for a given NBA game, including player and team usage percentages. Requires a game ID."""
    json_response = fetch_boxscore_usage_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

class BoxscoreDefensiveInput(BaseModel):
    """Input schema for the NBA Defensive Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")

@tool("get_nba_boxscore_defensive", args_schema=BoxscoreDefensiveInput)
def get_nba_boxscore_defensive(game_id: str) -> str:
    """Fetches defensive box score data for a given NBA game, including player and team defensive statistics. Requires a game ID."""
    json_response = fetch_boxscore_defensive_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

class BoxscoreSummaryInput(BaseModel):
    """Input schema for the NBA Summary Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")

@tool("get_nba_boxscore_summary", args_schema=BoxscoreSummaryInput)
def get_nba_boxscore_summary(game_id: str) -> str:
    """Fetches a comprehensive summary box score for a given NBA game, including game info, line score, officials, and season series. Requires a game ID."""
    json_response = fetch_boxscore_summary_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

class BoxscoreMiscInput(BaseModel):
    """Input schema for the NBA Miscellaneous Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")
    start_period: Optional[int] = Field(default=0, description="Starting period number (0 for full game).")
    end_period: Optional[int] = Field(default=0, description="Ending period number (0 for full game).")
    start_range: Optional[int] = Field(default=0, description="Starting range in seconds.")
    end_range: Optional[int] = Field(default=0, description="Ending range in seconds.")
    range_type: Optional[int] = Field(default=0, description="Type of range (0 for full game).")

@tool("get_nba_boxscore_misc", args_schema=BoxscoreMiscInput)
def get_nba_boxscore_misc(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    start_range: int = 0,
    end_range: int = 0,
    range_type: int = 0
) -> str:
    """Fetches miscellaneous box score data for a given NBA game, including player and team miscellaneous statistics. Allows filtering by period and time range."""
    json_response = fetch_boxscore_misc_data(
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        start_range=start_range,
        end_range=end_range,
        range_type=range_type,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.game_playbyplay import fetch_playbyplay_logic as fetch_playbyplay_data

class PlayByPlayInput(BaseModel):
    """Input schema for the NBA Play-by-Play tool."""
    game_id: str = Field(description="The ID of the game to fetch play-by-play data for (e.g., '0022300001').")
    start_period: Optional[int] = Field(default=0, description="The starting period filter (0 for no filter).")
    end_period: Optional[int] = Field(default=0, description="The ending period filter (0 for no filter).")
    event_types: Optional[List[str]] = Field(
        default=None,
        description="List of event types to filter by (e.g., ['SHOT', 'REBOUND', 'TURNOVER']). Common types: 'SHOT', 'REBOUND', 'TURNOVER', 'FOUL', 'FREE_THROW', 'SUBSTITUTION', 'TIMEOUT', 'JUMP_BALL', 'BLOCK', 'STEAL', 'VIOLATION'."
    )
    player_name: Optional[str] = Field(default=None, description="Player name to filter plays by (partial matches allowed).")
    person_id: Optional[int] = Field(default=None, description="Player ID to filter plays by.")
    team_id: Optional[int] = Field(default=None, description="Team ID to filter plays by.")
    team_tricode: Optional[str] = Field(default=None, description="Team tricode to filter plays by (e.g., 'LAL', 'BOS').")

@tool("get_nba_play_by_play", args_schema=PlayByPlayInput)
def get_nba_play_by_play(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    event_types: Optional[List[str]] = None,
    player_name: Optional[str] = None,
    person_id: Optional[int] = None,
    team_id: Optional[int] = None,
    team_tricode: Optional[str] = None
) -> str:
    """Fetches play-by-play data for an NBA game. Attempts live data first if no period filters are applied, otherwise uses historical data. Provides granular filtering by period, event type, player, and team."""
    json_response = fetch_playbyplay_data(
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        event_types=event_types,
        player_name=player_name,
        person_id=person_id,
        team_id=team_id,
        team_tricode=team_tricode,
        return_dataframe=False
    )
    return json_response

class WinProbabilityPBPInput(BaseModel):
    """Input schema for the Win Probability Play-by-Play tool."""
    game_id: str = Field(
        ...,
        description="The NBA game ID (e.g., '0022300061')."
    )
    run_type: str = Field(
        "default",
        description=f"Type of run data to fetch. Options: {', '.join(_VALID_RUN_TYPES)}."
    )

@tool("get_win_probability_pbp", args_schema=WinProbabilityPBPInput)
def get_win_probability_pbp(game_id: str, run_type: str = "default") -> str:
    """
    Fetches detailed win probability calculations throughout a game's timeline. This tool provides:
    - Win probability at each moment
    - Play-by-play progression
    - Momentum shift tracking
    - Game situation analysis
    
    Data includes:
    - Time-based probability changes
    - Score impact on win chances
    - Key play identification
    - Game flow metrics
    
    Available run types:
    - default: Standard time intervals
    - each second: Second-by-second analysis
    - each poss: Possession-based probability
    
    Useful for:
    - Analyzing game dynamics
    - Understanding momentum shifts
    - Identifying crucial moments
    - Evaluating decision impact
    - Studying close game situations
    """
    
    json_response = fetch_win_probability_pbp_logic(
        game_id=game_id,
        run_type=run_type,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.game_rotation import get_game_rotation as fetch_game_rotation_data

class GameRotationInput(BaseModel):
    """Input schema for the NBA Game Rotation tool."""
    game_id: str = Field(description="The ID of the game to fetch rotation data for (e.g., '0022400001').")
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )

@tool("get_nba_game_rotation", args_schema=GameRotationInput)
def get_nba_game_rotation(
    game_id: str,
    league_id: str = "00"
) -> str:
    """Fetches NBA game rotation data, including player in/out times, points scored during their time on court, and usage percentage. Allows filtering by game ID and league."""
    json_response = fetch_game_rotation_data(
        game_id=game_id,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.hustle_stats_boxscore import get_hustle_stats_boxscore as fetch_hustle_stats_boxscore_data

class HustleStatsBoxscoreInput(BaseModel):
    """Input schema for the NBA Hustle Stats Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch hustle stats for (e.g., '0022400001').")

@tool("get_nba_hustle_stats_boxscore", args_schema=HustleStatsBoxscoreInput)
def get_nba_hustle_stats_boxscore(game_id: str) -> str:
    """Fetches NBA hustle stats box score data, including game status, individual player hustle statistics, and team hustle totals. Requires a game ID."""
    json_response = fetch_hustle_stats_boxscore_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.infographic_fanduel_player import get_infographic_fanduel_player as fetch_infographic_fanduel_player_data

class InfographicFanDuelPlayerInput(BaseModel):
    """Input schema for the NBA FanDuel Player Infographic tool."""
    game_id: str = Field(description="The ID of the game to fetch FanDuel player infographic data for (e.g., '0022400001').")

@tool("get_nba_fanduel_player_infographic", args_schema=InfographicFanDuelPlayerInput)
def get_nba_fanduel_player_infographic(game_id: str) -> str:
    """Fetches FanDuel player infographic data, including player info, fantasy scoring, and traditional stats. Requires a game ID."""
    json_response = fetch_infographic_fanduel_player_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.game_finder import fetch_league_games_logic as fetch_league_games_data

class LeagueGameFinderInput(BaseModel):
    """Input schema for the NBA League Game Finder tool."""
    player_or_team_abbreviation: Optional[str] = Field(
        default="T",
        description="Specify 'P' for player games or 'T' for team games (default: 'T')."
    )
    player_id_nullable: Optional[int] = Field(
        default=None,
        description="NBA API player ID to filter games by."
    )
    team_id_nullable: Optional[int] = Field(
        default=None,
        description="NBA API team ID to filter games by."
    )
    season_nullable: Optional[str] = Field(
        default=None,
        description="Season in 'YYYY-YY' format (e.g., '2023-24')."
    )
    season_type_nullable: Optional[str] = Field(
        default=None,
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date in 'YYYY-MM-DD' format (e.g., '2023-10-24')."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date in 'YYYY-MM-DD' format (e.g., '2024-04-14')."
    )

@tool("get_nba_league_games", args_schema=LeagueGameFinderInput)
def get_nba_league_games(
    player_or_team_abbreviation: str = "T",
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = "00",
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """Fetches NBA league games with various filters. Allows filtering by player or team, player ID, team ID, season, season type, league, and date range. Note: Date filtering is applied post-API call due to API instability."""
    json_response = fetch_league_games_data(
        player_or_team_abbreviation=player_or_team_abbreviation,
        player_id_nullable=player_id_nullable,
        team_id_nullable=team_id_nullable,
        season_nullable=season_nullable,
        season_type_nullable=season_type_nullable,
        league_id_nullable=league_id_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=False
    )
    return json_response

class BoxscorePlayerTrackInput(BaseModel):
    """Input schema for the NBA Player Tracking Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")

@tool("get_nba_boxscore_player_track", args_schema=BoxscorePlayerTrackInput)
def get_nba_boxscore_player_track(game_id: str) -> str:
    """Fetches player tracking box score data for a given NBA game, including player and team tracking statistics. Requires a game ID."""
    json_response = fetch_boxscore_playertrack_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

class BoxscoreScoringInput(BaseModel):
    """Input schema for the NBA Scoring Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")
    start_period: Optional[int] = Field(default=0, description="Starting period number (0 for full game).")
    end_period: Optional[int] = Field(default=0, description="Ending period number (0 for full game).")
    start_range: Optional[int] = Field(default=0, description="Starting range in seconds.")
    end_range: Optional[int] = Field(default=0, description="Ending range in seconds.")
    range_type: Optional[int] = Field(default=0, description="Type of range (0 for full game).")

@tool("get_nba_boxscore_scoring", args_schema=BoxscoreScoringInput)
def get_nba_boxscore_scoring(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    start_range: int = 0,
    end_range: int = 0,
    range_type: int = 0
) -> str:
    """Fetches scoring box score data for a given NBA game, including player and team scoring statistics. Allows filtering by period and time range."""
    json_response = fetch_boxscore_scoring_data(
        game_id=game_id,
        start_period=start_period,
        end_period=end_period,
        start_range=start_range,
        end_range=end_range,
        range_type=range_type,
        return_dataframe=False
    )
    return json_response

class BoxscoreHustleInput(BaseModel):
    """Input schema for the NBA Hustle Box Score tool."""
    game_id: str = Field(description="The ID of the game to fetch data for (e.g., '0022300001').")

@tool("get_nba_boxscore_hustle", args_schema=BoxscoreHustleInput)
def get_nba_boxscore_hustle(game_id: str) -> str:
    """Fetches hustle box score data for a given NBA game, including player and team hustle statistics. Requires a game ID."""
    json_response = fetch_boxscore_hustle_data(
        game_id=game_id,
        return_dataframe=False
    )
    return json_response

class ScoreboardDataInput(BaseModel):
    """Input schema for the NBA Scoreboard Data tool."""
    game_date: Optional[str] = Field(
        default=None,
        description="The date for the scoreboard in YYYY-MM-DD format. Defaults to the current local date if None."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="The league ID (e.g., '00' for NBA). Defaults to '00' (NBA)."
    )
    day_offset: Optional[int] = Field(
        default=0,
        description="Day offset from game_date if game_date is also provided. Defaults to 0."
    )

@tool("get_nba_scoreboard_data", args_schema=ScoreboardDataInput)
def get_nba_scoreboard_data(
    game_date: Optional[str] = None,
    league_id: str = "00",
    day_offset: int = 0
) -> str:
    """Fetches NBA scoreboard data for a specific date, including game status, scores, and team information. Uses live data for the current date and static data for past/future dates. Allows filtering by date, league, and day offset."""
    
    json_response = fetch_scoreboard_data(
        game_date=game_date,
        league_id=league_id,
        day_offset=day_offset,
        return_dataframe=False
    )
    return json_response