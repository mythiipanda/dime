import logging
from nba_api.stats.endpoints import playerdashptshots

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("__main__")

try:
    # Player ID for LeBron James: 2544
    player_id = 2544
    # Team ID for Los Angeles Lakers: 1610612747
    team_id = 1610612747
    season = "2022-23"
    
    logger.info(f"Fetching shot data for player_id: {player_id}, team_id: {team_id}, season: {season}")
    
    # Create the endpoint instance with the required parameters
    endpoint = playerdashptshots.PlayerDashPtShots(
        player_id=player_id,
        team_id=team_id,
        season=season
    )
    
    # Log the endpoint object's attributes
    logger.info("Endpoint attributes:")
    for attr in dir(endpoint):
        if not attr.startswith('_'):
            logger.info(f"- {attr}")
    
    # Get data frames
    data_frames = endpoint.get_data_frames()
    
    # Log the shapes and columns of data frames
    logger.info("Data frames retrieved:")
    for i, df in enumerate(data_frames):
        logger.info(f"DataFrame {i} shape: {df.shape}")
        logger.info(f"DataFrame {i} columns: {df.columns.tolist()}")
    
    # Check for specific attributes
    attributes_to_check = ['general_shooting', 'shot_type_detail', 'shot_type_summary']
    
    for attr in attributes_to_check:
        if hasattr(endpoint, attr):
            df = getattr(endpoint, attr)
            logger.info(f"Found attribute '{attr}' with shape: {df.shape}")
            logger.info(f"Columns for '{attr}': {df.columns.tolist()}")
        else:
            logger.info(f"Attribute '{attr}' not found")
    
except Exception as e:
    logger.error(f"Error: {str(e)}") 