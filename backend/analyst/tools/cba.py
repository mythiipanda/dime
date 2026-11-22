from typing import Any

from langchain_core.tools import tool

from .common import call_sync, finish_dict_list, sanitize_for_wire
from .errors import enrich_error


def _invoke_cap_ledger(orig: Any, team: str, season: str | None) -> dict[str, Any]:
    try:
        fields = getattr(getattr(orig, "args_schema", None), "model_fields", {})
        call_args: dict[str, Any] = {}
        if "team_abbrev" in fields:
            call_args["team_abbrev"] = team
        if "team" in fields or not fields:
            call_args["team"] = team
        if "season" in fields and season is not None:
            call_args["season"] = season
        try:
            res = orig.invoke(call_args)
        except Exception:
            fallback = {"team_abbrev": team} if "team" in call_args else {"team": team}
            res = orig.invoke(fallback)
        if not isinstance(res, dict):
            return {"tool": "get_cap_ledger", "ok": False, "error": str(res)}
        return res
    except Exception as exc:
        return {"tool": "get_cap_ledger", "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _trade_check_rows(raw_rows: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(raw_rows, dict):
        legal_val = raw_rows.get("legal")
        issues_val = raw_rows.get("issues")
        for side_key in ("team_a", "team_b"):
            side_data = raw_rows.get(side_key)
            if isinstance(side_data, dict):
                rows.append({
                    "side": side_key,
                    "team": side_data.get("team", ""),
                    "payroll": side_data.get("payroll"),
                    "outgoing": side_data.get("out") if "out" in side_data else side_data.get("outgoing"),
                    "allowed_incoming": side_data.get("allowed_in") if "allowed_in" in side_data else side_data.get("allowed_incoming"),
                    "match_rule": side_data.get("match_rule"),
                    "outgoing_needed": side_data.get("outgoing_needed"),
                    "legal": legal_val,
                    "issues": issues_val,
                })
    elif isinstance(raw_rows, list):
        rows = [r for r in raw_rows if isinstance(r, dict)]
    return rows


def _player_value_row(side_key: str, side_team: str, p: dict[str, Any]) -> dict[str, Any]:
    sal = p.get("salary_26_27")
    salary_m = round(sal / 1e6, 2) if isinstance(sal, (int, float)) else p.get("salary_m")
    val_m = p.get("est_market_value_m") if "est_market_value_m" in p else p.get("value_m")
    return {
        "side": side_key,
        "player": p.get("name") or p.get("player", ""),
        "team": p.get("team") or side_team,
        "value_m": val_m,
        "salary_m": salary_m,
        "residual_m": p.get("residual_m"),
        **{key: p.get(key) for key in (
            'player_id', 'bref_slug', 'remaining_guaranteed',
            'contract_schedule_available', 'years_remaining', 'salary_by_season',
            'future_salaries', 'option_years', 'years_remaining_basis')},
    }


def _trade_value_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    rows: list[dict[str, Any]] = []
    for side_key in ("team_a", "team_b"):
        side_data = raw_rows.get(side_key)
        if isinstance(side_data, dict) and isinstance(side_data.get("players"), list):
            side_team = side_data.get("team", "")
            for p in side_data["players"]:
                if isinstance(p, dict):
                    rows.append(_player_value_row(side_key, side_team, p))
    if not rows and isinstance(raw_rows.get("verdict"), dict):
        v = raw_rows["verdict"]
        rows.append({
            "side": "verdict",
            "player": v.get("winner", ""),
            "team": "",
            "value_m": v.get("delta_m"),
            "salary_m": None,
            "residual_m": None,
        })
    return rows


def register() -> dict[str, Any]:
    from shared.tools.league import (
        get_cap_ledger as _orig_get_cap_ledger,
        get_cap_scenario as _orig_get_cap_scenario,
        get_cap_table as _orig_get_cap_table,
        get_contract_value as _orig_get_contract_value,
        get_draft_capital as _orig_get_draft_capital,
        get_trade_check as _orig_get_trade_check,
        get_trade_legality as _orig_get_trade_legality,
        get_trade_partners as _orig_get_trade_partners,
        get_trade_value as _orig_get_trade_value,
    )
    try:
        from shared.tools.transactions import get_transactions as _orig_get_transactions
    except ImportError:
        from backend.shared.tools.transactions import get_transactions as _orig_get_transactions

    @tool("get_cap_ledger", description=_orig_get_cap_ledger.description)
    def get_cap_ledger(team: str = "", season: str | None = None) -> dict:
        res = _invoke_cap_ledger(_orig_get_cap_ledger, team, season)
        default_cols = ["team", "total_salary", "cap_space", "tax_room", "first_apron_room", "second_apron_room"]
        raw_rows = res.get("rows")
        if res.get("ok"):
            rows = [raw_rows] if isinstance(raw_rows, dict) else ([r for r in raw_rows if isinstance(r, dict)] if isinstance(raw_rows, list) else [])
        else:
            rows = []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_cap_ledger", res)
        return sanitize_for_wire(res)

    @tool("get_cap_table", description=_orig_get_cap_table.description)
    def get_cap_table(season: str | None = None) -> dict:
        res = call_sync(_orig_get_cap_table, "get_cap_table", {"season": season})
        return finish_dict_list(res, "get_cap_table", ["team", "payroll", "cap_room", "room_under_apron2", "over_tax", "over_apron1", "over_apron2"])

    @tool("get_cap_scenario", description=_orig_get_cap_scenario.description)
    def get_cap_scenario(team: str = "", signings: str = "",
                         in_players: str = "", out_players: str = "",
                         season: str | None = None) -> dict:
        res = call_sync(_orig_get_cap_scenario, "get_cap_scenario", {
            "team": team, "signings": signings, "in_players": in_players,
            "out_players": out_players, "season": season,
        })
        default_cols = ["step", "kind", "detail", "delta", "payroll"]
        rows = [r for r in res.get("rows") or [] if isinstance(r, dict)] if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_cap_scenario", res)
        return sanitize_for_wire(res)

    @tool("get_contract_value", description=_orig_get_contract_value.description)
    def get_contract_value(season: str | None = None, min_gp: int = 20, team: str = "", player: str = "") -> dict:
        res = call_sync(_orig_get_contract_value, "get_contract_value", {
            "season": season, "min_gp": min_gp, "team": team, "player": player,
        })
        return finish_dict_list(res, "get_contract_value", ["player", "team", "salary", "salary_hat", "residual", "gp"])

    @tool("get_trade_check", description=_orig_get_trade_check.description)
    def get_trade_check(team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "", season: str | None = None) -> dict:
        res = call_sync(_orig_get_trade_check, "get_trade_check", {
            "team_a": team_a, "players_a": players_a, "team_b": team_b, "players_b": players_b, "season": season,
        })
        default_cols = ["side", "team", "payroll", "outgoing", "allowed_incoming", "match_rule", "outgoing_needed", "legal", "issues"]
        rows = _trade_check_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_trade_check", res)
        return sanitize_for_wire(res)

    @tool("get_trade_legality", description=_orig_get_trade_legality.description)
    def get_trade_legality(legs: str = "", sign_and_trade: str = "",
                           cash: str = "", tpe: str = "",
                           season: str | None = None) -> dict:
        res = call_sync(_orig_get_trade_legality, "get_trade_legality", {
            "legs": legs, "sign_and_trade": sign_and_trade,
            "cash": cash, "tpe": tpe, "season": season,
        })
        default_cols = ["team", "payroll_before", "payroll_after", "outgoing",
                        "incoming", "allowed_incoming", "match_rule",
                        "matching_ok", "hard_cap", "over_apron2"]
        rows = [r for r in res.get("rows") or [] if isinstance(r, dict)] if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_trade_legality", res)
        return sanitize_for_wire(res)

    @tool("get_trade_partners", description=_orig_get_trade_partners.description)
    def get_trade_partners(player: str = "", season: str | None = None, teams: str = "", max_packages: int = 3) -> dict:
        res = call_sync(_orig_get_trade_partners, "get_trade_partners", {
            "player": player, "season": season, "teams": teams, "max_packages": max_packages,
        })
        default_cols = ["team", "players", "package_salary", "incoming", "match_rule", "over_apron1", "over_apron2", "legal"]
        rows = list(res.get("rows") or []) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_trade_partners", res)
        return sanitize_for_wire(res)

    @tool("get_trade_value", description=_orig_get_trade_value.description)
    def get_trade_value(team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "", picks_a: str = "", picks_b: str = "") -> dict:
        res = call_sync(_orig_get_trade_value, "get_trade_value", {
            "team_a": team_a, "players_a": players_a, "team_b": team_b,
            "players_b": players_b, "picks_a": picks_a, "picks_b": picks_b,
        })
        default_cols = ["side", "player", "team", "value_m", "salary_m", "residual_m"]
        rows = _trade_value_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_trade_value", res)
        return sanitize_for_wire(res)

    @tool("get_draft_capital", description=_orig_get_draft_capital.description)
    def get_draft_capital(team: str = "", draft_year: str = "") -> dict:
        res = call_sync(_orig_get_draft_capital, "get_draft_capital", {
            "team": team, "draft_year": draft_year,
        })
        return finish_dict_list(res, "get_draft_capital", ["draft_year", "round", "orig_team", "status", "held_by", "direction", "est_slot", "est_value_m"])

    @tool("get_transactions", description=_orig_get_transactions.description)
    def get_transactions(team: str = "", start: str = "", end: str = "", txn_type: str = "") -> dict:
        cols = ["txn_date", "txn_type", "player", "team", "detail"]
        try:
            res = _orig_get_transactions.invoke({"team": team, "start": start, "end": end, "txn_type": txn_type})
            if not isinstance(res, dict) or not res.get("ok"):
                err = res.get("error") if isinstance(res, dict) else res
                return sanitize_for_wire(enrich_error("get_transactions", {
                    "ok": False, "tool": "get_transactions", "rows": [],
                    "columns": cols, "error": str(err or "Transactions lookup failed"),
                }))
        except Exception as exc:
            return sanitize_for_wire(enrich_error("get_transactions", {
                "tool": "get_transactions", "ok": False, "error": str(exc),
                "rows": [], "columns": [],
            }))
        raw_rows = res.get("rows")
        rows = [r for r in raw_rows if isinstance(r, dict)] if isinstance(raw_rows, list) else ([raw_rows] if isinstance(raw_rows, dict) else [])
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = True
        return sanitize_for_wire(res)

    return {
        "get_cap_ledger": get_cap_ledger,
        "get_cap_scenario": get_cap_scenario,
        "get_cap_table": get_cap_table,
        "get_contract_value": get_contract_value,
        "get_draft_capital": get_draft_capital,
        "get_trade_check": get_trade_check,
        "get_trade_legality": get_trade_legality,
        "get_trade_partners": get_trade_partners,
        "get_trade_value": get_trade_value,
        "get_transactions": get_transactions,
    }
