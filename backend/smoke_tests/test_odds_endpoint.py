"""
Smoke test for the odds endpoint.
Tests the functionality of the /odds/live endpoint with both standard and DataFrame outputs.
"""
import os

import json
import requests
from datetime import datetime



# Base URL for the API
BASE_URL = "http://localhost:8000/api/v1"

def test_odds_live_endpoint():
    """Test the /odds/live endpoint with default parameters."""
    print("\n=== Testing /odds/live endpoint (standard output) ===")
    
    url = f"{BASE_URL}/odds/live"
    print(f"Making GET request to: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses
        
        # Check if the response is valid JSON
        data = response.json()
        
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
        
        print(f"Response status code: {response.status_code}")
        print("\n=== Standard endpoint test completed ===")
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        print("Is the FastAPI server running? Make sure to start it with 'uvicorn main:app --reload' from the backend directory.")
        return None

def test_odds_live_endpoint_dataframe():
    """Test the /odds/live endpoint with as_dataframe=True."""
    print("\n=== Testing /odds/live endpoint (DataFrame output) ===")
    
    url = f"{BASE_URL}/odds/live?as_dataframe=true"
    print(f"Making GET request to: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses
        
        # Check if the response is valid JSON
        data = response.json()
        
        # Check if the response has the expected structure
        assert isinstance(data, dict), "Response should be a dictionary"
        
        # Check if there's an error in the response
        if "error" in data:
            print(f"API returned an error: {data['error']}")
            print("This might be expected if the NBA API is unavailable or rate-limited.")
            print("Continuing with other tests...")
        
        # Check if the dataframe_info field exists
        assert "dataframe_info" in data, "Response should have a 'dataframe_info' field when as_dataframe=True"
        df_info = data["dataframe_info"]
        
        # Print DataFrame info
        print(f"\nDataFrame shape: {df_info.get('dataframe_shape')}")
        print(f"DataFrame columns: {df_info.get('dataframe_columns')}")
        print(f"CSV path: {df_info.get('csv_path')}")
        
        # Check if the CSV file exists
        csv_path = os.path.abspath(df_info.get('csv_path', ''))
        if os.path.exists(csv_path):
            print(f"\nCSV file exists at: {csv_path}")
            csv_size = os.path.getsize(csv_path)
            print(f"CSV file size: {csv_size} bytes")
        else:
            print(f"\nWarning: CSV file not found at {csv_path}")
        
        # Display sample data if available
        sample_data = df_info.get('sample_data', [])
        if sample_data:
            print("\nSample data from DataFrame:")
            for i, record in enumerate(sample_data[:3]):  # Show up to 3 records
                print(f"\nRecord {i+1}:")
                for key, value in record.items():
                    print(f"  {key}: {value}")
        else:
            print("\nNo sample data available in the response.")
        
        print(f"Response status code: {response.status_code}")
        print("\n=== DataFrame endpoint test completed ===")
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        print("Is the FastAPI server running? Make sure to start it with 'uvicorn main:app --reload' from the backend directory.")
        return None

def run_all_tests():
    """Run all tests in sequence."""
    print(f"=== Running odds endpoint smoke tests at {datetime.now().isoformat()} ===\n")
    
    try:
        # Run the tests
        standard_data = test_odds_live_endpoint()
        df_data = test_odds_live_endpoint_dataframe()
        
        if standard_data is not None and df_data is not None:
            print("\n=== All tests completed successfully ===")
            return True
        else:
            print("\n!!! Some tests failed !!!")
            return False
    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)} !!!")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
