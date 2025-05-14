"""
Smoke test for the advanced shot charts functionality.
"""

import os
import sys
import logging
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for testing

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now that project_root is in sys.path, use absolute imports from backend
from backend.api_tools.advanced_shot_charts import process_shot_data_for_visualization
from backend.config import settings

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

    assert "error" not in result, f"Error processing shot data for scatter chart: {result.get('error')}"
    assert "file_path" in result, "No file path returned for scatter chart"
    logger.info(f"Scatter chart created at: {result['file_path']}")

    # Test heatmap chart
    logger.info("Testing heatmap chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="heatmap",
        output_format="file"
    )

    assert "error" not in result, f"Error processing shot data for heatmap chart: {result.get('error')}"
    assert "file_path" in result, "No file path returned for heatmap chart"
    logger.info(f"Heatmap chart created at: {result['file_path']}")

    # Test hexbin chart
    logger.info("Testing hexbin chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="hexbin",
        output_format="file"
    )

    assert "error" not in result, f"Error processing shot data for hexbin chart: {result.get('error')}"
    assert "file_path" in result, "No file path returned for hexbin chart"
    logger.info(f"Hexbin chart created at: {result['file_path']}")

    # Test animated chart
    logger.info("Testing animated chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="animated",
        output_format="file"
    )

    assert "error" not in result, f"Error processing shot data for animated chart: {result.get('error')}"
    assert "file_path" in result, "No file path returned for animated chart"
    logger.info(f"Animated chart created at: {result['file_path']}")

    # Test frequency chart
    logger.info("Testing frequency chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="frequency",
        output_format="file"
    )

    assert "error" not in result, f"Error processing shot data for frequency chart: {result.get('error')}"
    assert "file_path" in result, "No file path returned for frequency chart"
    logger.info(f"Frequency chart created at: {result['file_path']}")

    # Test distance chart
    logger.info("Testing distance chart...")
    result = process_shot_data_for_visualization(
        player_name=player_name,
        season=season,
        chart_type="distance",
        output_format="file"
    )

    assert "error" not in result, f"Error processing shot data for distance chart: {result.get('error')}"
    assert "file_path" in result, "No file path returned for distance chart"
    logger.info(f"Distance chart created at: {result['file_path']}")

    logger.info("process_shot_data tests passed!")

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

    assert "error" not in result, f"Error processing shot data for base64 scatter chart: {result.get('error')}"
    assert "image_data" in result, "No image data returned for base64 scatter chart"
    assert result["image_data"].startswith("data:image/png;base64,"), f"Invalid image data format for base64 scatter chart. Got: {result['image_data'][:100]}..." # Log part of the data if it fails
    logger.info("Base64 output test passed!")
