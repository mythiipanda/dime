import sys
import os
import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_tools.team_tracking_utils import _validate_team_tracking_params, _get_team_info_for_tracking

def test_validate_team_tracking_params():
    # Valid
    assert _validate_team_tracking_params("LAL", "2023-24") is None
    # Invalid: missing team
    assert "error" in _validate_team_tracking_params(None, "2023-24")
    # Invalid: bad season
    assert "error" in _validate_team_tracking_params("LAL", "badseason")

def test_get_team_info_for_tracking():
    # Valid by identifier
    err, tid, tname = _get_team_info_for_tracking("LAL", None)
    assert err is None and tid is not None and tname is not None
    # Valid by ID
    err, tid, tname = _get_team_info_for_tracking(None, 1610612747)
    assert err is None and tid == 1610612747
    # Invalid: neither provided
    err, tid, tname = _get_team_info_for_tracking(None, None)
    assert err is not None and tid is None and tname is None
    # Invalid: bad identifier
    err, tid, tname = _get_team_info_for_tracking("NotARealTeamName12345", None)
    assert err is not None and tid is None and tname is None

def main():
    test_validate_team_tracking_params()
    test_get_team_info_for_tracking()
    print("All team_tracking_utils tests completed.")

if __name__ == "__main__":
    main() 