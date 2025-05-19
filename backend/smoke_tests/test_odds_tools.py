"""
Smoke test for the odds_tools module.
Tests the functionality of fetching live betting odds for NBA games.
"""
import os

import json
import pandas as pd
from datetime import datetime



from api_tools.odds_tools import (
    fetch_odds_data_logic,
    _flatten_odds_data,
    _convert_to_dataframe,
    ODDS_CSV_PATH
)

def test_fetch_odds_data_json():
    """Test fetching odds data as JSON."""
    print("\n=== Testing fetch_odds_data_logic (JSON output) ===")

    # Test with default parameters (JSON output)
    json_response = fetch_odds_data_logic()

    # Parse the JSON response
    data = json.loads(json_response)

    # Check if the response has the expected structure
    assert isinstance(data, dict), "Response should be a dictionary"

    # Check if there's an error in the response
    if "error" in data:
        print(f"API returned an error: {data['error']}")
        print("This might be expected if the NBA API is unavailable or rate-limited.")
        print("Continuing with other tests...")
    else:
        # Check if the games field exists and is a list
        assert "games" in data, "Response should have a 'games' field"
        assert isinstance(data["games"], list), "'games' field should be a list"

        # Print some information about the games
        games = data["games"]
        print(f"Number of games found: {len(games)}")

        if games:
            # Print details of the first game
            first_game = games[0]
            print("\nFirst game details:")
            print(f"Game ID: {first_game.get('gameId', 'N/A')}")
            print(f"Home Team ID: {first_game.get('homeTeamId', 'N/A')}")
            print(f"Away Team ID: {first_game.get('awayTeamId', 'N/A')}")
            print(f"Game Time: {first_game.get('gameTime', 'N/A')}")
            print(f"Game Status: {first_game.get('gameStatus', 'N/A')} ({first_game.get('gameStatusText', 'N/A')})")

            # Check if markets exist
            markets = first_game.get("markets", [])
            print(f"Number of betting markets: {len(markets)}")

            if markets:
                # Print details of the first market
                first_market = markets[0]
                print(f"\nFirst market: {first_market.get('name', 'N/A')}")

                # Check if books exist
                books = first_market.get("books", [])
                print(f"Number of bookmakers: {len(books)}")

                if books:
                    # Print details of the first book
                    first_book = books[0]
                    print(f"First bookmaker: {first_book.get('name', 'N/A')}")

                    # Check if outcomes exist
                    outcomes = first_book.get("outcomes", [])
                    print(f"Number of outcomes: {len(outcomes)}")

                    if outcomes:
                        # Print details of all outcomes
                        print("\nOutcomes:")
                        for outcome in outcomes:
                            outcome_type = outcome.get("type", "N/A")
                            odds = outcome.get("odds", "N/A")
                            value = outcome.get("value", "N/A")
                            print(f"  {outcome_type}: {odds} (value: {value})")

    print("\n=== JSON test completed ===")
    return json_response

def test_fetch_odds_data_dataframe():
    """Test fetching odds data as DataFrame."""
    print("\n=== Testing fetch_odds_data_logic (DataFrame output) ===")

    # Test with return_dataframe=True
    result = fetch_odds_data_logic(return_dataframe=True)

    # Check if the result is a tuple
    assert isinstance(result, tuple), "Result should be a tuple when return_dataframe=True"
    assert len(result) == 2, "Result tuple should have 2 elements"

    json_response, df = result

    # Check if the first element is a JSON string
    assert isinstance(json_response, str), "First element should be a JSON string"

    # Check if the second element is a DataFrame
    assert isinstance(df, pd.DataFrame), "Second element should be a pandas DataFrame"

    # Print DataFrame info
    print(f"\nDataFrame shape: {df.shape}")
    print(f"DataFrame columns: {df.columns.tolist()}")

    # Check if the CSV file was created
    if os.path.exists(ODDS_CSV_PATH):
        print(f"\nCSV file created at: {ODDS_CSV_PATH}")
        csv_size = os.path.getsize(ODDS_CSV_PATH)
        print(f"CSV file size: {csv_size} bytes")

        # Read the CSV file to verify it matches the DataFrame
        df_from_csv = pd.read_csv(ODDS_CSV_PATH)
        print(f"CSV DataFrame shape: {df_from_csv.shape}")

        # Check if the shapes match
        assert df.shape == df_from_csv.shape, "DataFrame and CSV should have the same shape"
    else:
        print(f"\nWarning: CSV file not found at {ODDS_CSV_PATH}")

    # Display a sample of the DataFrame if not empty
    if not df.empty:
        print("\nSample of DataFrame (first 5 rows):")
        print(df.head())
    else:
        print("\nDataFrame is empty. This might be expected if no games are available.")

    print("\n=== DataFrame test completed ===")
    return df

def test_flatten_odds_data():
    """Test the _flatten_odds_data function with sample data."""
    print("\n=== Testing _flatten_odds_data ===")

    # Create a sample games list with nested structure
    sample_games = [
        {
            "gameId": "12345",
            "homeTeamId": 1610612737,  # Atlanta Hawks
            "awayTeamId": 1610612738,  # Boston Celtics
            "gameTime": "2023-12-25T12:00:00Z",
            "gameStatus": 1,
            "gameStatusText": "Scheduled",
            "markets": [
                {
                    "marketId": "spread",
                    "name": "Point Spread",
                    "books": [
                        {
                            "bookId": "book1",
                            "name": "DraftKings",
                            "outcomes": [
                                {
                                    "type": "home",
                                    "odds": "-110",
                                    "value": "-5.5"
                                },
                                {
                                    "type": "away",
                                    "odds": "-110",
                                    "value": "+5.5"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]

    # Flatten the data
    flattened_records = _flatten_odds_data(sample_games)

    # Check the results
    assert isinstance(flattened_records, list), "Result should be a list"
    assert len(flattened_records) == 2, "Should have 2 records (one for each outcome)"

    # Print the flattened records
    print(f"Number of flattened records: {len(flattened_records)}")
    for i, record in enumerate(flattened_records):
        print(f"\nRecord {i+1}:")
        for key, value in record.items():
            print(f"  {key}: {value}")

    # Convert to DataFrame
    df = _convert_to_dataframe(sample_games)

    # Check the DataFrame
    assert isinstance(df, pd.DataFrame), "Result should be a DataFrame"
    assert df.shape[0] == 2, "DataFrame should have 2 rows"
    assert 'gameId' in df.columns, "DataFrame should have 'gameId' column"
    assert 'outcomeType' in df.columns, "DataFrame should have 'outcomeType' column"

    print("\nDataFrame from sample data:")
    print(df)

    print("\n=== _flatten_odds_data test completed ===")
    return flattened_records

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running odds_tools smoke tests at {datetime.now().isoformat()} ===\n")

    try:
        # Run the tests
        json_response = test_fetch_odds_data_json()
        df = test_fetch_odds_data_dataframe()
        flattened_records = test_flatten_odds_data()

        print("\n=== All tests completed successfully ===")
        return True
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    success = run_all_tests()
    sys.exit(0 if success else 1)
