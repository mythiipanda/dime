from typing import Literal

SeasonType = Literal['regular-season', 'playoffs']
MeasureType = Literal['base', 'advanced', 'defense', 'misc', 'opponent', 'scoring', 'usage']
PerMode = Literal['totals', 'pergame']

DEFAULT_FILTER = "season_type = 'regular-season' AND measure_type = 'base' AND per_mode = 'totals'"
