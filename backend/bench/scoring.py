"""Scoring for DimeBench. Static tool-to-family map is config, not test cases."""

import re

NUM_RX = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?%?")

TOOL_FAMILY: dict[str, str | None] = {
    "get_leaders": "lookup",
    "delegate_league": "lookup",
    "get_standings": "lookup",
    "get_standings_deep": "lookup",
    "get_ratings": "lookup",
    "get_elo": "lookup",
    "get_playoffs": "lookup",
    "get_injuries": "lookup",
    "get_clutch": "lookup",
    "get_hustle": "lookup",
    "get_hustle_boards": "lookup",
    "get_risers": "lookup",
    "get_leaderboard_deltas": "lookup",
    "snapshot_leaderboard": "lookup",
    "get_draft_board": "lookup",
    "get_draft_model": "lookup",
    "get_combine": "lookup",
    "get_compare": "compare",
    "get_debate_card": "compare",
    "get_shot_compare": "compare",
    "get_comps": "compare",
    "get_player_intel": "chain",
    "get_last_x": "chain",
    "get_trend": "chain",
    "get_boxscore": "chain",
    "get_team_hub": "chain",
    "get_games_on_date": "chain",
    "get_playoff_intel": "chain",
    "get_splits": "chain",
    "get_shot_zones": "chain",
    "get_lineups": "chain",
    "get_rotation_check": "chain",
    "get_scout_pack": "chain",
    "get_scouting_report": "chain",
    "delegate_scout": "chain",
    "get_percentiles": "adjudicate",
    "get_on_off": "adjudicate",
    "get_wowy": "adjudicate",
    "get_advanced": "adjudicate",
    "get_four_factors": "adjudicate",
    "get_rapm": "adjudicate",
    "get_raptor_history": "adjudicate",
    "get_trade_check": "trade",
    "get_cap_ledger": "trade",
    "get_contract_value": "trade",
    "get_today": "brief",
    "get_morning_briefing": "brief",
    "get_briefing": "brief",
    "delegate_team": "brief",
    "get_preview": "brief",
    "get_recap": "brief",
    "get_win_prob": "brief",
    "get_playoff_sim": "brief",
    "get_injury_impact": "brief",
    "get_team_splits": "brief",
    "get_finder": "finder",
    "get_rest": "finder",
    "resolve_entity": None,
    "search_nba": None,
    "run_python": None,
    "text_to_sql": None,
    "get_watchlist": None,
    "add_watchlist_item": None,
    "remove_watchlist_item": None,
}


def tool_f1(observed: list[str], gold: list[str]) -> float:
    obs = {TOOL_FAMILY.get(n) for n in observed}
    obs.discard(None)
    gold_set = set(gold)
    if not gold_set:
        return 1.0 if not obs else 0.0
    if not obs:
        return 0.0
    inter = len(obs & gold_set)
    precision = inter / len(obs)
    recall = inter / len(gold_set)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 3)


def _numeric_forms(value: float | int) -> set[str]:
    forms = set()
    try:
        forms.add(str(int(round(float(value)))))
    except (TypeError, ValueError):
        return forms
    forms.add(f"{float(value):.1f}")
    forms.add(f"{int(round(float(value))):,}")
    forms.add(str(value))
    return forms


def numeric_acc(facts: dict, answer: str) -> float:
    nums = {k: v for k, v in facts.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if not nums:
        return 1.0
    text = answer or ""
    lowered = text.lower()
    names = [str(v) for v in facts.values() if isinstance(v, str)]
    hits = 0
    for value in nums.values():
        if any(f and f in text for f in _numeric_forms(value)):
            hits += 1
            continue
        if any(len(n.split()[-1]) > 2 and n.split()[-1].lower() in lowered
               for n in names if n.strip()):
            hits += 1
    return round(hits / len(nums), 3)


def _norm_num(raw: str) -> str:
    return raw.replace(",", "").rstrip("%")


def groundedness(answer: str, payload_text: str) -> float:
    found = NUM_RX.findall(answer or "")
    if not found:
        return 1.0
    pool = {_norm_num(n) for n in NUM_RX.findall(payload_text or "")}
    if not pool:
        return 0.0
    hits = 0
    for raw in found:
        cand = _norm_num(raw)
        try:
            alts = {cand, str(int(round(float(cand))))}
            if raw.endswith("%"):
                alts.add(str(round(float(cand) / 100, 4)))
                alts.add(str(float(cand) / 100))
        except (TypeError, ValueError):
            alts = {cand}
        if alts & pool:
            hits += 1
    return round(hits / len(found), 3)
