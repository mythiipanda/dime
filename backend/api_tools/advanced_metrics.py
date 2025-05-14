"""
Advanced metrics module for NBA player analysis.
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from nba_api.stats.endpoints import playerestimatedmetrics, leaguedashplayerstats, playerawards, playercareerstats
from nba_api.stats.static import players
from config import settings
from api_tools.utils import retry_on_timeout, format_response, get_player_id_from_name
import os

# Import our RAPTOR metrics implementation
try:
    from api_tools.raptor_metrics import get_player_raptor_metrics, generate_skill_grades
    RAPTOR_AVAILABLE = True
except ImportError:
    RAPTOR_AVAILABLE = False
    logging.warning("RAPTOR metrics module not available. Using fallback metrics.")

# Path to cache directory for historical player data
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Award point values for achievements
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

logger = logging.getLogger(__name__)

def fetch_player_advanced_analysis_logic(player_name: str, season: Optional[str] = None) -> str:
    """
    Fetches advanced metrics, skill grades, and similar players for a specified player.

    Args:
        player_name (str): The full name of the player to analyze.
        season (str, optional): The NBA season in format YYYY-YY (e.g., "2023-24").
            If None, uses the current season.

    Returns:
        str: JSON string containing advanced metrics, skill grades, and similar players.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "advanced_metrics": {
                     "RAPTOR_OFFENSE": float,
                     "RAPTOR_DEFENSE": float,
                     "RAPTOR_TOTAL": float,
                     "WAR": float,
                     "ELO_RATING": float,
                     // ... other advanced metrics
                 },
                 "skill_grades": {
                     "perimeter_shooting": str, // A+, A, A-, B+, B, etc.
                     "interior_scoring": str,
                     // ... other skill grades
                 },
                 "similar_players": [
                     {"player_id": int, "player_name": str, "similarity_score": float},
                     // ... other similar players
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    try:
        # Get player ID
        player_id_result = get_player_id_from_name(player_name)
        if isinstance(player_id_result, dict) and 'error' in player_id_result:
            return json.dumps(player_id_result)

        player_id = player_id_result

        # Find the player's official name
        all_players = players.get_players()
        for p in all_players:
            if p['id'] == player_id:
                player_name = p['full_name']  # Use the official name from the API
                break

        # Get current season if not provided
        if not season:
            # In a real implementation, you would determine the current season
            # For now, we'll use a hardcoded value
            season = settings.CURRENT_NBA_SEASON

        # Use RAPTOR metrics if available
        if RAPTOR_AVAILABLE:
            try:
                # Get RAPTOR metrics
                raptor_metrics = get_player_raptor_metrics(player_id, season)

                # Log the RAPTOR metrics for debugging
                logger.info(f"RAPTOR metrics for {player_name}: {raptor_metrics}")

                # Get basic stats for skill grades
                basic_stats = {}

                # Fetch basic stats
                def fetch_basic_stats():
                    return leaguedashplayerstats.LeagueDashPlayerStats(
                        season=season,
                        season_type_all_star='Regular Season',
                        measure_type_detailed_defense='Base',
                        per_mode_detailed='PerGame'
                    )

                basic_stats_data = retry_on_timeout(fetch_basic_stats)
                basic_stats_df = basic_stats_data.get_data_frames()[0]

                if not basic_stats_df.empty:
                    # Filter to find the player in the dataframe
                    player_stats = basic_stats_df[basic_stats_df['PLAYER_ID'] == player_id]
                    if not player_stats.empty:
                        basic_stats = player_stats.iloc[0].to_dict()
                        logger.info(f"Found basic stats for player ID {player_id}")
                    else:
                        logger.warning(f"Player ID {player_id} not found in basic stats dataframe")

                # Generate skill grades
                try:
                    skill_grades = generate_skill_grades(player_id, raptor_metrics, basic_stats)
                    logger.info(f"Skill grades for {player_name}: {skill_grades}")
                except Exception as e:
                    logger.error(f"Error generating skill grades for {player_name}: {str(e)}")
                    # Fallback to default skill grades
                    skill_grades = {
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

                # Find similar players
                try:
                    similar_players = find_similar_players(player_id, raptor_metrics, season)
                except Exception as e:
                    logger.error(f"Error finding similar players for {player_name}: {str(e)}")
                    # Fallback to empty similar players list
                    similar_players = []

                # Ensure the metrics use the correct keys that the frontend expects
                # Map RAPTOR_OFFENSE to RAPTOR_OFFENSE and RAPTOR_OFF for backward compatibility
                if 'RAPTOR_OFFENSE' in raptor_metrics:
                    raptor_metrics['RAPTOR_OFF'] = raptor_metrics['RAPTOR_OFFENSE']

                # Map RAPTOR_DEFENSE to RAPTOR_DEFENSE and RAPTOR_DEF for backward compatibility
                if 'RAPTOR_DEFENSE' in raptor_metrics:
                    raptor_metrics['RAPTOR_DEF'] = raptor_metrics['RAPTOR_DEFENSE']

                # Map RAPTOR_TOTAL to RAPTOR for backward compatibility
                if 'RAPTOR_TOTAL' in raptor_metrics:
                    raptor_metrics['RAPTOR'] = raptor_metrics['RAPTOR_TOTAL']

                # Map WAR to PLAYER_VALUE for backward compatibility
                if 'WAR' in raptor_metrics:
                    raptor_metrics['PLAYER_VALUE'] = raptor_metrics['WAR']

                result = {
                    "player_name": player_name,
                    "player_id": player_id,
                    "advanced_metrics": raptor_metrics,
                    "skill_grades": skill_grades,
                    "similar_players": similar_players
                }

                return format_response(result)

            except Exception as e:
                logger.warning(f"Error using RAPTOR metrics for {player_name}: {str(e)}. Falling back to standard metrics.")
                # Fall back to standard metrics if RAPTOR fails

        # Fallback to standard metrics
        # Fetch player estimated metrics
        advanced_metrics = fetch_player_estimated_metrics(player_id, season)

        # Fetch additional advanced stats
        additional_metrics = fetch_player_advanced_stats(player_id, season)

        # Combine metrics
        combined_metrics = {**advanced_metrics, **additional_metrics}

        # Generate skill grades based on the metrics
        skill_grades = generate_skill_grades_legacy(combined_metrics)

        # Find similar players
        similar_players = find_similar_players(player_id, combined_metrics, season)

        result = {
            "player_name": player_name,
            "player_id": player_id,
            "advanced_metrics": combined_metrics,
            "skill_grades": skill_grades,
            "similar_players": similar_players
        }

        return format_response(result)

    except Exception as e:
        logger.error(f"Error in fetch_player_advanced_analysis_logic for {player_name}: {str(e)}", exc_info=True)
        return format_response({"error": f"Failed to fetch advanced metrics for {player_name}: {str(e)}"})

def fetch_player_estimated_metrics(player_id: int, season: str) -> Dict[str, float]:
    """Fetch player estimated metrics from the NBA API."""
    try:
        def fetch_metrics():
            return playerestimatedmetrics.PlayerEstimatedMetrics(
                league_id='00',
                season=season,
                season_type='Regular Season'
            )

        metrics_data = retry_on_timeout(fetch_metrics)
        metrics_df = metrics_data.get_data_frames()[0]

        # Find the player in the dataframe
        player_metrics = metrics_df[metrics_df['PLAYER_ID'] == player_id]

        # Debug log to check if player is found
        if player_metrics.empty:
            logger.warning(f"Player ID {player_id} not found in playerestimatedmetrics data")
        else:
            logger.info(f"Found player ID {player_id} in playerestimatedmetrics data")

        if player_metrics.empty:
            logger.warning(f"No estimated metrics found for player ID {player_id} in season {season}")
            return {}

        # Extract the metrics we want
        metrics = {
            "E_OFF_RATING": float(player_metrics['E_OFF_RATING'].iloc[0]),
            "E_DEF_RATING": float(player_metrics['E_DEF_RATING'].iloc[0]),
            "E_NET_RATING": float(player_metrics['E_NET_RATING'].iloc[0]),
            "E_AST_RATIO": float(player_metrics['E_AST_RATIO'].iloc[0]),
            "E_OREB_PCT": float(player_metrics['E_OREB_PCT'].iloc[0]),
            "E_DREB_PCT": float(player_metrics['E_DREB_PCT'].iloc[0]),
            "E_REB_PCT": float(player_metrics['E_REB_PCT'].iloc[0]),
            "E_TOV_PCT": float(player_metrics['E_TOV_PCT'].iloc[0]),
            "E_USG_PCT": float(player_metrics['E_USG_PCT'].iloc[0]),
            "E_PACE": float(player_metrics['E_PACE'].iloc[0]),
        }

        # Map to our standardized metric names
        return {
            "ORTG": metrics["E_OFF_RATING"],
            "DRTG": metrics["E_DEF_RATING"],
            "NETRTG": metrics["E_NET_RATING"],
            "AST_PCT": metrics["E_AST_RATIO"],
            "OREB_PCT": metrics["E_OREB_PCT"],
            "DREB_PCT": metrics["E_DREB_PCT"],
            "REB_PCT": metrics["E_REB_PCT"],
            "TOV_PCT": metrics["E_TOV_PCT"],
            "USG_PCT": metrics["E_USG_PCT"],
            "PACE": metrics["E_PACE"],
        }

    except Exception as e:
        logger.error(f"Error fetching estimated metrics for player ID {player_id}: {str(e)}", exc_info=True)
        return {}

def fetch_player_advanced_stats(player_id: int, season: str) -> Dict[str, float]:
    """Fetch advanced stats from the NBA API."""
    try:
        def fetch_advanced_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Advanced',
                per_mode_detailed='PerGame',
                last_n_games=0,
                month=0,
                opponent_team_id=0,
                period=0,
                pace_adjust='N',
                plus_minus='N',
                rank='N'
            )

        advanced_data = retry_on_timeout(fetch_advanced_stats)
        advanced_df = advanced_data.get_data_frames()[0]

        # Find the player in the dataframe
        player_advanced = advanced_df[advanced_df['PLAYER_ID'] == player_id]

        # Debug log to check if player is found
        if player_advanced.empty:
            logger.warning(f"Player ID {player_id} not found in advanced stats data")
        else:
            logger.info(f"Found player ID {player_id} in advanced stats data")

        if advanced_df.empty:
            logger.warning(f"No advanced stats found for player ID {player_id} in season {season}")
            return {}

        # Extract the metrics we want
        # Note: The actual column names may vary, this is an example
        # You'll need to check the actual column names in the dataframe
        metrics = {}

        # Map common advanced metrics if they exist in the dataframe
        metric_mappings = {
            "PER": "PER",
            "TS_PCT": "TS_PCT",
            "USG_PCT": "USG_PCT",
            "BPM": "BPM",
            "VORP": "VORP",
            "WS": "WS",
            "WS_PER_48": "WS_PER_48",
            "PACE": "PACE",
            "PIE": "PIE",
            "POSS": "POSS",
        }

        # Use player-specific data if available
        if not player_advanced.empty:
            for api_name, our_name in metric_mappings.items():
                if api_name in player_advanced.columns:
                    metrics[our_name] = float(player_advanced[api_name].iloc[0])
        else:
            # Fallback to first row if player not found (should be fixed)
            logger.warning(f"Using fallback method for advanced stats for player ID {player_id}")
            for api_name, our_name in metric_mappings.items():
                if api_name in advanced_df.columns:
                    metrics[our_name] = float(advanced_df[api_name].iloc[0])

        # Calculate our own advanced metrics based on real NBA data

        # NBA PLUS - Our own player rating system (similar to 538's RAPTOR but using available NBA stats)
        # Base calculation using Player Impact Estimate (PIE) and other available metrics

        # Offensive Rating (0-100 scale)
        off_rating = 0
        if "ORTG" in metrics:
            # Scale ORTG to a 0-100 rating (league average ORTG is typically around 110-115)
            off_rating = min(100, max(0, (metrics["ORTG"] - 85) * 100 / 40))
        elif "PIE" in metrics:
            # Fallback to PIE for offensive contribution
            off_rating = min(100, max(0, metrics.get("PIE", 0) * 100 * 2))

        # Defensive Rating (0-100 scale)
        def_rating = 0
        if "DRTG" in metrics:
            # Scale DRTG to a 0-100 rating (lower DRTG is better, typical range 100-120)
            def_rating = min(100, max(0, (130 - metrics["DRTG"]) * 100 / 40))
        elif "PIE" in metrics:
            # Fallback to PIE for defensive contribution
            def_rating = min(100, max(0, metrics.get("PIE", 0) * 100 * 1.5))

        # Overall Rating (0-100 scale)
        overall_rating = (off_rating * 0.6) + (def_rating * 0.4)

        # Convert to a +/- scale similar to other advanced metrics
        metrics["NBA_PLUS"] = round((overall_rating - 50) / 5, 1)  # -10 to +10 scale
        metrics["NBA_PLUS_OFF"] = round((off_rating - 50) / 5, 1)
        metrics["NBA_PLUS_DEF"] = round((def_rating - 50) / 5, 1)

        # ELO Rating (1000-2000 scale, similar to 538's player ratings)
        # This incorporates historical data and current season performance
        try:
            # Get historical data for the player
            historical_data = get_historical_player_data(player_id)

            # Base ELO starts at 1500 (average player)
            base_elo = 1500

            # Current season performance (from PIE or overall rating)
            current_season_bonus = 0
            if "PIE" in metrics:
                # PIE typically ranges from 0 to 0.2 for most players
                current_season_bonus = metrics["PIE"] * 1000  # Reduced weight from 2000 to 1000
            else:
                current_season_bonus = (overall_rating - 50) * 5  # Reduced weight from 10 to 5

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

                # Combine all historical factors
                historical_bonus = longevity_bonus + achievements_bonus + career_stats_bonus

                # Scale historical bonus (max +300)
                historical_bonus = min(300, historical_bonus)

            # Calculate final ELO rating
            # 60% current season, 40% historical performance
            metrics["ELO_RATING"] = round(base_elo + (current_season_bonus * 0.6) + (historical_bonus * 0.4), 0)

            # Add historical components for reference
            metrics["ELO_CURRENT"] = round(base_elo + current_season_bonus, 0)
            metrics["ELO_HISTORICAL"] = round(base_elo + historical_bonus, 0)

        except Exception as e:
            logger.error(f"Error calculating ELO rating: {str(e)}")
            # Fallback to simple calculation
            if "PIE" in metrics:
                metrics["ELO_RATING"] = round(base_elo + metrics["PIE"] * 2000, 0)
            else:
                metrics["ELO_RATING"] = round(base_elo + (overall_rating - 50) * 10, 0)

        # Player Value (similar to WAR/VORP concepts)
        if "VORP" in metrics:
            metrics["PLAYER_VALUE"] = round(metrics["VORP"], 1)
        elif "WS" in metrics:
            metrics["PLAYER_VALUE"] = round(metrics["WS"] / 2.5, 1)
        else:
            metrics["PLAYER_VALUE"] = round(metrics.get("PIE", 0) * 10, 1)

        return metrics

    except Exception as e:
        logger.error(f"Error fetching advanced stats for player ID {player_id}: {str(e)}", exc_info=True)
        return {}

def generate_skill_grades_legacy(metrics: Dict[str, float]) -> Dict[str, str]:
    """
    Legacy function to generate skill grades based on actual league-wide statistics and percentiles.
    Uses real NBA data to calculate percentile rankings for each skill.

    Note: This is a fallback method used when the RAPTOR metrics module is not available.
    """
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
        if "TS_PCT" in metrics and "TS_PCT" in league_stats:
            ts_pct_percentile = calculate_percentile(metrics["TS_PCT"], league_stats["TS_PCT"])
            shooting_metrics.append((ts_pct_percentile, 0.5))  # 50% weight

        if "FG3_PCT" in metrics and "FG3_PCT" in league_stats:
            fg3_pct_percentile = calculate_percentile(metrics["FG3_PCT"], league_stats["FG3_PCT"])
            shooting_metrics.append((fg3_pct_percentile, 0.5))  # 50% weight

        if shooting_metrics:
            skill_percentiles["perimeter_shooting"] = sum(pct * weight for pct, weight in shooting_metrics) / sum(weight for _, weight in shooting_metrics)
        else:
            skill_percentiles["perimeter_shooting"] = 0.0

        # 2. Interior Scoring
        interior_metrics = []
        if "FG_PCT" in metrics and "FG_PCT" in league_stats:
            fg_pct_percentile = calculate_percentile(metrics["FG_PCT"], league_stats["FG_PCT"])
            interior_metrics.append((fg_pct_percentile, 0.4))  # 40% weight

        if "FG2_PCT" in metrics and "FG2_PCT" in league_stats:
            fg2_pct_percentile = calculate_percentile(metrics["FG2_PCT"], league_stats["FG2_PCT"])
            interior_metrics.append((fg2_pct_percentile, 0.6))  # 60% weight

        if interior_metrics:
            skill_percentiles["interior_scoring"] = sum(pct * weight for pct, weight in interior_metrics) / sum(weight for _, weight in interior_metrics)
        else:
            skill_percentiles["interior_scoring"] = 0.0

        # 3. Playmaking
        playmaking_metrics = []
        if "AST" in metrics and "AST" in league_stats:
            ast_percentile = calculate_percentile(metrics["AST"], league_stats["AST"])
            playmaking_metrics.append((ast_percentile, 0.4))  # 40% weight

        if "AST_PCT" in metrics and "AST_PCT" in league_stats:
            ast_pct_percentile = calculate_percentile(metrics["AST_PCT"], league_stats["AST_PCT"])
            playmaking_metrics.append((ast_pct_percentile, 0.4))  # 40% weight

        if "AST_TO" in metrics and "AST_TO" in league_stats:
            ast_to_percentile = calculate_percentile(metrics["AST_TO"], league_stats["AST_TO"])
            playmaking_metrics.append((ast_to_percentile, 0.2))  # 20% weight

        if playmaking_metrics:
            skill_percentiles["playmaking"] = sum(pct * weight for pct, weight in playmaking_metrics) / sum(weight for _, weight in playmaking_metrics)
        else:
            skill_percentiles["playmaking"] = 0.0

        # 4. Perimeter Defense
        perimeter_def_metrics = []
        if "STL" in metrics and "STL" in league_stats:
            stl_percentile = calculate_percentile(metrics["STL"], league_stats["STL"])
            perimeter_def_metrics.append((stl_percentile, 0.5))  # 50% weight

        if "DRTG" in metrics and "DRTG" in league_stats:
            # For DRTG, lower is better, so we invert the percentile
            drtg_percentile = 1.0 - calculate_percentile(metrics["DRTG"], league_stats["DRTG"])
            perimeter_def_metrics.append((drtg_percentile, 0.5))  # 50% weight

        if perimeter_def_metrics:
            skill_percentiles["perimeter_defense"] = sum(pct * weight for pct, weight in perimeter_def_metrics) / sum(weight for _, weight in perimeter_def_metrics)
        else:
            skill_percentiles["perimeter_defense"] = 0.0

        # 5. Interior Defense
        interior_def_metrics = []
        if "BLK" in metrics and "BLK" in league_stats:
            blk_percentile = calculate_percentile(metrics["BLK"], league_stats["BLK"])
            interior_def_metrics.append((blk_percentile, 0.5))  # 50% weight

        if "DRTG" in metrics and "DRTG" in league_stats:
            # For DRTG, lower is better, so we invert the percentile
            drtg_percentile = 1.0 - calculate_percentile(metrics["DRTG"], league_stats["DRTG"])
            interior_def_metrics.append((drtg_percentile, 0.5))  # 50% weight

        if interior_def_metrics:
            skill_percentiles["interior_defense"] = sum(pct * weight for pct, weight in interior_def_metrics) / sum(weight for _, weight in interior_def_metrics)
        else:
            skill_percentiles["interior_defense"] = 0.0

        # 6. Rebounding
        rebounding_metrics = []
        if "REB" in metrics and "REB" in league_stats:
            reb_percentile = calculate_percentile(metrics["REB"], league_stats["REB"])
            rebounding_metrics.append((reb_percentile, 0.3))  # 30% weight

        if "REB_PCT" in metrics and "REB_PCT" in league_stats:
            reb_pct_percentile = calculate_percentile(metrics["REB_PCT"], league_stats["REB_PCT"])
            rebounding_metrics.append((reb_pct_percentile, 0.3))  # 30% weight

        if "OREB_PCT" in metrics and "OREB_PCT" in league_stats:
            oreb_pct_percentile = calculate_percentile(metrics["OREB_PCT"], league_stats["OREB_PCT"])
            rebounding_metrics.append((oreb_pct_percentile, 0.2))  # 20% weight

        if "DREB_PCT" in metrics and "DREB_PCT" in league_stats:
            dreb_pct_percentile = calculate_percentile(metrics["DREB_PCT"], league_stats["DREB_PCT"])
            rebounding_metrics.append((dreb_pct_percentile, 0.2))  # 20% weight

        if rebounding_metrics:
            skill_percentiles["rebounding"] = sum(pct * weight for pct, weight in rebounding_metrics) / sum(weight for _, weight in rebounding_metrics)
        else:
            skill_percentiles["rebounding"] = 0.0

        # 7. Off-Ball Movement (harder to measure directly)
        # We'll use a combination of shooting efficiency and offensive metrics
        offball_metrics = []
        if "TS_PCT" in metrics and "TS_PCT" in league_stats:
            ts_pct_percentile = calculate_percentile(metrics["TS_PCT"], league_stats["TS_PCT"])
            offball_metrics.append((ts_pct_percentile, 0.5))  # 50% weight

        if "ORTG" in metrics and "ORTG" in league_stats:
            ortg_percentile = calculate_percentile(metrics["ORTG"], league_stats["ORTG"])
            offball_metrics.append((ortg_percentile, 0.5))  # 50% weight

        if offball_metrics:
            skill_percentiles["off_ball_movement"] = sum(pct * weight for pct, weight in offball_metrics) / sum(weight for _, weight in offball_metrics)
        else:
            skill_percentiles["off_ball_movement"] = 0.0

        # 8. Hustle (combination of steals, blocks, offensive rebounds)
        hustle_metrics = []
        if "STL" in metrics and "STL" in league_stats:
            stl_percentile = calculate_percentile(metrics["STL"], league_stats["STL"])
            hustle_metrics.append((stl_percentile, 0.3))  # 30% weight

        if "BLK" in metrics and "BLK" in league_stats:
            blk_percentile = calculate_percentile(metrics["BLK"], league_stats["BLK"])
            hustle_metrics.append((blk_percentile, 0.3))  # 30% weight

        if "OREB_PCT" in metrics and "OREB_PCT" in league_stats:
            oreb_pct_percentile = calculate_percentile(metrics["OREB_PCT"], league_stats["OREB_PCT"])
            hustle_metrics.append((oreb_pct_percentile, 0.4))  # 40% weight

        if hustle_metrics:
            skill_percentiles["hustle"] = sum(pct * weight for pct, weight in hustle_metrics) / sum(weight for _, weight in hustle_metrics)
        else:
            skill_percentiles["hustle"] = 0.0

        # 9. Versatility (based on all-around contributions)
        versatility_metrics = []
        if "PTS" in metrics and "PTS" in league_stats:
            pts_percentile = calculate_percentile(metrics["PTS"], league_stats["PTS"])
            versatility_metrics.append((pts_percentile, 0.2))  # 20% weight

        if "AST" in metrics and "AST" in league_stats:
            ast_percentile = calculate_percentile(metrics["AST"], league_stats["AST"])
            versatility_metrics.append((ast_percentile, 0.2))  # 20% weight

        if "REB" in metrics and "REB" in league_stats:
            reb_percentile = calculate_percentile(metrics["REB"], league_stats["REB"])
            versatility_metrics.append((reb_percentile, 0.2))  # 20% weight

        if "STL" in metrics and "STL" in league_stats:
            stl_percentile = calculate_percentile(metrics["STL"], league_stats["STL"])
            versatility_metrics.append((stl_percentile, 0.2))  # 20% weight

        if "BLK" in metrics and "BLK" in league_stats:
            blk_percentile = calculate_percentile(metrics["BLK"], league_stats["BLK"])
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
            skill_percentiles["versatility"] = 0.0

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
        logger.error(f"Error generating skill grades: {str(e)}", exc_info=True)
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
                season="2023-24",  # Current season
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Base',
                per_mode_detailed='PerGame',
                last_n_games=0,
                month=0,
                opponent_team_id=0,
                period=0,
                pace_adjust='N',
                plus_minus='N',
                rank='N'
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
                last_n_games=0,
                month=0,
                opponent_team_id=0,
                period=0,
                pace_adjust='N',
                plus_minus='N',
                rank='N'
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
            'PACE', 'PIE', 'ORTG', 'DRTG'
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

        # Cache the league stats
        try:
            with open(cache_file, 'w') as f:
                json.dump(league_stats, f)
        except Exception as e:
            logger.warning(f"Error caching league stats: {str(e)}")

        return league_stats

    except Exception as e:
        logger.error(f"Error fetching league stats: {str(e)}", exc_info=True)
        # Return empty stats if there's an error
        return {}

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

        # Get advanced career stats if available
        career_per = 0
        career_ws = 0
        career_vorp = 0

        if not career_totals_df.empty:
            # Some players might not have these stats
            if 'PER' in career_totals_df.columns:
                career_per = float(career_totals_df['PER'].iloc[0])
            if 'WS' in career_totals_df.columns:
                career_ws = float(career_totals_df['WS'].iloc[0])
            if 'VORP' in career_totals_df.columns:
                career_vorp = float(career_totals_df['VORP'].iloc[0])

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

        # Compile the data
        historical_data = {
            "years_played": years_played,
            "achievements_value": achievements_value,
            "career_per": career_per,
            "career_ws": career_ws,
            "career_vorp": career_vorp
        }

        # Cache the data
        try:
            with open(cache_file, 'w') as f:
                json.dump(historical_data, f)
        except Exception as e:
            logger.warning(f"Error caching historical data for player {player_id}: {str(e)}")

        return historical_data

    except Exception as e:
        logger.error(f"Error fetching historical data for player {player_id}: {str(e)}", exc_info=True)
        return {}

def find_similar_players(player_id: int, player_metrics: Dict[str, float], season: str) -> List[Dict[str, Any]]:
    """Find players with similar statistical profiles using our NBA_PLUS metrics."""
    try:
        # Fetch all players' advanced stats
        def fetch_all_advanced_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Advanced',
                per_mode_detailed='PerGame',
                last_n_games=0,
                month=0,
                opponent_team_id=0,
                period=0,
                pace_adjust='N',
                plus_minus='N',
                rank='N'
            )

        all_stats = retry_on_timeout(fetch_all_advanced_stats)
        all_stats_df = all_stats.get_data_frames()[0]

        # Also fetch basic stats to get more comparison points
        def fetch_all_basic_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Base',
                per_mode_detailed='PerGame',
                last_n_games=0,
                month=0,
                opponent_team_id=0,
                period=0,
                pace_adjust='N',
                plus_minus='N',
                rank='N'
            )

        basic_stats = retry_on_timeout(fetch_all_basic_stats)
        basic_stats_df = basic_stats.get_data_frames()[0]

        # Merge advanced and basic stats
        merged_stats = pd.merge(
            all_stats_df,
            basic_stats_df[['PLAYER_ID', 'PTS', 'AST', 'REB', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT']],
            on='PLAYER_ID',
            how='left'
        )

        # Filter out the current player and players with minimal minutes
        other_players_df = merged_stats[(merged_stats['PLAYER_ID'] != player_id) & (merged_stats['MIN'] > 15)]

        if other_players_df.empty:
            logger.warning(f"No other players found for comparison in season {season}")
            return []

        # Get the current player's stats
        current_player_stats = merged_stats[merged_stats['PLAYER_ID'] == player_id]

        if current_player_stats.empty:
            logger.warning(f"Current player stats not found for ID {player_id}")
            return []

        # Calculate NBA_PLUS metrics for all players
        all_players_with_metrics = []

        for _, player_row in pd.concat([current_player_stats, other_players_df]).iterrows():
            player_dict = player_row.to_dict()

            # Calculate NBA_PLUS metrics
            player_metrics = {}

            # Copy existing metrics
            for key in player_dict:
                if isinstance(player_dict[key], (int, float)) and not pd.isna(player_dict[key]):
                    player_metrics[key] = float(player_dict[key])

            # Calculate offensive rating (0-100 scale)
            off_rating = 0
            if "OFFRTG" in player_metrics:
                off_rating = min(100, max(0, (player_metrics["OFFRTG"] - 85) * 100 / 40))
            elif "PIE" in player_metrics:
                off_rating = min(100, max(0, player_metrics.get("PIE", 0) * 100 * 2))

            # Calculate defensive rating (0-100 scale)
            def_rating = 0
            if "DEFRTG" in player_metrics:
                def_rating = min(100, max(0, (130 - player_metrics["DEFRTG"]) * 100 / 40))
            elif "PIE" in player_metrics:
                def_rating = min(100, max(0, player_metrics.get("PIE", 0) * 100 * 1.5))

            # Overall Rating (0-100 scale)
            overall_rating = (off_rating * 0.6) + (def_rating * 0.4)

            # Add NBA_PLUS metrics
            player_metrics["NBA_PLUS"] = (overall_rating - 50) / 5  # -10 to +10 scale
            player_metrics["NBA_PLUS_OFF"] = (off_rating - 50) / 5
            player_metrics["NBA_PLUS_DEF"] = (def_rating - 50) / 5

            # Add to list
            all_players_with_metrics.append({
                'player_id': int(player_dict['PLAYER_ID']),
                'player_name': player_dict['PLAYER_NAME'],
                'metrics': player_metrics
            })

        # Get current player metrics
        current_player = next(p for p in all_players_with_metrics if p['player_id'] == player_id)
        current_metrics = current_player['metrics']

        # Define comparison metrics with weights
        comparison_metrics = {
            # Advanced metrics
            'PIE': 3.0,           # Player Impact Estimate (very important)
            'USG_PCT': 2.0,       # Usage percentage
            'TS_PCT': 2.0,        # True shooting percentage
            'AST_PCT': 1.5,       # Assist percentage
            'REB_PCT': 1.5,       # Rebound percentage
            'NBA_PLUS': 3.0,      # Our overall rating (very important)
            'NBA_PLUS_OFF': 1.5,  # Our offensive rating
            'NBA_PLUS_DEF': 1.5,  # Our defensive rating

            # Basic stats
            'PTS': 2.0,           # Points per game
            'AST': 1.5,           # Assists per game
            'REB': 1.5,           # Rebounds per game
            'STL': 1.0,           # Steals per game
            'BLK': 1.0,           # Blocks per game
            'FG_PCT': 1.0,        # Field goal percentage
            'FG3_PCT': 1.0,       # Three-point percentage
            'FT_PCT': 0.5,        # Free throw percentage
        }

        # Calculate similarity scores
        similarity_scores = []
        other_players = [p for p in all_players_with_metrics if p['player_id'] != player_id]

        for player in other_players:
            player_metrics = player['metrics']

            # Calculate weighted Euclidean distance
            weighted_squared_diffs = []
            total_weight = 0

            for metric, weight in comparison_metrics.items():
                if metric in current_metrics and metric in player_metrics:
                    # Get the values
                    current_value = current_metrics[metric]
                    player_value = player_metrics[metric]

                    # Calculate normalized difference
                    # Use all players to get standard deviation
                    all_values = [p['metrics'].get(metric) for p in all_players_with_metrics
                                 if metric in p['metrics']]
                    std_dev = np.std(all_values) if len(all_values) > 1 else 1

                    if std_dev > 0:
                        normalized_diff = (current_value - player_value) / std_dev
                        weighted_squared_diffs.append(normalized_diff ** 2 * weight)
                        total_weight += weight

            # Calculate weighted distance and similarity
            if total_weight > 0:
                weighted_distance = np.sqrt(sum(weighted_squared_diffs) / total_weight)
                similarity = 1 / (1 + weighted_distance)  # Convert distance to similarity (0 to 1)

                similarity_scores.append({
                    'player_id': player['player_id'],
                    'player_name': player['player_name'],
                    'similarity_score': round(similarity, 2)
                })

        # Sort by similarity (highest first) and take top 5
        similarity_scores.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similarity_scores[:5]

    except Exception as e:
        logger.error(f"Error finding similar players for player ID {player_id}: {str(e)}", exc_info=True)
        return []
