import os
import sys
from typing import List
from langchain_core.tools import Tool

# Add project root to sys.path for imports
_current_script_path = os.path.abspath(__file__)
_langgraph_agent_dir = os.path.dirname(_current_script_path)
_backend_dir = os.path.dirname(_langgraph_agent_dir)
_project_root_dir = os.path.dirname(_backend_dir)

if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

from langgraph_agent.tool_manager import all_tools

def test_all_tools_loaded():
    """
    Tests that all tools are correctly loaded from tool_manager.py
    and prints their names.
    """
    print(f"Total tools loaded: {len(all_tools)}")
    if not all_tools:
        print("No tools were loaded. This indicates an issue with tool_manager.py or its imports.")
        return False
    
    print("\nLoaded Tools:")
    for tool_obj in all_tools:
        print(f"- {tool_obj.name}")
    
    # Basic check to ensure some expected tools are present
    expected_tools = [
        "get_player_shot_chart",
        "get_nba_player_contract",
        "get_nba_draft_combine_stats",
        "get_nba_boxscore_traditional",
        "get_all_time_nba_leaders"
    ]
    
    loaded_tool_names = {tool.name for tool in all_tools}
    
    all_expected_found = True
    for expected_tool in expected_tools:
        if expected_tool not in loaded_tool_names:
            print(f"ERROR: Expected tool '{expected_tool}' not found.")
            all_expected_found = False
    
    if all_expected_found:
        print("\nAll expected tools found. Tool loading seems successful.")
        return True
    else:
        print("\nMissing expected tools. Please check tool_manager.py imports.")
        return False

if __name__ == "__main__":
    if test_all_tools_loaded():
        print("\nTool loading test PASSED.")
    else:
        print("\nTool loading test FAILED.")