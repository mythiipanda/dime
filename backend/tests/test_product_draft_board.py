import duckdb
import pytest


def _con():
    con = duckdb.connect(':memory:')
    con.execute('CREATE TABLE silver_draft_boards("ORDER" INTEGER, PLAYER_NAME VARCHAR, POSITION VARCHAR, SCHOOL VARCHAR, BOARD VARCHAR, _season VARCHAR, _fetched_at VARCHAR)')
    con.execute('CREATE TABLE silver_prospect_stats(PLAYER_NAME VARCHAR, TEAM VARCHAR, GP DOUBLE, PTS DOUBLE, REB DOUBLE, AST DOUBLE, TS_PCT DOUBLE, USG DOUBLE, _season VARCHAR)')
    return con


def test_draft_board_uses_one_coherent_board_type():
    from analyst.direct_data import _draft_board

    con = _con()
    con.executemany('INSERT INTO silver_draft_boards VALUES (?, ?, ?, ?, ?, ?, ?)', [
        (1, 'Shared Prospect', 'G', 'Duke', 'mock_draft', '2027', 'fetched'),
        (2, 'Mock Only', 'F', 'Kansas', 'mock_draft', '2027', 'fetched'),
        (1, 'Shared Prospect', 'G', 'Duke', 'big_board', '2027', 'fetched'),
        (2, 'Big Board Only', 'F', 'UCLA', 'big_board', '2027', 'fetched'),
    ])

    out = _draft_board(con, {'silver_draft_boards'}, '2027')

    assert [r['name'] for r in out['rows']] == ['Shared Prospect', 'Big Board Only']


def test_draft_board_falls_back_to_mock_draft():
    from analyst.direct_data import _draft_board

    con = _con()
    con.executemany('INSERT INTO silver_draft_boards VALUES (?, ?, ?, ?, ?, ?, ?)', [
        (1, 'Mock Prospect', 'G', 'Duke', 'mock_draft', '2027', 'fetched'),
    ])

    out = _draft_board(con, {'silver_draft_boards'}, '2027')

    assert [r['name'] for r in out['rows']] == ['Mock Prospect']


def test_draft_board_matches_collided_stats_by_school():
    from analyst.direct_data import _draft_board

    con = _con()
    con.executemany('INSERT INTO silver_draft_boards VALUES (?, ?, ?, ?, ?, ?, ?)', [
        (1, 'Christian Jones', 'G', 'Murray St.', 'big_board', '2027', 'fetched'),
    ])
    con.executemany('INSERT INTO silver_prospect_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', [
        ('Christian Jones', 'Murray St.', 10.0, 11.1, 3.1, 2.1, 0.61, 22.2, '2027'),
        ('Christian Jones', 'UMass Lowell', 30.0, 31.0, 8.0, 5.0, 0.55, 33.3, '2027'),
        ('Christian Jones', 'Long Beach St.', 25.0, 25.0, 6.0, 4.0, 0.58, 28.7, '2027'),
    ])

    out = _draft_board(con, {'silver_draft_boards', 'silver_prospect_stats'}, '2027')
    row = out['rows'][0]

    assert row['gp'] == 10.0
    assert row['pts'] == 11.1
    assert row['usg'] == pytest.approx(0.222)


def test_draft_board_leaves_ambiguous_collided_stats_absent():
    from analyst.direct_data import _draft_board

    con = _con()
    con.executemany('INSERT INTO silver_draft_boards VALUES (?, ?, ?, ?, ?, ?, ?)', [
        (1, 'Christian Jones', 'G', 'Murray State', 'big_board', '2027', 'fetched'),
    ])
    con.executemany('INSERT INTO silver_prospect_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', [
        ('Christian Jones', 'UMass Lowell', 30.0, 31.0, 8.0, 5.0, 0.55, 33.3, '2027'),
        ('Christian Jones', 'Long Beach St.', 25.0, 25.0, 6.0, 4.0, 0.58, 28.7, '2027'),
    ])

    out = _draft_board(con, {'silver_draft_boards', 'silver_prospect_stats'}, '2027')
    row = out['rows'][0]

    assert row['gp'] is None
    assert row['pts'] is None
    assert row['usg'] is None
