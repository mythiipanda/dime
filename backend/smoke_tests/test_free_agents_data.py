"""
Smoke test for the free_agents_data module.
Tests the functionality of fetching NBA free agent data.
"""
import os
import sys
import json


from api_tools.free_agents_data import (
    fetch_free_agents_data_logic,
    get_free_agent_info,
    get_team_free_agents,
    get_top_free_agents,
    search_free_agents
)

def test_fetch_all_free_agents():
    """Test fetching all free agent data."""
    print("Testing fetch_free_agents_data_logic() - all free agents...")
    
    try:
        # Test basic fetch
        json_response = fetch_free_agents_data_logic()
        data = json.loads(json_response)
        
        print(f"✓ Successfully fetched free agent data")
        print(f"✓ Data sets: {list(data.get('data_sets', {}).keys())}")
        
        free_agents = data.get('data_sets', {}).get('free_agents', [])
        print(f"✓ Total free agents: {len(free_agents)}")
        
        if free_agents:
            sample = free_agents[0]
            print(f"✓ Sample free agent keys: {list(sample.keys())}")
            
            # Show free agent types
            fa_types = {}
            for fa in free_agents:
                fa_type = fa.get('type')
                fa_types[fa_type] = fa_types.get(fa_type, 0) + 1
            print(f"✓ Free agent types: {fa_types}")
        
        # Test with DataFrame output
        json_response, dataframes = fetch_free_agents_data_logic(return_dataframe=True)
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

def test_free_agent_info():
    """Test fetching info for a specific free agent."""
    print("\nTesting get_free_agent_info()...")
    
    try:
        # First get all free agents to find a valid player ID
        json_response = fetch_free_agents_data_logic()
        data = json.loads(json_response)
        free_agents = data.get('data_sets', {}).get('free_agents', [])
        
        if not free_agents:
            print("✗ No free agents found")
            return False
        
        # Test with first available player
        test_player = free_agents[0]
        test_player_id = test_player.get('nba_player_id')
        test_player_name = test_player.get('playerDisplayName')
        
        if not test_player_id:
            print("✗ No valid player ID found")
            return False
        
        print(f"Testing with player: {test_player_name} (ID: {test_player_id})")
        
        # Test free agent info fetch
        json_response = get_free_agent_info(int(test_player_id))
        data = json.loads(json_response)
        
        player_info = data.get('data_sets', {}).get('free_agents', [])
        if player_info:
            fa_info = player_info[0]
            print(f"✓ Successfully retrieved info for {fa_info.get('playerDisplayName')}")
            print(f"✓ Position: {fa_info.get('position')}")
            print(f"✓ Age: {fa_info.get('age')}")
            print(f"✓ Experience: {fa_info.get('exp')} years")
            print(f"✓ Free agent type: {fa_info.get('type')}")
            print(f"✓ Stats: {fa_info.get('PPG')} PPG, {fa_info.get('RPG')} RPG, {fa_info.get('APG')} APG")
        else:
            print(f"✗ No free agent info found for player ID {test_player_id}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_team_free_agents():
    """Test fetching free agents for a specific team."""
    print("\nTesting get_team_free_agents()...")
    
    try:
        # First get all free agents to find a valid team ID
        json_response = fetch_free_agents_data_logic()
        data = json.loads(json_response)
        free_agents = data.get('data_sets', {}).get('free_agents', [])
        
        if not free_agents:
            print("✗ No free agents found")
            return False
        
        # Find a team with valid NBA ID
        test_team_id = None
        for fa in free_agents:
            if fa.get('nba_old_team_id'):
                test_team_id = int(fa['nba_old_team_id'])
                break
        
        if not test_team_id:
            print("✗ No teams with valid NBA API IDs found")
            return False
        
        print(f"Testing with team ID: {test_team_id}")
        
        # Test team free agents fetch
        json_response = get_team_free_agents(test_team_id)
        data = json.loads(json_response)
        
        team_fas = data.get('data_sets', {}).get('free_agents', [])
        if team_fas:
            print(f"✓ Successfully retrieved {len(team_fas)} free agents for team {test_team_id}")
            
            # Show top free agents by PPG
            sorted_fas = sorted(team_fas, key=lambda x: x.get('PPG', 0) or 0, reverse=True)
            print(f"Top free agents by PPG:")
            for i, fa in enumerate(sorted_fas[:3]):
                print(f"  {i+1}. {fa.get('playerDisplayName')} ({fa.get('position')}): {fa.get('PPG')} PPG")
        else:
            print(f"✗ No free agents found for team ID {test_team_id}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_top_free_agents():
    """Test fetching top free agents."""
    print("\nTesting get_top_free_agents()...")
    
    try:
        # Test all free agents
        json_response = get_top_free_agents(limit=10)
        data = json.loads(json_response)
        
        top_fas = data.get('data_sets', {}).get('top_free_agents', [])
        if top_fas:
            print(f"✓ Successfully retrieved top {len(top_fas)} free agents")
            
            print("Top free agents by PPG:")
            for i, fa in enumerate(top_fas):
                print(f"  {i+1}. {fa.get('playerDisplayName')} ({fa.get('position')}): {fa.get('PPG')} PPG, {fa.get('age')} years old")
        else:
            print("✗ No top free agents found")
            return False
        
        # Test with position filter
        json_response = get_top_free_agents(position="G", limit=5)
        data = json.loads(json_response)
        guard_fas = data.get('data_sets', {}).get('top_free_agents', [])
        if guard_fas:
            print(f"\n✓ Found {len(guard_fas)} top guards")
        
        # Test with free agent type filter
        json_response = get_top_free_agents(free_agent_type="ufa", limit=5)
        data = json.loads(json_response)
        ufa_fas = data.get('data_sets', {}).get('top_free_agents', [])
        if ufa_fas:
            print(f"✓ Found {len(ufa_fas)} top UFAs")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_search_free_agents():
    """Test searching for free agents."""
    print("\nTesting search_free_agents()...")
    
    try:
        # Search for a common name
        json_response = search_free_agents("James")
        data = json.loads(json_response)
        
        search_results = data.get('data_sets', {}).get('free_agent_search', [])
        if search_results:
            print(f"✓ Successfully found {len(search_results)} free agents with 'James' in name")
            
            print("Top 3 search results:")
            for i, fa in enumerate(search_results[:3]):
                print(f"  {i+1}. {fa.get('playerDisplayName')}: {fa.get('PPG')} PPG")
        else:
            print("✗ No free agents found with 'James' in name")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_filtered_free_agents():
    """Test fetching free agents with various filters."""
    print("\nTesting filtered free agent queries...")
    
    try:
        # Test position filter
        json_response = fetch_free_agents_data_logic(position="G")
        data = json.loads(json_response)
        guards = data.get('data_sets', {}).get('free_agents', [])
        print(f"✓ Position filter (G): {len(guards)} guards")
        
        # Test free agent type filter
        json_response = fetch_free_agents_data_logic(free_agent_type="ufa")
        data = json.loads(json_response)
        ufas = data.get('data_sets', {}).get('free_agents', [])
        print(f"✓ Type filter (ufa): {len(ufas)} unrestricted free agents")
        
        # Test minimum PPG filter
        json_response = fetch_free_agents_data_logic(min_ppg=10.0)
        data = json.loads(json_response)
        scorers = data.get('data_sets', {}).get('free_agents', [])
        print(f"✓ PPG filter (>=10): {len(scorers)} players averaging 10+ PPG")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("FREE AGENTS DATA SMOKE TESTS")
    print("=" * 60)
    
    tests = [
        test_fetch_all_free_agents,
        test_free_agent_info,
        test_team_free_agents,
        test_top_free_agents,
        test_search_free_agents,
        test_filtered_free_agents,
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
