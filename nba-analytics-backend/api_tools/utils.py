# nba-analytics-backend/api_tools/utils.py
import logging
import pandas as pd
import re

logger = logging.getLogger(__name__)

def _validate_season_format(season: str) -> bool:
    """Validates season string format (e.g., '2023-24')."""
    return bool(re.match(r"^\d{4}-\d{2}$", season))

def _process_dataframe(df: pd.DataFrame | None, single_row: bool = True) -> list | dict | None:
    """
    Processes a pandas DataFrame into a list of dictionaries or a single dictionary,
    handling NaN values by converting them to None.
    Returns None if DataFrame processing fails.
    """
    if df is None or df.empty:
        return {} if single_row else []
    try:
        # Convert NaN/NaT to None before converting to dict
        df_processed = df.where(pd.notna(df), None)
        records = df_processed.to_dict(orient='records')

        # Ensure all values within records are JSON serializable (redundant if where worked, but safe)
        # processed_records = [
        #     {k: (v if pd.notna(v) else None) for k, v in row.items()}
        #     for row in records
        # ] # This inner loop might be redundant now

        if single_row:
            return records[0] if records else {}
        else:
            return records
    except Exception as e:
        logger.error(f"Error processing DataFrame: {e}", exc_info=True)
        return None # Indicate failure