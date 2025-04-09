import sys
import os
import pytest
from requests.exceptions import Timeout

# Add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_tools.team_tools import _find_team_id
from api_tools.team_tracking import fetch_team_passing_stats_logic

@pytest.mark.parametrize("season_type", ["Regular Season", "Playoffs"])
def test_team_passing_stats(season_type):
    """Test the team passing stats function with different season types."""
    # Test setup
    team_id = _find_team_id('LAL')
    assert team_id is not None, "Team ID not found for LAL"
    
    try:
        result = fetch_team_passing_stats_logic(team_id, '2022-23', season_type)
        
        # Basic response validation
        assert result is not None, "Result should not be None"
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # Check for required data structures
        assert "PassesMade" in result or "PassesReceived" in result, "Missing required passing stats data"
        
        if "PassesMade" in result:
            passes = result["PassesMade"]
            assert isinstance(passes, list), "PassesMade should be a list"
            if passes:  # If we have data
                first_pass = passes[0]
                assert "TEAM_ID" in first_pass, "TEAM_ID missing from passes data"
                assert "PASS_TYPE" in first_pass, "PASS_TYPE missing from passes data"
                
        if "PassesReceived" in result:
            receives = result["PassesReceived"]
            assert isinstance(receives, list), "PassesReceived should be a list"
            if receives:  # If we have data
                first_receive = receives[0]
                assert "TEAM_ID" in first_receive, "TEAM_ID missing from receives data"
                assert "PASS_TYPE" in first_receive, "PASS_TYPE missing from receives data"
                
    except Timeout:
        pytest.skip("NBA API timeout - skipping test")
    except Exception as e:
        pytest.fail(f"Unexpected error: {str(e)}") 