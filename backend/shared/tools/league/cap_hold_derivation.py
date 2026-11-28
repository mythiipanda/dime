from functools import lru_cache
from typing import Any

from ..cap_holds import (
    EXACTNESS_APPROXIMATE,
    EXACTNESS_ESTIMATED,
    EXACTNESS_OFFICIAL,
    EXACTNESS_UNKNOWN,
    RIGHTS_EARLY_QUALIFYING,
    RIGHTS_NON_QUALIFYING,
    RIGHTS_QUALIFYING,
    RIGHTS_UNKNOWN,
    ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR,
    ROOKIE_SCALE_NONE,
    ROOKIE_SCALE_OPTION_DECLINED,
    ROUND_HALF_UP,
    calculate_cap_hold,
)

_MONEY_UNIT = "usd_dollars"
CAP_HOLD_CONTRACT = {
    "cap_hold": "effective planning estimate used in scenario arithmetic; null when unknown and never zero-filled",
    "cap_hold_est": "compatibility alias for the same effective estimate as cap_hold; null when unknown",
    "legacy_cap_hold_est": "unvalidated silver_free_agents.CAP_HOLD_EST seed retained for comparison",
    "legacy_fallback": "when derivation inputs are unavailable, the effective estimate is the labeled legacy seed rather than a calculator-derived value",
    "scenario_arithmetic": "projected_room is null while unknown-amount holds remain retained; projected_room_upper_bound excludes those amounts, and cap-hold sums are labeled known-dollar partial sums when unknowns are present",
}
_CAP_2026_27 = 164_961_000
_EAPS_2026_27 = 15_163_000
_MINIMUM_SCALE_2026_27 = [
    1_357_763, 2_185_116, 2_449_421, 2_537_526, 2_625_627,
    2_845_883, 3_066_143, 3_286_399, 3_506_659, 3_524_115,
    3_876_529,
]
_ACTIVE_FA_TYPES = {"ufa", "rfa", "two_way"}
_OPTION_FA_TYPES = {"player_option", "team_option"}


def _tables(con) -> set[str]:
    try:
        return {str(r[0]) for r in con.execute("SHOW TABLES").fetchall()}
    except Exception:
        return set()


def _columns(con, table: str) -> set[str]:
    try:
        return {str(r[1]) for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def _fa_year(fa_year: object) -> int | None:
    try:
        year = int(str(fa_year).strip())
    except (TypeError, ValueError):
        return None
    return year if 1000 <= year <= 9999 else None


def _cap_season(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d}"


def _end_year(season: str) -> int | None:
    try:
        return int(str(season)[:4]) + 1
    except (TypeError, ValueError):
        return None


def _dependency(fa_type: object) -> str:
    value = str(fa_type or "").lower()
    if value in _ACTIVE_FA_TYPES:
        return "active_expired_contract"
    if value in _OPTION_FA_TYPES:
        return "option_decision_required"
    return "active_type_unknown"


def _legacy_row(row: dict[str, Any], reason: str) -> dict[str, Any]:
    seeded = row.get("CAP_HOLD")
    if seeded is not None:
        amount = int(seeded)
        dependency = _dependency(row.get("FA_TYPE"))
        return {
            **row,
            "player": row.get("PLAYER_NAME"),
            "team": row.get("TEAM"),
            "fa_type": row.get("FA_TYPE"),
            "prior_salary": row.get("PRIOR_SALARY"),
            "cap_hold": amount,
            "cap_hold_est": amount,
            "legacy_cap_hold_est": int(row.get("CAP_HOLD_EST") or 0),
            "money_unit": _MONEY_UNIT,
            "scenario_dependency": dependency,
            "active_in_baseline": dependency == "active_expired_contract",
            "rights_classification": None,
            "rookie_scale_status": None,
            "hold_rule": row.get("CAP_HOLD_RULE") or "seeded_derivation",
            "hold_basis": "seeded_derivation",
            "hold_exactness": row.get("CAP_HOLD_EXACTNESS") or EXACTNESS_ESTIMATED,
            "provenance_class": "seeded_derivation",
            "input_exactness": {},
            "input_provenance": {},
            "uncertainty": [
                "consumer-time derivation inputs incomplete; retained seeder-written calculator-derived hold",
                reason,
            ],
            "derivation_status": "seeded_derivation_fallback",
        }
    amount = int(row.get("CAP_HOLD_EST") or 0)
    dependency = _dependency(row.get("FA_TYPE"))
    return {
        **row,
        "player": row.get("PLAYER_NAME"),
        "team": row.get("TEAM"),
        "fa_type": row.get("FA_TYPE"),
        "prior_salary": row.get("PRIOR_SALARY"),
        "cap_hold": amount,
        "cap_hold_est": amount,
        "legacy_cap_hold_est": amount,
        "money_unit": _MONEY_UNIT,
        "scenario_dependency": dependency,
        "active_in_baseline": dependency == "active_expired_contract",
        "rights_classification": None,
        "rookie_scale_status": None,
        "hold_rule": "legacy_seed_estimate",
        "hold_basis": "legacy_seed_estimate",
        "hold_exactness": "legacy_seed_estimate",
        "provenance_class": "legacy_seed_estimate",
        "input_exactness": {},
        "input_provenance": {},
        "uncertainty": [
            "supporting derivation inputs incomplete; retained warehouse CAP_HOLD_EST without calculator validation",
            reason,
        ],
        "derivation_status": "legacy_fallback",
    }


def _scaled_minimum(years: int, target_cap: int) -> int:
    base = _MINIMUM_SCALE_2026_27[max(0, min(int(years), 10))]
    return (base * target_cap + _CAP_2026_27 // 2) // _CAP_2026_27


def _eaps(prior_end_year: int) -> tuple[int, str, str]:
    if prior_end_year == 2027:
        return (_EAPS_2026_27, EXACTNESS_OFFICIAL,
                "league-reported 2026-27 estimated average player salary, 15,163,000")
    years = max(0, prior_end_year - 2027)
    value = _EAPS_2026_27
    for _ in range(years):
        value = int(round(value * 1.045))
    return (value, EXACTNESS_APPROXIMATE,
            "2026-27 league-reported EAPS projected forward at 104.5% per season; projection convention not league-verified")


def _ordinary_max_tier(years: int) -> int:
    if years < 7:
        return 25
    if years < 10:
        return 30
    return 35


def _season_end_from_date(value: object) -> int | None:
    text = str(value or "")
    try:
        year = int(text[:4])
        month = int(text[5:7])
    except (TypeError, ValueError):
        return None
    return year + 1 if month >= 7 else year


@lru_cache(maxsize=1)
def _static_team_ids() -> dict[int, str]:
    try:
        from nba_api.stats.static import teams as static_teams
        return {int(t["id"]): str(t["abbreviation"]).upper()
                for t in static_teams.get_teams()}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _static_team_names() -> dict[str, str]:
    try:
        from nba_api.stats.static import teams as static_teams
        return {str(t["abbreviation"]).upper(): str(t["full_name"]).lower()
                for t in static_teams.get_teams()}
    except Exception:
        return {}


def _txn_key(name: object) -> str:
    text = str(name or "").strip().lower()
    out = []
    for ch in text:
        out.append(ch if ch.isalnum() else "-")
    return "-".join(part for part in "".join(out).split("-") if part)


def _fetch_salary_index(con, cols: set[str]) -> dict[tuple[str, str], dict[str, Any]]:
    if not {"PLAYER_NAME", "TEAM", "BREF_SLUG"}.issubset(cols):
        return {}
    wanted = ["PLAYER_NAME", "TEAM", "BREF_SLUG", "PLAYER_ID", "SALARY"]
    seasonal = sorted(c for c in cols
                      if c.startswith("SALARY_") or c.startswith("OPTION_"))
    pick = [c for c in wanted if c in cols] + seasonal
    try:
        cur = con.execute("SELECT " + ", ".join(pick) + " FROM silver_salaries")
        rows = [dict(zip(pick, r)) for r in cur.fetchall()]
    except Exception:
        return {}
    out = {}
    for row in rows:
        slug = str(row.get("BREF_SLUG") or "").lower()
        team = str(row.get("TEAM") or "").upper()
        if slug and team and (slug, team) not in out:
            out[(slug, team)] = row
    return out


def _fetch_draft(con, tables: set[str]) -> dict[int, dict[str, Any]]:
    if "silver_hist_draft" not in tables:
        return {}
    cols = _columns(con, "silver_hist_draft")
    if not {"PERSON_ID", "DRAFT_YEAR", "ROUND_NUMBER"}.issubset(cols):
        return {}
    try:
        rows = con.execute(
            "SELECT PERSON_ID, DRAFT_YEAR, ROUND_NUMBER, OVERALL_PICK FROM silver_hist_draft"
        ).fetchall()
    except Exception:
        return {}
    return {int(r[0]): {"draft_year": int(r[1] or 0), "round": int(r[2] or 0),
                        "overall_pick": int(r[3] or 0)}
            for r in rows if r and r[0]}


def _fetch_contract_types(con, tables: set[str]) -> dict[str, str]:
    out = {}
    if "silver_cap_players" in tables:
        try:
            rows = con.execute(
                "SELECT player, contract_type FROM silver_cap_players "
                "WHERE _season = (SELECT MAX(_season) FROM silver_cap_players)"
            ).fetchall()
            out.update({str(r[0]).lower(): str(r[1] or "") for r in rows if r and r[0]})
        except Exception:
            pass
    if "silver_contracts" in tables:
        try:
            rows = con.execute(
                "SELECT PLAYER_NAME, CONTRACT_SOURCE, TWO_WAY FROM silver_contracts "
                "WHERE _season = (SELECT MAX(_season) FROM silver_contracts)"
            ).fetchall()
            for name, source, two_way in rows:
                key = str(name or "").lower()
                if key and (key not in out or two_way):
                    out[key] = str(source or "") + (" two_way" if two_way else "")
        except Exception:
            pass
    return out


def _lookup_player_id(con, tables: set[str], name: object) -> int | None:
    player = str(name or "")
    if not player:
        return None
    lookups = []
    if "silver_hist_player_seasons" in tables:
        lookups.append(("silver_hist_player_seasons", "player_id", "player_name"))
    if "silver_player_season" in tables:
        lookups.append(("silver_player_season", "PLAYER_ID", "PLAYER"))
    for table, id_col, name_col in lookups:
        try:
            rows = con.execute(
                f"SELECT DISTINCT {id_col} FROM {table} "
                f"WHERE LOWER({name_col}) = LOWER(?)", [player]).fetchall()
        except Exception:
            continue
        ids = [int(r[0]) for r in rows if r and r[0]]
        if len(set(ids)) == 1:
            return ids[0]
    return None


def _fetch_service_years(con, tables: set[str], player_id: int | None,
                         prior_end: int) -> set[int]:
    years = set()
    if player_id and "silver_hist_player_seasons" in tables:
        try:
            rows = con.execute(
                "SELECT DISTINCT season FROM silver_hist_player_seasons "
                "WHERE player_id = ? AND season <= ?", [player_id, prior_end]).fetchall()
            years.update(int(r[0]) for r in rows if r and r[0])
        except Exception:
            pass
    if player_id and "silver_player_season" in tables:
        try:
            rows = con.execute(
                "SELECT DISTINCT _season FROM silver_player_season WHERE PLAYER_ID = ?",
                [player_id]).fetchall()
            for row in rows:
                end = _end_year(str(row[0] or ""))
                if end and end <= prior_end:
                    years.add(end)
        except Exception:
            pass
    return years


def _fetch_transactions(con, tables: set[str], player_id: int | None,
                        name: object) -> list[dict[str, Any]]:
    if "silver_transactions" not in tables:
        return []
    cols = _columns(con, "silver_transactions")
    if not {"txn_date", "txn_type", "team_id"}.issubset(cols):
        return []
    try:
        if player_id:
            rows = con.execute(
                "SELECT txn_date, txn_type, team_id, detail FROM silver_transactions "
                "WHERE player_id = ? ORDER BY txn_date", [player_id]).fetchall()
        else:
            rows = con.execute(
                "SELECT txn_date, txn_type, team_id, detail FROM silver_transactions "
                "WHERE player = ? ORDER BY txn_date", [_txn_key(name)]).fetchall()
    except Exception:
        return []
    return [{"date": r[0], "type": str(r[1] or ""), "team_id": int(r[2] or 0),
             "detail": str(r[3] or "")} for r in rows]


def _rights_from_transactions(txns: list[dict[str, Any]], prior_end: int,
                              team_ids: dict[int, str], target_team: str) -> dict[str, Any]:
    start = None
    current = 0
    reset_next_signing = False
    explicit_start = False
    open_chain = False
    latest_date = None
    for txn in txns:
        end = _season_end_from_date(txn.get("date"))
        tid = int(txn.get("team_id") or 0)
        kind = str(txn.get("type") or "")
        if not end or end > prior_end or not tid:
            continue
        latest_date = str(txn.get("date") or "")
        if kind in {"Trade", "AwardOnWaivers"}:
            if start is None and current == 0:
                open_chain = True
            current = tid
            reset_next_signing = False
        elif kind == "Waive" and (current == 0 or current == tid):
            start = None
            current = 0
            reset_next_signing = True
            explicit_start = False
            open_chain = False
        elif kind in {"Signing", "ContractConverted"}:
            if current == 0 or reset_next_signing or current != tid:
                explicit_start = bool(reset_next_signing or (current != 0 and current != tid))
                start = end
                open_chain = False
            current = tid
            reset_next_signing = False
    if start is None:
        return {"rights": None, "start": None, "latest_date": latest_date,
                "conflict": False, "explicit_start": False, "open_chain": open_chain}
    seasons = prior_end - int(start) + 1
    if seasons >= 3:
        rights = RIGHTS_QUALIFYING
    elif seasons == 2:
        rights = RIGHTS_EARLY_QUALIFYING
    elif seasons == 1:
        rights = RIGHTS_NON_QUALIFYING
    else:
        rights = None
    current_abbr = team_ids.get(current, "")
    conflict = bool(current_abbr and current_abbr != target_team)
    return {"rights": rights, "start": int(start), "latest_date": latest_date,
            "conflict": conflict, "current_abbr": current_abbr, "seasons": seasons,
            "explicit_start": explicit_start, "open_chain": open_chain}


def _trade_matches_prior_team(txn: dict[str, Any], prior_team: str) -> bool:
    source = _static_team_names().get(prior_team)
    detail = str(txn.get("detail") or "").lower()
    return bool(source and f"from {source}" in detail)


def _latest_waiver_reset(txns: list[dict[str, Any]], prior_end: int) -> tuple[int | None, bool]:
    latest_date = ""
    latest_end = None
    for txn in txns:
        end = _season_end_from_date(txn.get("date"))
        date = str(txn.get("date") or "")
        if txn.get("type") == "Waive" and end and end <= prior_end and date >= latest_date:
            latest_date = date
            latest_end = end
    if latest_end is None:
        return None, False
    restarted = any(
        txn.get("type") in {"Signing", "ContractConverted"}
        and str(txn.get("date") or "") > latest_date
        and (_season_end_from_date(txn.get("date")) or prior_end + 1) <= prior_end
        for txn in txns)
    return latest_end, restarted


def _team_transition_evidence(txns: list[dict[str, Any]], team_ids: dict[int, str],
                              prior_team: str, current_team: str,
                              season_end: int) -> str:
    events = []
    for txn in txns:
        end = _season_end_from_date(txn.get("date"))
        abbr = team_ids.get(int(txn.get("team_id") or 0), "")
        if end == season_end and abbr:
            events.append({**txn, "end": end, "abbr": abbr})
    carry = None
    for txn in events:
        if txn["abbr"] == current_team and txn["type"] in {"Trade", "AwardOnWaivers"}:
            carry = txn
            break
    if carry is not None:
        if not _trade_matches_prior_team(carry, prior_team):
            return "unknown"
        carry_date = str(carry.get("date") or "")
        prior_reset = any(
            str(txn.get("date") or "") < carry_date
            and txn["type"] in {"Signing", "ContractConverted"}
            and txn["abbr"] != prior_team
            for txn in events)
        return "reset" if prior_reset else "carry"
    if any(txn["abbr"] == current_team
           and txn["type"] in {"Signing", "ContractConverted"}
           for txn in events):
        return "reset"
    return "unknown"


def _season_teams_by_year(con, tables: set[str], player_id: int,
                          prior_end: int) -> dict[int, str]:
    by_year = {}
    if "silver_hist_player_seasons" in tables:
        try:
            rows = con.execute(
                "SELECT season, team_abbreviation FROM silver_hist_player_seasons "
                "WHERE player_id = ? AND season <= ? ORDER BY season DESC",
                [player_id, prior_end]).fetchall()
        except Exception:
            rows = []
        for season, team in rows:
            year = int(season or 0)
            if year and year not in by_year:
                by_year[year] = str(team or "").upper()
    if "silver_player_season" in tables:
        try:
            current_rows = con.execute(
                "SELECT _season, TEAM FROM silver_player_season WHERE PLAYER_ID = ?",
                [player_id]).fetchall()
            for season, team in current_rows:
                year = _end_year(str(season or ""))
                if year and year <= prior_end and year not in by_year:
                    by_year[year] = str(team or "").upper()
        except Exception:
            pass
    return by_year


def _rights_from_seasons(con, tables: set[str], player_id: int | None,
                         prior_end: int, target_team: str,
                         txns: list[dict[str, Any]],
                         team_ids: dict[int, str]) -> dict[str, Any] | None:
    if not player_id or not ({"silver_hist_player_seasons", "silver_player_season"} & tables):
        return None
    by_year = _season_teams_by_year(con, tables, player_id, prior_end)
    if by_year.get(prior_end) != target_team:
        return None
    count = 1
    exact_start = False
    unresolved = False
    first_observed_year = min(by_year) if by_year else prior_end
    waiver_end, waiver_restarted = _latest_waiver_reset(txns, prior_end)
    year = prior_end - 1
    while count < 3:
        if waiver_end is not None and year < waiver_end <= year + 1:
            exact_start = waiver_restarted
            unresolved = not exact_start
            break
        if year not in by_year:
            exact_start = not (year + 1 == first_observed_year
                               and first_observed_year <= 1997)
            unresolved = not exact_start
            break
        prior_team = by_year[year]
        current_team = by_year[year + 1]
        if prior_team == current_team:
            count += 1
            year -= 1
            continue
        transition = _team_transition_evidence(
            txns, team_ids, prior_team, current_team, year + 1)
        if transition == "carry":
            count += 1
            year -= 1
            continue
        if transition == "reset":
            exact_start = True
            break
        unresolved = True
        break
    if count >= 3:
        return {"rights": RIGHTS_QUALIFYING, "seasons": 3,
                "source": "season continuity with trade carryover"}
    if exact_start:
        rights = (RIGHTS_EARLY_QUALIFYING if count == 2
                  else RIGHTS_NON_QUALIFYING)
        return {"rights": rights, "seasons": count,
                "source": "season continuity with a proven service-chain start"}
    if unresolved:
        return {"rights": RIGHTS_UNKNOWN, "seasons": count,
                "source": "season continuity reaches a team change without proof of trade carryover or a service-chain reset"}
    return None


def _infer_rights(con, tables: set[str], row: dict[str, Any], salary: dict[str, Any],
                  prior_end: int, target_team: str) -> tuple[str, str]:
    player_id = salary.get("PLAYER_ID")
    player_id = int(player_id) if player_id else None
    txns = _fetch_transactions(con, tables, player_id, row.get("PLAYER_NAME"))
    team_ids = _static_team_ids()
    chain = _rights_from_transactions(txns, prior_end, team_ids, target_team)
    chain_usable = bool(chain.get("rights") and not chain.get("conflict")
                        and (chain.get("seasons", 0) >= 3 or chain.get("explicit_start")))
    if chain_usable:
        seasons = chain.get("seasons")
        rule = (f"inference:silver_transactions continuous signing/trade chain reaches {seasons} "
                f"season(s) with {target_team} through {prior_end}; trades preserve the chain and waivers reset it")
        return str(chain["rights"]), rule
    fallback = _rights_from_seasons(con, tables, player_id, prior_end, target_team,
                                    txns, team_ids)
    if fallback and fallback.get("rights") != RIGHTS_UNKNOWN:
        rule = (f"inference:silver_hist_player_seasons/silver_player_season shows {fallback['seasons']} consecutive "
                f"season(s) in the rights chain through {prior_end}; {fallback['source']}")
        return str(fallback["rights"]), rule
    if chain.get("open_chain"):
        reason = ("first observed transaction is a trade or waiver award, so prior-team service "
                  "cannot be established from the transaction feed")
    elif chain.get("rights") and not chain.get("explicit_start"):
        reason = ("observed signing may be a re-signing that preserves earlier service; "
                  "the transaction feed cannot prove the chain start")
    elif fallback and fallback.get("source"):
        reason = str(fallback["source"])
    else:
        reason = "no reliable silver_transactions chain or continuous-season evidence"
    rule = f"inference insufficient: {reason}; no Bird-rights classification is guessed"
    return RIGHTS_UNKNOWN, rule


def _service_years(con, tables: set[str], salary: dict[str, Any], prior_end: int,
                   draft: dict[str, Any] | None) -> tuple[int | None, str]:
    player_id = salary.get("PLAYER_ID")
    player_id = int(player_id) if player_id else None
    years = _fetch_service_years(con, tables, player_id, prior_end)
    if years:
        return len(years), "inference:count distinct NBA seasons in silver_hist_player_seasons plus silver_player_season through the prior season"
    if draft and draft.get("draft_year"):
        value = max(0, prior_end - int(draft["draft_year"]))
        return value, "inference:prior season end year minus silver_hist_draft draft year because season rows are absent"
    return None, "unknown:no silver_hist_player_seasons, silver_player_season, or draft evidence for years of service"


def _rookie_status(row: dict[str, Any], salary: dict[str, Any], draft: dict[str, Any] | None,
                   contract_type: str, fa_year: int, cap_season: str) -> tuple[str, int | None, str]:
    is_rookie_contract = "rookie" in contract_type.lower()
    first_round = bool(draft and int(draft.get("round") or 0) == 1)
    if not is_rookie_contract or not first_round:
        return ROOKIE_SCALE_NONE, None, "inference:no current rookie-scale contract evidence in silver_cap_players/silver_contracts or no first-round draft row"
    fa_type = str(row.get("FA_TYPE") or "").lower()
    draft_year = int((draft or {}).get("draft_year") or 0)
    suffix = str(cap_season).replace("-", "_")
    target_salary = salary.get(f"SALARY_{suffix}")
    target_option = str(salary.get(f"OPTION_{suffix}") or "").lower()
    if fa_type == "team_option" and target_option == "team" and target_salary:
        return (ROOKIE_SCALE_OPTION_DECLINED, int(target_salary),
                "inference:option-dependent calculation assumes the pending first-round rookie-scale team option is declined")
    if draft_year and draft_year == fa_year - 4:
        return (ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR, None,
                "inference:first-round rookie-scale contract reaches the fourth rookie-scale season in the FA year")
    return ROOKIE_SCALE_NONE, None, "inference:first-round rookie-scale evidence present but neither completion nor declined-option path applies"


def _metadata(prior_salary: int, years: int | None, rights: str, rights_rule: str,
              rookie_status: str, max_tier: int, target_cap: int, eaps: int,
              eaps_exactness: str, eaps_source: str, minimum: int,
              unreimbursed: int, target_zero: int | None, two_way: bool,
              declined_amount: int | None, restricted: bool) -> tuple[dict[str, str], dict[str, str]]:
    exactness = {
        "years_of_service": EXACTNESS_APPROXIMATE if years is not None else EXACTNESS_UNKNOWN,
        "rights_classification": EXACTNESS_APPROXIMATE if rights != RIGHTS_UNKNOWN else EXACTNESS_UNKNOWN,
        "rookie_scale_status": EXACTNESS_APPROXIMATE,
        "max_player_tier": EXACTNESS_APPROXIMATE,
        "completed_two_way_contract": EXACTNESS_APPROXIMATE,
        "restricted_free_agent": EXACTNESS_APPROXIMATE,
        "prior_salary": EXACTNESS_ESTIMATED,
        "final_prior_contract_salary": EXACTNESS_APPROXIMATE,
        "target_salary_cap": EXACTNESS_ESTIMATED,
        "prior_year_eaps": eaps_exactness,
        "applicable_minimum": EXACTNESS_APPROXIMATE,
        "target_unreimbursed_minimum": EXACTNESS_APPROXIMATE,
    }
    provenance = {
        "years_of_service": "silver_hist_player_seasons/silver_player_season or draft-year fallback; inference disclosed",
        "rights_classification": rights_rule,
        "rookie_scale_status": "silver_hist_draft plus silver_cap_players/silver_contracts and silver_salaries option-year evidence; inference disclosed",
        "max_player_tier": "ordinary years-of-service max tier; higher-max award/designated-player criteria not available in warehouse",
        "completed_two_way_contract": "silver_free_agents FA_TYPE plus silver_contracts TWO_WAY evidence; historical conversion coverage incomplete",
        "restricted_free_agent": "silver_free_agents FA_TYPE only; qualifying-offer existence and amounts unavailable",
        "prior_salary": "silver_free_agents.PRIOR_SALARY direct seed value; no salary-schedule join supplies this amount",
        "final_prior_contract_salary": "proxy: prior-season salary reused as final prior-contract salary because complete multi-year contract schedules are unreliable",
        "target_salary_cap": "silver_cap_room.PROJECTED_CAP for the target cap season; exact seed projection value, not a rounded public millions figure",
        "prior_year_eaps": eaps_source,
        "applicable_minimum": "2026-27 minimum scale scaled by target-cap growth; projection convention disclosed",
        "target_unreimbursed_minimum": "2026-27 two-year unreimbursed minimum scaled by target-cap growth for veterans; projection convention disclosed",
    }
    if two_way:
        exactness["target_zero_yos_minimum"] = EXACTNESS_APPROXIMATE
        provenance["target_zero_yos_minimum"] = "2026-27 zero-year minimum scaled by target-cap growth; projection convention disclosed"
    if declined_amount is not None:
        exactness["declined_option_amount"] = EXACTNESS_ESTIMATED
        provenance["declined_option_amount"] = "silver_salaries target-season team-option salary column"
    return exactness, provenance


def _target_cap(con, tables: set[str], cap_season: str) -> int | None:
    if "silver_cap_room" not in tables:
        return None
    try:
        row = con.execute(
            "SELECT PROJECTED_CAP FROM silver_cap_room WHERE CAP_SEASON = ? "
            "AND PROJECTED_CAP IS NOT NULL LIMIT 1", [cap_season]).fetchone()
    except Exception:
        return None
    return int(row[0]) if row and row[0] else None


def _compute_row(con, tables: set[str], row: dict[str, Any], salary_index: dict,
                 draft_index: dict, contract_types: dict, fa_year: int,
                 cap_season: str, target_cap: int) -> dict[str, Any]:
    key = (str(row.get("BREF_SLUG") or "").lower(), str(row.get("TEAM") or "").upper())
    salary = dict(salary_index.get(key) or {})
    if not salary.get("PLAYER_ID"):
        recovered = _lookup_player_id(con, tables, row.get("PLAYER_NAME"))
        if recovered:
            salary["PLAYER_ID"] = recovered
    prior_salary = int(row.get("PRIOR_SALARY") or 0)
    draft = draft_index.get(int(salary.get("PLAYER_ID") or 0)) if salary.get("PLAYER_ID") else None
    contract_type = contract_types.get(str(row.get("PLAYER_NAME") or "").lower(), "")
    prior_end = fa_year
    years, service_rule = _service_years(con, tables, salary, prior_end, draft)
    rights, rights_rule = _infer_rights(con, tables, row, salary, prior_end,
                                        str(row.get("TEAM") or "").upper())
    rookie_status, declined_amount, rookie_rule = _rookie_status(
        row, salary, draft, contract_type, fa_year, cap_season)
    fa_type = str(row.get("FA_TYPE") or "").lower()
    two_way = fa_type == "two_way" or "two_way" in contract_type.lower()
    restricted = fa_type == "rfa"
    eaps, eaps_exactness, eaps_source = _eaps(prior_end)
    service_for_min = int(years or 0)
    minimum = _scaled_minimum(service_for_min, target_cap)
    unreimbursed = _scaled_minimum(2 if service_for_min >= 2 else service_for_min, target_cap)
    target_zero = _scaled_minimum(0, target_cap) if two_way else None
    max_tier = _ordinary_max_tier(service_for_min)
    exactness, provenance = _metadata(
        prior_salary, years, rights, rights_rule, rookie_status, max_tier,
        target_cap, eaps, eaps_exactness, eaps_source, minimum, unreimbursed,
        target_zero, two_way, declined_amount, restricted)
    if years is None or not prior_salary:
        result = {"amount": None, "hold_rule": "essential_input_unavailable",
                  "hold_basis": "uncomputed", "hold_exactness": "unknown",
                  "input_exactness": exactness, "input_provenance": provenance,
                  "integer_rounding": None, "adjustments": [],
                  "calculation": {"computed": False, "reason": service_rule}}
    else:
        try:
            result = calculate_cap_hold(
                prior_salary=prior_salary, final_prior_contract_salary=prior_salary,
                years_of_service=years, rights_classification=rights,
                rookie_scale_status=rookie_status, max_player_tier=max_tier,
                target_salary_cap=target_cap, prior_year_eaps=eaps,
                applicable_minimum=minimum, target_unreimbursed_minimum=unreimbursed,
                target_zero_yos_minimum=target_zero, completed_two_way_contract=two_way,
                declined_option_amount=declined_amount, restricted_free_agent=restricted,
                input_exactness=exactness, provenance=provenance,
                integer_rounding=ROUND_HALF_UP)
        except ValueError as exc:
            result = {"amount": None, "hold_rule": "calculator_input_invalid",
                      "hold_basis": "uncomputed", "hold_exactness": "unknown",
                      "input_exactness": exactness, "input_provenance": provenance,
                      "integer_rounding": None, "adjustments": [],
                      "calculation": {"computed": False, "reason": str(exc)}}
    uncertainty = [rights_rule, service_rule, rookie_rule,
                   "rounding uses half-up dollars because public league rounding practice is not pinned",
                   "qualifying-offer, maximum qualifying-offer and first-refusal exercise-notice amounts unavailable; RFA comparison uses the normal hold only",
                   "unsigned first-round draft-rights holds are not included in veteran free-agent rows"]
    if years is not None and int(years or 0) < 3 and restricted:
        uncertainty.append("restricted-free-agent status comes only from FA_TYPE; QO state is unverified")
    dependency = _dependency(row.get("FA_TYPE"))
    provenance_class = ("uncomputed_unknown_inputs" if result.get("amount") is None
                        else "warehouse_inferred_approximate")
    legacy = int(row.get("CAP_HOLD_EST") or 0)
    return {
        **row,
        "player": row.get("PLAYER_NAME"),
        "team": row.get("TEAM"),
        "fa_type": row.get("FA_TYPE"),
        "prior_salary": prior_salary,
        "cap_hold": result.get("amount"),
        "cap_hold_est": result.get("amount"),
        "legacy_cap_hold_est": legacy,
        "money_unit": _MONEY_UNIT,
        "scenario_dependency": dependency,
        "active_in_baseline": dependency == "active_expired_contract",
        "rights_classification": rights,
        "rookie_scale_status": rookie_status,
        "years_of_service": years,
        "hold_rule": result.get("hold_rule"),
        "hold_basis": result.get("hold_basis"),
        "hold_exactness": result.get("hold_exactness"),
        "provenance_class": provenance_class,
        "input_exactness": result.get("input_exactness") or {},
        "input_provenance": result.get("input_provenance") or {},
        "integer_rounding": result.get("integer_rounding"),
        "adjustments": result.get("adjustments") or [],
        "calculation": result.get("calculation") or {},
        "uncertainty": uncertainty,
        "derivation_status": "calculator_derived",
    }


def _pin_table() -> dict[str, str]:
    return {
        "free_agent_seed": "silver_free_agents(PLAYER_NAME, TEAM, BREF_SLUG, FA_YEAR, FA_TYPE, PRIOR_SALARY, CAP_HOLD_EST)",
        "salary_schedule_join": "silver_salaries(BREF_SLUG, TEAM, PLAYER_ID, SALARY_2027_28, OPTION_2027_28)",
        "rights_inference": "silver_transactions(player_id, txn_date, txn_type, team_id, detail)",
        "rookie_scale_inference": "silver_hist_draft(PERSON_ID, DRAFT_YEAR, ROUND_NUMBER) plus silver_cap_players(player, contract_type) and silver_salaries option columns",
        "years_of_service": "silver_hist_player_seasons(player_id, season) plus silver_player_season(PLAYER_ID, _season)",
        "target_cap": "silver_cap_room(CAP_SEASON, PROJECTED_CAP)",
        "two_way_evidence": "silver_free_agents.FA_TYPE plus silver_contracts.TWO_WAY where available",
    }


def derive_cap_holds(con, fa_year: object, team: str = "") -> dict[str, Any]:
    year = _fa_year(fa_year)
    if year is None:
        return {"rows": [], "total": 0, "active_total": 0, "unknown_count": 0,
                "meta": {"error": "invalid fa_year"}}
    cap_season = _cap_season(year)
    tables = _tables(con)
    params: list[Any] = [year]
    where = "WHERE FA_YEAR = ?"
    if team:
        where += " AND UPPER(TEAM) = UPPER(?)"
        params.append(team)
    try:
        available = _columns(con, "silver_free_agents")
        wanted = ["PLAYER_NAME", "TEAM", "BREF_SLUG", "FA_YEAR", "FA_TYPE",
                  "PRIOR_SALARY", "CAP_HOLD_EST", "CAP_HOLD", "CAP_HOLD_EXACTNESS",
                  "CAP_HOLD_RULE", "_source", "_season", "_fetched_at"]
        pick = [c for c in wanted if c in available]
        rows = [dict(zip(pick, r))
                for r in con.execute(
                    "SELECT " + ", ".join(chr(34) + c + chr(34) for c in pick) +
                    " FROM silver_free_agents " + where +
                    " ORDER BY TEAM, PRIOR_SALARY DESC", params).fetchall()]
    except Exception as exc:
        return {"rows": [], "total": 0, "active_total": 0, "unknown_count": 0,
                "meta": {"error": str(exc)[:200]}}
    required = {"silver_salaries", "silver_cap_room"}
    target_cap = _target_cap(con, tables, cap_season)
    if not required.issubset(tables) or target_cap is None:
        reason = ("required supporting tables missing" if not required.issubset(tables)
                  else f"silver_cap_room.PROJECTED_CAP absent for {cap_season}")
        legacy = [_legacy_row(row, reason) for row in rows]
        return _result(legacy, cap_season, "legacy_fallback", reason)
    salary_cols = _columns(con, "silver_salaries")
    salary_index = _fetch_salary_index(con, salary_cols)
    draft_index = _fetch_draft(con, tables)
    contract_types = _fetch_contract_types(con, tables)
    derived = [_compute_row(con, tables, row, salary_index, draft_index,
                            contract_types, year, cap_season, target_cap)
               for row in rows]
    divergent = [r["player"] for r, row in zip(derived, rows)
                 if row.get("CAP_HOLD") is not None
                 and r.get("cap_hold") is not None
                 and int(row["CAP_HOLD"]) != int(r["cap_hold"])]
    result = _result(derived, cap_season, "calculator_derived", "", target_cap)
    if divergent:
        result["meta"]["seeded_divergence"] = {
            "count": len(divergent),
            "players": divergent[:10],
            "meaning": "consumer-time derivation disagrees with seeder-written CAP_HOLD; "
                       "freshly-derived values win — the warehouse seed predates input changes",
        }
    return result


def _cap_projection_meta(cap_season: str, target_cap: int | None) -> dict[str, Any]:
    if target_cap is None:
        return {}
    derivation = "silver_cap_room seed projection marked ESTIMATED; exact dollar value is used"
    if cap_season == "2027-28" and target_cap == 181_457_100:
        derivation = ("seed_free_agents derives the exact projection as official 2026-27 cap "
                      "164,961,000 × 1.10 = 181,457,100; rounded references to 181.5M are display rounding, "
                      "and the projection is estimated rather than league-official")
    elif cap_season == "2027-28" and target_cap == 181_500_000:
        derivation = ("warehouse seed uses rounded projection 181,500,000; the exact 10% growth derivation "
                      "from official 2026-27 cap 164,961,000 is 181,457,100, a 42,900 difference; "
                      "the exact stored row value is used")
    return {"cap_season": cap_season, "projected_cap": target_cap,
            "money_unit": _MONEY_UNIT, "exactness": EXACTNESS_ESTIMATED,
            "derivation": derivation}


def _result(rows: list[dict[str, Any]], cap_season: str, status: str,
            note: str, target_cap: int | None = None) -> dict[str, Any]:
    amounts = [int(r["cap_hold"]) for r in rows if r.get("cap_hold") is not None]
    active_amounts = [int(r["cap_hold"]) for r in rows
                      if r.get("cap_hold") is not None and r.get("active_in_baseline")]
    unknown = sum(1 for r in rows if r.get("cap_hold") is None)
    return {
        "rows": rows,
        "total": sum(amounts),
        "active_total": sum(active_amounts),
        "unknown_count": unknown,
        "money_unit": _MONEY_UNIT,
        "meta": {
            "derivation_status": status,
            "cap_season": cap_season,
            "money_unit": _MONEY_UNIT,
            "cap_hold_contract": CAP_HOLD_CONTRACT,
            "cap_projection": _cap_projection_meta(cap_season, target_cap),
            "derivation_source_pin": _pin_table(),
            "uncertainty_rules": {
                "warehouse_facts": "warehouse-derived inputs are marked estimated and carry table/column provenance",
                "inference": "rights, rookie-scale status, service time, ordinary max tier and two-way/RFA state are approximate inferences; each row discloses its inference rule",
                "unknowns": "rights-unknown and missing essential-service rows are not guessed; cap_hold is null and those rows are excluded from totals",
                "option_players": "player/team-option rows are option-dependent potential holds, excluded from active baseline totals until an explicit option decline",
                "excluded": "unsigned first-round draft-rights holds and RFA qualifying-offer comparison amounts are not fabricated",
            },
            "derivation_note": note,
        },
    }


def hold_amount(row: dict[str, Any]) -> int:
    value = row.get("cap_hold")
    return int(value) if value is not None else 0
