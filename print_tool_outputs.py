from backend.tools import (
    get_season_matchups,
    get_matchups_rollup,
    get_synergy_play_types,
    get_player_analysis
)


def main():
    print("=== get_season_matchups ===")
    print(get_season_matchups('2544', '201939', '2023-24', 'Regular Season'), end='\n\n')

    print("=== get_matchups_rollup ===")
    print(get_matchups_rollup('2544', '2023-24', 'Regular Season'), end='\n\n')

    print("=== get_synergy_play_types ===")
    # Use valid endpoint parameters: Totals for team-level data
    print(get_synergy_play_types('00', 'Totals', 'T', 'Regular Season', '2023-24'), end='\n\n')

    print("=== get_player_analysis ===")
    print(get_player_analysis('LeBron James', '2023-24', 'Regular Season', 'PerGame', '00'))


if __name__ == "__main__":
    main()
