import argparse
import os
import sys
import time as _time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store

_sleep = _time.sleep

SOURCE = "parlay"
TABLE = "silver_odds"
SPORT_KEY = "basketball_nba"
CLOSING_URL = f"https://parlay-api.com/v1/historical/sports/{SPORT_KEY}/closing-odds"

TEAM_ABBREV = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}

COLUMNS = ["game_date", "commence_time", "home_team", "away_team", "book",
           "market", "outcome", "price", "point"]


def season_for_date(date: str) -> str:
    year, month = int(date[:4]), int(date[5:7])
    if month >= 10:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"


def _curl_transport(url: str, headers: dict, params: dict,
                    timeout_s: int = 60, attempts: int = 3) -> str:
    import subprocess
    import urllib.parse
    query = urllib.parse.urlencode(params)
    full = url + ("?" + query if query else "")
    args = ["curl", "-s", "--max-time", str(timeout_s), "-w", "\n%{http_code}"]
    for key, value in headers.items():
        args += ["-H", f"{key}: {value}"]
    args.append(full)
    last = "no attempts made"
    for attempt in range(attempts):
        try:
            proc = subprocess.run(args, capture_output=True, timeout=timeout_s + 30)
            body, _, code = proc.stdout.decode().rpartition("\n")
            if proc.returncode == 0 and code.strip().startswith("2"):
                return body
            last = f"HTTP {code.strip()}: {body[:200]}"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < attempts - 1:
            _sleep(2 * (attempt + 1))
    raise RuntimeError(f"parlay request failed after {attempts} attempts ({last})")


def fetch_closing_odds(date: str, transport=_curl_transport) -> list:
    import json
    key = os.environ.get("PARLAY_API_KEY")
    if not key:
        raise RuntimeError("missing PARLAY_API_KEY: set it to seed closing lines")
    body = transport(CLOSING_URL, {"X-API-Key": key},
                     {"date": date, "regions": "us",
                      "markets": "h2h,spreads,totals"})
    payload = json.loads(body)
    if not isinstance(payload, list):
        raise ValueError("malformed closing-odds payload: expected a list of rows")
    return payload


def _team(name: str) -> str:
    return TEAM_ABBREV.get(name, name)


def map_closing_odds(payload: list, date: str) -> pl.DataFrame:
    if not isinstance(payload, list):
        raise ValueError("malformed closing-odds payload: expected a list of rows")
    rows = []
    for pos, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"malformed closing-odds row {pos}: expected an object")
        game_date = row.get("game_date") or date
        base = {
            "game_date": game_date,
            "commence_time": row.get("commence_time"),
            "home_team": _team(row.get("home_team")),
            "away_team": _team(row.get("away_team")),
            "book": row.get("bookmaker") or row.get("book"),
            "market": row.get("market_key") or row.get("market"),
        }
        point = row.get("line", row.get("point"))
        if "over_odds" in row and "under_odds" in row:
            pairs = [("Over", row["over_odds"]), ("Under", row["under_odds"])]
        elif "price" in row:
            name = row.get("outcome") or row.get("name") or row.get("player") or ""
            pairs = [(name, row["price"])]
        else:
            raise ValueError(
                f"malformed closing-odds row {pos}: no price fields "
                f"(keys: {sorted(row.keys())})")
        for outcome, price in pairs:
            rows.append(dict(base, outcome=outcome, price=price, point=point))
    if not rows:
        return pl.DataFrame([], schema={c: pl.String for c in COLUMNS})
    return pl.DataFrame(rows, strict=False).select(COLUMNS)


def _seeded(season: str, entity: str) -> bool:
    try:
        return bool(store.last_fetch(TABLE, season, entity))
    except Exception:
        return False


def seed_date(date: str, season: str, fetch_fn=fetch_closing_odds) -> int:
    entity = f"closing:{date}"
    if _seeded(season, entity):
        return 0
    frame = map_closing_odds(fetch_fn(date), date)
    if frame.height == 0:
        return 0
    return store.write_unit(TABLE, frame, season, SOURCE, entity,
                            "_season = ? AND _entity = ?", [season, entity])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Seed silver_odds closing lines for one date.")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD game date")
    ap.add_argument("--season", default="", help=" season label like 2023-24 (derived from date when empty)")
    args = ap.parse_args(argv)
    if not os.environ.get("PARLAY_API_KEY"):
        print("abort: PARLAY_API_KEY is not set, closing lines need a ParlayAPI key")
        return 1
    season = args.season or season_for_date(args.date)
    try:
        n = seed_date(args.date, season)
    except Exception as exc:
        print(f"abort: odds seed for {args.date} failed ({exc})")
        return 1
    print(f"silver_odds {args.date}: {n} rows saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
