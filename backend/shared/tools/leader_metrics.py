COUNTING_METRICS = (
    "PTS", "REB", "AST", "STL", "BLK", "OREB", "DREB", "TOV", "PF",
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
)

PER_GAME_SUFFIX = "_PER_GAME"

def per_game_column(metric: str) -> str:
    return f"{metric}{PER_GAME_SUFFIX}"

def per_game_value(total, games):
    if isinstance(total, bool) or isinstance(games, bool):
        return None
    try:
        counted = float(total)
        played = float(games)
    except (TypeError, ValueError):
        return None
    if played <= 0:
        return None
    return round(counted / played, 1)
