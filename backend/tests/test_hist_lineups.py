import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.lineup import get_lineup_stats
from shared.tools.player import get_on_off, get_wowy
from shared.tools.team import get_lineups

BOS = 1610612738
TATUM = 1628369
BROWN = 1627759
SEASON = "2022-23"
TOP_UNIT = "A. Horford - M. Smart - J. Brown - J. Tatum - D. White"
TOP_MIN = 432.4

@pytest.mark.canonical_warehouse
def test_get_lineup_stats_hist_season_returns_rows():
    res = get_lineup_stats.invoke(
        {"team": "BOS", "season": SEASON, "min_possessions": 100})
    assert res["ok"] is True
    assert len(res["rows"]) > 0
    assert res["best_net_unit"] is not None
    assert res["meta"].get("coverage") == "historical_lineups"

def test_get_lineup_stats_hist_floor_hides_everything_when_absurd():
    res = get_lineup_stats.invoke(
        {"team": "BOS", "season": SEASON, "min_possessions": 100000})
    assert res["ok"] is True
    assert res["rows"] == []
    assert "hidden" in res["meta"].get("data_note", "")

def test_get_lineup_stats_hist_uses_real_minutes_without_play_data(monkeypatch):
    import shared.tools.lineup as _lineup

    fixture = [{"GROUP_ID": "1-2-3-4-5", "GROUP_NAME": "starters",
                "GP": 35, "MIN": 432.4, "PTS": 1138.0, "PLUS_MINUS": 103.0,
                "FGA": 801.0, "OREB": 57.0, "TOV": 98.0, "FTA": 187.0,
                "TEAM_ID": BOS, "TEAM_ABBREVIATION": "BOS"}]
    monkeypatch.setattr(_lineup, "_warehouse_or_live",
                        lambda *a, **k: ([], {"source": "warehouse"}))
    monkeypatch.setattr(_lineup, "_possession_aggs", lambda *a: None)
    import shared.tools.team as _team
    monkeypatch.setattr(_team, "_hist_lineup_rows", lambda *a: list(fixture))
    res = get_lineup_stats.invoke(
        {"team": "BOS", "season": SEASON, "min_possessions": 10})
    assert res["ok"] is True
    assert res["rows"][0]["EST_MIN"] == 432.4
    assert any("estimated-possessions" in f
               for f in res["rows"][0]["flags"])
    assert "clock minutes" in res["meta"].get("data_note", "")

def test_get_lineups_hist_season_returns_rows_sorted_by_min():
    res = get_lineups.invoke({"team_id": "BOS", "season": SEASON})
    assert res["ok"] is True
    assert len(res["rows"]) > 10
    assert res["rows"][0]["GROUP_NAME"] == TOP_UNIT
    assert round(float(res["rows"][0]["MIN"]), 1) == TOP_MIN
    assert res["rows"][0]["SAMPLE_TIER"] == "large"
    mins = [float(r.get("MIN") or 0) for r in res["rows"]]
    assert mins == sorted(mins, reverse=True)

def test_get_wowy_hist_season_uses_real_minutes():
    res = get_wowy.invoke({"player_a": str(TATUM), "player_b": str(BROWN),
                           "team_id": "BOS", "season": SEASON})
    assert res["ok"] is True
    both = next(r for r in res["rows"] if r["split"] == "Both ON")
    assert both["minutes"] == 1433.6
    assert res["meta"].get("source") == "silver_hist_lineups"
    from shared import store
    with store.connect(read_only=True) as con:
        expected = con.execute(
            "SELECT round(sum(off_rating * poss)/sum(poss),2) FROM silver_hist_lineups "
            "WHERE _season=? AND team_id=? AND group_id LIKE '%-1628369-%' "
            "AND group_id LIKE '%-1627759-%' AND season_type='regular-season' "
            "AND measure_type='advanced' AND per_mode='totals' "
            "AND group_id IN (SELECT group_id FROM silver_hist_lineups WHERE _season=? "
            "AND team_id=? AND season_type='regular-season' AND measure_type='base' "
            "AND per_mode='totals')", [SEASON, BOS, SEASON, BOS],
        ).fetchone()[0]
    assert both['off_rating'] == expected

def test_get_on_off_hist_season_returns_rows():
    res = get_on_off.invoke({"player_id": str(TATUM),
                             "team_id": "BOS", "season": SEASON})
    assert res["ok"] is True
    stats = [r["Stat"] for r in res["rows"]]
    assert "Net Rating" in stats

@pytest.mark.canonical_warehouse
def test_get_lineup_stats_current_season_still_serves_warehouse():
    res = get_lineup_stats.invoke({"team": "BOS", "season": "2025-26"})
    assert res["ok"] is True
    assert len(res["rows"]) > 0
    assert res["meta"].get("coverage") != "historical_lineups"


def test_hist_advanced_ratings_join_and_unique_units():
    from shared import store
    from shared.tools.team import _hist_lineup_rows
    rows = _hist_lineup_rows(BOS, SEASON)
    assert len(rows) == len({r['GROUP_ID'] for r in rows})
    top = max(rows, key=lambda r: r['MIN'])
    assert round(top['MIN'], 1) == TOP_MIN
    with store.connect(read_only=True) as con:
        expected = con.execute(
            "SELECT off_rating, def_rating, net_rating, pace FROM silver_hist_lineups "
            "WHERE team_id=? AND _season=? AND group_id=? AND season_type='regular-season' "
            "AND measure_type='advanced' AND per_mode='totals'",
            [BOS, SEASON, top['GROUP_ID']],
        ).fetchone()
    assert tuple(top[k] for k in ('OFF_RATING', 'DEF_RATING', 'NET_RATING', 'PACE')) == expected
    assert all(v is not None for v in expected)


def test_hist_lineup_leaders_qualified_base_totals():
    from shared.tools.league import get_lineup_leaders
    res = get_lineup_leaders.invoke({'season': SEASON, 'min_minutes': 100, 'limit': 1})
    assert res['ok']
    assert res['rows'][0]['TEAM_ABBREVIATION'] == 'GSW'
    assert res['rows'][0]['MIN'] == 169.9
    assert res['rows'][0]['NET48'] == 21.2


@pytest.mark.parametrize('season_type,measure_type,per_mode', [
    ('playoffs', 'base', 'totals'), ('regular-season', 'base', 'pergame'),
    ('regular-season', 'advanced', 'totals'),
])
def test_hist_lineup_variant_selection(season_type, measure_type, per_mode):
    from shared.tools.team import _hist_lineup_rows
    from shared import store
    rows = _hist_lineup_rows(BOS, SEASON, season_type, measure_type, per_mode)
    with store.connect(read_only=True) as con:
        expected = con.execute(
            'SELECT count(*), sum(min) FROM silver_hist_lineups WHERE team_id=? AND _season=? '
            'AND season_type=? AND measure_type=? AND per_mode=?',
            [BOS, SEASON, season_type, measure_type, per_mode],
        ).fetchone()
    assert len(rows) == expected[0]
    assert sum(r['MIN'] for r in rows) == pytest.approx(expected[1])


def test_hist_lineup_empty_and_invalid_variant():
    from shared.tools.team import _hist_lineup_rows
    assert _hist_lineup_rows(BOS, '1900-01') == []
    with pytest.raises(ValueError):
        get_lineups.invoke({'team_id': 'BOS', 'season_type': 'invalid'})


def test_wowy_playoffs_uses_selected_totals():
    from shared import store
    res = get_wowy.invoke({'player_a': str(TATUM), 'player_b': str(BROWN),
                           'season': SEASON, 'team_id': 'BOS', 'season_type': 'playoffs'})
    assert res['ok']
    with store.connect(read_only=True) as con:
        expected = con.execute(
            "SELECT round(sum(min),1) FROM silver_hist_lineups WHERE _season=? AND team_id=? "
            "AND group_id LIKE '%-1628369-%' AND group_id LIKE '%-1627759-%' "
            "AND season_type='playoffs' AND measure_type='base' AND per_mode='totals'",
            [SEASON, BOS],
        ).fetchone()[0]
    assert next(r for r in res['rows'] if r['split'] == 'Both ON')['minutes'] == expected


@pytest.mark.parametrize('player_a,player_b', [('', ''), (str(TATUM), ''), (str(TATUM), str(BROWN))])
def test_wowy_playoffs_never_uses_regular_season_fallback(monkeypatch, player_a, player_b):
    import shared.tools.player as player
    import shared.tools.player.on_off_wowy as wowy

    def unexpected(*args, **kwargs):
        raise AssertionError('regular-season fallback must not be called')

    def broken_frame(*args, **kwargs):
        raise RuntimeError('warehouse split unavailable')

    monkeypatch.setattr(player, '_warehouse_or_live', unexpected)
    monkeypatch.setattr(wowy, '_wowy_split_frame', broken_frame)
    res = get_wowy.invoke({'player_a': player_a, 'player_b': player_b,
                           'team_id': 'BOS', 'season': SEASON, 'season_type': 'playoffs'})
    assert res['ok'] is False
    assert res['rows'] == []
    assert 'Playoff WOWY is not available' in res['error']


def test_wowy_fallback_cache_is_season_type_scoped(monkeypatch):
    import shared.tools.player as player
    calls = []

    def cached(*args, **kwargs):
        calls.append(kwargs['entity'])
        return [], {}

    monkeypatch.setattr(player, '_warehouse_or_live', cached)
    assert get_wowy.invoke({'season': SEASON})['ok']
    assert calls == ['wowy:regular-season:_']


def test_playoff_lineups_skip_unfiltered_competitive_possessions(monkeypatch):
    import shared.tools.team as team
    calls = []

    def competitive(*args):
        calls.append(args)
        return {}

    monkeypatch.setattr(team, '_competitive_lineup_nets', competitive)
    res = get_lineups.invoke({'team_id': 'BOS', 'season': SEASON, 'season_type': 'playoffs'})
    assert res['ok'] and res['rows']
    assert calls == []
    assert all(r['competitive_net'] is None and r['competitive_poss'] is None for r in res['rows'])
    assert all('playoffs' in r['competitive_note'] for r in res['rows'])
    assert 'omitted' in res['meta']['competitive_note']
    assert res['meta']['season_type'] == 'playoffs'


@pytest.mark.parametrize('measure,column', [('advanced', 'poss'), ('misc', 'pts_paint'),
                                            ('scoring', 'pct_pts_3pt'), ('usage', 'fgm')])
def test_selected_measure_stats_survive_codemode(measure, column):
    from analyst.tools.team import register
    from shared import store
    tool = register()['get_lineups']
    res = tool.invoke({'team_id': 'BOS', 'season': SEASON, 'measure_type': measure})
    assert res['ok'] and res['rows']
    with store.connect(read_only=True) as con:
        populated = con.execute(
            'SELECT * FROM silver_hist_lineups WHERE team_id=? AND _season=? '
            "AND season_type='regular-season' AND measure_type=? AND per_mode='totals' LIMIT 1",
            [BOS, SEASON, measure],
        ).fetchdf().to_dict('records')[0]
    row = next(r for r in res['rows'] if r['GROUP_ID'] == populated['group_id'])
    assert row[column.upper()] == populated[column]
    assert column.upper() in res['columns']
    assert row['GP'] is not None and row['MIN'] is not None
    assert row['PTS'] is not None
