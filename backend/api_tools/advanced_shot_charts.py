"""
Advanced shot chart generation module for NBA player shot analysis.
This module provides enhanced visualization capabilities for shot charts,
including heatmaps, animated sequences, and interactive elements.
"""

import logging
import os
import json
import base64
from io import BytesIO
from typing import Dict, List, Optional, Any, Tuple, Union
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle, Arc, Polygon
from nba_api.stats.endpoints import shotchartdetail
from ..config import settings
from ..core.errors import Errors
from .utils import format_response, find_player_id_or_error
from ..utils.validation import _validate_season_format

logger = logging.getLogger(__name__)

# Module-level constants
COURT_WIDTH = 500
COURT_HEIGHT = 470
THREE_POINT_RADIUS = 237.5
THREE_POINT_SIDE_RADIUS = 220
THREE_POINT_SIDE_HEIGHT = 140
PAINT_WIDTH = 160
PAINT_HEIGHT = 190
BACKBOARD_WIDTH = 60
HOOP_RADIUS = 7.5
RESTRICTED_AREA_RADIUS = 40
FREE_THROW_CIRCLE_RADIUS = 60
CORNER_THREE_SIDE_DIST = 220

# Shot zone positions for annotations
ZONE_POSITIONS = {
    'Above the Break 3': {'offset_x': 0, 'offset_y': 30},
    'Left Corner 3': {'offset_x': -20, 'offset_y': 20},
    'Right Corner 3': {'offset_x': 20, 'offset_y': 20},
    'Mid-Range': {'offset_x': 0, 'offset_y': 25},
    'In The Paint (Non-RA)': {'offset_x': 0, 'offset_y': 20},
    'Restricted Area': {'offset_x': 0, 'offset_y': -30}
}

# Custom color maps
HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    'shot_heatmap',
    [(0, '#0000FF'), (0.5, '#800080'), (1, '#FF0000')],
    N=256
)

def draw_court(ax: plt.Axes, color: str = 'black', lw: float = 2,
               outer_lines: bool = False, court_bg_color: str = '#F2F3F5',
               paint_color: str = '#F9FAFB', three_point_color: str = '#E5E7EB') -> plt.Axes:
    """
    Draw an NBA basketball court with accurate dimensions and styling.

    Args:
        ax: Matplotlib axes object
        color: Color of the court lines
        lw: Line width
        outer_lines: Whether to draw the outer court boundaries
        court_bg_color: Background color of the court
        paint_color: Color of the paint area
        three_point_color: Color of the three-point area

    Returns:
        The matplotlib axes object with the court drawn
    """
    # Court background
    court = Rectangle((-COURT_WIDTH/2, 0), COURT_WIDTH, COURT_HEIGHT,
                     color=court_bg_color, fill=True, zorder=0)
    ax.add_patch(court)

    # Paint area with custom color
    paint = Rectangle((-PAINT_WIDTH/2, 0), PAINT_WIDTH, PAINT_HEIGHT,
                     color=paint_color, fill=True, zorder=1)
    ax.add_patch(paint)

    # Paint outline
    paint_outline = Rectangle((-PAINT_WIDTH/2, 0), PAINT_WIDTH, PAINT_HEIGHT,
                             fill=False, color=color, linewidth=lw, zorder=2)
    ax.add_patch(paint_outline)

    # Three-point line
    three_point_left = Rectangle((-COURT_WIDTH/2, 0),
                               0, THREE_POINT_SIDE_HEIGHT, color=color,
                               linewidth=lw, zorder=2)
    three_point_right = Rectangle((COURT_WIDTH/2, 0),
                                0, THREE_POINT_SIDE_HEIGHT, color=color,
                                linewidth=lw, zorder=2)
    ax.add_patch(three_point_left)
    ax.add_patch(three_point_right)

    # Three point arc
    theta = np.linspace(0, np.pi, 100)
    three_point_arc_x = THREE_POINT_RADIUS * np.cos(theta)
    three_point_arc_y = THREE_POINT_RADIUS * np.sin(theta)
    ax.plot(three_point_arc_x, three_point_arc_y, color=color, linewidth=lw, zorder=2)

    # Backboard
    ax.plot([-BACKBOARD_WIDTH/2, BACKBOARD_WIDTH/2], [0, 0],
           color=color, linewidth=lw*1.5, zorder=2)

    # Hoop
    hoop = Circle((0, 0), HOOP_RADIUS, color=color,
                 fill=False, linewidth=lw, zorder=2)
    ax.add_patch(hoop)

    # Restricted area
    restricted = Circle((0, 0), RESTRICTED_AREA_RADIUS,
                      color=color, fill=False, linewidth=lw, zorder=2)
    ax.add_patch(restricted)

    # Free throw circle
    free_throw = Circle((0, PAINT_HEIGHT), FREE_THROW_CIRCLE_RADIUS,
                       color=color, fill=False, linewidth=lw, zorder=2)
    ax.add_patch(free_throw)

    # Free throw line
    ax.plot([-PAINT_WIDTH/2, PAINT_WIDTH/2], [PAINT_HEIGHT, PAINT_HEIGHT],
           color=color, linewidth=lw, zorder=2)

    # Set aspect ratio and remove axes
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])

    # Set axis limits to show only the offensive half-court
    ax.set_xlim(-COURT_WIDTH/2, COURT_WIDTH/2)
    ax.set_ylim(0, COURT_HEIGHT)

    return ax

def create_static_shotchart(
    shot_data: Dict[str, Any],
    chart_type: str = 'scatter',
    output_format: str = 'base64'
) -> Dict[str, Any]:
    """
    Create a static shot chart visualization from the shot data.

    Args:
        shot_data: Dictionary containing shot chart data
        chart_type: Type of chart ('scatter', 'heatmap', 'hexbin')
        output_format: Output format ('base64', 'file')

    Returns:
        Dict containing the visualization data or file path
    """
    # Create figure and axis
    fig = plt.figure(figsize=(12, 11), facecolor='white')
    ax = fig.add_subplot(111)

    # Draw court
    draw_court(ax)

    # Extract shot locations
    shots = []
    for shot in shot_data.get("shot_locations", []):
        shots.append({
            "x": shot.get("x", 0),
            "y": shot.get("y", 0),
            "made": shot.get("made", False),
            "zone": shot.get("zone", ""),
            "value": 3 if "3PT" in shot.get("shot_type", "") else 2
        })

    # Plot shots based on chart type
    if chart_type == 'scatter':
        _plot_scatter_shots(ax, shots)
    elif chart_type == 'heatmap':
        _plot_heatmap_shots(ax, shots)
    elif chart_type == 'hexbin':
        _plot_hexbin_shots(ax, shots)

    # Add title and stats
    stats = shot_data.get("overall_stats", {})
    title = f"{shot_data.get('player_name', 'Player')} Shot Chart {shot_data.get('season', '')}\n"
    title += f"FG: {stats.get('made_shots', 0)}/{stats.get('total_shots', 0)} ({stats.get('field_goal_percentage', 0)}%)"
    plt.title(title, pad=20, size=14, weight='bold')

    # Add zone percentages
    _add_zone_annotations(ax, shot_data.get("zone_breakdown", {}), shots)

    # Add legend
    made_patch = plt.scatter([], [], c='#2ECC71', alpha=0.7, s=50,
                           marker='o', edgecolor='white', label='Made')
    missed_patch = plt.scatter([], [], c='#E74C3C', alpha=0.6, s=40,
                             marker='x', linewidth=1.5, label='Missed')
    ax.legend(handles=[made_patch, missed_patch], loc='upper right',
             bbox_to_anchor=(1, 1), framealpha=1)

    # Return the visualization based on output format
    if output_format == 'base64':
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            "image_data": f"data:image/png;base64,{image_base64}",
            "chart_type": chart_type
        }
    else:
        # Save to file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"shotchart_{shot_data.get('player_name', 'player').replace(' ', '_')}_{shot_data.get('season', '')}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return {
            "file_path": filepath,
            "chart_type": chart_type
        }

def _plot_scatter_shots(ax: plt.Axes, shots: List[Dict[str, Any]]) -> None:
    """Plot shots as a scatter plot."""
    for shot in shots:
        x = shot["x"]
        y = shot["y"]
        made = shot["made"]

        if made:
            ax.scatter(x, y, c='#2ECC71', alpha=0.7, s=50,
                      marker='o', edgecolor='white', linewidth=0.5, zorder=3)
        else:
            ax.scatter(x, y, c='#E74C3C', alpha=0.6, s=40,
                      marker='x', linewidth=1.5, zorder=3)

def _plot_heatmap_shots(ax: plt.Axes, shots: List[Dict[str, Any]]) -> None:
    """Plot shots as a heatmap."""
    x = [shot["x"] for shot in shots]
    y = [shot["y"] for shot in shots]

    # Create heatmap using kernel density estimation
    if len(x) > 5:  # Need enough points for KDE
        from scipy.stats import gaussian_kde
        xy = np.vstack([x, y])
        z = gaussian_kde(xy)(xy)

        # Sort the points by density, so that the densest points are plotted last
        idx = z.argsort()
        x = np.array(x)[idx]
        y = np.array(y)[idx]
        z = z[idx]

        scatter = ax.scatter(x, y, c=z, cmap=HEATMAP_CMAP, s=30, alpha=0.7, zorder=3)
        plt.colorbar(scatter, ax=ax, label='Shot Frequency')
    else:
        # Fall back to scatter plot if not enough points
        _plot_scatter_shots(ax, shots)

def _plot_hexbin_shots(ax: plt.Axes, shots: List[Dict[str, Any]]) -> None:
    """Plot shots as a hexbin plot."""
    x = [shot["x"] for shot in shots]
    y = [shot["y"] for shot in shots]

    if len(x) > 10:  # Need enough points for hexbin
        hexbin = ax.hexbin(
            x, y,
            gridsize=25,
            cmap=HEATMAP_CMAP,
            alpha=0.7,
            mincnt=1,
            zorder=3
        )
        plt.colorbar(hexbin, ax=ax, label='Shot Frequency')
    else:
        # Fall back to scatter plot if not enough points
        _plot_scatter_shots(ax, shots)

def _add_zone_annotations(ax: plt.Axes, zone_breakdown: Dict[str, Any], shots: List[Dict[str, Any]]) -> None:
    """Add zone percentage annotations to the shot chart."""
    for zone, stats in zone_breakdown.items():
        # Calculate average position for the zone
        zone_shots = [(shot["x"], shot["y"]) for shot in shots if shot.get("zone") == zone]
        if zone_shots:
            avg_x = sum(x for x, _ in zone_shots) / len(zone_shots)
            avg_y = sum(y for _, y in zone_shots) / len(zone_shots)

            # Apply zone-specific positioning
            offset = ZONE_POSITIONS.get(zone, {'offset_x': 0, 'offset_y': 25})
            text_x = avg_x + offset['offset_x']
            text_y = avg_y + offset['offset_y']

            # Add text with zone stats
            text = f"{zone}\n{stats.get('made', 0)}/{stats.get('attempts', 0)}\n{stats.get('percentage', 0)}%"
            ax.text(text_x, text_y, text, ha='center', va='bottom',
                   bbox=dict(facecolor='white', alpha=0.7, edgecolor='#222222',
                            boxstyle='round,pad=0.5'),
                   size=8, weight='bold', zorder=4)

def create_animated_shotchart(
    shot_data: Dict[str, Any],
    output_format: str = 'base64'
) -> Dict[str, Any]:
    """
    Create an animated shot chart visualization showing shots appearing sequentially.

    Args:
        shot_data: Dictionary containing shot chart data
        output_format: Output format ('base64', 'file')

    Returns:
        Dict containing the visualization data or file path
    """
    # Extract shot locations
    shots = []
    for shot in shot_data.get("shot_locations", []):
        shots.append({
            "x": shot.get("x", 0),
            "y": shot.get("y", 0),
            "made": shot.get("made", False),
            "zone": shot.get("zone", ""),
            "value": 3 if "3PT" in shot.get("shot_type", "") else 2,
            "game_date": shot.get("game_date", "")
        })

    # Sort shots by game date if available
    if all("game_date" in shot for shot in shots):
        shots.sort(key=lambda x: x["game_date"])

    # Create figure and axis
    fig = plt.figure(figsize=(12, 11), facecolor='white')
    ax = fig.add_subplot(111)

    # Draw court
    draw_court(ax)

    # Add title and stats
    stats = shot_data.get("overall_stats", {})
    title = f"{shot_data.get('player_name', 'Player')} Shot Chart {shot_data.get('season', '')}\n"
    title += f"FG: {stats.get('made_shots', 0)}/{stats.get('total_shots', 0)} ({stats.get('field_goal_percentage', 0)}%)"
    plt.title(title, pad=20, size=14, weight='bold')

    # Add legend
    made_patch = plt.scatter([], [], c='#2ECC71', alpha=0.7, s=50,
                           marker='o', edgecolor='white', label='Made')
    missed_patch = plt.scatter([], [], c='#E74C3C', alpha=0.6, s=40,
                             marker='x', linewidth=1.5, label='Missed')
    ax.legend(handles=[made_patch, missed_patch], loc='upper right',
             bbox_to_anchor=(1, 1), framealpha=1)

    # Initialize empty scatter plots for made and missed shots
    made_shots = ax.scatter([], [], c='#2ECC71', alpha=0.7, s=50,
                          marker='o', edgecolor='white', linewidth=0.5, zorder=3)
    missed_shots = ax.scatter([], [], c='#E74C3C', alpha=0.6, s=40,
                            marker='x', linewidth=1.5, zorder=3)

    # Animation function
    def update(frame):
        # Get shots up to the current frame
        current_shots = shots[:frame]

        # Separate made and missed shots
        made_x = [shot["x"] for shot in current_shots if shot["made"]]
        made_y = [shot["y"] for shot in current_shots if shot["made"]]
        missed_x = [shot["x"] for shot in current_shots if not shot["made"]]
        missed_y = [shot["y"] for shot in current_shots if not shot["made"]]

        # Update scatter plots
        made_shots.set_offsets(np.c_[made_x, made_y])
        missed_shots.set_offsets(np.c_[missed_x, missed_y])

        return made_shots, missed_shots

    # Create animation
    frames = min(len(shots), 100)  # Limit to 100 frames for performance
    step = max(1, len(shots) // frames)
    anim = animation.FuncAnimation(
        fig, update, frames=range(1, len(shots) + 1, step),
        interval=50, blit=True
    )

    # Return the animation based on output format
    if output_format == 'base64':
        buffer = BytesIO()
        writer = animation.PillowWriter(fps=10)
        anim.save(buffer, writer=writer)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close(fig)
        return {
            "animation_data": f"data:image/gif;base64,{image_base64}",
            "chart_type": "animated"
        }
    else:
        # Save to file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"animated_shotchart_{shot_data.get('player_name', 'player').replace(' ', '_')}_{shot_data.get('season', '')}.gif"
        filepath = os.path.join(output_dir, filename)
        writer = animation.PillowWriter(fps=10)
        anim.save(filepath, writer=writer)
        plt.close(fig)
        return {
            "file_path": filepath,
            "chart_type": "animated"
        }

def create_shot_frequency_chart(
    shot_data: Dict[str, Any],
    output_format: str = 'base64'
) -> Dict[str, Any]:
    """
    Create a shot frequency chart visualization showing frequency and efficiency.

    Args:
        shot_data: Dictionary containing shot chart data
        output_format: Output format ('base64', 'file')

    Returns:
        Dict containing the visualization data or file path
    """
    # Create figure and axis
    fig = plt.figure(figsize=(12, 11), facecolor='white')
    ax = fig.add_subplot(111)

    # Draw court
    draw_court(ax)

    # Extract shot locations
    shots = []
    for shot in shot_data.get("shot_locations", []):
        shots.append({
            "x": shot.get("x", 0),
            "y": shot.get("y", 0),
            "made": shot.get("made", False),
            "zone": shot.get("zone", ""),
            "value": 3 if "3PT" in shot.get("shot_type", "") else 2
        })

    # Create hexbin plot for frequency
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

        # Add title and stats
        stats = shot_data.get("overall_stats", {})
        title = f"{shot_data.get('player_name', 'Player')} Shot Frequency {shot_data.get('season', '')}\n"
        title += f"FG: {stats.get('made_shots', 0)}/{stats.get('total_shots', 0)} ({stats.get('field_goal_percentage', 0)}%)"
        plt.title(title, pad=20, size=14, weight='bold')
    else:
        # Fall back to scatter plot if not enough points
        _plot_scatter_shots(ax, shots)

        # Add title and stats
        stats = shot_data.get("overall_stats", {})
        title = f"{shot_data.get('player_name', 'Player')} Shot Chart {shot_data.get('season', '')}\n"
        title += f"FG: {stats.get('made_shots', 0)}/{stats.get('total_shots', 0)} ({stats.get('field_goal_percentage', 0)}%)"
        plt.title(title, pad=20, size=14, weight='bold')

    # Return the visualization based on output format
    if output_format == 'base64':
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            "image_data": f"data:image/png;base64,{image_base64}",
            "chart_type": "frequency"
        }
    else:
        # Save to file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"frequency_shotchart_{shot_data.get('player_name', 'player').replace(' ', '_')}_{shot_data.get('season', '')}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return {
            "file_path": filepath,
            "chart_type": "frequency"
        }

def create_shot_distance_chart(
    shot_data: Dict[str, Any],
    output_format: str = 'base64'
) -> Dict[str, Any]:
    """
    Create a shot distance chart visualization showing efficiency by distance.

    Args:
        shot_data: Dictionary containing shot chart data
        output_format: Output format ('base64', 'file')

    Returns:
        Dict containing the visualization data or file path
    """
    # Create figure and axis
    fig = plt.figure(figsize=(12, 8), facecolor='white')
    ax = fig.add_subplot(111)

    # Extract shot locations with distances
    shots = []
    for shot in shot_data.get("shot_locations", []):
        shots.append({
            "distance": shot.get("distance", 0),
            "made": shot.get("made", False),
            "value": 3 if "3PT" in shot.get("shot_type", "") else 2
        })

    # Group shots by distance (rounded to nearest foot)
    distance_groups = {}
    for shot in shots:
        distance = round(shot["distance"])
        if distance not in distance_groups:
            distance_groups[distance] = {"attempts": 0, "made": 0}

        distance_groups[distance]["attempts"] += 1
        if shot["made"]:
            distance_groups[distance]["made"] += 1

    # Calculate percentages and prepare data for plotting
    distances = []
    percentages = []
    sizes = []

    for distance, stats in sorted(distance_groups.items()):
        if stats["attempts"] >= 3:  # Only include distances with enough attempts
            distances.append(distance)
            percentages.append((stats["made"] / stats["attempts"]) * 100)
            sizes.append(stats["attempts"] * 5)  # Scale size by number of attempts

    # Create scatter plot with size representing number of attempts
    scatter = ax.scatter(distances, percentages, s=sizes, alpha=0.7, c=percentages,
                        cmap='RdYlGn', vmin=0, vmax=100, edgecolors='black', linewidths=0.5)

    # Add league average line
    league_avg = 45  # Approximate league average FG%
    ax.axhline(y=league_avg, color='gray', linestyle='--', alpha=0.7, label='League Average')

    # Add trend line
    if len(distances) > 1:
        try:
            import numpy as np
            from scipy import stats

            slope, intercept, r_value, p_value, std_err = stats.linregress(distances, percentages)
            line_x = np.array([min(distances), max(distances)])
            line_y = slope * line_x + intercept
            ax.plot(line_x, line_y, 'b-', alpha=0.5, label=f'Trend (r={r_value:.2f})')
        except:
            # If scipy is not available, skip trend line
            pass

    # Add labels and title
    ax.set_xlabel('Distance (feet)', fontsize=12)
    ax.set_ylabel('Field Goal Percentage (%)', fontsize=12)

    stats = shot_data.get("overall_stats", {})
    title = f"{shot_data.get('player_name', 'Player')} Shooting by Distance {shot_data.get('season', '')}\n"
    title += f"FG: {stats.get('made_shots', 0)}/{stats.get('total_shots', 0)} ({stats.get('field_goal_percentage', 0)}%)"
    plt.title(title, pad=20, size=14, weight='bold')

    # Add colorbar
    cbar = plt.colorbar(scatter)
    cbar.set_label('Field Goal Percentage (%)')

    # Add legend for bubble size
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', markersize=5, label='5 Attempts'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', markersize=10, label='20 Attempts'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', markersize=15, label='50 Attempts')
    ]
    ax.legend(handles=legend_elements, loc='upper right')

    # Set y-axis limits
    ax.set_ylim(0, 100)

    # Add grid
    ax.grid(True, alpha=0.3)

    # Return the visualization based on output format
    if output_format == 'base64':
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            "image_data": f"data:image/png;base64,{image_base64}",
            "chart_type": "distance"
        }
    else:
        # Save to file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"distance_shotchart_{shot_data.get('player_name', 'player').replace(' ', '_')}_{shot_data.get('season', '')}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return {
            "file_path": filepath,
            "chart_type": "distance"
        }

def process_shot_data_for_visualization(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    chart_type: str = "scatter",
    output_format: str = "base64",
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Process shot data for a player and create visualizations.

    Args:
        player_name: Name of the player
        season: NBA season in format YYYY-YY
        season_type: Type of season (Regular Season, Playoffs, etc.)
        chart_type: Type of chart to create (scatter, heatmap, hexbin, animated, frequency)
        output_format: Output format (base64, file)
        use_cache: Whether to use cached visualizations

    Returns:
        Dict containing the visualization data and metadata
    """
    from .visualization_cache import VisualizationCache

    # Create cache parameters
    cache_params = {
        "player_name": player_name,
        "season": season,
        "season_type": season_type,
        "chart_type": chart_type,
        "output_format": output_format
    }

    # Check cache first if enabled
    if use_cache:
        cached_result = VisualizationCache.get(cache_params)
        if cached_result:
            logger.info(f"Using cached visualization for {player_name}, {season}, {chart_type}")
            return cached_result

    try:
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

        # Prepare data for visualization
        shot_data = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "overall_stats": {
                "total_shots": total_shots,
                "made_shots": made_shots,
                "field_goal_percentage": field_goal_percentage
            },
            "zone_breakdown": zone_breakdown,
            "shot_locations": shot_locations
        }

        # Create visualization based on chart type
        result = None
        if chart_type == "scatter":
            result = create_static_shotchart(shot_data, "scatter", output_format)
        elif chart_type == "heatmap":
            result = create_static_shotchart(shot_data, "heatmap", output_format)
        elif chart_type == "hexbin":
            result = create_static_shotchart(shot_data, "hexbin", output_format)
        elif chart_type == "animated":
            result = create_animated_shotchart(shot_data, output_format)
        elif chart_type == "frequency":
            result = create_shot_frequency_chart(shot_data, output_format)
        elif chart_type == "distance":
            result = create_shot_distance_chart(shot_data, output_format)
        elif chart_type == "comparison":
            # Comparison requires additional parameters
            return {
                "error": "Player comparison requires additional parameters. Use the comparison endpoint instead."
            }
        else:
            return {
                "error": f"Invalid chart type: {chart_type}. Valid types are: scatter, heatmap, hexbin, animated, frequency, distance, comparison"
            }

        # Cache the result if successful
        if result and use_cache and "error" not in result:
            VisualizationCache.set(cache_params, result)

        return result

    except Exception as e:
        logger.error(f"Error processing shot data for {player_name}: {str(e)}", exc_info=True)
        return {
            "error": f"Failed to process shot data: {str(e)}"
        }
