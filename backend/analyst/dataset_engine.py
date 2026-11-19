
import io, time, base64
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

def warehouse_table(table: str, season: str = '') -> dict:
    from shared import store
    if not re.fullmatch(r'silver_[a-z0-9_]+', table):
        return {'ok': False, 'error': 'Table not found'}
    con = store.connect(read_only=True)
    try:
        if table not in {r[0] for r in con.execute('SHOW TABLES').fetchall()}:
            return {'ok': False, 'error': 'Table not found'}
        schema = con.execute(f'DESCRIBE "{table}"').fetchall()
        columns = [r[0] for r in schema]
        where = ' WHERE _season = ?' if season and '_season' in columns else ''
        args = [season] if where else []
        count = con.execute(f'SELECT count(*) FROM "{table}"{where}', args).fetchone()[0]
        cursor = con.execute(f'SELECT * FROM "{table}"{where} LIMIT 50', args)
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        seasons = [r[0] for r in con.execute(f'SELECT DISTINCT _season FROM "{table}" WHERE _season IS NOT NULL ORDER BY 1 DESC LIMIT 100').fetchall()] if '_season' in columns else []
        fetched = con.execute(f'SELECT max(_fetched_at) FROM "{table}"{where}', args).fetchone()[0] if '_fetched_at' in columns else None
        from shared.freshness import table_data_through
        result = {'ok': True, 'table': table, 'columns': [{'name': r[0], 'type': r[1]} for r in schema], 'rows': rows, 'count': count, 'seasons': seasons, 'last_fetch': fetched, 'data_through': table_data_through(con, table, columns), 'limit': 50}
        return json.loads(json.dumps(result, default=str))
    finally:
        con.close()

def home_snapshot() -> dict:
    from shared import store
    today = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
        schedule = {'table': 'silver_scoreboard', 'available': False, 'games': [], 'next_date': None, 'seasons': [], 'last_fetch': None}
        for table, date_column in [('silver_schedule', 'date'), ('silver_scoreboard', 'GAME_DATE_EST')]:
            if table not in tables:
                continue
            columns = [r[0] for r in con.execute(f'DESCRIBE "{table}"').fetchall()]
            if date_column in columns:
                day = "cast(coalesce(try_cast(date AS TIMESTAMPTZ), try_strptime(date, '%Y-%m-%dT%H:%MZ') AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York' AS DATE)" if table == 'silver_schedule' else 'try_cast(GAME_DATE_EST AS DATE)'
                cursor = con.execute(f'SELECT * FROM "{table}" WHERE {day} = cast(? AS DATE)', [today])
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                games = list({str(row.get('GAME_ID', row.get('id', i))): row for i, row in enumerate(rows)}.values())
                next_date = con.execute(f'SELECT min({day}) FROM "{table}" WHERE {day} > cast(? AS DATE)', [today]).fetchone()[0]
                seasons = [str(row[0]) for row in con.execute(f'SELECT DISTINCT _season FROM "{table}" WHERE _season IS NOT NULL ORDER BY 1 DESC').fetchall()] if '_season' in columns else []
                fetched = con.execute(f'SELECT max(_fetched_at) FROM "{table}"').fetchone()[0] if '_fetched_at' in columns else None
                candidate = {**schedule, 'table': table, 'available': True, 'games': games, 'next_date': next_date, 'seasons': seasons, 'last_fetch': fetched}
                if not schedule['available'] or games or (next_date and not schedule['next_date']):
                    schedule = candidate
                if games:
                    break
        snapshot = {'table': 'silver_team_ratings', 'season': None, 'rows': [], 'last_fetch': None}
        if 'silver_team_ratings' in tables:
            season = con.execute('SELECT max(_season) FROM silver_team_ratings').fetchone()[0]
            if season:
                cursor = con.execute('SELECT TEAM_NAME, GP, NET_RATING, _fetched_at FROM silver_team_ratings WHERE _season = ? ORDER BY NET_RATING DESC NULLS LAST LIMIT 8', [season])
                rows = [dict(zip(['TEAM_NAME', 'GP', 'NET_RATING', '_fetched_at'], row)) for row in cursor.fetchall()]
                snapshot = {**snapshot, 'season': season, 'rows': rows, 'last_fetch': max((str(row['_fetched_at']) for row in rows if row.get('_fetched_at')), default=None)}
        return json.loads(json.dumps({'ok': True, 'date': today, 'schedule': schedule, 'snapshot': snapshot}, default=str))
    finally:
        con.close()

def binary_data(content, media_type):
    raw = content.encode() if isinstance(content, str) else content
    return {"encoding": "base64", "media_type": media_type, "body": base64.b64encode(raw).decode()}

_DATASETS_TABLES = {'standings': 'silver_standings', 'leaders': 'silver_leaders_pts', 'injuries': 'silver_injuries', 'player_gamelogs': 'silver_player_gamelogs', 'team_games': 'silver_team_games', 'scoreboard': 'silver_scoreboard', 'shots': 'silver_shots', 'lineups': 'silver_lineups', 'on_off': 'silver_on_off', 'wowy': 'silver_wowy', 'four_factors': 'silver_four_factors', 'hustle': 'silver_hustle_player', 'combine': 'silver_combine', 'ratings': 'silver_team_ratings', 'playoffs': 'silver_playoffs', 'playoff_gamelogs': 'silver_playoff_gamelogs', 'draft': 'silver_hist_draft', 'raptor': 'silver_raptor_player', 'player_seasons': 'silver_hist_player_seasons'}

_DATASETS_FRESHNESS_TTL_S = 300

_DATASETS_FRESHNESS_CACHE = {'at': 0.0, 'payload': None}

def _datasets_freshness_payload() -> dict:
    from shared import store
    from shared.freshness import table_data_through
    con = store.connect(read_only=True)
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
        stale = store.read_frame(table, '_season = ? AND _entity = ?', [season, entity])
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
    try:
        frame = frame.with_columns(pl.col('GAME_DATE').str.strptime(pl.Date, '%b %d, %Y', strict=False).fill_null(pl.col('GAME_DATE').str.strptime(pl.Date, '%Y-%m-%d', strict=False)).alias('_d'))
        if frame['_d'].null_count() < frame.height:
            frame = frame.sort('_d', descending=True, nulls_last=True).drop('_d')
        else:
            frame = frame.drop('_d')
    except Exception:
        if '_d' in frame.columns:
            frame = frame.drop('_d')
    return frame

def dataset(name: str, season: str='2025-26', player_id: int=0, team_id: int=0, game_id: str='', game_date: str='', stat: str='PTS', ids: str='', player_a: str='', player_b: str='', fmt: str='json'):
    import polars as pl
    if name == 'zone_splits':
        from shared.tools.player import get_shot_zones
        if not player_id:
            return {'ok': False, 'error': 'missing id param for this dataset'}
        result = get_shot_zones.invoke({'player_id': player_id, 'season': season, 'min_attempts': 0})
        if not result.get('ok'):
            return {'ok': False, 'error': result.get('error', 'shot zones unavailable'), 'meta': result.get('meta')}
        frame = pl.DataFrame(result.get('rows', []))
        if fmt == 'csv':
            return binary_data(frame.write_csv(), 'text/csv')
        if fmt == 'parquet':
            buf = io.BytesIO()
            frame.write_parquet(buf)
            return binary_data(buf.getvalue(), 'application/octet-stream')
        return {'ok': True, 'data': frame.to_dicts(), 'meta': result.get('meta')}
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
    try:
        frame = store.read_frame(table, '_season = ?', [season])
    except store.TableAbsent:
        if name != 'shots':
            raise
        frame = pl.DataFrame()
    if name == 'leaders' and frame.height > 0:
        from shared.tools import clamp_stat
        stat_col = clamp_stat(stat)
        if stat_col in frame.columns:
            frame = frame.sort(stat_col, descending=True, nulls_last=True)
    if entity_scoped:
        if entity and (name != 'shots' or frame.width):
            frame = store.read_frame(table, '_season = ? AND _entity = ?', [season, entity])
        else:
            frame = frame.clear()
    cached = frame.height > 0
    if not cached:
        live = _datasets_fetch_live(name, season, player_id, team_id, game_id, game_date, stat, ids)
        if live is None:
            return {'ok': False, 'error': 'missing id param for this dataset'}
        if not live.ok and not (name == 'shots' and live.error == 'empty upstream response'):
            if name == 'shots':
                return {'ok': False, 'error': live.error or 'Shot data unavailable for this player and season', 'source': live.meta.source}
            return _failed_live_response(live, entity_scoped, entity, table, season)
        if name == 'shots':
            frame = live.frame
        else:
            try:
                store.save_frame(table, live, entity)
            except PermissionError:
                pass
            if entity_scoped:
                try:
                    frame = store.read_frame(table, '_fetched_at = ?', [live.meta.fetched_at])
                except store.TableAbsent:
                    frame = getattr(live, 'frame', frame)
            else:
                try:
                    frame = store.read_frame(table, '_season = ?', [season])
                except store.TableAbsent:
                    frame = getattr(live, 'frame', frame)
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
    if name == 'shots' and not cached:
        out['meta'].update(source=live.meta.source, fetched_at=live.meta.fetched_at)
    out['ok'] = True
    return out
