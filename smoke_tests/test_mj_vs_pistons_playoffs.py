from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import leaguegamefinder
import pandas as pd

def get_mj_vs_pistons_playoff_matchups():
    """
    Finds historical playoff game data for when Michael Jordan played against the Detroit Pistons.
    Focuses on demonstrating the necessary nba_api function calls.
    """
    try:
        # Get Michael Jordan's player ID
        player_list = players.find_players_by_full_name("Michael Jordan")
        if not player_list:
            print("Michael Jordan not found.")
            return None
        mj_id = player_list[0]['id']
        print(f"Found Michael Jordan's ID: {mj_id}")

        # Get Detroit Pistons' team ID
        team_list = teams.find_teams_by_full_name("Detroit Pistons")
        if not team_list:
            print("Detroit Pistons not found.")
            return None
        pistons_id = team_list[0]['id']
        print(f"Found Detroit Pistons' ID: {pistons_id}")

        # Find games using LeagueGameFinder
        # We are looking for games where MJ (player_id_nullable) played AGAINST the Pistons (vs_team_id_nullable)
        game_finder = leaguegamefinder.LeagueGameFinder(
            player_id_nullable=mj_id,
            vs_team_id_nullable=pistons_id,
            season_type_nullable="Playoffs"  # Ensure this is the correct value for playoffs
        )
        
        games_df = game_finder.get_data_frames()[0]

        if games_df.empty:
            print("No playoff games found for Michael Jordan against the Detroit Pistons.")
            return pd.DataFrame()

        print(f"Found {len(games_df)} playoff games for Michael Jordan vs. Detroit Pistons.")
        
        # Display some basic info about the games found
        # print("Sample of games found:")
        # print(games_df[['GAME_ID', 'GAME_DATE', 'MATCHUP', 'WL', 'PTS']].head())
        
        return games_df

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    print("Fetching historical matchup data for Michael Jordan vs. Detroit Pistons (Playoffs)...")
    matchup_data = get_mj_vs_pistons_playoff_matchups()
    if matchup_data is not None and not matchup_data.empty:
        print("\n--- Matchup Data Summary ---")
        print(f"Total games found: {len(matchup_data)}")
        # For brevity in a smoke test, just show a few relevant columns and the first 5 games
        print(matchup_data[['GAME_DATE', 'MATCHUP', 'WL', 'PTS']].head())
    elif matchup_data is not None and matchup_data.empty:
        print("Search completed, but no specific games were found matching the criteria.")
    else:
        print("Failed to fetch matchup data.") 