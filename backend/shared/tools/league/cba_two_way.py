import re
from datetime import date as calendar_date

from ...contracts import canonical_team_abbr, normalize_name
from ...possessions import TEAM_NICKNAMES
from ..competitive import _resolve_team_abbr


_STATE_ENTRIES_KEY = ("meta", "states")


def _player_id_value(player_id: object) -> int | None:
    try:
        return int(player_id) if player_id is not None else None
    except (TypeError, ValueError):
        return None


def _identity_name(name: object) -> str:
    return normalize_name(str(name or "").replace("-", " "))


def _identity_keys(name: object, player_id: object = None) -> list[tuple[str, object]]:
    keys: list[tuple[str, object]] = []
    pid = _player_id_value(player_id)
    if pid is not None:
        keys.append(("id", pid))
    normalized = _identity_name(name)
    if normalized:
        keys.append(("name", normalized))
    return keys


def _empty_contract_state() -> dict:
    return {"active_team": "", "active_date": "", "active_season": "",
            "evidence": "", "waives": [], "terminations": [],
            "standard_team": "", "standard_date": "", "two_way_end": None,
            "standard_signings": [], "resurrections": []}


def _state_entries(index: dict) -> list[dict]:
    return index.setdefault(_STATE_ENTRIES_KEY, [])


def _new_state_entry() -> dict:
    return {"state": _empty_contract_state(), "ids": set(), "names": set()}


def _contract_state(index: dict, name: object, player_id: object = None) -> dict:
    entries = _state_entries(index)
    pid = _player_id_value(player_id)
    normalized = _identity_name(name)
    candidates = []
    if pid is not None:
        candidates = [entry for entry in entries if pid in entry["ids"]]
    if not candidates and normalized:
        candidates = [entry for entry in entries
                      if normalized in entry["names"]
                      and (pid is None or not entry["ids"])]
    if candidates:
        entry = candidates[0]
    else:
        entry = _new_state_entry()
        entries.append(entry)
    if pid is not None:
        entry["ids"].add(pid)
    if normalized:
        entry["names"].add(normalized)
    state = entry["state"]
    for key in _identity_keys(name, player_id):
        index.setdefault(key, state)
    return state


def two_way_state_for_record(index: dict, name: object, player_id: object = None) -> dict | None:
    entries = index.get(_STATE_ENTRIES_KEY) or []
    pid = _player_id_value(player_id)
    normalized = _identity_name(name)
    if entries:
        candidates = []
        if pid is not None:
            candidates = [entry for entry in entries if pid in entry["ids"]]
            if not candidates and normalized:
                candidates = [entry for entry in entries
                              if normalized in entry["names"] and not entry["ids"]]
        elif normalized:
            candidates = [entry for entry in entries if normalized in entry["names"]]
        if candidates:
            return candidates[0]["state"]
        return None
    for key in _identity_keys(name, player_id):
        if key in index:
            return index[key]
    return None


def _transaction_identity_matches(row: dict, name: object, player_id: object) -> bool:
    row_id = _player_id_value(row.get("player_id"))
    salary_id = _player_id_value(player_id)
    if row_id is not None and salary_id is not None:
        return row_id == salary_id
    row_name = _identity_name(row.get("player"))
    salary_name = _identity_name(name)
    return bool(row_name and salary_name and row_name == salary_name)


def _transaction_team_abbr(value: object) -> str:
    text = str(value or "").strip().lower()
    resolved = _resolve_team_abbr(text)
    if not resolved:
        resolved = TEAM_NICKNAMES.get(text) or TEAM_NICKNAMES.get(text.replace("-", " "))
    return canonical_team_abbr(resolved or value)


def _seed_contract_two_way_states(index: dict, con: object, season: str | None,
                                  tables: set[str],
                                  transaction_rows: list[dict] | None = None) -> None:
    if "silver_contracts" not in tables:
        return
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(silver_contracts)").fetchall()]
        if not {"PLAYER_NAME", "TEAM", "TWO_WAY"} <= set(cols):
            return
        where = " WHERE _season = ?" if season and "_season" in cols else ""
        params = [season] if where else []
        rows = [dict(zip(cols, values, strict=False))
                for values in con.execute("SELECT * FROM silver_contracts" + where, params).fetchall()]
    except Exception:
        return
    for row in rows:
        if not row.get("TWO_WAY") or row.get("TERMINATED"):
            continue
        if transaction_rows and any(
                _transaction_identity_matches(transaction, row.get("PLAYER_NAME"), row.get("PLAYER_ID"))
                for transaction in transaction_rows):
            continue
        state = _contract_state(index, row.get("PLAYER_NAME"), row.get("PLAYER_ID"))
        if not state["active_team"]:
            state["active_team"] = canonical_team_abbr(row.get("TEAM"))
            state["active_season"] = str(row.get("_season") or season or "")
            state["evidence"] = "silver_contracts.TWO_WAY"


def league_year_for_date(value: object) -> str | None:
    text = str(value or "")[:10]
    try:
        parsed = calendar_date.fromisoformat(text)
    except ValueError:
        return None
    start = parsed.year if parsed.month >= 7 else parsed.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _season_start_year(season: object) -> int | None:
    match = re.fullmatch(r"(\d{4})-\d{2}", str(season or ""))
    return int(match.group(1)) if match else None


def _evidence_league_years(season: str | None) -> set[str] | None:
    start_year = _season_start_year(season)
    if start_year is None:
        return None
    return {f"{year}-{str(year + 1)[-2:]}"
            for year in range(start_year - 2, start_year + 1)}


def active_two_way_for_season(state: dict | None, season: str | None) -> bool | None:
    if not state or not state.get("active_team"):
        return False
    formation_year = league_year_for_date(state.get("active_date"))
    formation_start = _season_start_year(formation_year)
    target_start = _season_start_year(season)
    if formation_start is None or target_start is None:
        if state.get("active_season") and str(state.get("active_season")) == str(season or ""):
            return True
        return None
    return 0 <= target_start - formation_start <= 1


def _first_present(row: dict, *names: str) -> object:
    for name in names:
        if name in row:
            return row.get(name)
    return None


def _group_order(value: object) -> tuple[int, int, str]:
    text = str(value or "").strip()
    match = re.search(r"(\d+)\s*$", text)
    if not match:
        return (1, 0, text)
    return (0, int(match.group(1)), text)


def _numeric_order(value: object) -> tuple[int, float]:
    try:
        if value is None or str(value).strip() == "":
            return (1, 0.0)
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, 0.0)


def _transaction_sort_key(row: dict) -> tuple:
    group = _first_present(row, "group_sort", "GroupSort")
    additional = _first_present(row, "additional_sort", "Additional_Sort")
    txn_type = str(row.get("txn_type") or "").lower()
    waiver_claim = txn_type in {"awardonwaivers", "awardedonwaivers"}
    date = str(row.get("txn_date") or "")
    date_order = date if league_year_for_date(date) is not None else "9999-99-99"
    return (date_order,
            _group_order(group),
            _numeric_order(additional),
            1 if waiver_claim else 0,
            txn_type,
            _transaction_team_abbr(row.get("team")),
            str(row.get("player") or "").lower(),
            str(row.get("detail") or "").lower())


def _all_transaction_rows(con: object, tables: set[str]) -> list[dict]:
    if "silver_transactions" not in tables:
        return []
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(silver_transactions)").fetchall()]
        if not {"txn_date", "txn_type", "player", "team", "detail"} <= set(cols):
            return []
        return [dict(zip(cols, values, strict=False))
                for values in con.execute("SELECT * FROM silver_transactions").fetchall()]
    except Exception:
        return []


def _contract_state_transaction(row: dict) -> bool:
    txn_type = str(row.get("txn_type") or "").lower()
    if txn_type in {"signing", "waive", "trade", "contractconverted",
                    "awardonwaivers", "awardedonwaivers"}:
        return True
    return "two-way contract" in str(row.get("detail") or "").lower()


def _transaction_two_way_rows(rows: list[dict], season: str | None) -> list[dict]:
    evidence_years = _evidence_league_years(season)
    if evidence_years is not None:
        rows = [row for row in rows
                if league_year_for_date(row.get("txn_date")) in evidence_years
                or (league_year_for_date(row.get("txn_date")) is None
                    and _contract_state_transaction(row))]
    return sorted(rows, key=_transaction_sort_key)


def _link_terminations(state: dict, formation_team: str, formation_date: str) -> None:
    latest: dict[str, dict] = {}
    for waive in state.get("waives") or []:
        if waive.get("claimed") or waive.get("contract_kind") not in {"", "standard"}:
            continue
        waive_date = str(waive.get("date") or "")
        if formation_date and waive_date and waive_date > formation_date:
            continue
        team = canonical_team_abbr(waive.get("team"))
        if team and (team not in latest or waive_date >= str(latest[team].get("date") or "")):
            latest[team] = waive
    for waive in latest.values():
        team = canonical_team_abbr(waive.get("team"))
        date = str(waive.get("date") or "")
        exists = any(item.get("team") == team and item.get("waive_date") == date
                     for item in state.get("terminations") or [])
        if not exists:
            state["terminations"].append({
                "team": team, "waive_date": date,
                "formation_team": formation_team, "formation_date": formation_date})


def _latest_unclaimed_waive(state: dict, date: str) -> dict | None:
    for waive in reversed(state.get("waives") or []):
        waive_date = str(waive.get("date") or "")
        if not waive.get("claimed") and (not date or not waive_date or waive_date <= date):
            return waive
    return None


def _record_standard_start(state: dict, team: str, date: str) -> None:
    state.setdefault("standard_signings", []).append(
        {"team": canonical_team_abbr(team), "date": str(date or "")})


def _orderable_event_date(value: object) -> bool:
    return league_year_for_date(value) is not None


def _finalize_resurrections(state: dict) -> None:
    state["resurrections"] = []
    used_waives: set[int] = set()
    signings = sorted(state.get("standard_signings") or [],
                      key=lambda item: str(item.get("date") or ""))
    for signing in signings:
        team = canonical_team_abbr(signing.get("team"))
        resign_date = str(signing.get("date") or "")[:10]
        if not team or not _orderable_event_date(resign_date):
            continue
        candidates = []
        for index, waive in enumerate(state.get("waives") or []):
            if index in used_waives or waive.get("claimed"):
                continue
            if waive.get("contract_kind") not in {"", "standard"}:
                continue
            if canonical_team_abbr(waive.get("team")) != team:
                continue
            waive_date = str(waive.get("date") or "")[:10]
            if (not _orderable_event_date(waive_date)
                    or not _orderable_event_date(resign_date)
                    or waive_date >= resign_date):
                continue
            candidates.append((waive_date, index, waive))
        if not candidates:
            continue
        waive_date, index, waive = max(candidates, key=lambda item: (item[0], item[1]))
        used_waives.add(index)
        waive["resurrected_by"] = resign_date
        state["resurrections"].append({
            "team": team,
            "waive_date": waive_date,
            "resign_date": resign_date,
            "contract_kind": str(waive.get("contract_kind") or "unknown"),
            "formation_date": str(waive.get("formation_date") or ""),
        })


def _apply_contract_transaction(state: dict, row: dict) -> None:
    team = _transaction_team_abbr(row.get("team"))
    txn_type = str(row.get("txn_type") or "").lower()
    detail = str(row.get("detail") or "").lower()
    date = str(row.get("txn_date") or "")[:10]
    if txn_type == "waive":
        contract_kind = ""
        formation_date = ""
        if state["active_team"] == team:
            contract_kind = "two_way"
            formation_date = str(state.get("active_date") or "")
        elif state["standard_team"] == team:
            contract_kind = "standard"
        state["waives"].append({"team": team, "date": date,
                                "contract_kind": contract_kind,
                                "formation_date": formation_date})
        if contract_kind == "two_way":
            state["active_team"] = ""
            state["active_date"] = ""
            state["two_way_end"] = {"kind": "waive", "team": team, "date": date,
                                    "formation_date": formation_date}
        if contract_kind == "standard":
            state["standard_team"] = ""
            state["standard_date"] = ""
        return
    if txn_type == "trade":
        if state["active_team"]:
            state["active_team"] = team
        if state["standard_team"]:
            state["standard_team"] = team
        return
    if txn_type in {"awardonwaivers", "awardedonwaivers"}:
        waive = _latest_unclaimed_waive(state, date)
        if waive is None:
            return
        waive["claimed"] = True
        waive_team = canonical_team_abbr(waive.get("team"))
        waive_date = str(waive.get("date") or "")
        state["terminations"] = [item for item in state.get("terminations") or []
                                 if not (canonical_team_abbr(item.get("team")) == waive_team
                                         and str(item.get("waive_date") or "") == waive_date)]
        if waive.get("contract_kind") == "two_way":
            state["active_team"] = team
            state["active_date"] = str(waive.get("formation_date") or "") or date
            state["standard_team"] = ""
            state["standard_date"] = ""
            state["two_way_end"] = None
        elif waive.get("contract_kind") == "standard":
            state["active_team"] = ""
            state["active_date"] = ""
            state["standard_team"] = team
            state["standard_date"] = date
            state["two_way_end"] = None
        return
    if "to a two-way contract" in detail:
        _link_terminations(state, team, date)
        state["active_team"] = team
        state["active_date"] = date
        state["evidence"] = str(row.get("detail") or "")
        state["standard_team"] = ""
        state["standard_date"] = ""
        state["two_way_end"] = None
        return
    if txn_type == "contractconverted" and "to an nba contract" in detail:
        _record_standard_start(state, team, date)
        state["active_team"] = ""
        state["active_date"] = ""
        state["standard_team"] = team
        state["standard_date"] = date
        state["two_way_end"] = None
        return
    if txn_type == "signing" and "two-way" not in detail:
        _record_standard_start(state, team, date)
        state["active_team"] = ""
        state["active_date"] = ""
        state["standard_team"] = team
        state["standard_date"] = date
        state["two_way_end"] = None


def two_way_states(con: object, season: str | None, tables: set[str]) -> dict:
    index: dict = {}
    all_rows = _all_transaction_rows(con, tables)
    _seed_contract_two_way_states(index, con, season, tables, all_rows)
    for row in _transaction_two_way_rows(all_rows, season):
        state = _contract_state(index, row.get("player"), row.get("player_id"))
        _apply_contract_transaction(state, row)
    for entry in index.get(_STATE_ENTRIES_KEY) or []:
        _finalize_resurrections(entry["state"])
    return index


def _salary_column_season(scol: str) -> str | None:
    match = re.fullmatch(r"SALARY_(\d{4})_(\d{2})", scol or "")
    return f"{match.group(1)}-{match.group(2)}" if match else None


def payroll_evidence_season(records: list[dict], scol: str,
                            season: str | None) -> str | None:
    if season:
        return season
    column_season = _salary_column_season(scol)
    if column_season:
        return column_season
    seasons = [str(r.get("_season") or "") for r in records if r.get("_season")]
    return max(seasons) if seasons else None


def _has_positive_future_salary(row: dict, season: str | None) -> bool:
    try:
        current_year = int(str(season or "")[:4])
    except ValueError:
        current_year = 0
    for key, value in row.items():
        match = re.fullmatch(r"SALARY_(\d{4})_\d{2}", str(key))
        if not match or int(match.group(1)) <= current_year:
            continue
        try:
            if value is not None and float(value) > 0:
                return True
        except (TypeError, ValueError):
            pass
    return False


def _deterministic_dead_amount(row: dict, season: str | None) -> int | None:
    try:
        salary = int(row.get("salary") or 0)
        guaranteed = int(row.get("GUARANTEED"))
    except (TypeError, ValueError):
        return None
    if salary <= 0 or guaranteed < salary:
        return None
    if _has_positive_future_salary(row, season):
        return None
    return salary


def terminated_contract_fact(state: dict | None, row_team: str) -> dict | None:
    if not state:
        return None
    team = canonical_team_abbr(row_team)
    facts = [item for item in state.get("terminations") or []
             if canonical_team_abbr(item.get("team")) == team]
    if not facts:
        return None
    return max(facts, key=lambda item: (str(item.get("waive_date") or ""),
                                        str(item.get("formation_date") or "")))


def resurrected_contract_fact(state: dict | None, row_team: str) -> dict | None:
    if not state:
        return None
    team = canonical_team_abbr(row_team)
    facts = [item for item in state.get("resurrections") or []
             if canonical_team_abbr(item.get("team")) == team]
    if not facts:
        return None
    return max(facts, key=lambda item: (str(item.get("waive_date") or ""),
                                        str(item.get("resign_date") or "")))


def _resurrection_matches_termination(fact: dict | None, resurrection: dict | None) -> bool:
    if fact is None or resurrection is None:
        return False
    return (canonical_team_abbr(fact.get("team")) == canonical_team_abbr(resurrection.get("team"))
            and str(fact.get("waive_date") or "") == str(resurrection.get("waive_date") or ""))


def _dead_fact_for_inference(state: dict | None, row_team: str) -> dict | None:
    fact = terminated_contract_fact(state, row_team)
    if fact is None:
        return None
    if canonical_team_abbr(row_team) == canonical_team_abbr(fact.get("formation_team")):
        return None
    return fact


def _dead_amount_unknown(row: dict, season: str | None) -> bool:
    try:
        salary = int(row.get("salary") or 0)
    except (TypeError, ValueError):
        return False
    if salary <= 0:
        return False
    try:
        guaranteed = int(row.get("GUARANTEED"))
    except (TypeError, ValueError):
        return True
    return guaranteed < salary or _has_positive_future_salary(row, season)


def _case_insensitive_value(row: dict, name: str) -> object:
    for key, value in row.items():
        if str(key).lower() == name:
            return value
    return None


def declared_row_kind(row: dict) -> str | None:
    value = str(_case_insensitive_value(row, "row_kind") or "").strip().lower().replace("-", "_")
    return value or None


def explicit_row_kind(row: dict) -> str | None:
    value = declared_row_kind(row)
    return value if value in {"roster", "two_way", "dead_money"} else None


def unknown_row_kind_record(row: dict) -> bool:
    return declared_row_kind(row) == "unknown"


def explicit_resurrected_record(row: dict) -> bool:
    value = _case_insensitive_value(row, "resurrected")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def explicit_two_way_record(row: dict) -> bool:
    row_kind = explicit_row_kind(row)
    if row_kind is not None:
        return row_kind == "two_way"
    contract_type = str(_case_insensitive_value(row, "contract_type") or "").lower().replace("-", "_")
    return contract_type == "two_way"


def explicit_dead_money_record(row: dict) -> bool:
    return explicit_row_kind(row) == "dead_money"


def _attach_dead_player_id(entry: dict | None, row: dict) -> dict | None:
    if entry is not None and row.get("PLAYER_ID") is not None:
        entry["_player_id"] = row.get("PLAYER_ID")
    return entry


def inferred_dead_entry(row: dict, state: dict | None, row_team: str,
                        season: str | None) -> dict | None:
    if _dead_fact_for_inference(state, row_team) is None:
        return None
    amount = _deterministic_dead_amount(row, season)
    entry = None
    if amount is not None:
        entry = {"player": row.get('PLAYER_NAME'), "salary": amount, "team": row_team,
                 "row_kind": "dead_money",
                 "basis": "waived_standard_contract_before_two_way"}
    elif _dead_amount_unknown(row, season):
        entry = {"player": row.get('PLAYER_NAME'), "salary": None, "team": row_team,
                 "row_kind": "dead_money",
                 "basis": "waived_standard_contract_before_two_way_protection_unknown",
                 "amount_unknown": True}
    return _attach_dead_player_id(entry, row)


def resurrected_dead_entry(row: dict, state: dict | None, row_team: str) -> dict | None:
    if resurrected_contract_fact(state, row_team) is None and not explicit_resurrected_record(row):
        return None
    entry = {"player": row.get('PLAYER_NAME'), "salary": None, "team": row_team,
             "row_kind": "dead_money",
             "basis": "waived_standard_contract_before_same_team_resign_protection_unknown",
             "amount_unknown": True}
    return _attach_dead_player_id(entry, row)


def unknown_row_kind_dead_entry(row: dict, row_team: str) -> dict:
    entry = {"player": row.get('PLAYER_NAME'), "salary": None, "team": row_team,
             "row_kind": "dead_money",
             "basis": "row_kind_unknown_protection_unknown",
             "amount_unknown": True}
    return _attach_dead_player_id(entry, row)


def salary_row_cap_status(row: dict, state: dict | None, row_team: str,
                          season: str | None) -> dict:
    explicit = explicit_two_way_record(row)
    explicit_dead = explicit_dead_money_record(row)
    undeclared_unknown = unknown_row_kind_record(row)
    reconstruct = explicit_row_kind(row) is None and not explicit
    active_state = active_two_way_for_season(state, season) if reconstruct else False
    active = active_state is True
    unknown = reconstruct and active_state is None
    termination = terminated_contract_fact(state, row_team)
    resurrection = resurrected_contract_fact(state, row_team)
    termination_overridden = _resurrection_matches_termination(termination, resurrection)
    resurrection_applies = termination_overridden or (termination is None and resurrection is not None)
    resurrected = resurrection_applies or explicit_resurrected_record(row)
    terminated = (reconstruct and termination is not None
                  and not termination_overridden)
    no_standard = reconstruct and bool(state and state.get("two_way_end")
                                       and not state.get("standard_team"))
    counts = not (explicit or explicit_dead or active or terminated or no_standard
                  or undeclared_unknown)
    dead_entry = None
    if not explicit_dead and resurrected:
        dead_entry = resurrected_dead_entry(row, state, row_team)
    elif reconstruct:
        dead_entry = inferred_dead_entry(row, state, row_team, season)
    if dead_entry is None and undeclared_unknown and not active:
        dead_entry = unknown_row_kind_dead_entry(row, row_team)
    return {"explicit_two_way": explicit,
            "explicit_dead_money": explicit_dead,
            "active_two_way": active,
            "two_way_classification_unknown": unknown,
            "terminated_standard": terminated,
            "no_standard_roster": no_standard,
            "resurrected_standard": bool(resurrected),
            "counts_as_standard": counts,
            "dead_entry": dead_entry}


def dead_key(row: dict) -> tuple[str, str, int]:
    try:
        salary = int(row.get("salary") or 0)
    except (TypeError, ValueError):
        salary = 0
    return (str(row.get("player") or "").lower(),
            canonical_team_abbr(row.get("team")), salary)


def _dead_player_id(row: dict) -> int | None:
    value = row.get("_player_id", row.get("PLAYER_ID", row.get("player_id")))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def dead_identity(row: dict) -> dict[str, object]:
    return {"player_id": _dead_player_id(row),
            "name": normalize_name(row.get("player") or ""),
            "team": canonical_team_abbr(row.get("team"))}


def same_dead_identity(left: dict, right: dict) -> bool:
    a = dead_identity(left)
    b = dead_identity(right)
    if a["team"] != b["team"]:
        return False
    if a["player_id"] is not None and b["player_id"] is not None:
        return a["player_id"] == b["player_id"]
    return bool(a["name"] and a["name"] == b["name"])


def _public_dead_row(row: dict) -> dict:
    return {key: value for key, value in row.items() if not str(key).startswith("_")}


def merge_dead_rows(explicit: list[dict], inferred: list[dict],
                    team_code: str) -> list[dict]:
    explicit_rows = list(explicit)
    dead = [_public_dead_row(row) for row in explicit_rows]
    seen = {dead_key(row) for row in explicit_rows}
    for row in inferred:
        key = dead_key(row)
        suppressed = any(same_dead_identity(row, existing) for existing in explicit_rows)
        if (canonical_team_abbr(row.get("team")) == team_code
                and not suppressed and key not in seen):
            dead.append(_public_dead_row(row))
            seen.add(key)
    return dead
