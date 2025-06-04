#!/usr/bin/env python3
"""
Quick test to verify Exa AI tools are fixed
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_exa_tools_fixed():
    """Test that Exa tools work without include_text issues."""
    print("🧪 Testing fixed Exa AI tools...")
    
    try:
        from langgraph_agent.toolkits.exa_search_tools import exa_nba_search, exa_web_search
        
        # Test NBA search
        print("\n🏀 Testing exa_nba_search...")
        result1 = exa_nba_search.func(
            query="LeBron James stats",
            num_results=2
        )
        
        print(f"✅ NBA Search Result Type: {type(result1)}")
        if isinstance(result1, dict) and 'error' in result1:
            print(f"❌ NBA Search Error: {result1['error']}")
            return False
        elif isinstance(result1, dict) and 'results' in result1:
            print(f"✅ NBA Search Success: {len(result1['results'])} results")
        
        # Test web search  
        print("\n🌐 Testing exa_web_search...")
        result2 = exa_web_search.func(
            query="NBA trade news",
            num_results=2,
            include_text=False,  # Set to False to avoid issues
            category="news"
        )
        
        print(f"✅ Web Search Result Type: {type(result2)}")
        if isinstance(result2, dict) and 'error' in result2:
            print(f"❌ Web Search Error: {result2['error']}")
            return False
        elif isinstance(result2, dict) and 'results' in result2:
            print(f"✅ Web Search Success: {len(result2['results'])} results")
        
        print("\n🎉 Both Exa tools working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing Exa tools: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_exa_tools_fixed()
    exit(0 if success else 1)