"""
Smoke test for the advanced shot charts functionality.
"""

import os
import sys
import logging
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for testing

# Add the parent directory to the path so we can import from the backend package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import directly from the module
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from api_tools.advanced_shot_charts import process_shot_data_for_visualization
from config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_process_shot_data():
    """Test the process_shot_data_for_visualization function."""
    logger.info("Testing process_shot_data_for_visualization...")

    # Test with a known player
    player_name = "LeBron James"
    season = settings.CURRENT_NBA_SEASON

    # Test scatter chart
    logger.info("Testing scatter chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="scatter",
        output_format="file"
    )

    if "error" in result:
        logger.error(f"Error processing shot data: {result['error']}")
        return False

    if "file_path" not in result:
        logger.error("No file path returned")
        return False

    logger.info(f"Scatter chart created at: {result['file_path']}")

    # Test heatmap chart
    logger.info("Testing heatmap chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="heatmap",
        output_format="file"
    )

    if "error" in result:
        logger.error(f"Error processing shot data: {result['error']}")
        return False

    if "file_path" not in result:
        logger.error("No file path returned")
        return False

    logger.info(f"Heatmap chart created at: {result['file_path']}")

    # Test hexbin chart
    logger.info("Testing hexbin chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="hexbin",
        output_format="file"
    )

    if "error" in result:
        logger.error(f"Error processing shot data: {result['error']}")
        return False

    if "file_path" not in result:
        logger.error("No file path returned")
        return False

    logger.info(f"Hexbin chart created at: {result['file_path']}")

    # Test animated chart
    logger.info("Testing animated chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="animated",
        output_format="file"
    )

    if "error" in result:
        logger.error(f"Error processing shot data: {result['error']}")
        return False

    if "file_path" not in result:
        logger.error("No file path returned")
        return False

    logger.info(f"Animated chart created at: {result['file_path']}")

    # Test frequency chart
    logger.info("Testing frequency chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="frequency",
        output_format="file"
    )

    if "error" in result:
        logger.error(f"Error processing shot data: {result['error']}")
        return False

    if "file_path" not in result:
        logger.error("No file path returned")
        return False

    logger.info(f"Frequency chart created at: {result['file_path']}")

    # Test distance chart
    logger.info("Testing distance chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="distance",
        output_format="file"
    )

    if "error" in result:
        logger.error(f"Error processing shot data: {result['error']}")
        return False

    if "file_path" not in result:
        logger.error("No file path returned")
        return False

    logger.info(f"Distance chart created at: {result['file_path']}")

    logger.info("All tests passed!")
    return True

def test_base64_output():
    """Test the base64 output format."""
    logger.info("Testing base64 output format...")

    # Test with a known player
    player_name = "Stephen Curry"
    season = settings.CURRENT_NBA_SEASON

    # Test scatter chart with base64 output
    logger.info("Testing scatter chart with base64 output...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="scatter",
        output_format="base64"
    )

    if "error" in result:
        logger.error(f"Error processing shot data: {result['error']}")
        return False

    if "image_data" not in result:
        logger.error("No image data returned")
        return False

    if not result["image_data"].startswith("data:image/png;base64,"):
        logger.error("Invalid image data format")
        return False

    logger.info("Base64 output test passed!")
    return True

if __name__ == "__main__":
    success = test_process_shot_data() and test_base64_output()
    sys.exit(0 if success else 1)
