import json
from langchain_core.tools import tool

@tool(description='List the supported warehouse-backed board metrics.')
def product_board_metrics() -> dict:
    from analyst.boards import metrics
    return metrics()

@tool(description='Fill a bounded player board with read-only warehouse values and citations.')
def product_board_fill(payload: dict) -> dict:
    from analyst.boards import fill
    return fill(payload)

@tool(description='Seed a player board deterministically from one warehouse metric.')
def product_board_seed(payload: dict) -> dict:
    from analyst.boards import seed
    return seed(payload)

@tool(description='Read a bounded public warehouse table schema and sample.')
def product_table_detail(table: str, season: str = '') -> dict:
    from analyst.dataset_engine import warehouse_table
    return warehouse_table(table, season)

@tool(description='Read the cached schedule and warehouse team ratings snapshot.')
def product_home() -> dict:
    from analyst.dataset_engine import home_snapshot
    return home_snapshot()

@tool(description='Append an existing product chat row to the state database.')
def product_save_chat(thread: str, role: str, content: str, owner: str) -> dict:
    from shared import store
    store.save_chat(thread, role, content, owner=owner)
    return {"ok": True}

@tool(description='Append an existing product run row to the state database.')
def product_save_run(thread: str, question: str, answer: str, owner: str, run_id: str) -> dict:
    from shared import store
    store.save_run(thread, question, answer, [], [], owner=owner, run_id=run_id)
    return {"ok": True}

@tool(description='List existing product state threads for one owner.')
def product_threads(owner: str) -> dict:
    from shared import store
    return {"threads": store.list_threads(owner=owner)}

@tool(description='List existing product state runs for one owner and thread.')
def product_runs(thread: str, owner: str) -> dict:
    from shared import store
    return {"runs": store.list_runs(thread, owner=owner)}

@tool(description='Read the data engine warehouse identity and semantic baseline.')
def product_warehouse_identity() -> dict:
    from shared import store
    from shared.semantic_baseline import SEMANTIC_BASELINE
    identity = store.warehouse_identity()
    return {"warehouse": {"warehouse_id": identity["warehouse_id"], "sha256": identity["warehouse_sha256"], "sha256_derivation": store.WAREHOUSE_SHA256_DERIVATION}, "semantic_baseline": dict(SEMANTIC_BASELINE)}

@tool(description='Check the existing ratings readiness contract.')
def product_warehouse_health() -> dict:
    from shared import store
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {"ok": False, "reason": "warehouse_unreachable"}
    try:
        if 'silver_team_ratings' not in {row[0] for row in con.execute('SHOW TABLES').fetchall()}:
            return {"ok": False, "reason": "ratings_table_missing"}
        count = con.execute('SELECT COUNT(*) FROM silver_team_ratings').fetchone()[0]
    except Exception:
        return {"ok": False, "reason": "ratings_unreadable"}
    finally:
        con.close()
    return {"ok": True} if count else {"ok": False, "reason": "ratings_table_empty"}

@tool(description='Read or fetch a dataset using the existing Python season and source semantics.')
def product_dataset(name: str, season: str = '2025-26', player_id: int = 0, team_id: int = 0, game_id: str = '', game_date: str = '', stat: str = 'PTS', ids: str = '', player_a: str = '', player_b: str = '', fmt: str = 'json') -> dict:
    from analyst.dataset_engine import dataset
    return dataset(name, season, player_id, team_id, game_id, game_date, stat, ids, player_a, player_b, fmt)

@tool(description='Read the cached existing dataset freshness report.')
def product_freshness() -> dict:
    from analyst.dataset_engine import datasets_freshness
    return datasets_freshness()

@tool(description='Run the existing read-only SQL rerun operation.')
async def product_rerun(sql: str) -> dict:
    from shared.tools.league import rerun_sql
    return await rerun_sql(sql)

@tool(description='Resolve NBA entities using the existing resolver.')
def product_resolve(query: str) -> dict:
    from shared.tools import resolve_entity
    return resolve_entity.invoke({'query': query})

@tool(description='Check a trade using the existing Python domain implementation.')
def product_trade(team_a: str, players_a: str, team_b: str, players_b: str, season: str = '2025-26') -> dict:
    from shared.tools import get_trade_check
    try:
        return get_trade_check.invoke(dict(team_a=team_a,players_a=players_a,team_b=team_b,players_b=players_b,season=season))
    except ValueError as error:
        return {'ok': False, 'error': str(error)}

@tool(description='Find salary-matching packages for a player via the existing domain implementation.')
def product_trade_partners(player: str, season: str = '2026-27', teams: str = '', max_packages: int = 3) -> dict:
    from shared.tools import get_trade_partners
    try:
        return get_trade_partners.invoke(dict(player=player, season=season, teams=teams, max_packages=max_packages))
    except ValueError as error:
        return {'ok': False, 'error': str(error)}

@tool(description='List one team\'s trade assets: roster salaries and owned draft picks.')
def product_trade_assets(team: str, season: str = '2026-27') -> dict:
    from shared import store
    from shared.contracts import salary_records
    abbr = str(team or '').strip().upper()
    if not abbr:
        return {'ok': False, 'error': 'team needed'}
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {'ok': False, 'error': 'warehouse unreachable'}
    try:
        records = [r for r in salary_records(con, salary_season=season, include_fallback=True)
                   if str(r.get('TEAM') or '').upper() == abbr and isinstance(r.get('salary'), (int, float))]
        records.sort(key=lambda r: -(r['salary'] or 0))
        players = [{'name': str(r.get('PLAYER_NAME') or ''), 'salary': round(float(r['salary']) / 1_000_000, 1)}
                   for r in records if r.get('PLAYER_NAME')]
        picks = []
        tables = {row[0] for row in con.execute('SHOW TABLES').fetchall()}
        if 'silver_future_picks' in tables:
            rows = con.execute(
                "SELECT DRAFT_YEAR, ROUND, ORIG_TEAM, PROTECTION, CONDITIONAL, SUMMARY "
                "FROM silver_future_picks WHERE ? IN (SELECT UNNEST(string_split(HELD_BY, ';')))",
                [abbr]).fetchall()
            picks = [{'year': int(r[0]), 'round': int(r[1]), 'orig': str(r[2] or ''),
                      'protection': r[3], 'conditional': bool(r[4]), 'summary': str(r[5] or '')}
                     for r in rows]
        source = 'salary_records' + (' + silver_future_picks' if 'silver_future_picks' in tables else '')
        return {'ok': True, 'team': abbr, 'season': season, 'players': players, 'picks': picks,
                'meta': {'source': source, 'season': season}}
    except Exception as error:
        return {'ok': False, 'error': str(error)}
    finally:
        con.close()

_ESPN_ABBR = {'GSW': 'GS', 'SAS': 'SA', 'NOP': 'NO', 'NYK': 'NY', 'UTA': 'UTAH', 'WAS': 'WSH'}
_ESPN_ABBR_INV = {v: k for k, v in _ESPN_ABBR.items()}

def _team_full_name(abbr: str) -> str:
    try:
        from nba_api.stats.static import teams as _teams
        item = next(t for t in _teams.get_teams() if t['abbreviation'] == abbr)
        return str(item.get('full_name') or '')
    except Exception:
        return ''

def _standings_row(con, abbr: str) -> dict | None:
    full = _team_full_name(abbr)
    if not full:
        return None
    row = con.execute(
        "SELECT TeamCity, TeamName, WINS, LOSSES, WinPCT, PlayoffRank, L10, Conference, _fetched_at "
        "FROM silver_standings WHERE (TeamCity || ' ' || TeamName) = ? LIMIT 1", [full]).fetchone()
    if not row:
        return None
    return {'team': full, 'wins': row[2], 'losses': row[3], 'win_pct': row[4],
            'playoff_rank': row[5], 'l10': row[6], 'conference': row[7], 'as_of': str(row[8])}

@tool(description='Aggregate one team\'s morning page: last result, next game, opponent form, injuries, news, standings vs projection and cap status.')
def product_morning(team: str, season: str = '') -> dict:
    from shared import store
    abbr = str(team or '').strip().upper()
    if not abbr:
        return {'ok': False, 'error': 'team needed'}
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {'ok': False, 'error': 'warehouse unreachable'}
    blocks: dict = {}
    try:
        tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
        if not season:
            season = '2025-26'
            if 'silver_scoreboard' in tables:
                latest = con.execute("SELECT MAX(_season) FROM silver_scoreboard").fetchone()
                if latest and latest[0]:
                    season = str(latest[0])
        last = None
        last_as_of = None
        if 'silver_scoreboard' in tables:
            row = con.execute(
                "SELECT GAME_DATE_EST, HOME_TEAM_ABBREVIATION, VISITOR_TEAM_ABBREVIATION, "
                "HOME_TEAM_PTS, VISITOR_TEAM_PTS, GAME_STATUS_TEXT, _fetched_at FROM silver_scoreboard "
                "WHERE _season = ? AND (HOME_TEAM_ABBREVIATION = ? OR VISITOR_TEAM_ABBREVIATION = ?) "
                "AND GAME_STATUS_TEXT = 'Final' ORDER BY GAME_DATE_EST DESC LIMIT 1",
                [season, abbr, abbr]).fetchone()
            if row:
                won = (row[1] == abbr and (row[3] or 0) > (row[4] or 0)) or (row[2] == abbr and (row[4] or 0) > (row[3] or 0))
                last = {'date': str(row[0])[:10], 'home': row[1], 'away': row[2],
                        'home_pts': row[3], 'away_pts': row[4], 'result': 'W' if won else 'L',
                        'opponent': row[2] if row[1] == abbr else row[1]}
                last_as_of = str(row[6])
        blocks['last_result'] = {'ok': 'silver_scoreboard' in tables, 'game': last,
                                 'provenance': {'table': 'silver_scoreboard', 'as_of': last_as_of}}
        if 'silver_scoreboard' not in tables:
            blocks['last_result']['error'] = 'silver_scoreboard not in warehouse'
        sched_abbr = _ESPN_ABBR.get(abbr, abbr)
        next_game = None
        next_as_of = None
        next_opp_full = ''
        if 'silver_schedule' in tables:
            cutoff = last['date'] if last else '1900-01-01'
            row = con.execute(
                "SELECT date, name, short_name, season_type_name, _fetched_at FROM silver_schedule "
                "WHERE _entity = ? AND date > ? ORDER BY date LIMIT 1",
                [f'team:{sched_abbr}', cutoff]).fetchone()
            if row:
                next_as_of = str(row[4])
                name = str(row[1] or '')
                sides = str(row[2] or '').split(' @ ')
                opp = ''
                if len(sides) == 2:
                    ours = sides.index(sched_abbr) if sched_abbr in sides else 1
                    opp = _ESPN_ABBR_INV.get(sides[1 - ours], sides[1 - ours])
                if ' at ' in name:
                    parts = name.split(' at ')
                    home_full, away_full = parts[1], parts[0]
                    next_opp_full = away_full if abbr == (sides[1] if len(sides) == 2 else '') else home_full
                next_game = {'date': str(row[0]), 'name': name, 'short_name': str(row[2] or ''),
                             'season_type': str(row[3] or ''), 'opponent': opp}
        blocks['next_game'] = {'ok': 'silver_schedule' in tables, 'game': next_game,
                               'provenance': {'table': 'silver_schedule', 'as_of': next_as_of}}
        if 'silver_schedule' not in tables:
            blocks['next_game']['error'] = 'silver_schedule not in warehouse'
        opp_abbr = next_game['opponent'] if next_game else ''
        opponent = None
        if opp_abbr and 'silver_standings' in tables:
            opponent = _standings_row(con, opp_abbr)
            if opponent:
                opponent['abbr'] = opp_abbr
        blocks['opponent'] = {'ok': bool(opponent), 'row': opponent, 'name': next_opp_full,
                              'provenance': {'table': 'silver_standings', 'as_of': opponent and opponent.get('as_of')}}
        if opp_abbr and not opponent:
            blocks['opponent']['error'] = 'silver_standings not in warehouse' if 'silver_standings' not in tables else 'no standings row for opponent'
        standings = _standings_row(con, abbr) if 'silver_standings' in tables else None
        projection = None
        proj_as_of = None
        if 'silver_preseason_projections' in tables:
            prow = con.execute(
                "SELECT PROJECTED_WINS, PROJECTED_LOSSES, MAKE_PLAYOFFS_PCT, WIN_TITLE_PCT, _fetched_at "
                "FROM silver_preseason_projections WHERE TEAM = ? AND _season = ? LIMIT 1", [abbr, season]).fetchone()
            if prow:
                projection = {'projected_wins': prow[0], 'projected_losses': prow[1],
                              'make_playoffs_pct': prow[2], 'win_title_pct': prow[3]}
                proj_as_of = str(prow[4])
        pace = None
        if standings and projection and projection.get('projected_wins') is not None:
            played = (standings['wins'] or 0) + (standings['losses'] or 0)
            if played:
                pace = round(standings['wins'] / played * 82, 1)
        blocks['standings'] = {
            'ok': standings is not None, 'row': standings, 'projection': projection, 'pace_wins': pace,
            'provenance': {'table': 'silver_standings + silver_preseason_projections',
                           'as_of': (standings or {}).get('as_of') or proj_as_of}}
        if not standings:
            blocks['standings']['error'] = 'silver_standings not in warehouse' if 'silver_standings' not in tables else 'no standings row'
        injuries = []
        injuries_as_of = None
        if 'silver_injuries' in tables:
            try:
                from shared.tools import get_injuries
                res = get_injuries.invoke({'team': abbr, 'season': season})
                if isinstance(res, dict) and res.get('ok'):
                    injuries = res.get('rows') or []
                    injuries_as_of = (res.get('meta') or {}).get('as_of') or (res.get('meta') or {}).get('last_fetch')
            except Exception as error:
                blocks['injuries'] = {'ok': False, 'rows': [], 'error': str(error)[:160],
                                      'provenance': {'table': 'silver_injuries', 'as_of': None}}
        if 'injuries' not in blocks:
            blocks['injuries'] = {'ok': 'silver_injuries' in tables, 'rows': injuries,
                                  'provenance': {'table': 'silver_injuries', 'as_of': injuries_as_of}}
            if 'silver_injuries' not in tables:
                blocks['injuries']['error'] = 'silver_injuries not in warehouse'
        news = []
        news_as_of = None
        if 'silver_news' in tables:
            try:
                from shared.tools import get_news_feed
                res = get_news_feed.invoke({'team': abbr, 'limit': 5})
                if isinstance(res, dict) and res.get('ok'):
                    news = res.get('rows') or []
                    news_as_of = (res.get('meta') or {}).get('as_of') or (res.get('meta') or {}).get('last_fetch')
            except Exception as error:
                blocks['news'] = {'ok': False, 'rows': [], 'error': str(error)[:160],
                                  'provenance': {'table': 'silver_news', 'as_of': None}}
        if 'news' not in blocks:
            blocks['news'] = {'ok': 'silver_news' in tables, 'rows': news,
                              'provenance': {'table': 'silver_news', 'as_of': news_as_of}}
            if 'silver_news' not in tables:
                blocks['news']['error'] = 'silver_news not in warehouse'
        try:
            from shared.tools import get_cap_ledger
            cap = get_cap_ledger.invoke({'team': abbr})
            if isinstance(cap, dict) and cap.get('ok'):
                meta = cap.get('meta') or {}
                blocks['cap'] = {'ok': True, 'row': cap.get('rows'),
                                 'provenance': {'table': meta.get('source') or 'salary_records',
                                                'as_of': meta.get('salary_date')},
                                 'meta': meta}
            else:
                blocks['cap'] = {'ok': False, 'error': (cap or {}).get('error') or 'cap ledger failed',
                                 'provenance': {'table': 'salary_records', 'as_of': None}}
        except Exception as error:
            blocks['cap'] = {'ok': False, 'error': str(error)[:160],
                             'provenance': {'table': 'salary_records', 'as_of': None}}
        return {'ok': True, 'team': abbr, 'season': season, 'blocks': blocks}
    except Exception as error:
        return {'ok': False, 'error': str(error)[:200]}
    finally:
        con.close()

@tool(description='Build the current debate card with the domain season clamp.')
def product_debate(a: str, b: str, season: str = '2025-26') -> dict:
    from shared.tools import get_debate_card
    from shared.tools._core import InvalidSeasonError, clamp_season
    try:
        season = clamp_season(season)
    except InvalidSeasonError as error:
        return {"ok": False, "error": str(error)}
    try:
        result = get_debate_card.invoke(dict(a=a,b=b,season=season))
    except Exception:
        return {"ok": False, "error": "debate card failed"}
    return {"result": result, "season": season}

def _decoded(result):
    return json.loads(result) if isinstance(result, str) else result

@tool(description='Read the current today data.')
def product_today(season: str = '2025-26') -> dict:
    from shared.tools.today import get_today
    return _decoded(get_today.invoke({'season':season}))

@tool(description='Read the current watchlist data.')
def product_watchlist(season: str = '2025-26') -> dict:
    from shared.tools.watchlist import get_watchlist
    return _decoded(get_watchlist.invoke({'season':season}))

@tool(description='Apply the current direct product watchlist addition.')
def product_watchlist_add(entity_type: str, entity_id: str, season: str = '2025-26') -> dict:
    from shared.tools.watchlist import add_watchlist_item
    return _decoded(add_watchlist_item.invoke(dict(entity_type=entity_type,entity_id=entity_id,season=season)))

@tool(description='Apply the current direct product watchlist removal.')
def product_watchlist_remove(entity_type: str, entity_id: str) -> dict:
    from shared.tools.watchlist import remove_watchlist_item
    return _decoded(remove_watchlist_item.invoke(dict(entity_type=entity_type,entity_id=entity_id)))

@tool(description='Read and normalize current leaderboard deltas.')
def product_movers(season: str = '2025-26', days: int = 7) -> dict:
    from shared.tools.league import get_leaderboard_deltas
    from shared.tools.today import normalize_movers
    return normalize_movers(_decoded(get_leaderboard_deltas.invoke(dict(season=season,days=days))), season)

@tool(description='Read the existing morning briefing.')
def product_briefing(season: str = '2025-26') -> dict:
    from shared.tools.today import get_morning_briefing
    return _decoded(get_morning_briefing.invoke({'season':season}))

def internal_catalogue():
    operations = (product_board_metrics, product_board_fill, product_board_seed, product_save_chat, product_save_run, product_threads, product_runs,
        product_warehouse_identity, product_warehouse_health, product_dataset, product_freshness, product_table_detail, product_home,
        product_rerun, product_resolve, product_trade, product_trade_partners, product_trade_assets, product_morning, product_debate, product_today,
        product_watchlist, product_watchlist_add, product_watchlist_remove, product_movers, product_briefing)
    result = {operation.name: operation for operation in operations}
    for operation in operations:
        operation.args_schema.__doc__ = operation.description
    from analyst.python_tools import apply_param_docs
    for name, operation in result.items():
        apply_param_docs(name, operation)
    return result
