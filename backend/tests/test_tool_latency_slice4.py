import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.lineup import get_lineup_stats
from shared.tools.lineup_matrix import get_lineup_matchup_matrix

FIX = Path(__file__).resolve().parent / "fixtures"

STATS_CASES = {
    "stats_bos_2024": {"team": "BOS", "season": "2024-25"},
    "stats_nyk_2023_m50": {"team": "NYK", "season": "2023-24", "min_possessions": 50},
    "stats_lal_2025": {"team": "LAL", "season": "2025-26"},
    "stats_gsw_2024_m200": {"team": "GSW", "season": "2024-25", "min_possessions": 200},
}

MATRIX_CASES = {
    "matrix_bos_nyk_2024": {"team_a": "BOS", "team_b": "NYK", "season": "2024-25"},
    "matrix_lal_gsw_2023": {"team_a": "LAL", "team_b": "GSW", "season": "2023-24"},
    "matrix_bos_nyk_2025_m5": {"team_a": "BOS", "team_b": "NYK", "season": "2025-26", "min_minutes": 5},
}

ERROR_CASES = {
    "err_stats_bad_team": (get_lineup_stats, {"team": "Not A Real Team XYZ"}),
    "err_matrix_bad_team": (get_lineup_matchup_matrix, {"team_a": "Not A Real Team XYZ", "team_b": "BOS"}),
    "err_matrix_same_team": (get_lineup_matchup_matrix, {"team_a": "BOS", "team_b": "BOS"}),
}


def _norm(out):
    return json.loads(json.dumps(out, default=str, sort_keys=True))


def _load(name):
    return json.loads((FIX / f"{name}.json").read_text())


def _max_of_5(fn, kwargs):
    best = 0.0
    for _ in range(5):
        t0 = time.perf_counter()
        fn.invoke(kwargs)
        best = max(best, (time.perf_counter() - t0) * 1000)
    return best


def test_lineup_stats_matches_pre_pushdown_output():
    for name, kwargs in STATS_CASES.items():
        assert _norm(get_lineup_stats.invoke(kwargs)) == _load(name)


def test_lineup_matchup_matrix_matches_pre_pushdown_output():
    for name, kwargs in MATRIX_CASES.items():
        assert _norm(get_lineup_matchup_matrix.invoke(kwargs)) == _load(name)


def test_error_paths_unchanged():
    for name, (fn, kwargs) in ERROR_CASES.items():
        assert _norm(fn.invoke(kwargs)) == _load(name)


def test_lineup_stats_max_of_5_under_150ms():
    for name, kwargs in STATS_CASES.items():
        assert _max_of_5(get_lineup_stats, kwargs) < 150, name


def test_lineup_matchup_matrix_max_of_5_under_200ms():
    for name, kwargs in MATRIX_CASES.items():
        assert _max_of_5(get_lineup_matchup_matrix, kwargs) < 200, name
