"""F89 Muse regressions: current qualified usage and metric-sensitive asks."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.graph import _detect_entities, _triage_seed, presentation_agent
from app.tools import get_young_player_usage


def drain(q):
 async def go():
  st={"question":q,"history":[],"tool_results":[],"calls_made":[],"round":0}
  async for _ in _triage_seed(q,"p","m",st): pass
  return st
 return asyncio.run(go())

def present(q,st):
 async def go():
  x={**st,"question":q,"analysis":"","primary":"p","model":"m"}; out=''
  async for e in presentation_agent(x):
   if e.get('type')=='final_answer': out=e['data']['text']
  return out
 return asyncio.run(go())

def calls(st): return [x.split(':')[0] for x in st['calls_made']]

def test_young_usage_current_qualified_board():
 out=get_young_player_usage.invoke({})
 assert out['rows'][0]['PLAYER']=='Victor Wembanyama'
 assert out['rows'][0]['USG_PCT']==31.6
 assert out['meta']['min_minutes']==1000
 assert '1,000+ total minutes' in out['meta']['deterministic_answer']

def test_young_usage_prompt_is_one_call():
 st=drain('Which young player under 23 has the highest usage rate this season?')
 assert calls(st)==['get_young_player_usage']

def test_uppercase_lebron_metric_is_not_player():
 ps,_=_detect_entities('Can I trust EPM and LEBRON for Brunson?')
 assert ps==['Jalen Brunson']
 st=drain('Can I trust EPM and LEBRON for Brunson?')
 assert calls(st)==['metric_coverage']
 ans=st['tool_results'][0]['meta']['deterministic_answer']
 assert 'not available' in ans and 'LeBron James' not in ans

def test_efg_compare_uses_asked_metric():
 st=drain('Compare Jaylen Brown and Jayson Tatum in eFG% this season.')
 assert calls(st)==['get_compare']
 ans=present('Compare Jaylen Brown and Jayson Tatum in eFG% this season.',st)
 assert '52.2% eFG' in ans and '49.3% eFG' in ans
 assert '57.3% TS' not in ans
