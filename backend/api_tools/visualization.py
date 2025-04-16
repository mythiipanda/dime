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
        x, y = shot["x"], shot["y"]
        made = shot["made"]
        
        # Plot made shots as green dots, missed shots as red dots
        color = 'green' if made else 'red'
        alpha = 0.7 if made else 0.4
        marker = 'o' if made else 'x'
        
        ax.plot(x, y, marker=marker, color=color, alpha=alpha, markersize=8)
    
    # Add title and stats
    stats = shot_data["overall_stats"]
    title = f"{shot_data['player_name']} Shot Chart {shot_data['season']}\n"
    title += f"FG: {stats['made_shots']}/{stats['total_shots']} ({stats['field_goal_percentage']}%)"
    plt.title(title, pad=20)
    
    # Add zone percentages
    for zone, stats in shot_data["zone_breakdown"].items():
        # Calculate average position for the zone
        zone_shots = [(shot["x"], shot["y"]) for shot in shot_data["shot_locations"] 
                     if shot["zone"] == zone]
        if zone_shots:
            avg_x = sum(x for x, _ in zone_shots) / len(zone_shots)
            avg_y = sum(y for _, y in zone_shots) / len(zone_shots)
            
            # Add text with zone stats
            text = f"{zone}\n{stats['made']}/{stats['attempts']}\n{stats['percentage']}%"
            ax.text(avg_x, avg_y + 30, text, ha='center', va='bottom', 
                   bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    
    # Save plot
    os.makedirs(output_dir, exist_ok=True)
    filename = f"shotchart_{shot_data['player_name'].replace(' ', '_')}_{shot_data['season']}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    
    return filepath

def draw_court(ax: plt.Axes):
    """Draw an NBA basketball court."""
    # Court dimensions
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
                         color='#F0F0F0', fill=True)
    ax.add_patch(court)
    
    # Paint area
    paint = plt.Rectangle((-paint_width/2, -court_height/2), paint_width, paint_height, 
                         fill=False, color='black')
    ax.add_patch(paint)
    
    # Three-point line
    three_point_left = plt.Rectangle((-court_width/2, -three_point_side_height), 
                                   0, three_point_side_height*2, color='black', fill=False)
    three_point_right = plt.Rectangle((court_width/2, -three_point_side_height), 
                                    0, three_point_side_height*2, color='black', fill=False)
    ax.add_patch(three_point_left)
    ax.add_patch(three_point_right)
    
    # Three point arc
    theta = np.linspace(np.arccos(three_point_side_height/three_point_radius), 
                       np.pi - np.arccos(three_point_side_height/three_point_radius), 50)
    three_point_arc_x = three_point_radius * np.cos(theta)
    three_point_arc_y = three_point_radius * np.sin(theta)
    ax.plot(three_point_arc_x, three_point_arc_y, color='black')
    
    # Backboard
    ax.plot([-backboard_width/2, backboard_width/2], [0, 0], color='black')
    
    # Hoop
    hoop = plt.Circle((0, 0), hoop_radius, color='black', fill=False)
    ax.add_patch(hoop)
    
    # Restricted area
    restricted = plt.Circle((0, 0), restricted_area_radius, color='black', fill=False)
    ax.add_patch(restricted)
    
    # Set limits and aspect ratio
    ax.set_xlim(-court_width/2 - 50, court_width/2 + 50)
    ax.set_ylim(-court_height/2 - 50, court_height/2 + 50)
    ax.set_aspect('equal')
    
    # Remove axes
    ax.set_xticks([])
    ax.set_yticks([]) 