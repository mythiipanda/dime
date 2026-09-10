"""Scoring for DimeBench. Static tool-to-family map is config, not test cases."""

import re
from decimal import Decimal, ROUND_HALF_UP

NUM_RX = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?%?")
SEASON_RX = re.compile(r"\b(?:19|20)\d\d-\d{2}(?:\d{2})?\b")


def _strip_seasons(text: str) -> str:
    return SEASON_RX.sub("", text or "")

TOOL_FAMILY: dict[str, str | None] = {
    "get_leaders": "lookup",
    "delegate_league": "lookup",
    "get_standings": "lookup",
    "get_standings_deep": "lookup",
    "get_ratings": "lookup",
    "get_elo": "lookup",
    "get_elo_standings": "elo",
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
    "get_comps": "comps",
    "get_player_intel": "chain",
    "get_last_x": "chain",
    "get_trend": "chain",
    "get_boxscore": "chain",
    "get_team_hub": "chain",
    "get_games_on_date": "brief",
    "get_playoff_intel": "chain",
    "get_splits": "chain",
    "get_matchup_splits": "splits",
    "get_regression_check": "splits",
    "get_shot_zones": "chain",
    "get_lineups": "chain",
    "get_rotation_check": "rotation",
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
    "get_trade_value": "trade_value",
    "get_cap_ledger": "trade",
    "get_contract_value": "trade_value",
    "get_today": "brief",
    "get_morning_briefing": "brief",
    "get_briefing": "brief",
    "delegate_team": "brief",
    "get_preview": "brief",
    "get_matchup_preview": "brief",
    "get_recap": "brief",
    "get_win_prob": "brief",
    "get_playoff_sim": "brief",
    "get_injury_impact": "brief",
    "get_team_splits": "brief",
    "get_finder": "finder",
    "get_rest": "finder",
    "get_streaks": "streaks",
    "get_lineup_stats": "lineups",
    "get_award_race": "awards",
    "get_game_prediction": "prediction",
    "get_warehouse_freshness": "freshness",
    "get_head_to_head": "headtohead",
    "search_game_logs": "gamelog",
    "get_team_shot_zones": "zones",
    "get_impact_estimate": "impact",
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


def name_recall(facts: dict, answer: str) -> float:
    names = facts.get("names") if isinstance(facts, dict) else None
    if not isinstance(names, dict) or not names:
        return 1.0
    text = answer or ""
    hits = total = 0
    for expected in names.values():
        toks = str(expected or "").split()
        if not toks:
            continue
        total += 1
        if re.search(r"\b" + re.escape(toks[-1]) + r"\b", text,
                     re.IGNORECASE):
            hits += 1
    if not total:
        return 1.0
    return round(hits / total, 3)


def _numeric_forms(value: float | int, key: str = "") -> set[str]:
    forms = set()
    try:
        forms.add(str(int(round(float(value)))))
    except (TypeError, ValueError):
        return forms
    forms.add(f"{float(value):.1f}")
    # Float-repr artifact: f"{-3.15:.1f}" is "-3.1" because the float is
    # really -3.1499999..., but the true -3.15 rounds half-up to "-3.2".
    # When the decimal string of the value is exactly on a .x5 boundary at
    # 2dp, also emit the half-up 1dp form so the correct answer matches.
    try:
        d = Decimal(str(value))
        if d == d.quantize(Decimal("0.01")) and abs(d * 100) % 10 == 5:
            forms.add(str(d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)))
    except (ArithmeticError, TypeError, ValueError):
        pass
    forms.add(f"{int(round(float(value))):,}")
    forms.add(str(value))
    # Percent form, scoped tight: only for probability facts (win_prob_*
    # keys holding a 0-1 value). Lets "76.6%" / "76.6 percent" match 0.766
    # without letting e.g. an eFG of 0.5 match "50%" elsewhere.
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = None
    if v is not None and 0.0 <= v <= 1.0 and str(key).startswith("win_prob"):
        pct = v * 100
        forms.add(f"{pct:.1f}%")
        forms.add(f"{int(round(pct))}%")
        forms.add(f"{pct:.1f} percent")
        forms.add(f"{int(round(pct))} percent")
    return forms


def numeric_acc(facts: dict, answer: str) -> float:
    nums = {k: v for k, v in facts.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if not nums:
        return 1.0
    text = _strip_seasons(answer or "")
    hits = 0
    for key, value in nums.items():
        # Trailing guard blocks a following digit or a decimal continuation
        # (".5" in "98.75") but allows a sentence-final period ("98.7.").
        if any(f and re.search(r"(?<![\d.,])" + re.escape(f) + r"(?!\d|\.\d)",
                              text)
               for f in _numeric_forms(value, key)):
            hits += 1
    return round(hits / len(nums), 3)


def _norm_num(raw: str) -> str:
    return raw.replace(",", "").rstrip("%")


def groundedness(answer: str, payload_text: str) -> float:
    found = NUM_RX.findall(_strip_seasons(answer or ""))
    if not found:
        return 1.0
    pool = {_norm_num(n)
            for n in NUM_RX.findall(_strip_seasons(payload_text or ""))}
    if not pool:
        return 0.0
    pool_floats: list[float] = []
    for p in pool:
        try:
            pool_floats.append(float(p))
        except (TypeError, ValueError):
            pass
    hits = 0
    for raw in found:
        cand = _norm_num(raw)
        try:
            alts = {cand, str(int(round(float(cand))))}
            if raw.endswith("%"):
                alts.add(str(round(float(cand) / 100, 4)))
                alts.add(str(float(cand) / 100))
            else:
                alts.add(str(round(float(cand) * 100, 4)))
                alts.add(str(float(cand) * 100))
        except (TypeError, ValueError):
            alts = {cand}
        if alts & pool:
            hits += 1
            continue
        try:
            a = float(cand)
        except (TypeError, ValueError):
            continue
        if any(abs(a - p) <= 0.051 for p in pool_floats):
            hits += 1
    return round(hits / len(found), 3)
