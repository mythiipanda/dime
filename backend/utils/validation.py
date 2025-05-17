"""
Utility functions for validating various data formats and values
used within the NBA analytics backend application.
"""
import datetime
import re # Moved from bottom of file
from typing import Optional, List # Added List

# --- Module-Level Constants ---
_DEFAULT_VALID_LEAGUE_IDS: List[str] = ["00", "10", "20"] # Common NBA API League IDs: NBA, WNBA, G-League

# --- Validation Functions ---
def validate_date_format(date_string: Optional[str]) -> bool:
    """
    Validates that a date string is in the "YYYY-MM-DD" format.
    Returns True if the string is a valid date in this format, or if date_string is None.
    Returns False otherwise (e.g., empty string, incorrect format, invalid date).
    """
    if date_string is None:
        return True # Assuming None is acceptable for optional date fields
    if not isinstance(date_string, str) or not date_string: # Check for empty string explicitly
        return False
    try:
        datetime.datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def _validate_season_format(season: str, league_id: Optional[str] = "00") -> bool:
    """
    Validates the season string format.
    For NBA/G-League (league_id '00', '20'), expects "YYYY-YY" (e.g., "2023-24").
    For WNBA (league_id '10'), expects "YYYY" (e.g., "2023").
    """
    if not season or not isinstance(season, str):
        return False

    if league_id == "10": # WNBA
        # Regex to match YYYY format
        match = re.fullmatch(r"(\d{4})", season)
        if not match:
            return False
        try:
            year = int(match.group(1))
            # Basic sanity check for year
            if year < 1990 or year > datetime.datetime.now().year + 5: # WNBA started later
                return False
            return True
        except ValueError:
            return False
    else: # NBA, G-League, or default
        # Regex to match YYYY-YY format
        match = re.fullmatch(r"(\d{4})-(\d{2})", season)
        if not match:
            return False
        try:
            start_year_str, end_year_short_str = match.groups()
            start_year = int(start_year_str)
            end_year_short = int(end_year_short_str)

            # Allow a wider range for start year, especially for historical/future tests
            if start_year < 1940 or start_year > datetime.datetime.now().year + 75: # Extended future range
                return False
            
            expected_end_year_short = (start_year + 1) % 100
            return end_year_short == expected_end_year_short
        except ValueError: # Handles int() conversion errors
            return False

def validate_season_format(season: str, league_id: Optional[str] = "00") -> bool:
    """
    Public interface to validate the season string format based on league.
    """
    return _validate_season_format(season, league_id)

def validate_game_id_format(game_id: str) -> bool:
    """
    Validates that an NBA game ID string consists of exactly 10 digits.
    """
    if not game_id or not isinstance(game_id, str):
        return False
    return bool(re.fullmatch(r"^\d{10}$", game_id))

def _validate_league_id(league_id: str, valid_ids: Optional[List[str]] = None) -> bool: # Changed list to List
    """
    Validates that the league_id is one of the known valid IDs.
    Uses a default list if `valid_ids` is not provided.
    """
    if valid_ids is None:
        valid_ids = _DEFAULT_VALID_LEAGUE_IDS # Use module-level constant
    if not league_id or not isinstance(league_id, str):
        return False
    return league_id in valid_ids

def validate_team_id(team_id: int) -> bool:
    """
    Validates that an NBA team ID is a positive integer.
    Actual NBA team IDs are large positive integers (e.g., 1610612749).
    The value 0 is often used as a default for 'all teams' in opponent_team_id parameters,
    but this validator is for actual team IDs.
    """
    if not isinstance(team_id, int):
        return False
    # Team IDs are positive integers. Allow 0 only if it's explicitly handled elsewhere as "all teams".
    # Given the calling context (checks for not None and not 0 before calling), 
    # we expect actual team IDs here.
    return team_id > 0 

# `import re` moved to the top of the file.