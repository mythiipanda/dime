import duckdb


def _draft_con():
    con = duckdb.connect(':memory:')
    con.execute(
        'CREATE TABLE silver_draft_boards ('
        '"ORDER" INTEGER, PLAYER_NAME VARCHAR, PLAYER_SLUG VARCHAR, POSITION VARCHAR, '
        'SCHOOL VARCHAR, TEAM_ABBREVIATION VARCHAR, HEIGHT VARCHAR, WEIGHT_LBS INTEGER, '
        'CLASS_YEAR VARCHAR, AGE DOUBLE, BOARD VARCHAR, _source VARCHAR, _season VARCHAR, '
        '_fetched_at VARCHAR)')
    con.execute(
        'CREATE TABLE silver_prospect_stats ('
        'PLAYER_NAME VARCHAR, TEAM VARCHAR, GP DOUBLE, PTS DOUBLE, REB DOUBLE, AST DOUBLE, '
        'TS_PCT DOUBLE, USG DOUBLE, _source VARCHAR, _season VARCHAR, _fetched_at VARCHAR)')
    board_rows = [
        (1, 'Cam Prospect', 'cam-prospect', 'G', 'Duke', 'BKN', '6-5', 200, 'Fr', 18.5, 'mock_draft', 'tankathon', '2027', '2026-11-01'),
        (4, 'Mock Only', 'mock-only', 'G', 'Arizona', 'NYK', '6-4', 195, 'Fr', 18.4, 'mock_draft', 'tankathon', '2027', '2026-11-01'),
        (1, 'Cam Prospect', 'cam-prospect', 'G', 'Duke', '', '6-5', 200, 'Fr', 18.5, 'big_board', 'tankathon', '2027', '2026-11-01'),
        (30, 'Cameron Prospect', 'cam-prospect', 'G', 'Duke', '', '6-5', 200, 'Fr', 18.5, 'big_board', 'tankathon', '2027', '2026-11-01'),
        (2, 'Other Wing', 'other-wing', 'F', 'Kansas', '', '6-8', 215, 'Fr', 18.8, 'big_board', 'tankathon', '2027', '2026-11-01'),
        (3, 'Big Board Only', 'big-board-only', 'F', 'UConn', '', '6-7', 210, 'So', 19.4, 'big_board', 'tankathon', '2027', '2026-11-01'),
    ]
    con.executemany('INSERT INTO silver_draft_boards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', board_rows)
    stat_rows = [
        ('Cam Prospect', 'Duke', 10.0, 18.0, 5.0, 4.0, 0.61, 28.7, 'barttorvik', '2027', '2026-11-01'),
        ('Cam Prospect', 'Duke', 20.0, 19.2, 6.1, 4.0, 0.61, 28.7, 'barttorvik', '2027', '2026-11-01'),
        ('Other Wing', 'Kentucky', 31.0, 30.0, 7.0, 3.0, 0.59, 35.0, 'barttorvik', '2027', '2026-11-01'),
        ('Other Wing', 'Kansas', 25.0, 22.1, 6.0, 4.0, 0.58, 27.4, 'barttorvik', '2027', '2026-11-01'),
    ]
    con.executemany('INSERT INTO silver_prospect_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', stat_rows)
    return con


def _run_draft_board(con):
    from analyst.direct_data import _draft_board
    tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
    return _draft_board(con, tables, '')


def _draft_board_fixture():
    con = _draft_con()
    try:
        return _run_draft_board(con)
    finally:
        con.close()


def test_draft_board_selects_one_board_and_dedupes_prospect_slugs():
    board = _draft_board_fixture()
    rows = board['rows']
    assert board['board'] == 'big_board'
    assert board['order_semantics'] == 'rank'
    assert [(r['board_order'], r['name']) for r in rows] == [
        (1, 'Cam Prospect'), (2, 'Other Wing'), (3, 'Big Board Only')]
    assert [r['pick'] for r in rows] == [r['board_order'] for r in rows]
    assert 'Mock Only' not in {r['name'] for r in rows}


def test_draft_board_usg_stays_percent_point_scale():
    board = _draft_board_fixture()
    cam = next(r for r in board['rows'] if r['name'] == 'Cam Prospect')
    assert cam['usg'] == 28.7
    assert 20 <= cam['usg'] <= 35
    assert cam['ts_pct'] == 0.61


def test_draft_board_stats_use_school_to_break_name_collision():
    board = _draft_board_fixture()
    wing = next(r for r in board['rows'] if r['name'] == 'Other Wing')
    assert wing['pts'] == 22.1
    assert wing['usg'] == 27.4


def test_draft_board_mock_only_fallback_declares_pick_semantics():
    con = _draft_con()
    try:
        con.execute("DELETE FROM silver_draft_boards WHERE BOARD = 'big_board'")
        board = _run_draft_board(con)
    finally:
        con.close()
    assert board['board'] == 'mock_draft'
    assert board['order_semantics'] == 'pick'
    assert [(r['board_order'], r['name']) for r in board['rows']] == [
        (1, 'Cam Prospect'), (4, 'Mock Only')]


def test_draft_board_unresolved_same_name_collision_stays_stats_missing():
    con = _draft_con()
    try:
        con.execute(
            "UPDATE silver_draft_boards SET SCHOOL = 'Gonzaga' "
            "WHERE BOARD = 'big_board' AND PLAYER_NAME = 'Other Wing'")
        board = _run_draft_board(con)
    finally:
        con.close()
    wing = next(r for r in board['rows'] if r['name'] == 'Other Wing')
    assert wing['pts'] is None
    assert wing['usg'] is None


def test_prospect_usg_column_semantics_declare_percent_point_scale():
    from shared.tools.league.sql_schema import _column_semantics
    unit, note = _column_semantics('silver_prospect_stats', 'USG')
    assert unit == 'pct'
    assert '0-100' in note
    assert 'not a 0-1 fraction' in note
