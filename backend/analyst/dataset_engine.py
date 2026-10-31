"""Dataset engine extracted from the product HTTP adapter. No HTTP ownership."""

import io, time, base64

def binary_data(content, media_type):
    raw = content.encode() if isinstance(content, str) else content
    return {"encoding": "base64", "media_type": media_type, "body": base64.b64encode(raw).decode()}

_DATASETS_TABLES = {'standings': 'silver_standings', 'leaders': 'silver_leaders_pts', 'injuries': 'silver_injuries', 'player_gamelogs': 'silver_player_gamelogs', 'team_games': 'silver_team_games', 'scoreboard': 'silver_scoreboard', 'shots': 'silver_shots', 'lineups': 'silver_lineups', 'on_off': 'silver_on_off', 'wowy': 'silver_wowy', 'four_factors': 'silver_four_factors', 'hustle': 'silver_hustle_player', 'combine': 'silver_combine', 'ratings': 'silver_team_ratings', 'playoffs': 'silver_playoffs', 'playoff_gamelogs': 'silver_playoff_gamelogs', 'draft': 'silver_hist_draft', 'raptor': 'silver_raptor_player', 'player_seasons': 'silver_hist_player_seasons'}

_DATASETS_FRESHNESS_TTL_S = 300

_DATASETS_FRESHNESS_CACHE = {'at': 0.0, 'payload': None}

def _datasets_freshness_payload() -> dict:
    from shared import store
    from shared.freshness import table_data_through
    con = store.connect()
    try:
        tables = [r[0] for r in con.execute('SHOW TABLES').fetchall()]
        rows = []
        for t in sorted(tables):
            if not t.startswith('silver_'):
                continue
            cols = [r[1] for r in con.execute(f'PRAGMA table_info({t})').fetchall()]
            n = con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
            last = None
            if '_fetched_at' in cols:
                last = con.execute(f'SELECT MAX(_fetched_at) FROM {t}').fetchone()[0]
            rows.append({'table': t, 'rows': n, 'last_fetch': last, 'data_through': table_data_through(con, t, cols)})
    finally:
        con.close()
    return {'ok': True, 'rows': rows}

def datasets_freshness() -> dict:
    now = time.monotonic()
    cached = _DATASETS_FRESHNESS_CACHE
    if cached['payload'] is not None and now - cached['at'] < _DATASETS_FRESHNESS_TTL_S:
        return cached['payload']
    payload = _datasets_freshness_payload()
    cached['payload'] = payload
    cached['at'] = now
    return payload

def _pinned_rows(rows: list[dict], pin: list[str]) -> list[dict]:
    pinned = []
    for r in rows:
        keyed = {k: r[k] for k in pin if k in r}
        keyed.update({k: v for k, v in r.items() if k not in keyed})
        pinned.append(keyed)
    return pinned

def _sample_tier_rows(rows: list[dict]) -> list[dict]:
    from shared.tools._core import sample_tier
    for r in rows:
        tier, est = sample_tier(r.get('MIN'))
        r['SAMPLE_TIER'] = tier
        r['EST_POSS'] = est
        if tier == 'small' and (not r.get('SAMPLE')):
            r['SAMPLE'] = 'small: under ~100 possessions'
    return rows

def _datasets_envelope(table: str, season: str, frame: object, cached: bool) -> dict:
    import polars as pl
    assert isinstance(frame, pl.DataFrame)
    meta = {'season': season, 'rows': frame.height, 'cached': cached}
    if frame.height and '_source' in frame.columns:
        meta['source'] = frame['_source'][0]
        meta['fetched_at'] = frame['_fetched_at'][0]
    rows = frame.to_dicts()
    if table.startswith('silver_leaders_'):
        stat_col = table.rsplit('_', 1)[-1].upper()
        if stat_col == 'FG':
            stat_col = 'FG_PCT'
        rows = _pinned_rows(rows, ['RANK', 'PLAYER', 'TEAM', stat_col, 'GP', 'MIN'])
    if table == 'silver_standings':
        rows = _pinned_rows(rows, ['TeamCity', 'TeamName', 'Conference', 'Record', 'WINS', 'LOSSES', 'WinPCT', 'PlayoffRank', 'ClinchIndicator'])
    if table == 'silver_lineups':
        rows = _sample_tier_rows(rows)
    return {'data': rows, 'meta': meta}

def _datasets_fetch_live(name: str, season: str, player_id: int, team_id: int, game_id: str, game_date: str, stat: str, ids: str=''):
    from shared.sources import espn, nba_stats
    if name == 'standings':
        return nba_stats.standings(season)
    if name == 'leaders':
        from shared.tools import clamp_stat
        try:
            stat = clamp_stat(stat)
        except ValueError:
            stat = 'PTS'
        return nba_stats.leaders(stat, season)
    if name == 'injuries':
        return espn.injuries(season)
    if name == 'player_gamelogs' and player_id:
        return nba_stats.player_gamelog(player_id, season)
    if name == 'team_games' and team_id:
        return nba_stats.team_gamelog(team_id, season)
    if name == 'scoreboard' and game_date:
        return nba_stats.scoreboard(game_date, season)
    if name == 'shots' and player_id:
        return nba_stats.shot_chart(player_id, season, team_id)
    if name == 'lineups' and team_id:
        return nba_stats.lineups(team_id, season)
    if name in ('on_off', 'four_factors') and player_id and team_id:
        from shared.sources import pbpstats
        if name == 'on_off':
            return pbpstats.on_off(player_id, team_id, season)
        return pbpstats.four_factors(player_id, team_id, season)
    if name == 'combine':
        return nba_stats.combine(season)
    if name == 'ratings':
        return nba_stats.team_ratings(season)
    if name == 'playoffs':
        return nba_stats.playoff_results(season)
    if name == 'wowy' and team_id and ids:
        from shared.sources import pbpstats
        parsed = [int(x) for x in ids.split(',') if x.strip().isdigit()]
        return pbpstats.wowy(parsed, team_id, season)
    if name == 'hustle':
        return nba_stats.hustle('player', season)
    return None

def _wowy_dataset(season: str, player_a: str, player_b: str, team_id: int, fmt: str):
    import polars as pl
    from shared.tools.player import get_wowy
    res = get_wowy.invoke({'player_a': player_a, 'player_b': player_b, 'team_id': team_id, 'season': season})
    if not res.get('ok'):
        return {'ok': False, 'error': res.get('error', 'wowy failed')}
    rows = res.get('rows', [])
    if fmt == 'csv':
        df = pl.DataFrame(rows)
        return binary_data(df.write_csv(), media_type='text/csv')
    return {'ok': True, 'data': rows, 'verdict': res.get('verdict'), 'meta': res.get('meta')}

def _clamp_leaders_stat(stat: str) -> str:
    from shared.tools import clamp_stat
    try:
        return clamp_stat(stat)
    except ValueError:
        return 'PTS'

def _dataset_entity(player_id: int, team_id: int, game_id: str, game_date: str, ids: str) -> str:
    if player_id:
        return f'player:{player_id}'
    if team_id:
        return f'team:{team_id}'
    if game_id:
        return f'game:{game_id}'
    if game_date:
        return f'date:{game_date}'
    if ids:
        return f'wowy:{ids}'
    return ''

def _failed_live_response(live, entity_scoped: bool, entity: str, table: str, season: str) -> dict:
    from shared import store
    stale = None
    if entity_scoped and entity:
        stale = store.read_frame(table, '_entity = ?', [entity])
    if stale is not None and stale.height > 0:
        out = _datasets_envelope(table, season, stale, True)
        out['ok'] = True
        out['meta']['stale'] = True
        out['meta']['live_error'] = live.error or 'empty upstream response'
        out['meta']['live_source'] = live.meta.source
        return out
    return {'ok': False, 'error': live.error, 'source': live.meta.source, 'detail': 'live source failed and no cached rows for this entity'}

def _sort_frame_by_game_date(frame):
    import polars as pl
    for fmt_s in ('%b %d, %Y', '%Y-%m-%d'):
        try:
            frame = frame.with_columns(pl.col('GAME_DATE').str.strptime(pl.Date, fmt_s, strict=False).alias('_d'))
            if frame['_d'].null_count() < frame.height:
                frame = frame.sort('_d', descending=True, nulls_last=True).drop('_d')
            else:
                frame = frame.drop('_d')
                continue
            break
        except Exception:
            if '_d' in frame.columns:
                frame = frame.drop('_d')
            continue
    return frame

def dataset(name: str, season: str='2025-26', player_id: int=0, team_id: int=0, game_id: str='', game_date: str='', stat: str='PTS', ids: str='', player_a: str='', player_b: str='', fmt: str='json'):
    import polars as pl
    if name == 'wowy' and (player_a or ids):
        return _wowy_dataset(season, player_a or ids, player_b, team_id, fmt)
    if name not in _DATASETS_TABLES:
        return {'ok': False, 'error': f'unknown dataset, pick one of {sorted(_DATASETS_TABLES)}'}
    from shared import store
    table = _DATASETS_TABLES[name]
    if name == 'leaders':
        stat = _clamp_leaders_stat(stat)
        table = f'silver_leaders_{stat.lower()}'
    entity_scoped = name in ('player_gamelogs', 'team_games', 'shots', 'scoreboard', 'lineups', 'on_off', 'wowy', 'four_factors')
    entity = _dataset_entity(player_id, team_id, game_id, game_date, ids)
    frame = store.read_frame(table, '_season = ?', [season])
    if name == 'leaders' and frame.height > 0:
        from shared.tools import clamp_stat
        stat_col = clamp_stat(stat)
        if stat_col in frame.columns:
            frame = frame.sort(stat_col, descending=True, nulls_last=True)
    if entity_scoped:
        if entity:
            frame = store.read_frame(table, '_season = ? AND _entity = ?', [season, entity])
        else:
            frame = frame.clear()
    cached = frame.height > 0
    if not cached:
        live = _datasets_fetch_live(name, season, player_id, team_id, game_id, game_date, stat, ids)
        if live is None:
            return {'ok': False, 'error': 'missing id param for this dataset'}
        if not live.ok:
            return _failed_live_response(live, entity_scoped, entity, table, season)
        store.save_frame(table, live, entity)
        if entity_scoped:
            frame = store.read_frame(table, '_fetched_at = ?', [live.meta.fetched_at])
        else:
            frame = store.read_frame(table, '_season = ?', [season])
    if name in ('player_gamelogs', 'team_games', 'playoff_gamelogs') and frame.height > 0 and ('GAME_DATE' in frame.columns):
        frame = _sort_frame_by_game_date(frame)
    if name in ('player_gamelogs', 'team_games', 'playoff_gamelogs') and frame.height > 0:
        from shared.tools.gamelog import dedupe_game_log_frame
        frame = dedupe_game_log_frame(frame)
    if fmt == 'csv':
        return binary_data(frame.write_csv(), media_type='text/csv')
    if fmt == 'parquet':
        buf = io.BytesIO()
        frame.write_parquet(buf)
        return binary_data(buf.getvalue(), media_type='application/octet-stream')
    out = _datasets_envelope(table, season, frame, cached)
    out['ok'] = True
    return out
