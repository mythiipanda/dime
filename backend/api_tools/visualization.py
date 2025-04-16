import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any
import os

def create_shotchart(shot_data: Dict[str, Any], output_dir: str) -> str:
    """
    Create a shot chart visualization from the shot data.
    
    Args:
        shot_data: Dictionary containing shot chart data
        output_dir: Directory to save the visualization
        
    Returns:
        str: Path to the saved visualization file
    """
    # Create figure and axis
    fig = plt.figure(figsize=(12, 11))
    ax = fig.add_subplot(111)
    
    # Draw court
    draw_court(ax)
    
    # Plot shots
    for shot in shot_data["shot_locations"]:
        # NBA coordinates are in inches from center court
        # We need to flip both x and y coordinates for proper orientation
        x = -shot["x"]  # Flip x coordinate
        y = shot["y"]   # Keep y as is
        made = shot["made"]
        
        if made:
            ax.scatter(x, y, c='#2ECC71', alpha=0.7, s=50, 
                      marker='o', edgecolor='white', linewidth=0.5, zorder=2)
        else:
            ax.scatter(x, y, c='#E74C3C', alpha=0.6, s=40, 
                      marker='x', linewidth=1.5, zorder=2)
    
    # Add title and stats
    stats = shot_data["overall_stats"]
    title = f"{shot_data['player_name']} Shot Chart {shot_data['season']}\n"
    title += f"FG: {stats['made_shots']}/{stats['total_shots']} ({stats['field_goal_percentage']}%)"
    plt.title(title, pad=20, size=14, weight='bold')
    
    # Add zone percentages with adjusted positioning
    zone_positions = {
        'Above the Break 3': {'offset_x': 0, 'offset_y': 30},
        'Left Corner 3': {'offset_x': -20, 'offset_y': 20},
        'Right Corner 3': {'offset_x': 20, 'offset_y': 20},
        'Mid-Range': {'offset_x': 0, 'offset_y': 25},
        'In The Paint (Non-RA)': {'offset_x': 0, 'offset_y': 20},
        'Restricted Area': {'offset_x': 0, 'offset_y': -30}
    }
    
    for zone, stats in shot_data["zone_breakdown"].items():
        # Calculate average position for the zone with flipped x coordinates
        zone_shots = [(-shot["x"], shot["y"]) for shot in shot_data["shot_locations"] 
                     if shot["zone"] == zone]
        if zone_shots:
            avg_x = sum(x for x, _ in zone_shots) / len(zone_shots)
            avg_y = sum(y for _, y in zone_shots) / len(zone_shots)
            
            # Apply zone-specific positioning
            offset = zone_positions.get(zone, {'offset_x': 0, 'offset_y': 25})
            text_x = avg_x + offset['offset_x']
            text_y = avg_y + offset['offset_y']
            
            # Add text with zone stats
            text = f"{zone}\n{stats['made']}/{stats['attempts']}\n{stats['percentage']}%"
            ax.text(text_x, text_y, text, ha='center', va='bottom', 
                   bbox=dict(facecolor='white', alpha=0.7, edgecolor='#222222', 
                            boxstyle='round,pad=0.5'),
                   size=8, weight='bold', zorder=3)
    
    # Add legend
    made_patch = plt.scatter([], [], c='#2ECC71', alpha=0.7, s=50, 
                           marker='o', edgecolor='white', label='Made')
    missed_patch = plt.scatter([], [], c='#E74C3C', alpha=0.6, s=40, 
                             marker='x', linewidth=1.5, label='Missed')
    ax.legend(handles=[made_patch, missed_patch], loc='upper right',
             bbox_to_anchor=(1, 1), framealpha=1)
    
    # Set axis limits to show only the offensive half-court
    ax.set_xlim(-250, 250)
    ax.set_ylim(-50, 420)
    
    # Save plot
    os.makedirs(output_dir, exist_ok=True)
    filename = f"shotchart_{shot_data['player_name'].replace(' ', '_')}_{shot_data['season']}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return filepath

def draw_court(ax: plt.Axes):
    """Draw an NBA basketball court."""
    # Court dimensions (in inches)
    court_width = 500
    court_height = 470
    three_point_radius = 237.5
    three_point_side_radius = 220
    three_point_side_height = 140
    paint_width = 160
    paint_height = 190
    backboard_width = 60
    hoop_radius = 7.5
    restricted_area_radius = 40
    
    # Main court outline
    court = plt.Rectangle((-court_width/2, -court_height/2), court_width, court_height, 
                         color='#FFFFFF', fill=True, zorder=0)
    ax.add_patch(court)
    
    # Paint area
    paint = plt.Rectangle((-paint_width/2, 0), paint_width, paint_height, 
                         fill=False, color='black', linewidth=1, zorder=1)
    ax.add_patch(paint)
    
    # Three-point line
    three_point_left = plt.Rectangle((-court_width/2, 0), 
                                   0, three_point_side_height, color='black', 
                                   linewidth=1, zorder=1)
    three_point_right = plt.Rectangle((court_width/2, 0), 
                                    0, three_point_side_height, color='black', 
                                    linewidth=1, zorder=1)
    ax.add_patch(three_point_left)
    ax.add_patch(three_point_right)
    
    # Three point arc
    theta = np.linspace(0, np.pi, 50)
    three_point_arc_x = three_point_radius * np.cos(theta)
    three_point_arc_y = three_point_radius * np.sin(theta)
    ax.plot(three_point_arc_x, three_point_arc_y, color='black', linewidth=1, zorder=1)
    
    # Backboard
    ax.plot([-backboard_width/2, backboard_width/2], [0, 0], 
           color='black', linewidth=1, zorder=1)
    
    # Hoop
    hoop = plt.Circle((0, 0), hoop_radius, color='black', 
                     fill=False, linewidth=1, zorder=1)
    ax.add_patch(hoop)
    
    # Restricted area
    restricted = plt.Circle((0, 0), restricted_area_radius, 
                          color='black', fill=False, linewidth=1, zorder=1)
    ax.add_patch(restricted)
    
    # Set aspect ratio and remove axes
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([]) 