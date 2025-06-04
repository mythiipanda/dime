# This file manages all tools for the Langgraph agent, including NBA API tools, search, crawl, and data science tools. 

import os # Ensure os is imported first
import sys # Ensure sys is imported first
from typing import List
from langchain_core.tools import Tool
from pydantic import BaseModel

# --- Import Tools from Toolkits ---
# Player Tools
from langgraph_agent.toolkits.player_tools import (
    get_player_shot_chart,
    get_player_aggregate_stats,
    get_player_career_by_college_stats,
    get_player_career_by_college_rollup_stats,
    get_player_career_stats,
    get_player_awards,
    get_player_clutch_stats,
    get_player_info,
    get_player_compare_stats,
    get_player_dashboard_by_year_over_year,
    get_player_dashboard_game_splits,
    get_player_dashboard_general_splits,
    get_player_dashboard_last_n_games,
    get_player_dashboard_shooting_splits,
    get_player_profile,
    get_player_defense_stats,
    get_player_hustle_stats,
    get_player_estimated_metrics,
    get_player_fantasy_profile,
    get_player_fantasy_profile_bar_graph,
    get_player_game_logs,
    get_player_game_streak_finder,
    get_player_index,
    get_player_listings,
    get_player_passing_stats,
    get_player_rebounding_stats,
    get_player_shots_tracking_stats,
    get_player_vs_player_stats
)

# Team Tools
from langgraph_agent.toolkits.team_tools import (
    get_team_lineups,
    get_team_game_logs,
    get_team_historical_leaders,
    get_team_passing_stats,
    get_team_player_dashboard,
    get_team_player_on_off_summary,
    get_team_vs_player_stats,
    get_team_shooting_stats,
    get_team_player_on_off_details,
    get_team_rebounding_stats,
    get_team_info_and_roster,
    get_team_history,
    get_team_general_stats,
    get_team_estimated_metrics,
    get_team_shooting_splits,
    get_team_details,
    get_team_shot_dashboard
)

# Search Tools
from langgraph_agent.toolkits.search_tools import (
    search_nba_players,
    search_nba_teams,
    search_nba_games
)

# Exa AI Search Tools
from langgraph_agent.toolkits.exa_search_tools import (
    exa_web_search,
    exa_nba_search,
    exa_extract_content
)

# Synergy Tools
from langgraph_agent.toolkits.synergy_tools import (
    get_synergy_play_types
)

# Fantasy Tools
from langgraph_agent.toolkits.fantasy_tools import (
    get_nba_fantasy_widget_data
)

# Franchise Tools
from langgraph_agent.toolkits.franchise_tools import (
    get_nba_franchise_history,
    get_nba_franchise_players,
    get_nba_franchise_leaders
)

# Free Agent Tools
from langgraph_agent.toolkits.free_agent_tools import (
    get_nba_free_agent_info,
    get_nba_team_free_agents,
    get_nba_top_free_agents,
    search_nba_free_agents
)

# Contracts Tools
from langgraph_agent.toolkits.contracts_tools import (
    get_nba_player_contract,
    get_nba_team_payroll,
    get_nba_highest_paid_players,
    search_nba_player_contracts
)

# Draft Combine Tools
from langgraph_agent.toolkits.draft_combine_tools import (
    get_nba_draft_combine_drill_results,
    get_nba_draft_combine_nonstationary_shooting,
    get_nba_draft_combine_player_anthropometric,
    get_nba_draft_combine_stats,
    get_nba_draft_combine_spot_shooting,
    get_nba_draft_combine_drills
)

# Game Tools
from langgraph_agent.toolkits.game_tools import (
    get_nba_game_boxscore_matchups,
    get_nba_boxscore_traditional,
    get_nba_boxscore_advanced,
    get_nba_boxscore_four_factors,
    get_nba_boxscore_usage,
    get_nba_boxscore_defensive,
    get_nba_boxscore_summary,
    get_nba_boxscore_misc,
    get_nba_play_by_play,
    get_win_probability_pbp,
    get_nba_game_rotation,
    get_nba_hustle_stats_boxscore,
    get_nba_fanduel_player_infographic,
    get_nba_league_games,
    get_nba_boxscore_player_track,
    get_nba_boxscore_scoring,
    get_nba_boxscore_hustle,
    get_nba_scoreboard_data
)

# League Tools
from langgraph_agent.toolkits.league_tools import (
    get_all_time_nba_leaders,
    get_league_wide_shot_chart,
    get_nba_homepage_leaders,
    get_nba_homepage_v2_data,
    get_nba_ist_standings,
    get_nba_leaders_tiles,
    get_nba_assist_leaders,
    get_nba_league_player_bio_stats,
    get_nba_league_player_tracking_shot_stats,
    get_nba_league_player_clutch_stats,
    get_nba_league_game_log,
    get_league_hustle_stats_team,
    get_nba_league_lineups,
    get_nba_league_standings,
    get_nba_odds_data,
    get_nba_league_season_matchups,
    get_nba_matchups_rollup,
    get_nba_live_scoreboard,
    get_league_lineup_visualization,
    get_nba_league_player_stats,
    get_league_player_shot_locations,
    get_nba_schedule_league_v2_int,
    get_nba_league_wide_shot_chart,
    get_nba_playoff_picture,
    get_common_playoff_series
)

# --- Tool Registry by Category ---

player_tools: List[Tool] = [
    get_player_shot_chart,
    get_player_aggregate_stats,
    get_player_career_by_college_stats,
    get_player_career_by_college_rollup_stats,
    get_player_career_stats,
    get_player_awards,
    get_player_clutch_stats,
    get_player_info,
    get_player_compare_stats,
    get_player_dashboard_by_year_over_year,
    get_player_dashboard_game_splits,
    get_player_dashboard_general_splits,
    get_player_dashboard_last_n_games,
    get_player_dashboard_shooting_splits,
    get_player_profile,
    get_player_defense_stats,
    get_player_hustle_stats,
    get_player_estimated_metrics,
    get_player_fantasy_profile,
    get_player_fantasy_profile_bar_graph,
    get_player_game_logs,
    get_player_game_streak_finder,
    get_player_index,
    get_player_listings,
    get_player_passing_stats,
    get_player_rebounding_stats,
    get_player_shots_tracking_stats,
    get_player_vs_player_stats
]

team_tools: List[Tool] = [
    get_team_lineups,
    get_team_game_logs,
    get_team_historical_leaders,
    get_team_passing_stats,
    get_team_player_dashboard,
    get_team_player_on_off_summary,
    get_team_vs_player_stats,
    get_team_shooting_stats,
    get_team_player_on_off_details,
    get_team_rebounding_stats,
    get_team_info_and_roster,
    get_team_history,
    get_team_general_stats,
    get_team_estimated_metrics,
    get_team_shooting_splits,
    get_team_details,
    get_team_shot_dashboard
]

search_tools: List[Tool] = [
    search_nba_players,
    search_nba_teams,
    search_nba_games
]

exa_search_tools: List[Tool] = [
    exa_web_search,
    exa_nba_search,
    exa_extract_content
]

synergy_tools: List[Tool] = [
    get_synergy_play_types
]

fantasy_tools: List[Tool] = [
    get_nba_fantasy_widget_data
]

franchise_tools: List[Tool] = [
    get_nba_franchise_history,
    get_nba_franchise_players,
    get_nba_franchise_leaders
]

free_agent_tools: List[Tool] = [
    get_nba_free_agent_info,
    get_nba_team_free_agents,
    get_nba_top_free_agents,
    search_nba_free_agents
]

contracts_tools: List[Tool] = [
    get_nba_player_contract,
    get_nba_team_payroll,
    get_nba_highest_paid_players,
    search_nba_player_contracts
]

draft_combine_tools: List[Tool] = [
    get_nba_draft_combine_drill_results,
    get_nba_draft_combine_nonstationary_shooting,
    get_nba_draft_combine_player_anthropometric,
    get_nba_draft_combine_stats,
    get_nba_draft_combine_spot_shooting,
    get_nba_draft_combine_drills
]

game_tools: List[Tool] = [
    get_nba_game_boxscore_matchups,
    get_nba_boxscore_traditional,
    get_nba_boxscore_advanced,
    get_nba_boxscore_four_factors,
    get_nba_boxscore_usage,
    get_nba_boxscore_defensive,
    get_nba_boxscore_summary,
    get_nba_boxscore_misc,
    get_nba_play_by_play,
    get_win_probability_pbp,
    get_nba_game_rotation,
    get_nba_hustle_stats_boxscore,
    get_nba_fanduel_player_infographic,
    get_nba_league_games,
    get_nba_boxscore_player_track,
    get_nba_boxscore_scoring,
    get_nba_boxscore_hustle,
    get_nba_scoreboard_data
]

league_tools: List[Tool] = [
    get_all_time_nba_leaders,
    get_league_wide_shot_chart,
    get_nba_homepage_leaders,
    get_nba_homepage_v2_data,
    get_nba_ist_standings,
    get_nba_leaders_tiles,
    get_nba_assist_leaders,
    get_nba_league_player_bio_stats,
    get_nba_league_player_tracking_shot_stats,
    get_nba_league_player_clutch_stats,
    get_nba_league_game_log,
    get_league_hustle_stats_team,
    get_nba_league_lineups,
    get_nba_league_standings,
    get_nba_odds_data,
    get_nba_league_season_matchups,
    get_nba_matchups_rollup,
    get_nba_live_scoreboard,
    get_league_lineup_visualization,
    get_nba_league_player_stats,
    get_league_player_shot_locations,
    get_nba_schedule_league_v2_int,
    get_nba_league_wide_shot_chart,
    get_nba_playoff_picture,
    get_common_playoff_series
]

# --- Combine All Tools ---
all_tools: List[Tool] = (
    player_tools +
    team_tools +
    search_tools +
    exa_search_tools +
    synergy_tools +
    fantasy_tools +
    franchise_tools +
    free_agent_tools +
    contracts_tools +
    draft_combine_tools +
    game_tools +
    league_tools
)

# Example of how to get a dictionary of tools for Langgraph
# tool_executor = ToolExecutor(all_tools)
# runnable_tools = {tool.name: tool for tool in all_tools}

if __name__ == '__main__':
    # Print available tools by category
    print("\nAvailable Tools by Category:")
    print("\nPlayer Tools:")
    for tool in player_tools:
        print(f"- {tool.name}")
    
    print("\nTeam Tools:")
    for tool in team_tools:
        print(f"- {tool.name}")
    
    print("\nSearch Tools:")
    for tool in search_tools:
        print(f"- {tool.name}")
    
    print("\nSynergy Tools:")
    for tool in synergy_tools:
        print(f"- {tool.name}")
    
    print("\nFantasy Tools:")
    for tool in fantasy_tools:
        print(f"- {tool.name}")
    
    print("\nFranchise Tools:")
    for tool in franchise_tools:
        print(f"- {tool.name}")
    
    print("\nFree Agent Tools:")
    for tool in free_agent_tools:
        print(f"- {tool.name}")
    
    print("\nExa Search Tools:")
    for tool in exa_search_tools:
        print(f"- {tool.name}")
