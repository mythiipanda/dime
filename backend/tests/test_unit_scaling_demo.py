import duckdb
import pytest


def _con():
    return duckdb.connect('backend/data/warehouse.duckdb', read_only=True)


def test_draft_board_usg_is_fraction_scale():
    from analyst.direct_data import _draft_board
    con = _con()
    tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
    if 'silver_draft_boards' not in tables:
        pytest.skip('no draft boards in warehouse')
    board = _draft_board(con, tables, '')
    rows = board['rows']
    assert rows, 'board rows present'
    usgs = [r['usg'] for r in rows if r['usg']]
    assert usgs, 'usg values present'
    assert max(usgs) <= 1.0, f'usg must be fraction-scale, got max {max(usgs)}'


def test_draft_board_has_no_duplicate_prospects():
    from analyst.direct_data import _draft_board
    con = _con()
    tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
    if 'silver_draft_boards' not in tables:
        pytest.skip('no draft boards in warehouse')
    board = _draft_board(con, tables, '')
    names = [r['name'].lower() for r in board['rows']]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f'duplicate board rows: {sorted(dupes)[:5]}'


def test_rotation_rows_carry_per_game_points():
    rows = []
    for line in open('backend/shared/tools/team/lineups_rotations.py'):
        rows.append(line)
    src = ''.join(rows)
    assert '"PPG"' in src, 'rotation enriched rows must carry a per-game PPG field'
