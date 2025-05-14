"""
Simple smoke test for shot chart visualization.
"""

import os
import sys
import logging
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle, Arc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for court dimensions
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

def draw_court(ax, color='black', lw=2):
    """Draw a basketball court."""
    # Court background
    court = Rectangle((-COURT_WIDTH/2, 0), COURT_WIDTH, COURT_HEIGHT, 
                     color='#F2F3F5', fill=True, zorder=0)
    ax.add_patch(court)
    
    # Paint area
    paint = Rectangle((-PAINT_WIDTH/2, 0), PAINT_WIDTH, PAINT_HEIGHT, 
                     color='#F9FAFB', fill=True, zorder=1)
    ax.add_patch(paint)
    
    # Paint outline
    paint_outline = Rectangle((-PAINT_WIDTH/2, 0), PAINT_WIDTH, PAINT_HEIGHT, 
                             fill=False, color=color, linewidth=lw, zorder=2)
    ax.add_patch(paint_outline)
    
    # Three-point line
    ax.plot([-THREE_POINT_SIDE_RADIUS, -THREE_POINT_SIDE_RADIUS], 
           [0, THREE_POINT_SIDE_HEIGHT], color=color, linewidth=lw, zorder=2)
    ax.plot([THREE_POINT_SIDE_RADIUS, THREE_POINT_SIDE_RADIUS], 
           [0, THREE_POINT_SIDE_HEIGHT], color=color, linewidth=lw, zorder=2)
    
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

def create_sample_shot_chart():
    """Create a sample shot chart with random shots."""
    # Create figure and axis
    fig = plt.figure(figsize=(12, 11), facecolor='white')
    ax = fig.add_subplot(111)
    
    # Draw court
    draw_court(ax)
    
    # Generate random shots
    np.random.seed(42)  # For reproducibility
    num_shots = 100
    x = np.random.uniform(-COURT_WIDTH/2, COURT_WIDTH/2, num_shots)
    y = np.random.uniform(0, COURT_HEIGHT, num_shots)
    made = np.random.choice([True, False], num_shots, p=[0.45, 0.55])
    
    # Plot shots
    for i in range(num_shots):
        if made[i]:
            ax.scatter(x[i], y[i], c='#2ECC71', alpha=0.7, s=50, 
                      marker='o', edgecolor='white', linewidth=0.5, zorder=3)
        else:
            ax.scatter(x[i], y[i], c='#E74C3C', alpha=0.6, s=40, 
                      marker='x', linewidth=1.5, zorder=3)
    
    # Add title
    plt.title("Sample Shot Chart", pad=20, size=14, weight='bold')
    
    # Add legend
    made_patch = plt.scatter([], [], c='#2ECC71', alpha=0.7, s=50, 
                           marker='o', edgecolor='white', label='Made')
    missed_patch = plt.scatter([], [], c='#E74C3C', alpha=0.6, s=40, 
                             marker='x', linewidth=1.5, label='Missed')
    ax.legend(handles=[made_patch, missed_patch], loc='upper right',
             bbox_to_anchor=(1, 1), framealpha=1)
    
    # Save the figure
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "sample_shotchart.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"Sample shot chart created at: {filepath}")
    return filepath

def test_shot_chart():
    """Test creating a sample shot chart."""
    logger.info("Testing shot chart creation...")
    
    try:
        filepath = create_sample_shot_chart()
        if os.path.exists(filepath):
            logger.info("Shot chart test passed!")
            return True
        else:
            logger.error("Shot chart file was not created")
            return False
    except Exception as e:
        logger.error(f"Error creating shot chart: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_shot_chart()
    sys.exit(0 if success else 1)
