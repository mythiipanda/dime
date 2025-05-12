import datetime
from typing import Optional

def validate_date_format(date_string: Optional[str]) -> bool: # Changed to Optional[str] to match usage
    """
    Validates that a date string is in the "YYYY-MM-DD" format.
    Returns True if valid or if date_string is None, False otherwise.
    """
    if date_string is None:
        return True # Or False, depending on desired strictness for None. Assuming None is acceptable if optional.
                    # For now, let's keep it strict: if it's called, it should be a string.
                    # Reverting to original type hint for consistency with source.
    if not date_string or not isinstance(date_string, str):
        return False
    try:
        datetime.datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def _validate_season_format(season: str) -> bool:
    """
    Validates that the season string is in the "YYYY-YY" format (e.g., "2023-24").
    """
    if not season or not isinstance(season, str):
        return False
    
    # Regex to match YYYY-YY format
    match = re.fullmatch(r"(\d{4})-(\d{2})", season)
    if not match:
        return False

    try:
        start_year_str, end_year_short_str = match.groups()
        start_year = int(start_year_str)
        end_year_short = int(end_year_short_str)

        # Basic sanity check for start year (e.g., not too far in past/future)
        if start_year < 1940 or start_year > datetime.datetime.now().year + 5: # Allow a bit into future
            return False
        
        # Check if the YY part correctly follows the YYYY part
        # e.g., for 2023, YY should be 24
        expected_end_year_short = (start_year + 1) % 100
        
        return end_year_short == expected_end_year_short
    except ValueError: # Handles int() conversion errors
        return False

def validate_season_format(season: str) -> bool:
    """
    Public interface to validate that the season string is in the "YYYY-YY" format.
    """
    return _validate_season_format(season)

def validate_game_id_format(game_id: str) -> bool:
    """
    Validates that an NBA game ID string consists of exactly 10 digits.
    """
    if not game_id or not isinstance(game_id, str):
        return False
    return bool(re.fullmatch(r"^\d{10}$", game_id))

# Need to import re for _validate_season_format and validate_game_id_format
import re