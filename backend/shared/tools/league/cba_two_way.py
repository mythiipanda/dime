import re

from ...contracts import canonical_team_abbr, normalize_name
from ...possessions import TEAM_NICKNAMES
from ..competitive import _resolve_team_abbr


def _identity_keys(name: object, player_id: object = None) -> list[tuple[str, object]]:
    keys: list[tuple[str, object]] = []
    try:
        if player_id is not None:
            keys.append(("id", int(player_id)))
    except (TypeError, ValueError):
        pass
    normalized = normalize_name(str(name or "").replace("-", " "))
    if normalized:
        keys.append(("name", normalized))
    return keys


def _contract_state(index: dict, name: object, player_id: object = None) -> dict:
    keys = _identity_keys(name, player_id)
    found = next((index[key] for key in keys if key in index), None)
    if found is None:
        found = {"active_team": "", "active_date": "", "evidence": "", "waives": []}
    for key in keys:
        index[key] = found
    return found


def two_way_state_for_record(index: dict, name: object, player_id: object = None) -> dict | None:
    for key in _identity_keys(name, player_id):
        if key in index:
            return index[key]
    return None


def _transaction_team_abbr(value: object) -> str:
    text = str(value or "").strip().lower()
    resolved = _resolve_team_abbr(text)
    if not resolved:
        resolved = TEAM_NICKNAMES.get(text) or TEAM_NICKNAMES.get(text.replace("-", " "))
    return canonical_team_abbr(resolved or value)


def _seed_contract_two_way_states(index: dict, con: object, season: str | None,
                                  tables: set[str]) -> None:
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
        state = _contract_state(index, row.get("PLAYER_NAME"), row.get("PLAYER_ID"))
        if not state["active_team"]:
            state["active_team"] = canonical_team_abbr(row.get("TEAM"))
            state["evidence"] = "silver_contracts.TWO_WAY"


def _transaction_two_way_rows(con: object, season: str | None,
                              tables: set[str]) -> list[dict]:
    if "silver_transactions" not in tables:
        return []
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(silver_transactions)").fetchall()]
        if not {"txn_date", "txn_type", "player", "team", "detail"} <= set(cols):
            return []
        where = " WHERE _season = ?" if season and "_season" in cols else ""
        params = [season] if where else []
        rows = [dict(zip(cols, values, strict=False))
                for values in con.execute("SELECT * FROM silver_transactions" + where, params).fetchall()]
    except Exception:
        return []
    return sorted(rows, key=lambda row: str(row.get("txn_date") or ""))


def _apply_contract_transaction(state: dict, row: dict) -> None:
    team = _transaction_team_abbr(row.get("team"))
    txn_type = str(row.get("txn_type") or "").lower()
    detail = str(row.get("detail") or "").lower()
    date = str(row.get("txn_date") or "")
    if txn_type == "waive":
        state["waives"].append({"team": team, "date": date})
        if state["active_team"] == team:
            state["active_team"] = ""
            state["active_date"] = ""
        return
    if "to a two-way contract" in detail:
        state["active_team"] = team
        state["active_date"] = date
        state["evidence"] = str(row.get("detail") or "")
        return
    if txn_type == "contractconverted" and "to an nba contract" in detail:
        state["active_team"] = ""
        state["active_date"] = ""
        return
    if txn_type == "signing" and "two-way" not in detail:
        state["active_team"] = ""
        state["active_date"] = ""


def two_way_states(con: object, season: str | None, tables: set[str]) -> dict:
    index: dict = {}
    _seed_contract_two_way_states(index, con, season, tables)
    for row in _transaction_two_way_rows(con, season, tables):
        state = _contract_state(index, row.get("player"), row.get("player_id"))
        _apply_contract_transaction(state, row)
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


def _waived_before_two_way(state: dict, row_team: str) -> bool:
    active_date = str(state.get("active_date") or "")
    if not active_date:
        return False
    return any(w.get("team") == row_team and str(w.get("date") or "") <= active_date
               for w in state.get("waives") or [])


def _inferred_dead_amount(row: dict, state: dict | None, row_team: str,
                          season: str | None) -> int | None:
    if not state or not state.get("active_team") or state["active_team"] == row_team:
        return None
    if not _waived_before_two_way(state, row_team):
        return None
    return _deterministic_dead_amount(row, season)


def explicit_two_way_record(row: dict) -> bool:
    row_kind = str(row.get("ROW_KIND") or "").lower().replace("-", "_")
    contract_type = str(row.get("CONTRACT_TYPE") or "").lower().replace("-", "_")
    return row_kind == "two_way" or contract_type == "two_way"


def inferred_dead_entry(row: dict, state: dict | None, row_team: str,
                        season: str | None) -> dict | None:
    amount = _inferred_dead_amount(row, state, row_team, season)
    if amount is None:
        return None
    return {"player": row.get('PLAYER_NAME'), "salary": amount, "team": row_team,
            "basis": "waived_standard_contract_before_two_way"}
