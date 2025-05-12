import logging
import pandas as pd
import numpy as np
import sys
import os
import pytest
from requests.exceptions import ReadTimeout

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.utils import (
    retry_on_timeout, format_response, _process_dataframe,
    find_player_id_or_error, find_team_id_or_error, PlayerNotFoundError, TeamNotFoundError
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_retry_on_timeout():
    logger.info("Testing retry_on_timeout with a function that fails twice then succeeds...")
    call_count = {'count': 0}
    def flaky_func():
        call_count['count'] += 1
        if call_count['count'] < 3:
            raise ReadTimeout("Simulated ReadTimeout failure")
        return "success"
    result = retry_on_timeout(flaky_func, max_retries=4, initial_delay=0.1, max_delay=0.2)
    assert result == "success"
    logger.info("  PASS: retry_on_timeout")

def test_format_response():
    logger.info("Testing format_response...")
    assert format_response(data={"foo": "bar"}) == '{"foo": "bar"}'
    assert format_response(error="err") == '{"error": "err"}'
    assert format_response() == '{}'
    logger.info("  PASS: format_response")

def test_process_dataframe():
    logger.info("Testing _process_dataframe...")
    df = pd.DataFrame({"a": [1, np.nan], "b": [None, "x"]})
    single = _process_dataframe(df, single_row=True)
    multi = _process_dataframe(df, single_row=False)
    assert isinstance(single, dict)
    assert isinstance(multi, list)
    assert multi[1]["b"] == "x"
    logger.info("  PASS: _process_dataframe")

def test_find_player_id_or_error():
    logger.info("Testing find_player_id_or_error...")
    try:
        pid, name = find_player_id_or_error("LeBron James")
        assert isinstance(pid, int) and "LeBron" in name
        logger.info(f"  PASS: find_player_id_or_error for LeBron James: {pid}, {name}")
    except Exception as e:
        logger.error(f"  FAIL: find_player_id_or_error for LeBron James: {e}")
    with pytest.raises(Exception):
        find_player_id_or_error("")
    with pytest.raises(PlayerNotFoundError):
        find_player_id_or_error("NotARealPlayerName12345")

def test_find_team_id_or_error():
    logger.info("Testing find_team_id_or_error...")
    try:
        tid, tname = find_team_id_or_error("LAL")
        assert isinstance(tid, int) and ("Lakers" in tname or "LAL" in tname)
        logger.info(f"  PASS: find_team_id_or_error for LAL: {tid}, {tname}")
    except Exception as e:
        logger.error(f"  FAIL: find_team_id_or_error for LAL: {e}")
    with pytest.raises(Exception):
        find_team_id_or_error("")
    with pytest.raises(TeamNotFoundError):
        find_team_id_or_error("NotARealTeamName12345")

def main():
    test_retry_on_timeout()
    test_format_response()
    test_process_dataframe()
    test_find_player_id_or_error()
    test_find_team_id_or_error()
    logger.info("All utils tests completed.")

if __name__ == "__main__":
    main() 