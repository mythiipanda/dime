"""
Player comparison module for NBA player analysis.
Provides both JSON and DataFrame outputs with CSV caching.
"""

import logging
import os
import json
import base64
from io import BytesIO
from typing import Dict, List, Any, Optional, Union, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from nba_api.stats.endpoints import shotchartdetail
from ..config import settings
from .utils import find_player_id_or_error, format_response
from .advanced_shot_charts import draw_court
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
PLAYER_COMPARISON_CSV_DIR = get_cache_dir("player_comparison")

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_player_shots(
    player_id: str,
    season: str,
    season_type: str
) -> str:
    """
    Generates a file path for saving player shot data DataFrame as CSV.

    Args:
        player_id: The player's ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    return get_cache_file_path(
        f"player_{player_id}_shots_{season}_{clean_season_type}.csv",
        "player_comparison"
    )

def _get_csv_path_for_comparison(
    player_ids: List[str],
    season: str,
    season_type: str
) -> str:
    """
    Generates a file path for saving player comparison DataFrame as CSV.

    Args:
        player_ids: List of player IDs
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    # Convert player IDs to strings and join for filename
    player_ids_str = "_".join([str(player_id) for player_id in player_ids])

    return get_cache_file_path(
        f"comparison_{player_ids_str}_{season}_{clean_season_type}.csv",
        "player_comparison"
    )

def compare_player_shots(
    player_names: List[str],
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    output_format: str = "base64",
    chart_type: str = "scatter",
    context_measure: str = "FGA",
    league_id: str = "00",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    rookie_year_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    game_id_nullable: Optional[str] = None,
    ahead_behind_nullable: Optional[str] = None,
    clutch_time_nullable: Optional[str] = None,
    point_diff_nullable: Optional[str] = None,
    context_filter_nullable: Optional[str] = None,
    start_period_nullable: Optional[int] = None,
    end_period_nullable: Optional[int] = None,
    start_range_nullable: Optional[int] = None,
    end_range_nullable: Optional[int] = None,
    range_type_nullable: Optional[int] = None,
    position_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
    """
    Compare shot charts for multiple players.

    Args:
        player_names: List of player names to compare
        season: NBA season in format YYYY-YY
        season_type: Type of season (Regular Season, Playoffs, etc.)
        output_format: Output format (base64, file)
        chart_type: Type of chart to create (scatter, heatmap, zones)
        context_measure: Context measure for shot chart (FGA, FGM, FG_PCT, etc.)
        league_id: League ID (00 for NBA)
        last_n_games: Number of most recent games to include (0 for all)
        month: Filter by month (0 for all)
        opponent_team_id: Filter by opponent team ID (0 for all)
        period: Filter by period (0 for all)
        date_from_nullable: Start date filter (YYYY-MM-DD)
        date_to_nullable: End date filter (YYYY-MM-DD)
        game_segment_nullable: Filter by game segment (First Half, Second Half, Overtime)
        location_nullable: Filter by location (Home, Road)
        outcome_nullable: Filter by game outcome (W, L)
        player_position_nullable: Filter by player position (Guard, Forward, Center)
        rookie_year_nullable: Filter by rookie year
        season_segment_nullable: Filter by season segment (Pre All-Star, Post All-Star)
        vs_conference_nullable: Filter by opponent conference (East, West)
        vs_division_nullable: Filter by opponent division (Atlantic, Central, etc.)
        game_id_nullable: Filter by game ID
        ahead_behind_nullable: Filter by score situation (Ahead or Behind, Ahead or Tied, Behind or Tied)
        clutch_time_nullable: Filter by clutch time (Last 5 Minutes, Last 4 Minutes, etc.)
        point_diff_nullable: Filter by point differential
        context_filter_nullable: Additional context filter
        start_period_nullable: Start period filter
        end_period_nullable: End period filter
        start_range_nullable: Start range filter
        end_range_nullable: End range filter
        range_type_nullable: Range type filter
        position_nullable: Position filter
        return_dataframe: Whether to return DataFrames along with the visualization data

    Returns:
        If return_dataframe=False:
            Dict containing the visualization data and metadata
        If return_dataframe=True:
            Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]: A tuple containing the visualization data
                                                          and a dictionary of DataFrames
    """
    # Store DataFrames if requested
    dataframes = {}

    if len(player_names) < 2:
        error_response = {
            "error": "At least two players are required for comparison"
        }
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if len(player_names) > 4:
        error_response = {
            "error": "Maximum of 4 players can be compared at once"
        }
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        # Get player data
        player_data = []
        player_ids = []

        for player_name in player_names:
            # Get player ID
            player_id, player_actual_name = find_player_id_or_error(player_name)
            player_ids.append(player_id)

            # Fetch shot chart data
            shotchart_params = {
                'player_id': player_id,
                'team_id': 0,
                'season_nullable': season,
                'season_type_all_star': season_type,
                'timeout': settings.DEFAULT_TIMEOUT_SECONDS,
                'context_measure_simple': context_measure,
                'league_id': league_id,
                'last_n_games': last_n_games,
                'month': month,
                'opponent_team_id': opponent_team_id,
                'period': period
            }

            # Add nullable parameters if they are provided
            if date_from_nullable is not None:
                shotchart_params['date_from_nullable'] = date_from_nullable
            if date_to_nullable is not None:
                shotchart_params['date_to_nullable'] = date_to_nullable
            if game_segment_nullable is not None:
                shotchart_params['game_segment_nullable'] = game_segment_nullable
            if location_nullable is not None:
                shotchart_params['location_nullable'] = location_nullable
            if outcome_nullable is not None:
                shotchart_params['outcome_nullable'] = outcome_nullable
            if player_position_nullable is not None:
                shotchart_params['player_position_nullable'] = player_position_nullable
            if rookie_year_nullable is not None:
                shotchart_params['rookie_year_nullable'] = rookie_year_nullable
            if season_segment_nullable is not None:
                shotchart_params['season_segment_nullable'] = season_segment_nullable
            if vs_conference_nullable is not None:
                shotchart_params['vs_conference_nullable'] = vs_conference_nullable
            if vs_division_nullable is not None:
                shotchart_params['vs_division_nullable'] = vs_division_nullable
            if game_id_nullable is not None:
                shotchart_params['game_id_nullable'] = game_id_nullable
            if ahead_behind_nullable is not None:
                shotchart_params['ahead_behind_nullable'] = ahead_behind_nullable
            if clutch_time_nullable is not None:
                shotchart_params['clutch_time_nullable'] = clutch_time_nullable
            if point_diff_nullable is not None:
                shotchart_params['point_diff_nullable'] = point_diff_nullable
            if context_filter_nullable is not None:
                shotchart_params['context_filter_nullable'] = context_filter_nullable
            if start_period_nullable is not None:
                shotchart_params['start_period_nullable'] = start_period_nullable
            if end_period_nullable is not None:
                shotchart_params['end_period_nullable'] = end_period_nullable
            if start_range_nullable is not None:
                shotchart_params['start_range_nullable'] = start_range_nullable
            if end_range_nullable is not None:
                shotchart_params['end_range_nullable'] = end_range_nullable
            if range_type_nullable is not None:
                shotchart_params['range_type_nullable'] = range_type_nullable
            if position_nullable is not None:
                shotchart_params['position_nullable'] = position_nullable

            shotchart_endpoint = shotchartdetail.ShotChartDetail(**shotchart_params)

            shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
            league_avg_df = shotchart_endpoint.league_averages.get_data_frame()

            # Store DataFrames if requested
            if return_dataframe:
                dataframes[f"shots_{player_id}"] = shots_df
                dataframes[f"league_avg_{player_id}"] = league_avg_df

                # Save to CSV if not empty
                if not shots_df.empty:
                    csv_path = _get_csv_path_for_player_shots(
                        player_id=player_id,
                        season=season,
                        season_type=season_type
                    )
                    _save_dataframe_to_csv(shots_df, csv_path)

            if shots_df.empty:
                error_response = {
                    "error": f"No shot data found for {player_actual_name} in {season} {season_type}"
                }
                if return_dataframe:
                    return error_response, dataframes
                return error_response

            # Process shot data
            shot_locations = []
            for _, row in shots_df.iterrows():
                shot_locations.append({
                    "x": float(row['LOC_X']),
                    "y": float(row['LOC_Y']),
                    "made": bool(row['SHOT_MADE_FLAG']),
                    "shot_type": row['ACTION_TYPE'],
                    "zone": row['SHOT_ZONE_BASIC'],
                    "distance": float(row['SHOT_DISTANCE']),
                    "game_date": row['GAME_DATE'],
                    "period": int(row['PERIOD'])
                })

            # Calculate overall stats
            total_shots = len(shot_locations)
            made_shots = sum(1 for shot in shot_locations if shot["made"])
            field_goal_percentage = round((made_shots / total_shots) * 100, 1) if total_shots > 0 else 0

            # Calculate zone breakdown
            zone_breakdown = {}
            for zone in set(shot["zone"] for shot in shot_locations):
                zone_shots = [shot for shot in shot_locations if shot["zone"] == zone]
                zone_attempts = len(zone_shots)
                zone_made = sum(1 for shot in zone_shots if shot["made"])
                zone_percentage = round((zone_made / zone_attempts) * 100, 1) if zone_attempts > 0 else 0

                # Get league average for this zone
                league_zone_data = league_avg_df[league_avg_df['SHOT_ZONE_BASIC'] == zone]
                league_percentage = float(league_zone_data['FG_PCT'].iloc[0]) * 100 if not league_zone_data.empty else 0

                zone_breakdown[zone] = {
                    "attempts": zone_attempts,
                    "made": zone_made,
                    "percentage": zone_percentage,
                    "league_percentage": league_percentage,
                    "relative_percentage": round(zone_percentage - league_percentage, 1)
                }

            player_data.append({
                "player_name": player_actual_name,
                "player_id": player_id,
                "shot_locations": shot_locations,
                "overall_stats": {
                    "total_shots": total_shots,
                    "made_shots": made_shots,
                    "field_goal_percentage": field_goal_percentage
                },
                "zone_breakdown": zone_breakdown
            })

        # Create a combined DataFrame for all players if requested
        if return_dataframe and len(player_data) > 0:
            # Create a DataFrame with zone breakdown for all players
            zone_data = []
            for player in player_data:
                for zone, stats in player["zone_breakdown"].items():
                    zone_data.append({
                        "player_id": player["player_id"],
                        "player_name": player["player_name"],
                        "zone": zone,
                        "attempts": stats["attempts"],
                        "made": stats["made"],
                        "percentage": stats["percentage"],
                        "league_percentage": stats["league_percentage"],
                        "relative_percentage": stats["relative_percentage"]
                    })

            if zone_data:
                zone_df = pd.DataFrame(zone_data)
                dataframes["zone_breakdown"] = zone_df

                # Save to CSV
                csv_path = _get_csv_path_for_comparison(
                    player_ids=player_ids,
                    season=season,
                    season_type=season_type
                )
                _save_dataframe_to_csv(zone_df, csv_path)

        # Create visualization based on chart type
        result = None
        if chart_type == "scatter":
            result = create_comparison_scatter(player_data, season, season_type, output_format)
        elif chart_type == "heatmap":
            result = create_comparison_heatmap(player_data, season, season_type, output_format)
        elif chart_type == "zones":
            result = create_comparison_zones(player_data, season, season_type, output_format)
        else:
            error_response = {
                "error": f"Invalid chart type: {chart_type}. Valid types are: scatter, heatmap, zones"
            }
            if return_dataframe:
                return error_response, dataframes
            return error_response

        # Add DataFrame info to the result if requested
        if return_dataframe:
            # Add CSV paths to the result
            csv_paths = {}
            for player_id in player_ids:
                csv_path = _get_csv_path_for_player_shots(
                    player_id=player_id,
                    season=season,
                    season_type=season_type
                )
                csv_paths[f"shots_{player_id}"] = get_relative_cache_path(
                    os.path.basename(csv_path),
                    "player_comparison"
                )

            # Add comparison CSV path
            comparison_csv_path = _get_csv_path_for_comparison(
                player_ids=player_ids,
                season=season,
                season_type=season_type
            )
            csv_paths["zone_breakdown"] = get_relative_cache_path(
                os.path.basename(comparison_csv_path),
                "player_comparison"
            )

            result["dataframe_info"] = {
                "message": "Player comparison data has been converted to DataFrames and saved as CSV files",
                "dataframes": {
                    name: {
                        "shape": list(df.shape) if not df.empty else [],
                        "columns": df.columns.tolist() if not df.empty else [],
                        "csv_path": csv_paths.get(name, "")
                    } for name, df in dataframes.items() if not df.empty
                }
            }

            return result, dataframes

        return result

    except Exception as e:
        logger.error(f"Error comparing player shots: {str(e)}", exc_info=True)
        error_response = {
            "error": f"Failed to compare player shots: {str(e)}"
        }
        if return_dataframe:
            return error_response, dataframes
        return error_response

def create_comparison_scatter(
    player_data: List[Dict[str, Any]],
    season: str,
    season_type: str,
    output_format: str = "base64"
) -> Dict[str, Any]:
    """Create a scatter plot comparison of player shots."""
    # Create figure with subplots
    fig, axes = plt.subplots(1, len(player_data), figsize=(6 * len(player_data), 10), facecolor='white')

    # If only one subplot, make it iterable
    if len(player_data) == 1:
        axes = [axes]

    # Colors for each player
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    # Draw each player's shots
    for i, (ax, player, color) in enumerate(zip(axes, player_data, colors)):
        # Draw court
        draw_court(ax)

        # Extract shot locations
        shots = player["shot_locations"]

        # Plot shots
        made_x = [shot["x"] for shot in shots if shot["made"]]
        made_y = [shot["y"] for shot in shots if shot["made"]]
        missed_x = [shot["x"] for shot in shots if not shot["made"]]
        missed_y = [shot["y"] for shot in shots if not shot["made"]]

        ax.scatter(made_x, made_y, c=color, alpha=0.7, s=30, marker='o', edgecolor='white', linewidth=0.5, zorder=3)
        ax.scatter(missed_x, missed_y, c=color, alpha=0.4, s=20, marker='x', linewidth=1, zorder=2)

        # Add title
        stats = player["overall_stats"]
        title = f"{player['player_name']}\n"
        title += f"FG: {stats['made_shots']}/{stats['total_shots']} ({stats['field_goal_percentage']}%)"
        ax.set_title(title, pad=20, size=12, weight='bold')

    # Add overall title
    fig.suptitle(f"Shot Chart Comparison - {season} {season_type}", fontsize=16, weight='bold', y=0.98)

    # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # Return the visualization based on output format
    if output_format == 'base64':
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            "image_data": f"data:image/png;base64,{image_base64}",
            "chart_type": "comparison_scatter"
        }
    else:
        # Save to file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        player_names = "_vs_".join([player["player_name"].replace(" ", "_") for player in player_data])
        filename = f"comparison_scatter_{player_names}_{season}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return {
            "file_path": filepath,
            "chart_type": "comparison_scatter"
        }

def create_comparison_heatmap(
    player_data: List[Dict[str, Any]],
    season: str,
    season_type: str,
    output_format: str = "base64"
) -> Dict[str, Any]:
    """Create a heatmap comparison of player shots."""
    # Create figure with subplots
    fig, axes = plt.subplots(1, len(player_data), figsize=(6 * len(player_data), 10), facecolor='white')

    # If only one subplot, make it iterable
    if len(player_data) == 1:
        axes = [axes]

    # Draw each player's heatmap
    for i, (ax, player) in enumerate(zip(axes, player_data)):
        # Draw court
        draw_court(ax)

        # Extract shot locations
        shots = player["shot_locations"]

        # Create heatmap
        x = [shot["x"] for shot in shots]
        y = [shot["y"] for shot in shots]

        if len(x) > 10:
            # Create hexbin
            hexbin = ax.hexbin(
                x, y,
                gridsize=25,
                cmap='viridis',
                alpha=0.7,
                mincnt=1,
                zorder=3
            )
            plt.colorbar(hexbin, ax=ax, label='Shot Frequency')
        else:
            # Fall back to scatter plot if not enough points
            made_x = [shot["x"] for shot in shots if shot["made"]]
            made_y = [shot["y"] for shot in shots if shot["made"]]
            missed_x = [shot["x"] for shot in shots if not shot["made"]]
            missed_y = [shot["y"] for shot in shots if not shot["made"]]

            ax.scatter(made_x, made_y, c='#2ECC71', alpha=0.7, s=30, marker='o', edgecolor='white', linewidth=0.5, zorder=3)
            ax.scatter(missed_x, missed_y, c='#E74C3C', alpha=0.4, s=20, marker='x', linewidth=1, zorder=2)

        # Add title
        stats = player["overall_stats"]
        title = f"{player['player_name']}\n"
        title += f"FG: {stats['made_shots']}/{stats['total_shots']} ({stats['field_goal_percentage']}%)"
        ax.set_title(title, pad=20, size=12, weight='bold')

    # Add overall title
    fig.suptitle(f"Shot Frequency Comparison - {season} {season_type}", fontsize=16, weight='bold', y=0.98)

    # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # Return the visualization based on output format
    if output_format == 'base64':
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            "image_data": f"data:image/png;base64,{image_base64}",
            "chart_type": "comparison_heatmap"
        }
    else:
        # Save to file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        player_names = "_vs_".join([player["player_name"].replace(" ", "_") for player in player_data])
        filename = f"comparison_heatmap_{player_names}_{season}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return {
            "file_path": filepath,
            "chart_type": "comparison_heatmap"
        }

def create_comparison_zones(
    player_data: List[Dict[str, Any]],
    season: str,
    season_type: str,
    output_format: str = "base64"
) -> Dict[str, Any]:
    """Create a zone efficiency comparison of player shots."""
    # Define zones to compare
    zones = [
        "Above the Break 3",
        "Left Corner 3",
        "Right Corner 3",
        "Mid-Range",
        "In The Paint (Non-RA)",
        "Restricted Area"
    ]

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8), facecolor='white')

    # Colors for each player
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    # Set up bar positions
    bar_width = 0.2
    index = np.arange(len(zones))

    # Plot bars for each player
    for i, (player, color) in enumerate(zip(player_data, colors)):
        # Get zone percentages
        zone_breakdown = player["zone_breakdown"]
        percentages = []

        for zone in zones:
            if zone in zone_breakdown:
                percentages.append(zone_breakdown[zone]["percentage"])
            else:
                percentages.append(0)

        # Plot bars
        bars = ax.bar(index + i * bar_width, percentages, bar_width,
                     alpha=0.8, color=color, label=player["player_name"])

        # Add percentage labels
        for bar, percentage in zip(bars, percentages):
            if percentage > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                       f"{percentage:.1f}%", ha='center', va='bottom', fontsize=8)

    # Add league average line
    league_percentages = []
    for zone in zones:
        # Get league average from first player (should be the same for all)
        if zone in player_data[0]["zone_breakdown"]:
            league_percentages.append(player_data[0]["zone_breakdown"][zone]["league_percentage"])
        else:
            league_percentages.append(0)

    ax.plot(index + bar_width * (len(player_data) - 1) / 2, league_percentages, 'k--', label='League Average')

    # Add labels and title
    ax.set_xlabel('Shot Zone', fontsize=12)
    ax.set_ylabel('Field Goal Percentage (%)', fontsize=12)
    ax.set_title(f'Zone Efficiency Comparison - {season} {season_type}', fontsize=16, weight='bold')
    ax.set_xticks(index + bar_width * (len(player_data) - 1) / 2)
    ax.set_xticklabels(zones, rotation=45, ha='right')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3, axis='y')
    ax.legend()

    # Adjust layout
    plt.tight_layout()

    # Return the visualization based on output format
    if output_format == 'base64':
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            "image_data": f"data:image/png;base64,{image_base64}",
            "chart_type": "comparison_zones"
        }
    else:
        # Save to file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        player_names = "_vs_".join([player["player_name"].replace(" ", "_") for player in player_data])
        filename = f"comparison_zones_{player_names}_{season}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return {
            "file_path": filepath,
            "chart_type": "comparison_zones"
        }
