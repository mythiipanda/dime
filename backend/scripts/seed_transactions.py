import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from seed_odds import _curl_transport
from shared import store

SOURCE = "nba_official"
TABLE = "silver_transactions"
FEED_URL = "https://stats.nba.com/js/data/playermovement/NBA_Player_Movement.json"

COLUMNS = ["txn_date", "txn_type", "player", "player_id",
           "team", "team_id", "detail"]


def season_for_date(date: str) -> str:
    year, month = int(date[:4]), int(date[5:7])
    if month >= 10:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"


def fetch_transactions(transport=_curl_transport) -> dict:
    import json
    body = transport(FEED_URL, {"Referer": "https://www.nba.com/",
                                "User-Agent": "Mozilla/5.0"}, {})
    payload = json.loads(body)
    try:
        rows = payload["NBA_Player_Movement"]["rows"]
    except (KeyError, TypeError):
        raise ValueError("malformed movement payload: missing rows")
    if not isinstance(rows, list):
        raise ValueError("malformed movement payload: rows is not a list")
    return payload


def map_transactions(payload: dict) -> pl.DataFrame:
    try:
        rows = payload["NBA_Player_Movement"]["rows"]
    except (KeyError, TypeError, AttributeError):
        raise ValueError("malformed movement payload: missing rows")
    if not isinstance(rows, list):
        raise ValueError("malformed movement payload: rows is not a list")
    frame = pl.DataFrame([{
        "txn_date": r["TRANSACTION_DATE"][:10],
        "txn_type": r["Transaction_Type"],
        "player": r.get("PLAYER_SLUG"),
        "player_id": r.get("PLAYER_ID"),
        "team": r.get("TEAM_SLUG"),
        "team_id": r.get("TEAM_ID"),
        "detail": r["TRANSACTION_DESCRIPTION"],
    } for r in rows], strict=False)
    if frame.height == 0:
        return pl.DataFrame([], schema={c: pl.String for c in COLUMNS})
    return frame.select(COLUMNS)


def partition_by_season(frame: pl.DataFrame) -> dict:
    parts: dict = {}
    for row in frame.to_dicts():
        season = season_for_date(row["txn_date"])
        parts.setdefault(season, []).append(row)
    return {s: pl.DataFrame(r, strict=False).select(frame.columns)
            for s, r in sorted(parts.items())}


def _seeded(season: str, entity: str) -> bool:
    try:
        return bool(store.last_fetch(TABLE, season, entity))
    except Exception:
        return False


def seed_all(fetch_fn=fetch_transactions) -> dict:
    frame = map_transactions(fetch_fn())
    if frame.height == 0:
        return {}
    result = {}
    for season, part in partition_by_season(frame).items():
        entity = f"season:{season}"
        if _seeded(season, entity):
            result[season] = 0
            continue
        result[season] = store.write_unit(
            TABLE, part, season, SOURCE, entity,
            "_season = ? AND _entity = ?", [season, entity])
    return result


def main(argv=None, fetch_fn=None) -> int:
    ap = argparse.ArgumentParser(description="Seed silver_transactions from the NBA movement feed.")
    ap.parse_args(argv)
    try:
        result = seed_all(fetch_fn or fetch_transactions)
    except Exception as exc:
        print(f"abort: transactions seed failed ({exc})")
        return 1
    total = sum(result.values())
    for season, n in result.items():
        print(f"{season}: {n} rows saved")
    print(f"silver_transactions: {total} rows saved across {len(result)} seasons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
