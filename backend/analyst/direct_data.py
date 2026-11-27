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

@tool(description='Career arc for one player across all warehouse seasons.')
def product_history_career(player: str) -> dict:
    from shared.tools import get_career_arc
    if not player:
        return {'ok': False, 'error': 'pass a player name'}
    try:
        return get_career_arc.invoke({'player': player})
    except ValueError as error:
        return {'ok': False, 'error': str(error)}

@tool(description='Era-relative statistical neighbors for one player-season.')
def product_history_era_comps(player_id: int, season: str, k: int = 8, start_season: str = '', end_season: str = '', player: str = '') -> dict:
    from shared.tools.player.comps import get_era_comps
    if not player_id and player:
        try:
            from shared import store
            con = store.connect(read_only=True)
            hit = con.execute(
                'SELECT DISTINCT player_id FROM silver_hist_player_seasons WHERE lower(player_name) = lower(?) LIMIT 1',
                [player]).fetchone()
            if not hit:
                hit = con.execute(
                    'SELECT DISTINCT player_id FROM silver_hist_player_seasons WHERE lower(player_name) LIKE lower(?) LIMIT 1',
                    [f'%{player}%']).fetchone()
            if hit:
                player_id = int(hit[0])
        except Exception:
            pass
    try:
        return get_era_comps.invoke({'player_id': player_id, 'season': season, 'k': k,
                                     'start_season': start_season or None, 'end_season': end_season or None})
    except ValueError as error:
        return {'ok': False, 'error': str(error)}

@tool(description='Era-adjusted leaderboard for one season: within-season z-scores over the qualified pool.')
def product_history_leaders(season: str, category: str = 'pts') -> dict:
    if not season:
        return {'ok': False, 'error': 'pass a season'}
    allowed = {'pts', 'reb', 'ast', 'stl', 'blk', 'min', 'ts_pct', 'fg3_pct'}
    if category not in allowed:
        return {'ok': False, 'error': f'category must be one of {sorted(allowed)}'}
    try:
        from shared import store
        con = store.connect(read_only=True)
        table = 'silver_hist_player_seasons'
        cols = {row[1].lower(): row[1] for row in con.execute(f'PRAGMA table_info({table})').fetchall()}
        cat_col = cols.get(category)
        if not cat_col:
            return {'ok': False, 'error': f'no column for {category}'}
        name_col = cols.get('player_name') or cols.get('player')
        pid_col = cols.get('player_id')
        season_col = cols.get('_season') or cols.get('season')
        query = f'SELECT "{pid_col}" AS player_id, "{name_col}" AS player, "{cat_col}" AS value FROM {table} WHERE "{season_col}" = ? AND "{cat_col}" IS NOT NULL'
        rows = con.execute(query, [season]).fetchall()
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200]}
    if not rows:
        return {'ok': False, 'error': f'no rows for {season}', 'season': season, 'rows': []}
    import statistics
    values = [float(r[2]) for r in rows]
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) or 1.0
    ranked = sorted(rows, key=lambda r: float(r[2]), reverse=True)[:15]
    board = [{'rank': i + 1, 'player_id': r[0], 'player': r[1], 'value': round(float(r[2]), 2),
              'z': round((float(r[2]) - mean) / stdev, 2)} for i, r in enumerate(ranked)]
    return {'ok': True, 'season': season, 'category': category, 'rows': board,
            'meta': {'source': 'silver_hist_player_seasons', 'pool': len(values),
                     'normalization': 'z = (value - pool mean) / pool stdev within the season'}}

@tool(description='Evaluate a multi-team trade construction through the CBA legality engine.')
def product_trade_legs(legs: str, season: str = '2026-27') -> dict:
    import json as _json
    from shared.tools import get_trade_legality
    if not legs:
        return {'ok': False, 'error': 'pass a legs JSON array'}
    try:
        parsed = _json.loads(legs) if isinstance(legs, str) else legs
    except Exception:
        return {'ok': False, 'error': 'legs must be valid JSON'}
    if not isinstance(parsed, list) or not parsed:
        return {'ok': False, 'error': 'legs must be a non-empty array'}
    for leg in parsed:
        if not isinstance(leg, dict) or not leg.get('from') or not leg.get('to'):
            return {'ok': False, 'error': 'each leg needs from/to teams'}
    try:
        return get_trade_legality.invoke({'legs': _json.dumps(parsed), 'season': season})
    except ValueError as error:
        return {'ok': False, 'error': str(error)}

@tool(description='Find salary-matching packages for a player via the existing domain implementation.')
def product_trade_partners(player: str, season: str = '2026-27', teams: str = '', max_packages: int = 3) -> dict:
    from shared.tools import get_trade_partners
    try:
        return get_trade_partners.invoke(dict(player=player, season=season, teams=teams, max_packages=max_packages))
    except ValueError as error:
        return {'ok': False, 'error': str(error)}

@tool(description='Read one team multi-year cap sheet: per-player contract matrix, per-season totals, apron state.')
def product_cap_sheet(team: str, season: str = '2026-27') -> dict:
    from shared import store
    from shared.contracts import canonical_team_abbr
    abbr = canonical_team_abbr(team)
    if not abbr:
        return {'ok': False, 'error': 'team needed'}
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {'ok': False, 'error': 'warehouse unreachable'}
    try:
        from shared.tools.league.cap_sheet import cap_sheet_rows
        out = cap_sheet_rows(con, abbr, str(season or '2026-27'))
        return out
    except Exception as error:
        return {'ok': False, 'error': str(error)[:200]}
    finally:
        con.close()

@tool(description='Evaluate a typed cap scenario (signings, trades, waives, option decisions) for one team and season.')
def product_cap_scenario_eval(payload: dict) -> dict:
    from shared import store
    from shared.contracts import canonical_team_abbr
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'payload must be an object'}
    abbr = canonical_team_abbr(str(payload.get('team') or ''))
    if not abbr:
        return {'ok': False, 'error': 'team needed'}
    payload = {**payload, 'team': abbr}
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {'ok': False, 'error': 'warehouse unreachable'}
    try:
        from shared.tools.league.cap_sheet import evaluate_cap_scenario
        return evaluate_cap_scenario(con, payload)
    except Exception as error:
        return {'ok': False, 'error': str(error)[:200]}
    finally:
        con.close()

@tool(description='List one team\'s trade assets: roster salaries and owned draft picks.')
def product_trade_assets(team: str, season: str = '2026-27') -> dict:
    from shared import store
    from shared.contracts import canonical_team_abbr, salary_records
    abbr = canonical_team_abbr(team)
    if not abbr:
        return {'ok': False, 'error': 'team needed'}
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {'ok': False, 'error': 'warehouse unreachable'}
    try:
        records = [r for r in salary_records(con, salary_season=season, include_fallback=True)
                   if canonical_team_abbr(r.get('TEAM')) == abbr
                   and isinstance(r.get('salary'), (int, float))]
        records.sort(key=lambda r: -(r['salary'] or 0))
        players = [{'name': str(r.get('PLAYER_NAME') or ''), 'salary': round(float(r['salary']) / 1_000_000, 1)}
                   for r in records if r.get('PLAYER_NAME')]
        picks = []
        tables = {row[0] for row in con.execute('SHOW TABLES').fetchall()}
        if 'silver_future_picks' in tables:
            rows = con.execute(
                "SELECT DRAFT_YEAR, ROUND, ORIG_TEAM, PROTECTION, CONDITIONAL, SUMMARY, HELD_BY "
                "FROM silver_future_picks").fetchall()
            owned_rows = [r for r in rows
                          if abbr in {canonical_team_abbr(holder)
                                      for holder in str(r[6] or '').split(';')}]
            picks = [{'year': int(r[0]), 'round': int(r[1]), 'orig': str(r[2] or ''),
                      'protection': r[3], 'conditional': bool(r[4]), 'summary': str(r[5] or '')}
                     for r in owned_rows]
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

@tool(description='Read the live matchups slate: next game-date games with team ratings, form, and injuries.')
def product_matchups(season: str = '') -> dict:
    import ast
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from shared import store

    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
        if 'silver_schedule' not in tables or 'silver_team_ratings' not in tables:
            return {'ok': False, 'error': 'required warehouse tables missing', 'games': []}
        if 'silver_scoreboard' not in tables:
            return {'ok': False, 'error': 'required warehouse tables missing', 'games': []}
        day = 'try_cast(GAME_DATE_EST AS DATE)'
        slate = con.execute(f'SELECT max({day}) FROM silver_scoreboard').fetchone()[0]
        if slate is None:
            return {'ok': True, 'date': '', 'games': [], 'note': 'no games found'}
        rows = con.execute(
            f'SELECT GAME_ID, GAME_STATUS_TEXT, HOME_TEAM_ABBREVIATION, VISITOR_TEAM_ABBREVIATION, NATL_TV_BROADCASTER_ABBREVIATION, HOME_TV_BROADCASTER_ABBREVIATION, AWAY_TV_BROADCASTER_ABBREVIATION FROM silver_scoreboard WHERE {day} = cast(? AS DATE)',
            [slate.isoformat()],
        ).fetchall()
        games_by_id = {}
        for gid, status, home_abbr, away_abbr, natl, home_tv, away_tv in rows:
            games_by_id.setdefault(str(gid), {
                'id': str(gid), 'status': str(status or ''), 'home_abbr': str(home_abbr or ''),
                'away_abbr': str(away_abbr or ''), 'network': str(natl or home_tv or away_tv or ''),
            })
        ratings_season = con.execute('SELECT max(_season) FROM silver_team_ratings').fetchone()[0]
        ratings = {}
        for team_id, team_name, w, l, offr, defr, netr, pace, ts in con.execute(
            'SELECT TEAM_ID, TEAM_NAME, W, L, OFF_RATING, DEF_RATING, NET_RATING, PACE, TS_PCT FROM silver_team_ratings WHERE _season = ?',
            [ratings_season],
        ).fetchall():
            ratings[int(team_id)] = {'team_id': int(team_id), 'team_name': team_name, 'w': w, 'l': l,
                                     'off_rating': offr, 'def_rating': defr, 'net_rating': netr, 'pace': pace, 'ts_pct': ts}
        abbr_of = {}
        if 'silver_team_games' in tables:
            tg_season = con.execute('SELECT max(_season) FROM silver_team_games').fetchone()[0]
            for team_id, matchup in con.execute('SELECT DISTINCT "Team_ID", MATCHUP FROM silver_team_games WHERE _season = ?', [tg_season]).fetchall():
                abbr = str(matchup).split(' ')[0] if matchup else None
                if abbr:
                    abbr_of[abbr] = int(team_id)
        form = {}
        threes = {}
        if 'silver_team_games' in tables:
            tg_season = con.execute('SELECT max(_season) FROM silver_team_games').fetchone()[0]
            for team_id in ratings:
                games_rows = con.execute(
                    'SELECT "WL" FROM silver_team_games WHERE "Team_ID" = ? AND _season = ? ORDER BY "GAME_DATE" DESC LIMIT 10',
                    [team_id, tg_season],
                ).fetchall()
                form[team_id] = [r[0] for r in games_rows if r[0] in ('W', 'L')]
                agg = con.execute(
                    'SELECT sum(FG3M), sum(FG3A) FROM silver_team_games WHERE "Team_ID" = ? AND _season = ?',
                    [team_id, tg_season],
                ).fetchone()
                if agg and agg[1]:
                    threes[team_id] = round(100.0 * agg[0] / agg[1], 1)
        injuries_by_team = {}
        if 'silver_injuries' in tables:
            inj_season = con.execute('SELECT max(_season) FROM silver_injuries').fetchone()[0]
            for display, blob in con.execute('SELECT display_name, injuries FROM silver_injuries WHERE _season = ?', [inj_season]).fetchall():
                entries = []
                parsed = None
                if isinstance(blob, str):
                    try:
                        parsed = json.loads(blob)
                    except Exception:
                        try:
                            parsed = ast.literal_eval(blob)
                        except Exception:
                            parsed = None
                elif isinstance(blob, list):
                    parsed = blob
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get('status', '').lower() in ('out', 'doubtful'):
                            short = str(item.get('shortComment') or '')[:110]
                            if short:
                                entries.append(short)
                injuries_by_team[str(display)] = entries[:3]

        def team_payload(abbr):
            team_id = abbr_of.get(abbr)
            base = ratings.get(team_id, {}) if team_id else {}
            return {
                'abbr': abbr,
                'name': base.get('team_name', abbr),
                'record': f"{base.get('w', '?')}-{base.get('l', '?')}" if base else '',
                'net_rating': base.get('net_rating'),
                'off_rating': base.get('off_rating'),
                'def_rating': base.get('def_rating'),
                'pace': base.get('pace'),
                'ts_pct': (round(base['ts_pct'] * 100, 1) if base.get('ts_pct') is not None else None),
                'fg3_pct': threes.get(team_id) if team_id else None,
                'form': form.get(team_id, []) if team_id else [],
                'injuries': injuries_by_team.get(base.get('team_name', ''), []) if base else [],
            }

        games = []
        for game in sorted(games_by_id.values(), key=lambda g: g['status']):
            if not game['away_abbr'] or not game['home_abbr']:
                continue
            games.append({
                'id': game['id'],
                'away': team_payload(game['away_abbr']),
                'home': team_payload(game['home_abbr']),
                'time': game['status'],
                'network': game['network'],
                'date': slate.isoformat(),
            })
        return {'ok': True, 'date': slate.isoformat(), 'season': ratings_season, 'games': games}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200], 'games': []}
    finally:
        con.close()

@tool(description='Read the warehouse-backed award race projections across all tracked awards.')
def product_awards(season: str = '') -> dict:
    from shared.tools.awards import PROJECTION_SPECS, get_award_race
    awards = []
    for key in sorted(PROJECTION_SPECS):
        try:
            result = get_award_race.invoke({'award': key, 'season': season or None})
        except Exception as exc:
            awards.append({'award': key, 'ok': False, 'error': str(exc)[:200], 'candidates': []})
            continue
        result = _decoded(result)
        rows = result.get('rows') or {}
        candidates = rows.get('candidates') if isinstance(rows, dict) else None
        awards.append({
            'award': key,
            'ok': bool(result.get('ok')) and candidates is not None,
            'error': result.get('error'),
            'season': (result.get('meta') or {}).get('season'),
            'caveat': PROJECTION_SPECS[key].get('proxy_caveat'),
            'candidates': (candidates or [])[:10],
        })
    seasons = [a['season'] for a in awards if a.get('season')]
    return {'ok': True, 'season': seasons[0] if seasons else season, 'awards': awards}
@tool(description='Assemble the opponent-scout dossier: form, four factors, shot profile, lineups, rotation, injuries, head-to-head.')
def product_scout_dossier(team: str, opponent: str, season: str = '') -> dict:
    import asyncio
    from shared.tools.team.scouting import get_opponent_scout, get_scout_pack
    from shared.tools.team.lineups_rotations import get_rotation_check

    if not team or not opponent:
        return {'ok': False, 'error': 'pass both team and opponent', 'sections': {}}

    def gather():
        async def run():
            scout = get_opponent_scout.invoke({'team': team, 'opponent': opponent, 'season': season or None})
            pack = await get_scout_pack.ainvoke({'team': team, 'opponent': opponent, 'season': season or None})
            rotation = await get_rotation_check.ainvoke({'team': opponent, 'season': season or None})
            return scout, pack, rotation
        return asyncio.run(run())

    try:
        scout, pack, rotation = gather()
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200], 'sections': {}}
    scout = _decoded(scout)
    pack = _decoded(pack)
    rotation = _decoded(rotation)
    if not scout.get('ok'):
        return {'ok': False, 'error': scout.get('error') or 'opponent scout failed', 'sections': {}}
    rows = scout.get('rows') or {}
    sections = {}
    for key in ('recent_form', 'four_factors', 'shot_profile', 'top_lineups', 'injuries', 'head_to_head'):
        section = rows.get(key)
        if isinstance(section, dict):
            sections[key] = section
    rot_rows = rotation.get('rows')
    sections['rotation'] = {
        'source': 'rotation_check',
        'ok': bool(rotation.get('ok')),
        'error': rotation.get('error'),
        'rows': rot_rows,
    }
    pack_rows = pack.get('rows') or {}
    return {
        'ok': True,
        'season': (scout.get('meta') or {}).get('season') or season,
        'team': {'abbrev': (scout.get('meta') or {}).get('team', team)},
        'opponent': rows.get('opponent') or {'abbrev': opponent},
        'edge': pack_rows.get('edge') if isinstance(pack_rows, dict) else None,
        'pack': pack_rows if isinstance(pack_rows, dict) else {},
        'sections': sections,
    }

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

def _compare_tables(con) -> set:
    return {row[0] for row in con.execute("SHOW TABLES").fetchall()}

def _compare_as_of(con, table: str):
    try:
        value = con.execute(f"SELECT MAX(_fetched_at) FROM {table}").fetchone()[0]
        return str(value) if value is not None else None
    except Exception:
        return None

def _compare_name(con, pid: int) -> str:
    try:
        row = con.execute("SELECT player_name FROM silver_hist_player_seasons WHERE player_id = ? ORDER BY season DESC LIMIT 1", [pid]).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    try:
        row = con.execute("SELECT PLAYER FROM silver_player_season WHERE PLAYER_ID = ? LIMIT 1", [pid]).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    try:
        from nba_api.stats.static import players as _sp
        info = _sp.find_player_by_id(pid)
        if info and info.get("full_name"):
            return str(info["full_name"])
    except Exception:
        pass
    return str(pid)

def _hist_year(season: str) -> int:
    try:
        return int(str(season).split("-")[0])
    except Exception:
        return 0

def _compare_season_line(con, pid: int, season: str) -> dict:
    if "silver_hist_player_seasons" not in _compare_tables(con):
        return {"ok": False, "error": "silver_hist_player_seasons not in warehouse"}
    year = _hist_year(season)
    row = con.execute(
        """SELECT season, age, team_abbreviation, gp, min, pts, reb, ast, stl, blk,
                  fg_pct, fg3_pct, ft_pct, ts_pct, efg_pct, usg_pct, off_rating, def_rating, net_rating
           FROM silver_hist_player_seasons WHERE player_id = ? AND season = ? LIMIT 1""",
        [pid, year]).fetchone()
    if not row:
        return {"ok": False, "error": f"no season line for {season}", "provenance": {"table": "silver_hist_player_seasons", "as_of": _compare_as_of(con, "silver_hist_player_seasons")}}
    keys = ["season", "age", "team", "gp", "mpg", "ppg", "rpg", "apg", "spg", "bpg", "fg_pct", "fg3_pct", "ft_pct", "ts_pct", "efg_pct", "usg_pct", "off_rating", "def_rating", "net_rating"]
    return {"ok": True, "row": dict(zip(keys, row)), "provenance": {"table": "silver_hist_player_seasons", "as_of": _compare_as_of(con, "silver_hist_player_seasons")}}

def _compare_impact(con, pid: int, season: str) -> dict:
    if "silver_raptor_player" not in _compare_tables(con):
        return {"ok": False, "error": "silver_raptor_player not in warehouse"}
    cite = {"table": "silver_raptor_player", "as_of": _compare_as_of(con, "silver_raptor_player")}
    row = con.execute(
        "SELECT RAPTOR_TOTAL, WAR_TOTAL, MP FROM silver_raptor_player WHERE PLAYER_ID = ? AND _season = ? LIMIT 1",
        [pid, season]).fetchone()
    if not row:
        return {"ok": False, "error": f"no impact row for {season}", "provenance": cite}
    total = float(row[0])
    rank = con.execute(
        "SELECT COUNT(*) + 1 FROM silver_raptor_player WHERE _season = ? AND RAPTOR_TOTAL > ?",
        [season, row[0]]).fetchone()[0]
    of = con.execute("SELECT COUNT(*) FROM silver_raptor_player WHERE _season = ?", [season]).fetchone()[0]
    return {"ok": True, "raptor_total": total, "war_total": float(row[1]), "mp": float(row[2]), "rank": int(rank), "of": int(of), "provenance": cite}

def _compare_zones(con, pid: int, season: str) -> dict:
    if "silver_shots" not in _compare_tables(con):
        return {"ok": False, "error": "silver_shots not in warehouse"}
    cite = {"table": "silver_shots", "as_of": _compare_as_of(con, "silver_shots")}
    rows = con.execute(
        """SELECT SHOT_ZONE_BASIC AS zone, AVG(LOC_X) / 10.0 AS x, AVG(LOC_Y) / 10.0 AS y,
                  COUNT(*) AS att, SUM(CASE WHEN SHOT_MADE_FLAG = '1' THEN 1 ELSE 0 END) AS makes
           FROM silver_shots WHERE PLAYER_ID = ? AND _season = ? AND SHOT_ZONE_BASIC IS NOT NULL
           GROUP BY 1""", [pid, season]).fetchall()
    if not rows:
        return {"ok": False, "error": f"no shots for {season}", "provenance": cite}
    league = {r[0]: (r[1], r[2]) for r in con.execute(
        """SELECT SHOT_ZONE_BASIC, COUNT(*), SUM(CASE WHEN SHOT_MADE_FLAG = '1' THEN 1 ELSE 0 END)
           FROM silver_shots WHERE _season = ? AND SHOT_ZONE_BASIC IS NOT NULL GROUP BY 1""",
        [season]).fetchall()}
    zones = []
    for zone, x, y, att, makes in rows:
        att = int(att); makes = int(makes or 0)
        pct = round(100.0 * makes / att, 1)
        lg_att, lg_makes = league.get(str(zone), (0, 0))
        league_pct = round(100.0 * int(lg_makes) / int(lg_att), 1) if int(lg_att) else None
        zones.append({"zone": str(zone), "x": round(float(x or 0), 1), "y": round(float(y or 0), 1),
                      "att": att, "makes": makes, "pct": pct, "league_pct": league_pct,
                      "delta_pp": round(pct - league_pct, 1) if league_pct is not None else None})
    return {"ok": True, "zones": zones, "provenance": cite}

def _compare_contract(con, pid: int, name: str) -> dict:
    if "silver_cap_players" not in _compare_tables(con):
        return {"ok": False, "error": "silver_cap_players not in warehouse"}
    cite = {"table": "silver_cap_players", "as_of": _compare_as_of(con, "silver_cap_players")}
    row = con.execute(
        """SELECT team, salary, contract_type, guaranteed, player_option, team_option
           FROM silver_cap_players WHERE lower(player) = lower(?) ORDER BY _season DESC LIMIT 1""",
        [name]).fetchone()
    if not row:
        return {"ok": False, "error": "no cap row for player", "provenance": cite}
    return {"ok": True, "row": {"team": row[0], "salary": row[1], "contract_type": row[2], "guaranteed": row[3],
                                "player_option": row[4], "team_option": row[5]},
            "season": con.execute("SELECT MAX(_season) FROM silver_cap_players").fetchone()[0],
            "provenance": cite}

def _compare_arc(con, pid: int) -> dict:
    if "silver_hist_player_seasons" not in _compare_tables(con):
        return {"ok": False, "error": "silver_hist_player_seasons not in warehouse"}
    rows = con.execute(
        """SELECT season, age, gp, pts, ts_pct, usg_pct FROM silver_hist_player_seasons
           WHERE player_id = ? ORDER BY season""", [pid]).fetchall()
    if not rows:
        return {"ok": False, "error": "no career rows", "provenance": {"table": "silver_hist_player_seasons", "as_of": _compare_as_of(con, "silver_hist_player_seasons")}}
    return {"ok": True,
            "rows": [{"season": int(r[0]), "age": float(r[1]) if r[1] is not None else None, "gp": int(r[2]),
                      "pts": float(r[3]), "ts_pct": float(r[4]), "usg_pct": float(r[5])} for r in rows],
            "provenance": {"table": "silver_hist_player_seasons", "as_of": _compare_as_of(con, "silver_hist_player_seasons")}}

@tool(description='Compare 2-4 players across season line, impact, shot zones, contract and age curve.')
def product_compare(players: str = '', season: str = '2025-26') -> dict:
    from shared import store
    specs = [part.strip() for part in (players or '').split(',') if part.strip()]
    if not 2 <= len(specs) <= 4:
        return {"ok": False, "error": "compare needs 2-4 players"}
    parsed = []
    for spec in specs:
        pid_text, _, own = spec.partition(":")
        if not pid_text.isdigit():
            return {"ok": False, "error": f"unrecognized player spec {spec!r}"}
        parsed.append((int(pid_text), own.strip() or season))
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {"ok": False, "error": "warehouse_unreachable"}
    try:
        out = []
        for pid, useason in parsed:
            name = _compare_name(con, pid)
            out.append({
                "player_id": pid, "name": name, "season": useason,
                "season_line": _compare_season_line(con, pid, useason),
                "impact": _compare_impact(con, pid, useason),
                "zones": _compare_zones(con, pid, useason),
                "contract": _compare_contract(con, pid, name),
                "arc": _compare_arc(con, pid),
            })
    finally:
        con.close()
    return {"ok": True, "season": season, "players": out}

def _draft_as_of(con, table: str) -> str | None:
    try:
        row = con.execute(f"SELECT MAX(_fetched_at) FROM {table}").fetchone()
        return str(row[0]) if row and row[0] else None
    except Exception:
        return None

def _draft_board(con, tables: set, season: str) -> dict:
    if "silver_draft_boards" not in tables:
        return {"ok": False, "error": "silver_draft_boards not in warehouse",
                "provenance": {"table": "silver_draft_boards", "as_of": None}}
    use = season
    if not use:
        latest = con.execute("SELECT MAX(_season) FROM silver_draft_boards").fetchone()
        use = str(latest[0]) if latest and latest[0] else ""
    cite = {"table": "silver_draft_boards" + (" + silver_prospect_stats" if "silver_prospect_stats" in tables else ""),
            "as_of": _draft_as_of(con, "silver_draft_boards")}
    if "silver_prospect_stats" in tables:
        rows = con.execute(
            'SELECT b."ORDER", b.PLAYER_NAME, b.POSITION, b.SCHOOL, s.GP, s.PTS, s.REB, s.AST, s.TS_PCT, s.USG '
            'FROM silver_draft_boards b '
            'LEFT JOIN silver_prospect_stats s ON lower(s.PLAYER_NAME) = lower(b.PLAYER_NAME) AND s._season = b._season '
            'WHERE b._season = ? ORDER BY b."ORDER" LIMIT 60', [use]).fetchall()
    else:
        rows = [r[:4] + (None,) * 6 for r in con.execute(
            'SELECT "ORDER", PLAYER_NAME, POSITION, SCHOOL FROM silver_draft_boards '
            'WHERE _season = ? ORDER BY "ORDER" LIMIT 60', [use]).fetchall()]
    board = [{"pick": int(r[0]), "name": str(r[1]), "position": r[2], "school": r[3],
              "gp": r[4], "pts": r[5], "reb": r[6], "ast": r[7], "ts_pct": r[8], "usg": r[9]}
             for r in rows]
    return {"ok": bool(board), "season": use, "rows": board, "provenance": cite,
            **({"error": "no board rows for season"} if not board else {})}

def _draft_free_agents(con, tables: set) -> dict:
    if "silver_free_agents" not in tables:
        return {"ok": False, "error": "silver_free_agents not in warehouse",
                "provenance": {"table": "silver_free_agents", "as_of": None}}
    rows = con.execute(
        "SELECT PLAYER_NAME, TEAM, FA_TYPE, PRIOR_SALARY, CAP_HOLD_EST FROM silver_free_agents "
        "ORDER BY PRIOR_SALARY DESC LIMIT 40").fetchall()
    agents = [{"name": str(r[0]), "team": r[1], "fa_type": r[2], "prior_salary": r[3], "cap_hold": r[4]}
              for r in rows]
    return {"ok": bool(agents), "rows": agents,
            "provenance": {"table": "silver_free_agents", "as_of": _draft_as_of(con, "silver_free_agents")},
            **({"error": "no free agent rows"} if not agents else {})}

def _draft_cap_room(con, tables: set) -> dict:
    if "silver_cap_room" not in tables:
        return {"ok": False, "error": "silver_cap_room not in warehouse",
                "provenance": {"table": "silver_cap_room", "as_of": None}}
    rows = con.execute(
        "SELECT TEAM, COMMITTED_SALARY, PENDING_OPTION_SALARY, FA_HOLDS_EST, "
        "INCOMPLETE_ROSTER_CHARGES, PROJECTED_ROOM FROM silver_cap_room ORDER BY PROJECTED_ROOM DESC").fetchall()
    room = [{"team": str(r[0]), "committed": r[1], "option_salary": r[2],
             "fa_holds": r[3], "roster_charges": r[4], "projected_room": r[5]}
            for r in rows]
    return {"ok": bool(room), "rows": room,
            "provenance": {"table": "silver_cap_room", "as_of": _draft_as_of(con, "silver_cap_room")},
            **({"error": "no cap room rows"} if not room else {})}

_DRAFT_GAP_FACTORS = [
    ("off_rating", "Offense", "OFF_RATING", True),
    ("def_rating", "Defense", "DEF_RATING", False),
    ("rebounding", "Rebounding", "REB_PCT", True),
    ("shooting", "Shooting", "EFG_PCT", True),
    ("ball_security", "Ball security", "TM_TOV_PCT", False),
]
_DRAFT_GAP_STAT = {
    "off_rating": "s.PPG", "def_rating": "(s.SPG + s.BPG)", "rebounding": "s.RPG",
    "shooting": "s.FG3_PCT", "ball_security": "s.APG",
}

def _draft_fit(con, tables: set, abbr: str) -> dict:
    errors = []
    gaps = []
    ratings_as_of = None
    if "silver_team_ratings" in tables:
        ratings_as_of = _draft_as_of(con, "silver_team_ratings")
        full = _team_full_name(abbr)
        row = con.execute(
            "SELECT TEAM_NAME, OFF_RATING, DEF_RATING, REB_PCT, EFG_PCT, TM_TOV_PCT "
            "FROM silver_team_ratings WHERE TEAM_NAME = ? LIMIT 1", [full]).fetchone() if full else None
        total = con.execute("SELECT COUNT(*) FROM silver_team_ratings").fetchone()[0]
        if row:
            for key, label, col, high_is_good in _DRAFT_GAP_FACTORS:
                value = float(row[{c: i + 1 for i, c in enumerate(
                    ["OFF_RATING", "DEF_RATING", "REB_PCT", "EFG_PCT", "TM_TOV_PCT"])}[col]])
                better = ">" if high_is_good else "<"
                rank = con.execute(
                    f"SELECT COUNT(*) + 1 FROM silver_team_ratings WHERE {col} {better} ?",
                    [value]).fetchone()[0]
                gaps.append({"factor": key, "label": label, "value": value, "rank": int(rank), "of": int(total)})
            gaps.sort(key=lambda gap: -gap["rank"])
            gaps = gaps[:2]
        else:
            errors.append("no team ratings row")
    else:
        errors.append("silver_team_ratings not in warehouse")
    cap = None
    if "silver_cap_room" in tables:
        crow = con.execute(
            "SELECT COMMITTED_SALARY, PENDING_OPTION_SALARY, FA_HOLDS_EST, PROJECTED_ROOM "
            "FROM silver_cap_room WHERE TEAM = ? LIMIT 1", [abbr]).fetchone()
        if crow:
            cap = {"committed": crow[0], "option_salary": crow[1], "fa_holds": crow[2], "projected_room": crow[3]}
        else:
            errors.append("no cap room row")
    else:
        errors.append("silver_cap_room not in warehouse")
    targets = []
    if "silver_free_agents" in tables and "silver_player_season" in tables:
        metric = _DRAFT_GAP_STAT.get(gaps[0]["factor"] if gaps else "", "s.PPG")
        latest = con.execute("SELECT MAX(_season) FROM silver_player_season").fetchone()[0]
        rows = con.execute(
            f"SELECT f.PLAYER_NAME, f.TEAM, f.FA_TYPE, f.PRIOR_SALARY, f.CAP_HOLD_EST, "
            f"s.PPG, s.RPG, s.APG, s.SPG, s.BPG, s.FG3_PCT, s.GP "
            f"FROM silver_free_agents f JOIN silver_player_season s "
            f"ON lower(s.PLAYER) = lower(f.PLAYER_NAME) AND s._season = ? "
            f"ORDER BY ({metric}) DESC NULLS LAST LIMIT 12", [latest]).fetchall()
        targets = [{"name": str(r[0]), "team": r[1], "fa_type": r[2], "prior_salary": r[3],
                    "cap_hold": r[4], "ppg": r[5], "rpg": r[6], "apg": r[7],
                    "spg": r[8], "bpg": r[9], "fg3_pct": r[10], "gp": r[11]} for r in rows]
        if not targets:
            errors.append("no free agent rows joined to current season")
    elif "silver_free_agents" not in tables:
        errors.append("silver_free_agents not in warehouse")
    else:
        errors.append("silver_player_season not in warehouse")
    tables_used = [t for t in ("silver_team_ratings", "silver_cap_room", "silver_free_agents", "silver_player_season") if t in tables]
    ok = bool(gaps or cap or targets)
    return {"ok": ok, "team": abbr, "gaps": gaps, "cap": cap, "targets": targets,
            "errors": errors, "provenance": {"table": " + ".join(tables_used), "as_of": ratings_as_of},
            **({} if ok else {"error": "; ".join(errors)})}

@tool(description='Aggregate the draft and free-agency workspace: prospect board, 2027 free agent class, cap room, and team fit targets.')
def product_draft(team: str, season: str = '') -> dict:
    from shared import store
    abbr = str(team or '').strip().upper()
    try:
        con = store.connect(read_only=True)
    except Exception:
        return {"ok": False, "error": "warehouse unreachable"}
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        blocks = {
            "board": _draft_board(con, tables, str(season or '').strip()),
            "free_agents": _draft_free_agents(con, tables),
            "cap_room": _draft_cap_room(con, tables),
            "fit": _draft_fit(con, tables, abbr) if abbr else {"ok": False, "error": "team needed",
                "gaps": [], "cap": None, "targets": [], "errors": ["team needed"],
                "provenance": {"table": "", "as_of": None}},
        }
        return {"ok": True, "team": abbr, "season": str(season or ''), "blocks": blocks}
    except Exception as error:
        return {"ok": False, "error": str(error)[:200]}
    finally:
        con.close()

def internal_catalogue():
    operations = (product_board_metrics, product_board_fill, product_board_seed, product_save_chat, product_save_run, product_threads, product_runs,
        product_warehouse_identity, product_warehouse_health, product_dataset, product_freshness, product_table_detail, product_home,
        product_rerun, product_resolve, product_trade, product_trade_partners, product_trade_assets, product_morning, product_debate, product_today,
        product_watchlist, product_watchlist_add, product_watchlist_remove, product_movers, product_briefing,
        product_compare, product_draft, product_matchups, product_awards, product_scout_dossier,
        product_cap_sheet, product_cap_scenario_eval, product_trade_legs, product_history_career, product_history_era_comps, product_history_leaders)
    result = {operation.name: operation for operation in operations}
    for operation in operations:
        operation.args_schema.__doc__ = operation.description
    from analyst.python_tools import apply_param_docs
    for name, operation in result.items():
        apply_param_docs(name, operation)
    return result
