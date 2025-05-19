"""
Player comparison module for NBA player analysis.
"""

import logging
import os
import json
import base64
from io import BytesIO
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from nba_api.stats.endpoints import shotchartdetail
from ..config import settings
from .utils import find_player_id_or_error
from .advanced_shot_charts import draw_court

logger = logging.getLogger(__name__)

def compare_player_shots(
    player_names: List[str],
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    output_format: str = "base64",
    chart_type: str = "scatter"
) -> Dict[str, Any]:
    """
    Compare shot charts for multiple players.

    Args:
        player_names: List of player names to compare
        season: NBA season in format YYYY-YY
        season_type: Type of season (Regular Season, Playoffs, etc.)
        output_format: Output format (base64, file)
        chart_type: Type of chart to create (scatter, heatmap, zones)

    Returns:
        Dict containing the visualization data and metadata
    """
    if len(player_names) < 2:
        return {
            "error": "At least two players are required for comparison"
        }

    if len(player_names) > 4:
        return {
            "error": "Maximum of 4 players can be compared at once"
        }

    try:
        # Get player data
        player_data = []
        for player_name in player_names:
            # Get player ID
            player_id, player_actual_name = find_player_id_or_error(player_name)

            # Fetch shot chart data
            shotchart_endpoint = shotchartdetail.ShotChartDetail(
                player_id=player_id,
                team_id=0,
                season_nullable=season,
                season_type_all_star=season_type,
                timeout=settings.DEFAULT_TIMEOUT_SECONDS,
                context_measure_simple='FGA'
            )

            shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
            league_avg_df = shotchart_endpoint.league_averages.get_data_frame()

            if shots_df.empty:
                return {
                    "error": f"No shot data found for {player_actual_name} in {season} {season_type}"
                }

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

        # Create visualization based on chart type
        if chart_type == "scatter":
            return create_comparison_scatter(player_data, season, season_type, output_format)
        elif chart_type == "heatmap":
            return create_comparison_heatmap(player_data, season, season_type, output_format)
        elif chart_type == "zones":
            return create_comparison_zones(player_data, season, season_type, output_format)
        else:
            return {
                "error": f"Invalid chart type: {chart_type}. Valid types are: scatter, heatmap, zones"
            }

    except Exception as e:
        logger.error(f"Error comparing player shots: {str(e)}", exc_info=True)
        return {
            "error": f"Failed to compare player shots: {str(e)}"
        }

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
