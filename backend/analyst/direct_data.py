import json
from langchain_core.tools import tool

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
    return get_trade_check.invoke(dict(team_a=team_a,players_a=players_a,team_b=team_b,players_b=players_b,season=season))

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
    operations = (product_save_chat, product_save_run, product_threads, product_runs,
        product_warehouse_identity, product_warehouse_health, product_dataset, product_freshness, product_table_detail, product_home,
        product_rerun, product_resolve, product_trade, product_debate, product_today,
        product_watchlist, product_watchlist_add, product_watchlist_remove, product_movers, product_briefing)
    result = {operation.name: operation for operation in operations}
    for operation in operations:
        operation.args_schema.__doc__ = operation.description
    return result
