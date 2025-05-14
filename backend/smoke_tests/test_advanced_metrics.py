"""
Smoke test for the advanced metrics API.
"""

import json
import os
import sys
import logging

# Add the project root directory to sys.path to allow for absolute backend imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.advanced_metrics import fetch_player_advanced_analysis_logic

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_advanced_metrics():
    """Test the advanced metrics API with a known player."""
    player_name = "LeBron James"

    logger.info(f"Testing advanced metrics for {player_name}...")

    # Call the API
    result_json = fetch_player_advanced_analysis_logic(player_name)

    # Parse the result
    result = json.loads(result_json)

    # Check for errors and basic structure
    assert 'error' not in result, f"API returned an error: {result.get('error')}"
    
    logger.info(f"Player: {result.get('player_name')} (ID: {result.get('player_id')})")

    assert 'player_name' in result, "Response missing 'player_name'"
    assert 'player_id' in result, "Response missing 'player_id'"
    assert 'advanced_metrics' in result, "Response missing 'advanced_metrics'"
    assert isinstance(result['advanced_metrics'], dict), "'advanced_metrics' should be a dictionary"
    assert 'skill_grades' in result, "Response missing 'skill_grades'"
    assert isinstance(result['skill_grades'], dict), "'skill_grades' should be a dictionary"
    assert 'similar_players' in result, "Response missing 'similar_players'"
    assert isinstance(result['similar_players'], list), "'similar_players' should be a list"

    # Log advanced metrics
    logger.info("\nAdvanced Metrics:")
    for metric, value in result.get('advanced_metrics', {}).items():
        logger.info(f"{metric}: {value}")

    # Log skill grades
    logger.info("\nSkill Grades:")
    for skill, grade in result.get('skill_grades', {}).items():
        logger.info(f"{skill}: {grade}")

    # Log similar players
    logger.info("\nSimilar Players:")
    for player_data in result.get('similar_players', []):
        logger.info(f"{player_data.get('player_name')} (ID: {player_data.get('player_id')}): {player_data.get('similarity_score', 0) * 100:.1f}% similarity")

    logger.info(f"Advanced metrics test for {player_name} passed.")
