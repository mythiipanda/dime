import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult
from shared.tools.league.standings import _injury_entries

TABLE = "silver_injury_entries"
_RETURN_PAT = re.compile(
    r"(\d+\s*(?:-?\s*to\s*-?\s*|-\s*)\d+\s+(?:days?|weeks?|months?))|"
    r"(at least \w+\s+(?:week|month|day)s?)|"
    r"(remainder of (?:the )?season)|(out for (?:the )?season)|"
    r"(indefinitely)|(day-to-day)",
    re.IGNORECASE)
_ESPN_ID_PAT = re.compile(r"/(?:id|athletes)/(\d+)")


def _espn_id(entry: dict) -> str:
    ref = ((((entry.get("athlete") or {}).get("notes") or {})
            .get("items") or [{}])[0].get("injury") or {}).get("$ref", "")
    m = _ESPN_ID_PAT.search(ref)
    if m:
        return m.group(1)
    for link in (entry.get("athlete") or {}).get("links") or []:
        m = _ESPN_ID_PAT.search(str(link.get("href", "")))
        if m:
            return m.group(1)
    return ""


def _nba_id_map() -> dict:
    try:
        from nba_api.stats.static import players
        return {str(p["full_name"]).lower(): str(p["id"])
                for p in players.get_players() if p.get("full_name")}
    except Exception:
        return {}


def _return_estimate(entry: dict) -> str:
    text = " ".join(str(entry.get(k) or "")
                    for k in ("shortComment", "longComment"))
    m = _RETURN_PAT.search(text)
    return m.group(0) if m else ""


def normalize(rows: list[tuple]) -> pl.DataFrame:
    nba = _nba_id_map()
    out = []
    for row in rows:
        blob = row[2] if len(row) > 2 else row[-1]
        team_name = row[1] if len(row) > 2 else ""
        for e in _injury_entries(blob):
            if not isinstance(e, dict):
                continue
            a = e.get("athlete") or {}
            notes = ((a.get("notes") or {}).get("items") or [{}])
            out.append({
                "PLAYER": a.get("displayName", ""),
                "TEAM": (a.get("team") or {}).get("displayName", team_name),
                "TEAM_ABBR": (a.get("team") or {}).get("abbreviation", ""),
                "ESPN_ATHLETE_ID": _espn_id(e),
                "PERSON_ID": nba.get(str(a.get("displayName", "")).lower(), ""),
                "POSITION": (a.get("position") or {}).get("abbreviation", ""),
                "STATUS": e.get("status", ""),
                "ATHLETE_STATUS": (a.get("status") or {}).get("name", ""),
                "INJURY": e.get("shortComment", ""),
                "RETURN_ESTIMATE": _return_estimate(e),
                "REPORT_DATE": e.get("date", ""),
                "DETAIL": e.get("longComment", ""),
                "SOURCE": notes[0].get("source", "") or "espn",
            })
    return pl.DataFrame(out) if out else pl.DataFrame(
        schema={c: pl.Utf8 for c in
                ("PLAYER", "TEAM", "TEAM_ABBR", "ESPN_ATHLETE_ID",
                 "PERSON_ID", "POSITION", "STATUS", "ATHLETE_STATUS",
                 "INJURY", "RETURN_ESTIMATE", "REPORT_DATE", "DETAIL",
                 "SOURCE")})


def build(con) -> FetchResult:
    rows = con.execute(
        "select id, display_name, injuries from silver_injuries").fetchall()
    frame = normalize(rows)
    season = con.execute(
        "select max(_season) from silver_injuries").fetchone()[0] or "unknown"
    return FetchResult(frame=frame, meta=FetchMeta(
        source="derived:silver_injuries(espn)", season=season))


def save(con) -> int:
    res = build(con)
    n = store.save_frame(TABLE, res, entity="", replace_season=True)
    print(f"{TABLE}: {n} rows (season {res.meta.season})")
    return n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raw = args.scratch_db or os.environ.get("DIME_WAREHOUSE", "")
    if not raw:
        parser.error("pass --scratch-db or set DIME_WAREHOUSE")
    target = Path(raw).expanduser().resolve()
    if target == store.CANONICAL_DB_PATH:
        parser.error("refusing: target is the canonical warehouse")
    if not target.is_file():
        parser.error("target warehouse must exist")
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    if args.dry_run:
        with store.connect(read_only=True) as con:
            res = build(con)
        print(f"{TABLE}: {res.frame.height} rows (dry-run)")
        return
    with store.connect() as con:
        if "silver_injuries" not in {
                r[0] for r in con.execute("SHOW TABLES").fetchall()}:
            print("abort: silver_injuries missing from target warehouse")
            raise SystemExit(1)
        save(con)


if __name__ == "__main__":
    main()
