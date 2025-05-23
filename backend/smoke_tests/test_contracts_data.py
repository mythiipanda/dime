"""
Smoke test for the contracts_data module.
Tests the functionality of fetching NBA player contract data.
"""
import os
import sys
import json

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.api_tools.contracts_data import (
    fetch_contracts_data_logic,
    get_player_contract,
    get_team_payroll,
    get_highest_paid_players,
    search_player_contracts
)

def test_fetch_all_contracts():
    """Test fetching all contract data."""
    print("Testing fetch_contracts_data_logic() - all contracts...")
    
    try:
        # Test basic fetch
        json_response = fetch_contracts_data_logic()
        data = json.loads(json_response)
        
        print(f"✓ Successfully fetched contract data")
        print(f"✓ Data sets: {list(data.get('data_sets', {}).keys())}")
        
        contracts = data.get('data_sets', {}).get('contracts', [])
        print(f"✓ Total contracts: {len(contracts)}")
        
        if contracts:
            sample = contracts[0]
            print(f"✓ Sample contract keys: {list(sample.keys())}")
        
        # Test with DataFrame output
        json_response, dataframes = fetch_contracts_data_logic(return_dataframe=True)
        data = json.loads(json_response)
        print(f"✓ DataFrame test - DataFrames: {list(dataframes.keys())}")
        
        for name, df in dataframes.items():
            print(f"✓ DataFrame '{name}' shape: {df.shape}")
            if not df.empty:
                print(f"✓ Columns: {df.columns.tolist()}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_player_contract():
    """Test fetching contract for a specific player."""
    print("\nTesting get_player_contract()...")
    
    try:
        # First get all contracts to find a valid player ID
        json_response = fetch_contracts_data_logic()
        data = json.loads(json_response)
        contracts = data.get('data_sets', {}).get('contracts', [])
        
        if not contracts:
            print("✗ No contracts found")
            return False
        
        # Find a player with valid NBA ID
        test_player_id = None
        test_player_name = None
        for contract in contracts:
            if contract.get('nba_player_id'):
                test_player_id = int(contract['nba_player_id'])
                test_player_name = contract.get('Player')
                break
        
        if not test_player_id:
            print("✗ No players with valid NBA API IDs found")
            return False
        
        print(f"Testing with player: {test_player_name} (ID: {test_player_id})")
        
        # Test player contract fetch
        json_response = get_player_contract(test_player_id)
        data = json.loads(json_response)
        
        player_contracts = data.get('data_sets', {}).get('contracts', [])
        if player_contracts:
            contract = player_contracts[0]
            print(f"✓ Successfully retrieved contract for {contract.get('Player')}")
            print(f"✓ Team: {contract.get('Tm')}")
            print(f"✓ Guaranteed money: ${contract.get('Guaranteed'):,.0f}" if contract.get('Guaranteed') else "✓ Guaranteed money: N/A")
        else:
            print(f"✗ No contract found for player ID {test_player_id}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_team_payroll():
    """Test fetching payroll for a specific team."""
    print("\nTesting get_team_payroll()...")
    
    try:
        # First get all contracts to find a valid team ID
        json_response = fetch_contracts_data_logic()
        data = json.loads(json_response)
        contracts = data.get('data_sets', {}).get('contracts', [])
        
        if not contracts:
            print("✗ No contracts found")
            return False
        
        # Find a team with valid NBA ID
        test_team_id = None
        test_team_abbr = None
        for contract in contracts:
            if contract.get('nba_team_id'):
                test_team_id = int(contract['nba_team_id'])
                test_team_abbr = contract.get('Tm')
                break
        
        if not test_team_id:
            print("✗ No teams with valid NBA API IDs found")
            return False
        
        print(f"Testing with team: {test_team_abbr} (ID: {test_team_id})")
        
        # Test team payroll fetch
        json_response = get_team_payroll(test_team_id)
        data = json.loads(json_response)
        
        team_contracts = data.get('data_sets', {}).get('contracts', [])
        if team_contracts:
            print(f"✓ Successfully retrieved payroll for {test_team_abbr}")
            print(f"✓ Player count: {len(team_contracts)}")
            
            # Calculate total guaranteed money
            total_guaranteed = sum(c.get('Guaranteed', 0) or 0 for c in team_contracts)
            print(f"✓ Total guaranteed: ${total_guaranteed:,.0f}")
        else:
            print(f"✗ No payroll found for team ID {test_team_id}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_highest_paid_players():
    """Test fetching highest paid players."""
    print("\nTesting get_highest_paid_players()...")
    
    try:
        json_response = get_highest_paid_players(limit=10)
        data = json.loads(json_response)
        
        top_players = data.get('data_sets', {}).get('highest_paid_players', [])
        if top_players:
            print(f"✓ Successfully retrieved {len(top_players)} highest paid players")
            
            print("Top 5 highest paid players:")
            for i, player in enumerate(top_players[:5]):
                guaranteed = player.get('Guaranteed')
                if guaranteed:
                    print(f"  {i+1}. {player.get('Player')}: ${guaranteed:,.0f}")
                else:
                    print(f"  {i+1}. {player.get('Player')}: N/A")
        else:
            print("✗ No highest paid players found")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_search_contracts():
    """Test searching for player contracts."""
    print("\nTesting search_player_contracts()...")
    
    try:
        # Search for a common name
        json_response = search_player_contracts("James")
        data = json.loads(json_response)
        
        search_results = data.get('data_sets', {}).get('player_contracts', [])
        if search_results:
            print(f"✓ Successfully found {len(search_results)} players with 'James' in name")
            
            print("Top 3 search results:")
            for i, player in enumerate(search_results[:3]):
                guaranteed = player.get('Guaranteed')
                if guaranteed:
                    print(f"  {i+1}. {player.get('Player')}: ${guaranteed:,.0f}")
                else:
                    print(f"  {i+1}. {player.get('Player')}: N/A")
        else:
            print("✗ No players found with 'James' in name")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("CONTRACTS DATA SMOKE TESTS")
    print("=" * 60)
    
    tests = [
        test_fetch_all_contracts,
        test_player_contract,
        test_team_payroll,
        test_highest_paid_players,
        test_search_contracts,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed. Check the output above.")
