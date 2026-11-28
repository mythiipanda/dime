import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.contracts import resolve_player_ids
from shared.sources.salaries import TEAM_ABBR, get_contracts

SLUG_TO_ABBR = {
    "hawks": "ATL", "celtics": "BOS", "nets": "BKN", "hornets": "CHA", "bulls": "CHI",
    "cavaliers": "CLE", "mavericks": "DAL", "nuggets": "DEN", "pistons": "DET", "warriors": "GSW",
    "rockets": "HOU", "pacers": "IND", "clippers": "LAC", "lakers": "LAL", "grizzlies": "MEM",
    "heat": "MIA", "bucks": "MIL", "timberwolves": "MIN", "pelicans": "NOP", "knicks": "NYK",
    "thunder": "OKC", "magic": "ORL", "sixers": "PHI", "suns": "PHX", "blazers": "POR",
    "kings": "SAC", "spurs": "SAS", "raptors": "TOR", "jazz": "UTA", "wizards": "WAS",
}

TABLE = "silver_salaries"
SOURCE = "bref_contracts"
SEASON_COL = re.compile(r"^(SALARY|OPTION)_\d{4}_\d{2}$")


def _existing_rows(con) -> list[dict]:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if TABLE not in tables:
        return []
    cols = [r[0] for r in con.execute(f"DESCRIBE {TABLE}").fetchall()]
    data_cols = [c for c in cols if not c.startswith("_")]
    sel = ", ".join(f'"{c}"' for c in data_cols)
    out = []
    for row in con.execute(f"SELECT {sel} FROM {TABLE}").fetchall():
        out.append(dict(zip(data_cols, row)))
    return out


def merge_contracts(frame: pl.DataFrame, old_rows: list[dict]) -> pl.DataFrame:
    season_cols = sorted({
        c for r in old_rows for c in r
        if SEASON_COL.match(c)
    })
    all_cols = list(frame.columns) + [
        c for c in season_cols if c not in frame.columns]
    prior = {}
    for r in old_rows:
        name = r.get("PLAYER_NAME")
        if name is not None:
            prior[name] = {c: r.get(c) for c in season_cols}

    merged = []
    seen = set()
    fresh_names = set()
    for row in frame.to_dicts():
        key = (row["PLAYER_NAME"], row["TEAM"])
        if key in seen:
            continue
        seen.add(key)
        fresh_names.add(row["PLAYER_NAME"])
        old = prior.get(row["PLAYER_NAME"], {})
        for c in season_cols:
            if row.get(c) is None:
                row[c] = old.get(c)
        merged.append(row)

    carried = 0
    for r in old_rows:
        if r.get("PLAYER_NAME") in fresh_names:
            continue
        team = TEAM_ABBR.get(r.get("TEAM") or "", r.get("TEAM"))
        if (r.get("PLAYER_NAME"), r.get("TEAM")) in seen:
            continue
        if (r.get("PLAYER_NAME"), team) in seen:
            continue
        row = {c: None for c in all_cols}
        for c in all_cols:
            if c in r and r[c] is not None:
                row[c] = r[c]
        row["TEAM"] = team
        merged.append(row)
        carried += 1
    print(f"carry: {carried} departed rows kept")

    if not merged:
        return frame
    schema = dict(frame.schema)
    for c in season_cols:
        schema.setdefault(c, pl.String if c.startswith("OPTION_") else pl.Int64)
    return pl.DataFrame(merged, schema=schema)


def _player_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


_NAME_SUFFIXES = ("jr", "sr", "ii", "iii", "iv", "v")


def _slug_lookup(evidence: dict, name: str) -> list:
    slug = _player_slug(name)
    if slug in evidence:
        return evidence[slug]
    for suffix in _NAME_SUFFIXES:
        extended = f"{slug}-{suffix}"
        if extended in evidence:
            return evidence[extended]
    parts = slug.split("-")
    if parts and parts[-1] in _NAME_SUFFIXES:
        shortened = "-".join(parts[:-1])
        if shortened in evidence:
            return evidence[shortened]
    return []


def _contract_events(con) -> dict[str, list[tuple[str, str, str, str]]]:
    events: dict[str, list[tuple[str, str, str, str]]] = {}
    try:
        rows = con.execute(
            "SELECT player, txn_type, team, txn_date, detail FROM silver_transactions "
            "WHERE txn_type IN ('Signing', 'Waive', 'ContractConverted')").fetchall()
    except Exception:
        return events
    for slug, txn_type, team, txn_date, detail in rows:
        abbr = SLUG_TO_ABBR.get(team or "")
        events.setdefault(slug or "", []).append(
            (str(txn_date or ""), txn_type or "", abbr or "", (detail or "").lower()))
    for slug in events:
        events[slug].sort()
    return events


def contract_state(events: list[tuple[str, str, str, str]]) -> dict:
    two_way_team: str | None = None
    standard_by_team: dict[str, str] = {}
    waived_by: dict[str, str] = {}
    for date, txn_type, abbr, detail in events:
        if not abbr:
            continue
        if txn_type == "Waive":
            waived_by[abbr] = max(waived_by.get(abbr, ""), date)
            if two_way_team == abbr:
                two_way_team = None
            continue
        if "to a two-way contract" in detail:
            two_way_team = abbr
            continue
        if txn_type in ("Signing", "ContractConverted"):
            two_way_team = None
            standard_by_team[abbr] = max(standard_by_team.get(abbr, ""), date)
    dead_teams = {
        team for team, waive_date in waived_by.items()
        if standard_by_team.get(team, "") < waive_date
    }
    return {"two_way_team": two_way_team, "standard_by_team": standard_by_team,
            "dead_teams": dead_teams, "latest_standard_team": max(
                standard_by_team, key=lambda t: standard_by_team[t]) if standard_by_team else None}


def annotate_row_kinds(frame: pl.DataFrame, con) -> pl.DataFrame:
    rows = frame.to_dicts()
    by_player: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        by_player.setdefault(row.get("PLAYER_NAME") or "", []).append(i)
    evidence = _contract_events(con)
    kinds = ["roster"] * len(rows)
    dead = 0
    two_way = 0
    unresolved = 0
    for name, idxs in by_player.items():
        teams = {rows[i].get("TEAM") for i in idxs}
        state = contract_state(_slug_lookup(evidence, name))
        two_way_team = state["two_way_team"]
        dead_teams = state["dead_teams"]
        roster_abbr = state["latest_standard_team"]
        for i in idxs:
            team = rows[i].get("TEAM")
            if team in dead_teams:
                kinds[i] = "dead_money"
                dead += 1
            elif team == two_way_team:
                kinds[i] = "two_way"
                two_way += 1
            elif len(teams) > 1 and roster_abbr and team != roster_abbr and any(
                    rows[j].get("TEAM") == roster_abbr for j in idxs):
                kinds[i] = "dead_money"
                dead += 1
        if len(teams) > 1 and not roster_abbr:
            unresolved += 1
    print(f"row kinds: {dead} dead_money, {two_way} two_way rows annotated, "
          f"{unresolved} unresolved multi-team players left roster")
    return frame.with_columns(pl.Series("ROW_KIND", kinds))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch-db', type=Path)
    args = parser.parse_args()
    target = args.scratch_db or Path(os.environ.get('DIME_WAREHOUSE') or store.DB_PATH)
    if target.resolve() == store.CANONICAL_DB_PATH:
        parser.error('use --scratch-db or noncanonical DIME_WAREHOUSE')
    if not target.is_file():
        parser.error('scratch warehouse must be an existing copy')
    store.DB_PATH = target.resolve()
    store.LOCK_PATH = store.DB_PATH.parent / '.write.lock'
    res = get_contracts()
    if not res.ok or not res.meta.season or res.meta.season == "unknown":
        print(f"abort: y1 unobserved ({res.error or 'no season'})")
        raise SystemExit(1)
    with store.connect(read_only=True) as con:
        old_rows = _existing_rows(con)
        merged = merge_contracts(res.frame, old_rows)
        merged = resolve_player_ids(merged, con)
        merged = annotate_row_kinds(merged, con)
    scraped = res.frame.height
    print(f"scraped {scraped} salary rows (observed y1 {res.meta.season}); "
          f"merged {merged.height} rows with {len(old_rows)} prior rows")
    matched = merged['PLAYER_ID'].drop_nulls().len()
    print(f'PLAYER_ID matched={matched} unmatched={merged.height - matched}')
    n = store.write_unit(TABLE, merged, res.meta.season, SOURCE, "",
                         "1=1", [])
    print(f"silver_salaries: {n} rows saved (fetch_log season {res.meta.season})")

if __name__ == "__main__":
    main()
