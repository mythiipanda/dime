import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_player_name_key_sql_is_shared_across_tools():
    from shared.contracts import player_name_key_sql
    from shared.tools import career_arc, history
    from shared.tools.player import clutch_splits, comparisons

    assert history._player_name_key_sql is player_name_key_sql
    assert comparisons._player_name_key_sql is player_name_key_sql
    assert clutch_splits._player_name_key_sql is player_name_key_sql
    assert career_arc._player_name_key_sql is player_name_key_sql
