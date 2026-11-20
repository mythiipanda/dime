from itertools import product
from typing import get_args

import pytest

from shared.lineup_variants import MeasureType, PerMode, SeasonType, validate_variants
from shared.tools.player.on_off_wowy import _wowy_pairing
from shared.tools.team.lineups_rotations import _hist_lineup_rows


def test_all_stored_variants_are_valid():
    for values in product(get_args(SeasonType), get_args(MeasureType), get_args(PerMode)):
        validate_variants(*values)


@pytest.mark.parametrize('name', ['season_type', 'measure_type', 'per_mode'])
@pytest.mark.parametrize('value', ['', "regular-season' OR 1=1 --", 'invalid'])
def test_invalid_variants_rejected_before_query(name, value):
    with pytest.raises(ValueError, match=f'Invalid {name}'):
        _hist_lineup_rows(1610612738, '2022-23', **{name: value})
    if name == 'season_type':
        with pytest.raises(ValueError, match='Invalid season_type'):
            _wowy_pairing(None, '2022-23', None, 1628369, 1627759, season_type=value)
