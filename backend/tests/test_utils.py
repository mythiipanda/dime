import pytest
from ..api_tools.utils import (
    validate_season_format,
    validate_game_id_format,
    format_response,
    handle_api_error
)

def test_validate_season_format_valid():
    """Test season format validation with valid formats."""
    valid_seasons = [
        "2022-23",
        "1999-00",
        "2000-01"
    ]
    for season in valid_seasons:
        assert validate_season_format(season) is True

def test_validate_season_format_invalid():
    """Test season format validation with invalid formats."""
    invalid_seasons = [
        "2022",
        "22-23",
        "2022-2023",
        "abcd-ef",
        "",
        "2022/23",
        "2022_23"
    ]
    for season in invalid_seasons:
        assert validate_season_format(season) is False

def test_validate_game_id_format_valid():
    """Test game ID format validation with valid formats."""
    valid_game_ids = [
        "0022200021",
        "0021900001",
        "0041800001"
    ]
    for game_id in valid_game_ids:
        assert validate_game_id_format(game_id) is True

def test_validate_game_id_format_invalid():
    """Test game ID format validation with invalid formats."""
    invalid_game_ids = [
        "002220002",  # Too short
        "00222000211",  # Too long
        "abcd123456",  # Contains letters
        "",  # Empty
        "12345",  # Too short
        "XXXXXXXXXX"  # Invalid characters
    ]
    for game_id in invalid_game_ids:
        assert validate_game_id_format(game_id) is False

def test_format_response_success():
    """Test response formatting for successful cases."""
    test_data = {"key": "value"}
    response = format_response(test_data)
    
    assert isinstance(response, str)
    assert "error" not in response
    assert "key" in response
    assert "value" in response

def test_format_response_error():
    """Test response formatting for error cases."""
    test_error = "Test error message"
    response = format_response(error=test_error)
    
    assert isinstance(response, str)
    assert "error" in response
    assert test_error in response

def test_format_response_empty():
    """Test response formatting with empty data."""
    response = format_response({})
    
    assert isinstance(response, str)
    assert "{}" in response

@pytest.mark.parametrize("error_type,expected_message", [
    ("InvalidGameId", "Invalid game ID format"),
    ("InvalidSeason", "Invalid season format"),
    ("InvalidPlayer", "Player not found"),
    ("InvalidTeam", "Team not found"),
    ("Timeout", "Request timed out"),
    ("Unknown", "An unexpected error occurred")
])
def test_handle_api_error(error_type, expected_message):
    """Test API error handling for different error types."""
    error_response = handle_api_error(error_type)
    
    assert isinstance(error_response, str)
    assert "error" in error_response
    assert expected_message in error_response

def test_handle_api_error_with_custom_message():
    """Test API error handling with custom error message."""
    custom_message = "Custom error occurred"
    error_response = handle_api_error("Unknown", custom_message)
    
    assert isinstance(error_response, str)
    assert "error" in error_response
    assert custom_message in error_response

def test_handle_api_error_with_details():
    """Test API error handling with additional error details."""
    error_details = {"code": 404, "message": "Resource not found"}
    error_response = handle_api_error("Unknown", details=error_details)
    
    assert isinstance(error_response, str)
    assert "error" in error_response
    assert str(error_details["code"]) in error_response
    assert error_details["message"] in error_response 