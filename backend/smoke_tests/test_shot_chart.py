"""
Smoke test for the shot chart API.
"""

import json
import os
import sys
import logging

# Add the project root directory to sys.path to allow for absolute backend imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.shot_charts import fetch_player_shot_chart

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_shot_chart():
    """Test the shot chart API with a known player."""
    player_name = "LeBron James"

    logger.info(f"Testing shot chart for {player_name}...")

    # Call the API
    result_json = fetch_player_shot_chart(player_name)

    # Parse the result
    result = json.loads(result_json)

    # Check for errors and basic structure
    assert 'error' not in result, f"API returned an error: {result.get('error')}"
    
    expected_keys = ['player_name', 'player_id', 'team_name', 'team_id', 'season', 'season_type', 'shots', 'zones']
    for key in expected_keys:
        assert key in result, f"Response missing expected key: '{key}'"

    assert isinstance(result['shots'], list), "'shots' should be a list"
    assert isinstance(result['zones'], list), "'zones' should be a list"

    logger.info(f"Player: {result.get('player_name')} (ID: {result.get('player_id')})")
    logger.info(f"Team: {result.get('team_name')} (ID: {result.get('team_id')})")
    logger.info(f"Season: {result.get('season')}, Type: {result.get('season_type')}")
    
    if result['shots']:
        logger.info(f"Total shots: {len(result['shots'])}")
        made_shots = sum(1 for shot in result['shots'] if shot.get('made'))
        missed_shots = len(result['shots']) - made_shots
        logger.info(f"Made shots: {made_shots} ({made_shots / len(result['shots']) * 100:.1f}%)")
        logger.info(f"Missed shots: {missed_shots} ({missed_shots / len(result['shots']) * 100:.1f}%)")
    else:
        logger.info("No shots data found in the response.")

    logger.info("\nZone Analysis:")
    expected_zone_keys = ['zone', 'made', 'attempts', 'percentage', 'leaguePercentage', 'relativePercentage']
    for zone_data in result.get('zones', []):
        for key in expected_zone_keys:
            assert key in zone_data, f"Zone data missing expected key: '{key}' in zone {zone_data.get('zone')}"
        logger.info(f"{zone_data.get('zone')}: {zone_data.get('made')}/{zone_data.get('attempts')} ({zone_data.get('percentage', 0) * 100:.1f}%), " +
                      f"League: {zone_data.get('leaguePercentage', 0) * 100:.1f}%, " +
                      f"Diff: {zone_data.get('relativePercentage', 0) * 100:+.1f}%")
    
    logger.info(f"Shot chart test for {player_name} passed.")
