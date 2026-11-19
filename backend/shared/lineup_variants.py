from typing import Literal, get_args

SeasonType = Literal['regular-season', 'playoffs']
MeasureType = Literal['base', 'advanced', 'defense', 'misc', 'opponent', 'scoring', 'usage']
PerMode = Literal['totals', 'pergame']

DEFAULT_FILTER = "season_type = 'regular-season' AND measure_type = 'base' AND per_mode = 'totals'"


def validate_variants(season_type: str = 'regular-season', measure_type: str = 'base', per_mode: str = 'totals') -> None:
    for name, value, allowed in (
        ('season_type', season_type, get_args(SeasonType)),
        ('measure_type', measure_type, get_args(MeasureType)),
        ('per_mode', per_mode, get_args(PerMode)),
    ):
        if value not in allowed:
            raise ValueError(f'Invalid {name}: {value!r}; expected one of {allowed}')
