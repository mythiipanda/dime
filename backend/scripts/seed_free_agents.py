import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult
from shared.sources.salaries import get_contracts

FA_SEASON = "2026-27"
CAP_SEASON = "2027-28"
FA_YEAR = 2027

CAP_2026_27 = {"cap": 164_961_000, "tax": 200_428_000,
               "apron1": 209_015_000, "apron2": 221_686_000}
CAP_GROWTH = 1.10
EXCEPTIONS_2026_27 = {"ntmle": 15_044_000, "tmle": 6_064_000,
                      "room": 9_366_000, "bae": 5_477_000}
ROOKIE_MINIMUM_2026_27 = 1_357_763
MIN_SALARY = round(ROOKIE_MINIMUM_2026_27 * CAP_GROWTH)
ROSTER_SPOTS = 12

FA_COLS = ["PLAYER_NAME", "TEAM", "BREF_SLUG", "FA_YEAR", "FA_TYPE",
           "PRIOR_SALARY", "CAP_HOLD_EST"]
ROOM_COLS = ["TEAM", "CAP_SEASON", "COMMITTED_SALARY",
             "PENDING_OPTION_SALARY", "FA_HOLDS_EST",
             "INCOMPLETE_ROSTER_CHARGES", "ROSTER_CHARGE_MINIMUM",
             "PROJECTED_ROOM", "MAX_ROOM",
             "PROJECTED_CAP", "PROJECTED_TAX", "PROJECTED_APRON1",
             "PROJECTED_APRON2", "NTMLE_EST", "BAE_EST", "ROOM_EST",
             "TMLE_EST", "PLAYERS_UNDER_CONTRACT", "PENDING_OPTIONS",
             "ESTIMATED"]

_OPTION_TO_FA = {"player": "player_option", "team": "team_option",
                 "early-termination": "early_termination"}
BIRD_HOLD_PCT = 1.5


def resolve_target(raw_db: str | None) -> Path | None:
    raw = raw_db or os.environ.get("DIME_WAREHOUSE", "")
    if not raw:
        print("refusing: DIME_WAREHOUSE is not set")
        return None
    target = Path(raw).expanduser().resolve()
    print(f"target: {target}")
    if target == store.CANONICAL_DB_PATH:
        print("refusing: target is the canonical warehouse")
        return None
    return target


def _season_cols(frame: pl.DataFrame) -> list[str]:
    return sorted(c[7:] for c in frame.columns
                  if c.startswith("SALARY_"))


def _salary(frame_row: dict, season_key: str) -> int | None:
    return frame_row.get("SALARY_" + season_key)


def _option(frame_row: dict, season_key: str) -> str | None:
    return frame_row.get("OPTION_" + season_key)


def _contract_flags() -> dict[str, dict]:
    flags: dict[str, dict] = {}
    try:
        with store.connect(read_only=True) as con:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if "silver_contracts" not in tables:
                return flags
            for name, qo, tw in con.execute(
                    "SELECT PLAYER_NAME, QUALIFYING_OFFER, TWO_WAY"
                    " FROM silver_contracts WHERE _season = ?",
                    [FA_SEASON]).fetchall():
                flags[str(name).lower()] = {"qo": bool(qo), "tw": bool(tw)}
    except Exception:
        pass
    return flags


def build_frames(frame: pl.DataFrame, fa_season_key: str,
                 cap_season_key: str,
                 contract_flags: dict[str, dict] | None = None
                 ) -> tuple[pl.DataFrame, pl.DataFrame]:
    contract_flags = contract_flags or {}
    fa_rows: list[dict] = []
    room: dict[str, dict] = {}
    for row in frame.to_dicts():
        team = str(row.get("TEAM") or "")
        entry = room.setdefault(team, {
            "committed": 0, "option_salary": 0, "holds": 0,
            "under_contract": 0, "options": 0, "hold_count": 0})
        prior = _salary(row, fa_season_key)
        nxt = _salary(row, cap_season_key)
        opt = _option(row, cap_season_key)
        if nxt is not None:
            if opt:
                entry["option_salary"] += nxt
                entry["options"] += 1
            else:
                entry["committed"] += nxt
            entry["under_contract"] += 1
        if prior is not None and (nxt is None or opt):
            fa_type = _OPTION_TO_FA.get(opt, "ufa") if nxt is None or opt \
                else "ufa"
            flags = contract_flags.get(
                str(row["PLAYER_NAME"]).lower(), {})
            if flags.get("tw"):
                fa_type = "two_way"
            elif flags.get("qo") and fa_type in ("ufa", "team_option"):
                fa_type = "rfa"
            hold = int(prior * BIRD_HOLD_PCT)
            fa_rows.append({
                "PLAYER_NAME": row["PLAYER_NAME"], "TEAM": team,
                "BREF_SLUG": row.get("BREF_SLUG"), "FA_YEAR": FA_YEAR,
                "FA_TYPE": fa_type, "PRIOR_SALARY": prior,
                "CAP_HOLD_EST": hold})
            entry["holds"] += hold
            if hold > 0:
                entry["hold_count"] += 1
    room_rows = []
    cap = int(CAP_2026_27["cap"] * CAP_GROWTH)
    for team, e in sorted(room.items()):
        open_exercised = max(0, ROSTER_SPOTS - e["under_contract"]
                             - e["hold_count"])
        open_declined = max(0, ROSTER_SPOTS
                          - (e["under_contract"] - e["options"]))
        roster_charges = open_exercised * MIN_SALARY
        declined_charges = open_declined * MIN_SALARY
        room_rows.append({
            "TEAM": team, "CAP_SEASON": CAP_SEASON,
            "COMMITTED_SALARY": e["committed"],
            "PENDING_OPTION_SALARY": e["option_salary"],
            "FA_HOLDS_EST": e["holds"],
            "INCOMPLETE_ROSTER_CHARGES": roster_charges,
            "ROSTER_CHARGE_MINIMUM": MIN_SALARY,
            "PROJECTED_ROOM": cap - e["committed"] - e["option_salary"]
            - roster_charges,
            "MAX_ROOM": cap - e["committed"] - declined_charges,
            "PROJECTED_CAP": cap,
            "PROJECTED_TAX": int(CAP_2026_27["tax"] * CAP_GROWTH),
            "PROJECTED_APRON1": int(CAP_2026_27["apron1"] * CAP_GROWTH),
            "PROJECTED_APRON2": int(CAP_2026_27["apron2"] * CAP_GROWTH),
            "NTMLE_EST": int(EXCEPTIONS_2026_27["ntmle"] * CAP_GROWTH),
            "BAE_EST": int(EXCEPTIONS_2026_27["bae"] * CAP_GROWTH),
            "ROOM_EST": int(EXCEPTIONS_2026_27["room"] * CAP_GROWTH),
            "TMLE_EST": int(EXCEPTIONS_2026_27["tmle"] * CAP_GROWTH),
            "PLAYERS_UNDER_CONTRACT": e["under_contract"],
            "PENDING_OPTIONS": e["options"], "ESTIMATED": True})
    return (pl.DataFrame(fa_rows) if fa_rows
            else pl.DataFrame(schema={c: pl.String for c in FA_COLS}),
            pl.DataFrame(room_rows) if room_rows
            else pl.DataFrame(schema={c: pl.String for c in ROOM_COLS}))


def load(dry_run: bool) -> int:
    res = get_contracts()
    if not res.ok or res.frame.height == 0:
        print(f"bref contracts: FAILED {res.error}")
        return 0
    season_cols = _season_cols(res.frame)
    if len(season_cols) < 2:
        print(f"abort: expected >=2 season cols, got {season_cols}")
        return 0
    fa_key = season_cols[0]
    cap_key = season_cols[1]
    fa_frame, room_frame = build_frames(res.frame, fa_key, cap_key,
                                        _contract_flags())
    if dry_run:
        print(f"silver_free_agents ({fa_key}→{cap_key}): "
              f"{fa_frame.height} rows (dry-run)")
        print(f"silver_cap_room: {room_frame.height} rows (dry-run)")
        return 0
    fa_res = FetchResult(frame=fa_frame,
                         meta=FetchMeta(source="derived:bref_contracts",
                                        season=FA_SEASON))
    n_fa = store.save_frame("silver_free_agents", fa_res, entity="league")
    room_res = FetchResult(frame=room_frame,
                           meta=FetchMeta(source="derived:bref_contracts",
                                          season=FA_SEASON))
    n_room = store.save_frame("silver_cap_room", room_res, entity="league")
    print(f"silver_free_agents: {n_fa} rows "
          f"(fa_season {fa_key}, cap_season {cap_key})")
    print(f"silver_cap_room: {n_room} rows")
    n_fa = _enrich_derived_holds(n_fa)
    return n_fa + n_room


def _enrich_derived_holds(n_fa: int) -> int:
    from shared.tools.league.cap_hold_derivation import derive_cap_holds
    try:
        with store.connect(read_only=True) as con:
            derived = derive_cap_holds(con, FA_YEAR)
    except Exception as exc:
        print(f"cap-hold derivation skipped: {str(exc)[:120]}")
        return n_fa
    rows = derived.get("rows") or []
    if not rows:
        print("cap-hold derivation produced no rows")
        return n_fa
    by_key = {(str(r.get("PLAYER_NAME") or ""), str(r.get("TEAM") or "")): r
              for r in rows}
    try:
        with store.connect(read_only=True) as con:
            cols = [r[1] for r in con.execute(
                "PRAGMA table_info(silver_free_agents)").fetchall()]
            data_cols = [c for c in cols if not c.startswith("_")]
            sel = ", ".join(chr(34) + c + chr(34) for c in data_cols)
            current = [dict(zip(data_cols, r)) for r in con.execute(
                f"SELECT {sel} FROM silver_free_agents").fetchall()]
    except Exception as exc:
        print(f"cap-hold enrichment read failed: {str(exc)[:120]}")
        return n_fa
    enriched = 0
    for row in current:
        hit = by_key.get((str(row.get("PLAYER_NAME") or ""), str(row.get("TEAM") or "")))
        if hit is not None and hit.get("cap_hold") is not None:
            row["CAP_HOLD"] = int(hit["cap_hold"])
            row["CAP_HOLD_EXACTNESS"] = str(hit.get("hold_exactness") or "unknown")
            row["CAP_HOLD_RULE"] = str(hit.get("hold_rule") or "")
            enriched += 1
        else:
            row["CAP_HOLD"] = None
            row["CAP_HOLD_EXACTNESS"] = None
            row["CAP_HOLD_RULE"] = None
    frame = pl.DataFrame(current)
    res = FetchResult(frame=frame,
                      meta=FetchMeta(source="derived:bref_contracts",
                                     season=FA_SEASON))
    n = store.save_frame("silver_free_agents", res, entity="league")
    print(f"silver_free_agents: {enriched} derived cap holds written "
          f"({derived.get('meta', {}).get('derivation_status', '')})")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    target = resolve_target(args.scratch_db)
    if target is None:
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)

    old_db, old_lock = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    total = 0
    try:
        total += load(args.dry_run)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
    print(f"free-agent rows loaded: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
