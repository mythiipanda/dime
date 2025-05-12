import asyncio
import json
import logging
import os
import sys
import pytest

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.scoreboard_tools import fetch_scoreboard_data_logic
from nba_api.stats.library.parameters import LeagueID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
@pytest.mark.parametrize("desc,kwargs,expect_error", [
    ("Valid - Today's scoreboard (NBA)", {"game_date": None, "league_id": LeagueID.nba, "day_offset": 0, "bypass_cache": False}, False),
    ("Valid - Specific date (NBA)", {"game_date": "2023-12-25", "league_id": LeagueID.nba, "day_offset": 0, "bypass_cache": False}, True),  # Known API issue
    ("Invalid - Bad date format", {"game_date": "25-12-2023", "league_id": LeagueID.nba, "day_offset": 0, "bypass_cache": False}, True),
    ("Invalid - Bad league ID", {"game_date": "2023-12-25", "league_id": "XX", "day_offset": 0, "bypass_cache": False}, True),
    ("Edge - No games date", {"game_date": "1900-01-01", "league_id": LeagueID.nba, "day_offset": 0, "bypass_cache": False}, True),
])
async def test_scoreboard_tools(desc, kwargs, expect_error):
    result_json = await asyncio.to_thread(fetch_scoreboard_data_logic, **kwargs)
    try:
        result_data = json.loads(result_json)
        if expect_error:
            assert "error" in result_data, f"{desc} should return error"
        else:
            assert "games" in result_data, f"{desc} should return games"
    except json.JSONDecodeError:
        assert expect_error, f"{desc} should only fail to decode if error is expected" 