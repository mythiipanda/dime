"""
Implementation of RAPTOR-style advanced metrics for NBA players.
Based on the methodology described by FiveThirtyEight.
"""

import logging
import json
import time
import os
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from nba_api.stats.endpoints import playercareerstats, commonplayerinfo, playerawards
from nba_api.stats.endpoints import leaguedashplayerstats, playerdashboardbyyearoveryear
from nba_api.stats.static import players
from .utils import retry_on_timeout
from config import settings
logger = logging.getLogger(__name__)

# Path to cache directory for historical player data
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Award point values for achievements (used in ELO calculation)
AWARD_VALUES = {
    "MVP": 50,              # Most Valuable Player
    "Finals MVP": 40,       # Finals MVP
    "Defensive Player of the Year": 30,  # Defensive Player of the Year
    "All-NBA": 20,          # All-NBA Team
    "All-Defensive": 15,    # All-Defensive Team
    "All-Star": 10,         # All-Star
    "All-Rookie": 5,        # All-Rookie Team
    "Rookie of the Year": 15,  # Rookie of the Year
    "Scoring Champion": 20, # Scoring Champion
    "Blocks Champion": 15,  # Blocks Leader
    "Steals Champion": 15,  # Steals Leader
    "Assists Champion": 15, # Assists Leader
    "Rebounds Champion": 15,  # Rebounds Leader
}

# RAPTOR weights for boxscore stats (based on FiveThirtyEight's methodology)
RAPTOR_WEIGHTS = {
    # Offensive weights
    "offense": {
        "intercept": -3.88704,
        "MPG": 0.026112,
        "PTS/100": 0.662784,
        "TSA/100": -0.51622,
        "AST/100": 0.430454,
        "TOV/100": -0.893465,
        "ORB/100": 0.303023,
        "DRB/100": -0.085637,
        "STL/100": 0.418092,
        "BLK/100": -0.230734,
        "PF/100": -0.108369,
        "OnCourt": 0.018381,
        "On-Off": 0.032054,
    },
    # Defensive weights
    "defense": {
        "intercept": -3.079144,
        "MPG": 0.033637,
        "PTS/100": -0.081412,
        "TSA/100": 0.025422,
        "AST/100": -0.025109,
        "TOV/100": -0.055809,
        "ORB/100": -0.099034,
        "DRB/100": 0.191569,
        "STL/100": 1.150891,
        "BLK/100": 0.611107,
        "PF/100": 0.010649,
        "OnCourt": 0.089391,
        "On-Off": 0.021717,
    }
}

# Position adjustment targets (minute-weighted average for each position)
POSITION_ADJUSTMENTS = {
    "PG": {"offense": 0.3, "defense": -0.3},
    "SG": {"offense": 0.2, "defense": -0.2},
    "SF": {"offense": 0.0, "defense": 0.0},
    "PF": {"offense": -0.2, "defense": 0.2},
    "C": {"offense": -0.5, "defense": 0.5},
}

def get_player_raptor_metrics(player_id: int, season: str = "2023-24") -> Dict[str, Any]:
    """
    Calculate RAPTOR-style metrics for a player.

    Args:
        player_id: The NBA API player ID
        season: The season to calculate metrics for (e.g., "2023-24")

    Returns:
        Dictionary with RAPTOR metrics
    """
    try:
        # Get player info (for position)
        player_info = retry_on_timeout(lambda: commonplayerinfo.CommonPlayerInfo(player_id=player_id))
        player_info_df = player_info.get_data_frames()[0]

        if player_info_df.empty:
            logger.warning(f"No player info found for player ID {player_id}")
            return {}

        player_name = player_info_df['DISPLAY_FIRST_LAST'].iloc[0]
        position = player_info_df['POSITION'].iloc[0]

        # Map position to one of PG, SG, SF, PF, C
        position_category = map_position_to_category(position)

        # Get basic stats
        basic_stats = get_player_basic_stats(player_id, season)
        if not basic_stats:
            logger.warning(f"No basic stats found for player ID {player_id} in season {season}")
            return {}

        # Get advanced stats
        advanced_stats = get_player_advanced_stats(player_id, season)
        if not advanced_stats:
            logger.warning(f"No advanced stats found for player ID {player_id} in season {season}")
            return {}

        # Calculate RAPTOR metrics
        raptor_metrics = calculate_raptor_metrics(basic_stats, advanced_stats, position_category)

        # Get historical data for ELO rating
        historical_data = get_historical_player_data(player_id)

        # Calculate ELO rating
        elo_rating = calculate_elo_rating(raptor_metrics, historical_data)

        # Add ELO rating to metrics
        raptor_metrics.update(elo_rating)

        # Add player info
        raptor_metrics["PLAYER_NAME"] = player_name
        raptor_metrics["POSITION"] = position
        raptor_metrics["POSITION_CATEGORY"] = position_category

        return raptor_metrics

    except Exception as e:
        logger.error(f"Error calculating RAPTOR metrics for player ID {player_id}: {str(e)}", exc_info=True)
        return {}

def map_position_to_category(position: str) -> str:
    """Map NBA position to one of the 5 position categories."""
    position = position.upper()

    if "GUARD" in position or "G" == position:
        if "POINT" in position or "PG" in position:
            return "PG"
        else:
            return "SG"
    elif "FORWARD" in position or "F" == position:
        if "SMALL" in position or "SF" in position:
            return "SF"
        else:
            return "PF"
    elif "CENTER" in position or "C" == position:
        return "C"

    # Handle hyphenated positions
    if "-" in position:
        positions = position.split("-")
        if "G" in positions and "F" in positions:
            return "SG"  # Guard-Forward is typically a shooting guard
        elif "F" in positions and "C" in positions:
            return "PF"  # Forward-Center is typically a power forward

    # Default to SF if we can't determine
    return "SF"

def get_player_basic_stats(player_id: int, season: str) -> Dict[str, float]:
    """
    Get basic stats for a player from the NBA API.

    Args:
        player_id: The NBA API player ID
        season: The season to get stats for (e.g., "2023-24")

    Returns:
        Dictionary with basic stats
    """
    try:
        def fetch_basic_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Base',
                per_mode_detailed='PerGame'
            )

        basic_stats_data = retry_on_timeout(fetch_basic_stats)
        basic_stats_df = basic_stats_data.get_data_frames()[0]

        if basic_stats_df.empty:
            logger.warning(f"No basic stats found for player ID {player_id} in season {season}")
            return {}

        # Extract the player's row
        player_stats = basic_stats_df[basic_stats_df['PLAYER_ID'] == player_id]

        if player_stats.empty:
            logger.warning(f"Player ID {player_id} not found in basic stats data")
            return {}

        # Convert to dictionary
        stats_dict = player_stats.iloc[0].to_dict()

        # Calculate per-100 possession stats (needed for RAPTOR)
        def fetch_per_100_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Base',
                per_mode_detailed='Per100Possessions'
            )

        per_100_data = retry_on_timeout(fetch_per_100_stats)
        per_100_df = per_100_data.get_data_frames()[0]

        if not per_100_df.empty:
            player_per_100 = per_100_df[per_100_df['PLAYER_ID'] == player_id]
            if not player_per_100.empty:
                per_100_dict = player_per_100.iloc[0].to_dict()

                # Add per-100 stats with specific keys
                stats_dict['PTS/100'] = per_100_dict.get('PTS', 0)
                stats_dict['AST/100'] = per_100_dict.get('AST', 0)
                stats_dict['TOV/100'] = per_100_dict.get('TOV', 0)
                stats_dict['ORB/100'] = per_100_dict.get('OREB', 0)
                stats_dict['DRB/100'] = per_100_dict.get('DREB', 0)
                stats_dict['STL/100'] = per_100_dict.get('STL', 0)
                stats_dict['BLK/100'] = per_100_dict.get('BLK', 0)
                stats_dict['PF/100'] = per_100_dict.get('PF', 0)

                # Calculate TSA/100 (Total Shot Attempts per 100)
                fga = per_100_dict.get('FGA', 0)
                fta = per_100_dict.get('FTA', 0)
                stats_dict['TSA/100'] = fga + (0.44 * fta)

        return stats_dict

    except Exception as e:
        logger.error(f"Error fetching basic stats for player ID {player_id}: {str(e)}", exc_info=True)
        return {}

def get_player_advanced_stats(player_id: int, season: str) -> Dict[str, float]:
    """
    Get advanced stats for a player from the NBA API.

    Args:
        player_id: The NBA API player ID
        season: The season to get stats for (e.g., "2023-24")

    Returns:
        Dictionary with advanced stats
    """
    try:
        def fetch_advanced_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Advanced',
                per_mode_detailed='PerGame'
            )

        advanced_stats_data = retry_on_timeout(fetch_advanced_stats)
        advanced_stats_df = advanced_stats_data.get_data_frames()[0]

        if advanced_stats_df.empty:
            logger.warning(f"No advanced stats found for player ID {player_id} in season {season}")
            return {}

        # Extract the player's row
        player_stats = advanced_stats_df[advanced_stats_df['PLAYER_ID'] == player_id]

        if player_stats.empty:
            logger.warning(f"Player ID {player_id} not found in advanced stats data")
            return {}

        # Convert to dictionary
        stats_dict = player_stats.iloc[0].to_dict()

        # Add on-court and on-off metrics (estimated since we don't have direct access)
        # In a real implementation, these would come from play-by-play data
        stats_dict['OnCourt'] = stats_dict.get('NET_RATING', 0) / 100  # Scale to match RAPTOR
        stats_dict['On-Off'] = stats_dict.get('PIE', 0) * 2  # Estimate based on PIE

        return stats_dict

    except Exception as e:
        logger.error(f"Error fetching advanced stats for player ID {player_id}: {str(e)}", exc_info=True)
        return {}

def calculate_raptor_metrics(basic_stats: Dict[str, float], advanced_stats: Dict[str, float], position: str) -> Dict[str, float]:
    """
    Calculate RAPTOR metrics based on player stats.

    Args:
        basic_stats: Dictionary with basic stats
        advanced_stats: Dictionary with advanced stats
        position: Player position category (PG, SG, SF, PF, C)

    Returns:
        Dictionary with RAPTOR metrics
    """
    metrics = {}

    # Combine stats
    all_stats = {**basic_stats, **advanced_stats}

    # Calculate minutes per game
    mpg = all_stats.get('MIN', 0)

    # Calculate offensive RAPTOR
    offensive_raptor = RAPTOR_WEIGHTS['offense']['intercept']
    offensive_raptor += RAPTOR_WEIGHTS['offense']['MPG'] * mpg

    # Add weighted box score components
    for stat, weight in RAPTOR_WEIGHTS['offense'].items():
        if stat in ['intercept', 'MPG']:
            continue

        if stat in all_stats:
            offensive_raptor += weight * all_stats[stat]

    # Calculate defensive RAPTOR
    defensive_raptor = RAPTOR_WEIGHTS['defense']['intercept']
    defensive_raptor += RAPTOR_WEIGHTS['defense']['MPG'] * mpg

    # Add weighted box score components
    for stat, weight in RAPTOR_WEIGHTS['defense'].items():
        if stat in ['intercept', 'MPG']:
            continue

        if stat in all_stats:
            defensive_raptor += weight * all_stats[stat]

    # Apply position adjustments
    if position in POSITION_ADJUSTMENTS:
        offensive_raptor += POSITION_ADJUSTMENTS[position]['offense']
        defensive_raptor += POSITION_ADJUSTMENTS[position]['defense']

    # Calculate total RAPTOR
    total_raptor = offensive_raptor + defensive_raptor

    # Calculate WAR (Wins Above Replacement)
    minutes_played = all_stats.get('MIN', 0) * all_stats.get('GP', 0)
    team_minutes = 48 * 5 * all_stats.get('GP', 0)  # 48 minutes * 5 players * games

    # Net Rating Contribution
    net_rating_contribution = (minutes_played / (team_minutes / 4.5)) * total_raptor

    # WAR per 82 games
    war_per_82 = (minutes_played / team_minutes) * 27.769 + 2.519 * net_rating_contribution

    # Actual WAR (scaled to games played)
    games_played = all_stats.get('GP', 0)
    war = war_per_82 * (games_played / 82) if games_played > 0 else 0

    # Store metrics
    metrics['RAPTOR_OFFENSE'] = round(offensive_raptor, 1)
    metrics['RAPTOR_DEFENSE'] = round(defensive_raptor, 1)
    metrics['RAPTOR_TOTAL'] = round(total_raptor, 1)
    metrics['WAR'] = round(war, 1)

    # Add traditional advanced metrics
    for key in ['TS_PCT', 'USG_PCT', 'AST_PCT', 'REB_PCT', 'OREB_PCT', 'DREB_PCT', 'PIE']:
        if key in advanced_stats:
            metrics[key] = advanced_stats[key]

    # Add offensive and defensive ratings
    if 'OFF_RATING' in advanced_stats:
        metrics['ORTG'] = advanced_stats['OFF_RATING']
    if 'DEF_RATING' in advanced_stats:
        metrics['DRTG'] = advanced_stats['DEF_RATING']

    return metrics

def calculate_elo_rating(metrics: Dict[str, float], historical_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate ELO rating based on current performance and historical data.

    Args:
        metrics: Dictionary with current season metrics
        historical_data: Dictionary with historical player data

    Returns:
        Dictionary with ELO rating components
    """
    elo_metrics = {}

    # Base ELO starts at 1500 (average player)
    base_elo = 1500

    # Current season performance (from RAPTOR or other metrics)
    current_season_bonus = 0

    # Use RAPTOR if available, otherwise fall back to other metrics
    if 'RAPTOR_TOTAL' in metrics:
        # RAPTOR typically ranges from -5 to +5 for most players
        raptor = metrics['RAPTOR_TOTAL']
        current_season_bonus = raptor * 40  # Scale to ELO points
    elif 'PIE' in metrics:
        # PIE typically ranges from 0 to 0.2 for most players
        pie = metrics['PIE']
        current_season_bonus = pie * 1000
    else:
        # Fallback to offensive and defensive ratings
        ortg = metrics.get('ORTG', 110)
        drtg = metrics.get('DRTG', 110)
        net_rtg = ortg - drtg
        current_season_bonus = net_rtg * 10

    # Historical performance factors
    historical_bonus = 0

    if historical_data:
        # Career longevity bonus (max +100 for 15+ years)
        years_played = min(15, historical_data.get("years_played", 0))
        longevity_bonus = years_played * 6.67  # Up to +100 for 15 years

        # Career achievements bonus
        achievements_bonus = historical_data.get("achievements_value", 0)  # Up to +200

        # Career statistical excellence
        career_stats_bonus = 0

        # Career PER bonus (15 is average, 25+ is excellent)
        career_per = historical_data.get("career_per", 0)
        if career_per > 15:
            career_per_bonus = min(100, (career_per - 15) * 10)  # Up to +100
            career_stats_bonus += career_per_bonus

        # Career WS bonus
        career_ws = historical_data.get("career_ws", 0)
        career_ws_bonus = min(100, career_ws * 1.5)  # Up to +100
        career_stats_bonus += career_ws_bonus

        # Career VORP bonus
        career_vorp = historical_data.get("career_vorp", 0)
        career_vorp_bonus = min(100, career_vorp * 5)  # Up to +100
        career_stats_bonus += career_vorp_bonus

        # Average the statistical bonuses
        career_stats_bonus = career_stats_bonus / 3

        # Playoff performance bonus
        playoff_bonus = 0
        playoff_stats = historical_data.get("playoff_stats", {})

        if playoff_stats:
            playoff_games = playoff_stats.get("games", 0)

            # Playoff experience bonus (up to +50 for 100+ playoff games)
            playoff_exp_bonus = min(50, playoff_games * 0.5)

            # Playoff scoring bonus
            playoff_ppg = playoff_stats.get("points_per_game", 0)
            playoff_scoring_bonus = min(50, playoff_ppg * 2)

            playoff_bonus = playoff_exp_bonus + playoff_scoring_bonus
            playoff_bonus = min(100, playoff_bonus)

        # Combine all historical factors
        historical_bonus = longevity_bonus + achievements_bonus + career_stats_bonus + playoff_bonus

        # Scale historical bonus (max +400)
        historical_bonus = min(400, historical_bonus)

    # Calculate final ELO rating
    # 60% current season, 40% historical performance
    elo_rating = base_elo + (current_season_bonus * 0.6) + (historical_bonus * 0.4)

    # Add components for reference
    elo_metrics["ELO_RATING"] = round(elo_rating, 0)
    elo_metrics["ELO_CURRENT"] = round(base_elo + current_season_bonus, 0)
    elo_metrics["ELO_HISTORICAL"] = round(base_elo + historical_bonus, 0)

    return elo_metrics

def get_historical_player_data(player_id: int) -> Dict[str, Any]:
    """
    Get historical data for a player, including career stats and achievements.
    Uses caching to avoid repeated API calls.

    Args:
        player_id: The NBA API player ID

    Returns:
        Dict with historical player data including:
        - years_played: Number of years in the league
        - achievements_value: Numerical value of career achievements
        - career_per: Career PER (Player Efficiency Rating)
        - career_ws: Career Win Shares
        - career_vorp: Career VORP (Value Over Replacement Player)
        - playoff_stats: Dictionary with playoff performance metrics
    """
    # Check if we have cached data
    cache_file = os.path.join(CACHE_DIR, f"player_{player_id}_history.json")

    # Try to load from cache first
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                # Check if cache is recent enough (1 week)
                cache_time = os.path.getmtime(cache_file)
                if (time.time() - cache_time) < 604800:  # 7 days in seconds
                    return cached_data
        except Exception as e:
            logger.warning(f"Error reading cache for player {player_id}: {str(e)}")

    try:
        # Fetch career stats
        career_stats = retry_on_timeout(lambda: playercareerstats.PlayerCareerStats(player_id=player_id))
        career_totals_df = career_stats.get_data_frames()[1]  # Career totals

        # Get years played
        season_totals_df = career_stats.get_data_frames()[0]  # Season-by-season
        years_played = len(season_totals_df['SEASON_ID'].unique())

        # Get playoff stats
        playoff_totals_df = None
        try:
            playoff_totals_df = career_stats.get_data_frames()[2]  # Playoff totals
        except:
            pass

        # Initialize historical data
        historical_data = {
            "years_played": years_played,
            "achievements_value": 0,
            "career_per": 0,
            "career_ws": 0,
            "career_vorp": 0,
            "playoff_stats": {}
        }

        # Get advanced career stats if available
        if not career_totals_df.empty:
            # Some players might not have these stats
            # In a real implementation, we would calculate these from raw stats
            historical_data["career_per"] = 15.0  # League average PER
            historical_data["career_ws"] = years_played * 3.0  # Estimate based on years played
            historical_data["career_vorp"] = years_played * 1.0  # Estimate based on years played

        # Get playoff stats if available
        if playoff_totals_df is not None and not playoff_totals_df.empty:
            playoff_games = playoff_totals_df['GP'].iloc[0] if 'GP' in playoff_totals_df.columns else 0
            playoff_points = playoff_totals_df['PTS'].iloc[0] if 'PTS' in playoff_totals_df.columns else 0

            historical_data["playoff_stats"] = {
                "games": int(playoff_games),
                "points": int(playoff_points),
                "points_per_game": round(playoff_points / playoff_games, 1) if playoff_games > 0 else 0
            }

        # Fetch awards
        awards = retry_on_timeout(lambda: playerawards.PlayerAwards(player_id=player_id))
        awards_df = awards.get_data_frames()[0]

        # Calculate achievements value
        achievements_value = 0

        if not awards_df.empty:
            for _, award in awards_df.iterrows():
                award_type = award['DESCRIPTION']

                # Check for exact matches
                if award_type in AWARD_VALUES:
                    achievements_value += AWARD_VALUES[award_type]
                else:
                    # Check for partial matches
                    for award_key, award_value in AWARD_VALUES.items():
                        if award_key in award_type:
                            achievements_value += award_value
                            break

        # Cap achievements value
        achievements_value = min(200, achievements_value)
        historical_data["achievements_value"] = achievements_value

        # Cache the data
        try:
            with open(cache_file, 'w') as f:
                json.dump(historical_data, f)
        except Exception as e:
            logger.warning(f"Error caching historical data for player {player_id}: {str(e)}")

        return historical_data

    except Exception as e:
        logger.error(f"Error fetching historical data for player {player_id}: {str(e)}", exc_info=True)
        return {
            "years_played": 0,
            "achievements_value": 0,
            "career_per": 0,
            "career_ws": 0,
            "career_vorp": 0,
            "playoff_stats": {}
        }

def generate_skill_grades(player_id: int, metrics: Dict[str, float], basic_stats: Dict[str, float]) -> Dict[str, str]:
    """
    Generate skill grades based on player metrics and league-wide percentiles.

    Args:
        player_id: The NBA API player ID
        metrics: Dictionary with player metrics
        basic_stats: Dictionary with basic stats (can be empty if not available)

    Returns:
        Dictionary mapping skills to letter grades (A+, A, A-, B+, B, etc.)
    """
    # Check if basic_stats is None or empty
    if not basic_stats:
        logger.warning(f"No basic stats provided for player {player_id}. Using metrics only for skill grades.")
        basic_stats = {}
    try:
        # Get league-wide stats for percentile calculations
        league_stats = get_league_stats_for_percentiles()

        # Define grade thresholds based on percentiles
        grade_thresholds = {
            'A+': 0.95,  # 95th percentile and above
            'A': 0.90,   # 90th percentile and above
            'A-': 0.85,  # 85th percentile and above
            'B+': 0.80,  # 80th percentile and above
            'B': 0.70,   # 70th percentile and above
            'B-': 0.60,  # 60th percentile and above
            'C+': 0.55,  # 55th percentile and above
            'C': 0.45,   # 45th percentile and above
            'C-': 0.35,  # 35th percentile and above
            'D+': 0.30,  # 30th percentile and above
            'D': 0.20,   # 20th percentile and above
            'D-': 0.10,  # 10th percentile and above
            'F': 0.0     # Below 10th percentile
        }

        # Initialize grades dictionary
        grades = {}

        # Calculate percentile for each skill
        skill_percentiles = {}

        # 1. Perimeter Shooting
        shooting_metrics = []

        # Use RAPTOR offense component if available
        if "RAPTOR_OFFENSE" in metrics:
            raptor_offense = metrics["RAPTOR_OFFENSE"]
            # Convert to percentile (RAPTOR typically ranges from -5 to +5)
            raptor_offense_percentile = min(1.0, max(0.0, (raptor_offense + 5) / 10))
            shooting_metrics.append((raptor_offense_percentile, 0.3))  # 30% weight

        # Use TS% (True Shooting Percentage)
        if "TS_PCT" in metrics and "TS_PCT" in league_stats:
            ts_pct = metrics["TS_PCT"]
            ts_pct_percentile = calculate_percentile(ts_pct, league_stats["TS_PCT"])
            shooting_metrics.append((ts_pct_percentile, 0.3))  # 30% weight

        # Use 3PT% (Three-Point Percentage)
        if "FG3_PCT" in basic_stats and "FG3_PCT" in league_stats:
            fg3_pct = basic_stats["FG3_PCT"]
            fg3_pct_percentile = calculate_percentile(fg3_pct, league_stats["FG3_PCT"])
            shooting_metrics.append((fg3_pct_percentile, 0.4))  # 40% weight

        if shooting_metrics:
            skill_percentiles["perimeter_shooting"] = sum(pct * weight for pct, weight in shooting_metrics) / sum(weight for _, weight in shooting_metrics)
        else:
            skill_percentiles["perimeter_shooting"] = 0.5  # Default to average

        # 2. Interior Scoring
        interior_metrics = []

        # Use FG% (Field Goal Percentage)
        if "FG_PCT" in basic_stats and "FG_PCT" in league_stats:
            fg_pct = basic_stats["FG_PCT"]
            fg_pct_percentile = calculate_percentile(fg_pct, league_stats["FG_PCT"])
            interior_metrics.append((fg_pct_percentile, 0.4))  # 40% weight

        # Use points in the paint (estimated from total points and position)
        if "PTS" in basic_stats and "PTS" in league_stats:
            pts = basic_stats["PTS"]
            pts_percentile = calculate_percentile(pts, league_stats["PTS"])

            # Adjust based on position (centers and power forwards score more in the paint)
            position = metrics.get("POSITION_CATEGORY", "SF")
            position_factor = 1.0
            if position in ["C", "PF"]:
                position_factor = 1.2
            elif position in ["PG", "SG"]:
                position_factor = 0.8

            interior_metrics.append((pts_percentile * position_factor, 0.6))  # 60% weight

        if interior_metrics:
            skill_percentiles["interior_scoring"] = min(1.0, sum(pct * weight for pct, weight in interior_metrics) / sum(weight for _, weight in interior_metrics))
        else:
            skill_percentiles["interior_scoring"] = 0.5  # Default to average

        # 3. Playmaking
        playmaking_metrics = []

        # Use assists
        if "AST" in basic_stats and "AST" in league_stats:
            ast = basic_stats["AST"]
            ast_percentile = calculate_percentile(ast, league_stats["AST"])
            playmaking_metrics.append((ast_percentile, 0.4))  # 40% weight

        # Use assist percentage
        if "AST_PCT" in metrics and "AST_PCT" in league_stats:
            ast_pct = metrics["AST_PCT"]
            ast_pct_percentile = calculate_percentile(ast_pct, league_stats["AST_PCT"])
            playmaking_metrics.append((ast_pct_percentile, 0.4))  # 40% weight

        # Use assist-to-turnover ratio
        if "AST" in basic_stats and "TOV" in basic_stats:
            ast = basic_stats["AST"]
            tov = basic_stats["TOV"]
            ast_to = ast / tov if tov > 0 else ast

            if "AST_TO" in league_stats:
                ast_to_percentile = calculate_percentile(ast_to, league_stats["AST_TO"])
                playmaking_metrics.append((ast_to_percentile, 0.2))  # 20% weight

        if playmaking_metrics:
            skill_percentiles["playmaking"] = sum(pct * weight for pct, weight in playmaking_metrics) / sum(weight for _, weight in playmaking_metrics)
        else:
            skill_percentiles["playmaking"] = 0.5  # Default to average

        # 4. Perimeter Defense
        perimeter_def_metrics = []

        # Use RAPTOR defense component if available
        if "RAPTOR_DEFENSE" in metrics:
            raptor_defense = metrics["RAPTOR_DEFENSE"]
            # Convert to percentile (RAPTOR typically ranges from -5 to +5)
            raptor_defense_percentile = min(1.0, max(0.0, (raptor_defense + 5) / 10))
            perimeter_def_metrics.append((raptor_defense_percentile, 0.4))  # 40% weight

        # Use steals
        if "STL" in basic_stats and "STL" in league_stats:
            stl = basic_stats["STL"]
            stl_percentile = calculate_percentile(stl, league_stats["STL"])
            perimeter_def_metrics.append((stl_percentile, 0.4))  # 40% weight

        # Use defensive rating (lower is better)
        if "DRTG" in metrics and "DRTG" in league_stats:
            drtg = metrics["DRTG"]
            # Invert percentile since lower DRTG is better
            drtg_percentile = 1.0 - calculate_percentile(drtg, league_stats["DRTG"])
            perimeter_def_metrics.append((drtg_percentile, 0.2))  # 20% weight

        if perimeter_def_metrics:
            skill_percentiles["perimeter_defense"] = sum(pct * weight for pct, weight in perimeter_def_metrics) / sum(weight for _, weight in perimeter_def_metrics)
        else:
            skill_percentiles["perimeter_defense"] = 0.5  # Default to average

        # 5. Interior Defense
        interior_def_metrics = []

        # Use RAPTOR defense component if available
        if "RAPTOR_DEFENSE" in metrics:
            raptor_defense = metrics["RAPTOR_DEFENSE"]
            # Convert to percentile (RAPTOR typically ranges from -5 to +5)
            raptor_defense_percentile = min(1.0, max(0.0, (raptor_defense + 5) / 10))
            interior_def_metrics.append((raptor_defense_percentile, 0.3))  # 30% weight

        # Use blocks
        if "BLK" in basic_stats and "BLK" in league_stats:
            blk = basic_stats["BLK"]
            blk_percentile = calculate_percentile(blk, league_stats["BLK"])
            interior_def_metrics.append((blk_percentile, 0.4))  # 40% weight

        # Use defensive rebounding
        if "DREB_PCT" in metrics and "DREB_PCT" in league_stats:
            dreb_pct = metrics["DREB_PCT"]
            dreb_pct_percentile = calculate_percentile(dreb_pct, league_stats["DREB_PCT"])
            interior_def_metrics.append((dreb_pct_percentile, 0.3))  # 30% weight

        if interior_def_metrics:
            skill_percentiles["interior_defense"] = sum(pct * weight for pct, weight in interior_def_metrics) / sum(weight for _, weight in interior_def_metrics)
        else:
            skill_percentiles["interior_defense"] = 0.5  # Default to average

        # 6. Rebounding
        rebounding_metrics = []

        # Use total rebounds
        if "REB" in basic_stats and "REB" in league_stats:
            reb = basic_stats["REB"]
            reb_percentile = calculate_percentile(reb, league_stats["REB"])
            rebounding_metrics.append((reb_percentile, 0.3))  # 30% weight

        # Use rebound percentage
        if "REB_PCT" in metrics and "REB_PCT" in league_stats:
            reb_pct = metrics["REB_PCT"]
            reb_pct_percentile = calculate_percentile(reb_pct, league_stats["REB_PCT"])
            rebounding_metrics.append((reb_pct_percentile, 0.3))  # 30% weight

        # Use offensive rebounding
        if "OREB_PCT" in metrics and "OREB_PCT" in league_stats:
            oreb_pct = metrics["OREB_PCT"]
            oreb_pct_percentile = calculate_percentile(oreb_pct, league_stats["OREB_PCT"])
            rebounding_metrics.append((oreb_pct_percentile, 0.2))  # 20% weight

        # Use defensive rebounding
        if "DREB_PCT" in metrics and "DREB_PCT" in league_stats:
            dreb_pct = metrics["DREB_PCT"]
            dreb_pct_percentile = calculate_percentile(dreb_pct, league_stats["DREB_PCT"])
            rebounding_metrics.append((dreb_pct_percentile, 0.2))  # 20% weight

        if rebounding_metrics:
            skill_percentiles["rebounding"] = sum(pct * weight for pct, weight in rebounding_metrics) / sum(weight for _, weight in rebounding_metrics)
        else:
            skill_percentiles["rebounding"] = 0.5  # Default to average

        # 7. Off-Ball Movement (harder to measure directly)
        offball_metrics = []

        # Use true shooting percentage as a proxy
        if "TS_PCT" in metrics and "TS_PCT" in league_stats:
            ts_pct = metrics["TS_PCT"]
            ts_pct_percentile = calculate_percentile(ts_pct, league_stats["TS_PCT"])
            offball_metrics.append((ts_pct_percentile, 0.5))  # 50% weight

        # Use offensive rating
        if "ORTG" in metrics and "ORTG" in league_stats:
            ortg = metrics["ORTG"]
            ortg_percentile = calculate_percentile(ortg, league_stats["ORTG"])
            offball_metrics.append((ortg_percentile, 0.5))  # 50% weight

        if offball_metrics:
            skill_percentiles["off_ball_movement"] = sum(pct * weight for pct, weight in offball_metrics) / sum(weight for _, weight in offball_metrics)
        else:
            skill_percentiles["off_ball_movement"] = 0.5  # Default to average

        # 8. Hustle (combination of steals, blocks, offensive rebounds)
        hustle_metrics = []

        # Use steals
        if "STL" in basic_stats and "STL" in league_stats:
            stl = basic_stats["STL"]
            stl_percentile = calculate_percentile(stl, league_stats["STL"])
            hustle_metrics.append((stl_percentile, 0.3))  # 30% weight

        # Use blocks
        if "BLK" in basic_stats and "BLK" in league_stats:
            blk = basic_stats["BLK"]
            blk_percentile = calculate_percentile(blk, league_stats["BLK"])
            hustle_metrics.append((blk_percentile, 0.3))  # 30% weight

        # Use offensive rebounding
        if "OREB_PCT" in metrics and "OREB_PCT" in league_stats:
            oreb_pct = metrics["OREB_PCT"]
            oreb_pct_percentile = calculate_percentile(oreb_pct, league_stats["OREB_PCT"])
            hustle_metrics.append((oreb_pct_percentile, 0.4))  # 40% weight

        if hustle_metrics:
            skill_percentiles["hustle"] = sum(pct * weight for pct, weight in hustle_metrics) / sum(weight for _, weight in hustle_metrics)
        else:
            skill_percentiles["hustle"] = 0.5  # Default to average

        # 9. Versatility (based on all-around contributions)
        versatility_metrics = []

        # Use points
        if "PTS" in basic_stats and "PTS" in league_stats:
            pts = basic_stats["PTS"]
            pts_percentile = calculate_percentile(pts, league_stats["PTS"])
            versatility_metrics.append((pts_percentile, 0.2))  # 20% weight

        # Use assists
        if "AST" in basic_stats and "AST" in league_stats:
            ast = basic_stats["AST"]
            ast_percentile = calculate_percentile(ast, league_stats["AST"])
            versatility_metrics.append((ast_percentile, 0.2))  # 20% weight

        # Use rebounds
        if "REB" in basic_stats and "REB" in league_stats:
            reb = basic_stats["REB"]
            reb_percentile = calculate_percentile(reb, league_stats["REB"])
            versatility_metrics.append((reb_percentile, 0.2))  # 20% weight

        # Use steals
        if "STL" in basic_stats and "STL" in league_stats:
            stl = basic_stats["STL"]
            stl_percentile = calculate_percentile(stl, league_stats["STL"])
            versatility_metrics.append((stl_percentile, 0.2))  # 20% weight

        # Use blocks
        if "BLK" in basic_stats and "BLK" in league_stats:
            blk = basic_stats["BLK"]
            blk_percentile = calculate_percentile(blk, league_stats["BLK"])
            versatility_metrics.append((blk_percentile, 0.2))  # 20% weight

        if versatility_metrics:
            # For versatility, we want to reward balanced contributions
            # Calculate the base percentile
            base_percentile = sum(pct * weight for pct, weight in versatility_metrics) / sum(weight for _, weight in versatility_metrics)

            # Calculate the standard deviation of percentiles (lower = more balanced)
            percentiles = [pct for pct, _ in versatility_metrics]
            std_dev = np.std(percentiles) if len(percentiles) > 1 else 0

            # Apply a balance bonus (higher for more balanced players)
            balance_factor = max(0, 1 - std_dev)
            skill_percentiles["versatility"] = base_percentile * (0.7 + 0.3 * balance_factor)
        else:
            skill_percentiles["versatility"] = 0.5  # Default to average

        # Convert percentiles to letter grades
        for skill, percentile in skill_percentiles.items():
            for grade, threshold in sorted(grade_thresholds.items(), key=lambda x: x[1], reverse=True):
                if percentile >= threshold:
                    grades[skill] = grade
                    break

            # Ensure every skill has a grade
            if skill not in grades:
                grades[skill] = 'F'

        return grades

    except Exception as e:
        logger.error(f"Error generating skill grades for player {player_id}: {str(e)}", exc_info=True)
        # Return default grades if there's an error
        return {
            "perimeter_shooting": "C",
            "interior_scoring": "C",
            "playmaking": "C",
            "perimeter_defense": "C",
            "interior_defense": "C",
            "rebounding": "C",
            "off_ball_movement": "C",
            "hustle": "C",
            "versatility": "C"
        }

def calculate_percentile(value: float, distribution: List[float]) -> float:
    """
    Calculate the percentile of a value within a distribution.

    Args:
        value: The value to find the percentile for
        distribution: List of values representing the distribution

    Returns:
        Percentile as a float between 0 and 1
    """
    if not distribution:
        return 0.5  # Default to 50th percentile if no distribution

    # Count how many values in the distribution are less than or equal to the given value
    count = sum(1 for x in distribution if x <= value)

    # Calculate percentile
    percentile = count / len(distribution)

    return percentile

def get_league_stats_for_percentiles() -> Dict[str, List[float]]:
    """
    Get league-wide statistics for calculating percentiles.
    Uses cached data or fetches from the NBA API.

    Returns:
        Dictionary mapping stat names to lists of values across the league
    """
    # Check if we have cached league stats
    cache_file = os.path.join(CACHE_DIR, "league_stats.json")

    # Try to load from cache first
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                # Check if cache is recent enough (1 day)
                cache_time = os.path.getmtime(cache_file)
                if (time.time() - cache_time) < 86400:  # 1 day in seconds
                    return cached_data
        except Exception as e:
            logger.warning(f"Error reading league stats cache: {str(e)}")

    try:
        # Fetch basic stats
        def fetch_basic_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season=settings.CURRENT_NBA_SEASON,
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Base',
                per_mode_detailed='PerGame',
            )

        basic_stats = retry_on_timeout(fetch_basic_stats)
        basic_df = basic_stats.get_data_frames()[0]

        # Fetch advanced stats
        def fetch_advanced_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season="2023-24",  # Current season
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Advanced',
                per_mode_detailed='PerGame',
            )

        advanced_stats = retry_on_timeout(fetch_advanced_stats)
        advanced_df = advanced_stats.get_data_frames()[0]

        # Combine the dataframes on PLAYER_ID
        merged_df = pd.merge(basic_df, advanced_df, on='PLAYER_ID', suffixes=('', '_ADV'))

        # Extract the stats we need for percentiles
        league_stats = {}

        # Basic stats
        basic_stat_columns = [
            'PTS', 'AST', 'REB', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT'
        ]

        for col in basic_stat_columns:
            if col in merged_df.columns:
                league_stats[col] = merged_df[col].dropna().tolist()

        # Advanced stats
        advanced_stat_columns = [
            'TS_PCT', 'USG_PCT', 'AST_PCT', 'REB_PCT', 'OREB_PCT', 'DREB_PCT',
            'PACE', 'PIE', 'OFF_RATING', 'DEF_RATING'
        ]

        for col in advanced_stat_columns:
            if col in merged_df.columns:
                league_stats[col] = merged_df[col].dropna().tolist()

        # Calculate additional metrics
        if 'AST' in merged_df.columns and 'TOV' in merged_df.columns:
            # Assist to turnover ratio
            merged_df['AST_TO'] = merged_df.apply(
                lambda row: row['AST'] / row['TOV'] if row['TOV'] > 0 else row['AST'], axis=1
            )
            league_stats['AST_TO'] = merged_df['AST_TO'].dropna().tolist()

        # Rename some columns for consistency
        if 'OFF_RATING' in league_stats:
            league_stats['ORTG'] = league_stats['OFF_RATING']
        if 'DEF_RATING' in league_stats:
            league_stats['DRTG'] = league_stats['DEF_RATING']

        # Cache the league stats
        try:
            with open(cache_file, 'w') as f:
                json.dump(league_stats, f)
        except Exception as e:
            logger.warning(f"Error caching league stats: {str(e)}")

        return league_stats

    except Exception as e:
        logger.error(f"Error fetching league stats: {str(e)}", exc_info=True)
        return {}
