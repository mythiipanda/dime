import pytest
import json
from ..api_tools.search import (
    search_players_logic,
    search_teams_logic,
    search_games_logic
)

# Test data
VALID_PLAYER_QUERY = "LeBron"
VALID_TEAM_QUERY = "Lakers"
VALID_GAME_QUERY = "Lakers vs Celtics"
INVALID_QUERY = "xyzabc123notfound"
TEST_SEASON = "2022-23"

def test_search_players():
    """Test searching for players with valid query."""
    result = search_players_logic(VALID_PLAYER_QUERY)
    data = json.loads(result)
    
    assert "error" not in data
    assert "players" in data
    assert isinstance(data["players"], list)
    assert len(data["players"]) > 0
    
    # Verify player structure
    first_player = data["players"][0]
    required_fields = ["player_id", "player_name", "team_id", "team_name"]
    for field in required_fields:
        assert field in first_player
    
    # Verify search relevance
    assert any(VALID_PLAYER_QUERY.lower() in player["player_name"].lower() 
              for player in data["players"])

def test_search_players_invalid_query():
    """Test searching for players with invalid query."""
    result = search_players_logic(INVALID_QUERY)
    data = json.loads(result)
    
    assert "players" in data
    assert len(data["players"]) == 0

def test_search_players_empty_query():
    """Test searching for players with empty query."""
    result = search_players_logic("")
    data = json.loads(result)
    
    assert "error" in data
    assert "query" in data["error"].lower()

def test_search_teams():
    """Test searching for teams with valid query."""
    result = search_teams_logic(VALID_TEAM_QUERY)
    data = json.loads(result)
    
    assert "error" not in data
    assert "teams" in data
    assert isinstance(data["teams"], list)
    assert len(data["teams"]) > 0
    
    # Verify team structure
    first_team = data["teams"][0]
    required_fields = ["team_id", "team_name", "abbreviation", "city"]
    for field in required_fields:
        assert field in first_team
    
    # Verify search relevance
    assert any(VALID_TEAM_QUERY.lower() in team["team_name"].lower() 
              for team in data["teams"])

def test_search_teams_invalid_query():
    """Test searching for teams with invalid query."""
    result = search_teams_logic(INVALID_QUERY)
    data = json.loads(result)
    
    assert "teams" in data
    assert len(data["teams"]) == 0

def test_search_teams_empty_query():
    """Test searching for teams with empty query."""
    result = search_teams_logic("")
    data = json.loads(result)
    
    assert "error" in data
    assert "query" in data["error"].lower()

def test_search_games():
    """Test searching for games with valid query."""
    result = search_games_logic(VALID_GAME_QUERY, TEST_SEASON)
    data = json.loads(result)
    
    assert "error" not in data
    assert "games" in data
    assert isinstance(data["games"], list)
    assert len(data["games"]) > 0
    
    # Verify game structure
    first_game = data["games"][0]
    required_fields = ["game_id", "game_date", "home_team", "away_team", "status"]
    for field in required_fields:
        assert field in first_game
    
    # Verify search relevance
    assert any(VALID_TEAM_QUERY.lower() in 
              (game["home_team"].lower() + game["away_team"].lower()) 
              for game in data["games"])

def test_search_games_invalid_query():
    """Test searching for games with invalid query."""
    result = search_games_logic(INVALID_QUERY, TEST_SEASON)
    data = json.loads(result)
    
    assert "games" in data
    assert len(data["games"]) == 0

def test_search_games_empty_query():
    """Test searching for games with empty query."""
    result = search_games_logic("", TEST_SEASON)
    data = json.loads(result)
    
    assert "error" in data
    assert "query" in data["error"].lower()

def test_search_games_invalid_season():
    """Test searching for games with invalid season."""
    result = search_games_logic(VALID_GAME_QUERY, "9999-00")
    data = json.loads(result)
    
    assert "games" in data
    assert len(data["games"]) == 0

@pytest.mark.parametrize("limit", [1, 5, 10])
def test_search_results_limit(limit):
    """Test search results respect the limit parameter."""
    # Test players
    result = search_players_logic(VALID_PLAYER_QUERY, limit=limit)
    data = json.loads(result)
    assert len(data["players"]) <= limit
    
    # Test teams
    result = search_teams_logic(VALID_TEAM_QUERY, limit=limit)
    data = json.loads(result)
    assert len(data["teams"]) <= limit
    
    # Test games
    result = search_games_logic(VALID_GAME_QUERY, TEST_SEASON, limit=limit)
    data = json.loads(result)
    assert len(data["games"]) <= limit 