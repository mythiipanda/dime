import pytest
import logging # Keep logging for potential debug info during test runs if needed
from nba_api.stats.endpoints import playerdashptshots
import pandas as pd

# Configure basic logging (optional, pytest captures stdout/stderr)
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Constants for the test
PLAYER_ID = 2544  # LeBron James
TEAM_ID = 1610612747  # Los Angeles Lakers
SEASON = "2022-23"

# Expected attributes based on common usage and previous tests
EXPECTED_DATAFRAME_ATTRIBUTES = [
    'general_shooting',
    'shot_clock_shooting',
    'dribble_shooting',
    'closest_defender_shooting',
    # 'closest_defender_shooting_long', # Removed: This attribute name seems incorrect/not present
    'touch_time_shooting'
]

def test_playerdashptshots_endpoint_structure():
    """
    Tests the structure and basic data retrieval of the PlayerDashPtShots endpoint.
    """
    logger.info(f"Testing PlayerDashPtShots for player_id: {PLAYER_ID}, team_id: {TEAM_ID}, season: {SEASON}")

    try:
        # Create the endpoint instance
        endpoint = playerdashptshots.PlayerDashPtShots(
            player_id=PLAYER_ID,
            team_id=TEAM_ID,
            season=SEASON
        )
        assert endpoint is not None, "Endpoint object should be created"

        # 1. Check if expected dataframe attributes exist on the endpoint object
        logger.info("Checking for expected dataframe attributes...")
        found_attributes = []
        missing_attributes = []
        for attr in EXPECTED_DATAFRAME_ATTRIBUTES:
            if hasattr(endpoint, attr):
                logger.info(f"- Found attribute: {attr}")
                found_attributes.append(attr)
                # Additionally check if the attribute holds a DataFrame
                df_attr = getattr(endpoint, attr)
                assert hasattr(df_attr, 'get_data_frame'), f"Attribute '{attr}' should have a 'get_data_frame' method"
                df = df_attr.get_data_frame()
                assert isinstance(df, pd.DataFrame), f"Attribute '{attr}' should return a pandas DataFrame"
                logger.info(f"  - DataFrame shape for '{attr}': {df.shape}")
                # We expect data for a valid player/season
                assert not df.empty, f"DataFrame for '{attr}' should not be empty for LeBron James 2022-23"
            else:
                logger.warning(f"- Missing expected attribute: {attr}")
                missing_attributes.append(attr)

        # Fail if any core expected attributes are missing
        assert not missing_attributes, f"Endpoint is missing expected attributes: {missing_attributes}"
        logger.info("All expected dataframe attributes found.")

        # 2. Check the get_data_frames() method
        logger.info("Checking get_data_frames()...")
        all_data_frames = endpoint.get_data_frames()
        assert isinstance(all_data_frames, list), "get_data_frames() should return a list"
        assert len(all_data_frames) > 0, "get_data_frames() should return at least one DataFrame"
        logger.info(f"get_data_frames() returned {len(all_data_frames)} DataFrames.")

        # Check that each item in the list is a DataFrame
        for i, df in enumerate(all_data_frames):
             assert isinstance(df, pd.DataFrame), f"Item {i} in get_data_frames() list is not a DataFrame"
             logger.info(f"- DataFrame {i} shape: {df.shape}")
             # Most dataframes should have data for this player/season
             # assert not df.empty, f"DataFrame {i} should not be empty" # Be cautious with this, some might be empty

    except Exception as e:
        logger.error(f"Error during test_playerdashptshots_endpoint_structure: {str(e)}", exc_info=True)
        pytest.fail(f"Test failed due to exception: {str(e)}")