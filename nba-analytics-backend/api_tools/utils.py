import logging
import pandas as pd

logger = logging.getLogger(__name__)

def _process_dataframe(df: pd.DataFrame | None, single_row: bool = True) -> list | dict | None:
    """
    Processes a Pandas DataFrame into a list of dictionaries or a single dictionary,
    handling NaN values by converting them to None.

    Args:
        df: The Pandas DataFrame to process.
        single_row: If True, expects a single row DataFrame and returns a single dict.
                    If False, returns a list of dicts.

    Returns:
        A dictionary or list of dictionaries representing the DataFrame rows,
        or None if an error occurs during processing. Returns an empty dict/list
        if the input DataFrame is None or empty.
    """
    if df is None or df.empty:
        logger.debug("Input DataFrame is None or empty.")
        return {} if single_row else []
    try:
        # Replace NaN/NaT with None before converting to dict
        df_processed = df.where(pd.notna(df), None)
        records = df_processed.to_dict(orient='records')

        # The previous implementation iterated again, which is redundant
        # after using df.where. Keeping the structure in case specific
        # per-row logic was intended, but simplifying for now.
        # processed_records = [
        #     {k: (v if pd.notna(v) else None) for k, v in row.items()}
        #     for row in records
        # ]
        processed_records = records # Use directly after df.where

        if single_row:
            result = processed_records[0] if processed_records else {}
            logger.debug(f"Processed DataFrame to single dictionary: {len(result)} keys")
            return result
        else:
            logger.debug(f"Processed DataFrame to list of dictionaries: {len(processed_records)} records")
            return processed_records
    except Exception as e:
        logger.error(f"Error processing DataFrame: {e}", exc_info=True)
        return None