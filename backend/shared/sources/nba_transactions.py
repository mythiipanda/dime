import json
import re
import time
from datetime import datetime, timezone

import polars as pl
import requests

SOURCE_CSV = "rossgraham-csv"
SOURCE_JSON = "stats-nba-json"
CSV_URL = "https://raw.githubusercontent.com/rossgraham/NBA-Transaction-History/main/DB/Player_Trans.csv"
JSON_URL = "https://www.stats.nba.com/js/data/history/NBA_Player_Movement.json"
CSV_FILE = "DB/Player_Trans.csv"
JSON_FILE = "NBA_Player_Movement.json"
DEDUP_RULE = "same date, same teams, same players means one row; the surviving row names both sources"
MIN_INTERVAL_S = 1.0
TIMEOUT_S = 60

SCHEMA = {
    "TRANSACTION_DATE": pl.String,
    "SEASON": pl.String,
    "TEAMS": pl.String,
    "PLAYERS": pl.String,
    "PICKS": pl.String,
    "TRANSACTION_TYPE": pl.String,
    "SOURCE": pl.String,
    "SOURCE_FILE": pl.String,
    "FETCHED_AT": pl.String,
}
COLUMNS = list(SCHEMA)

PICK_TOKEN = re.compile(r"round|draft pick|pick", re.IGNORECASE)

class TransactionsSourceError(RuntimeError):
    pass

def season_label_from_date(text: str) -> str:
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text.strip())
    if not match:
        raise TransactionsSourceError(
            f"transaction date {text!r} is not ISO YYYY-MM-DD")
    year, month, _day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if month >= 7:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"

def season_year(season: str) -> int:
    match = re.fullmatch(r"(\d{4})-(\d{2})", str(season).strip())
    if not match:
        raise TransactionsSourceError(
            f"season {season!r} is not in YYYY-YY form")
    start = int(match.group(1))
    return start + 1

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _split_teams(text: str) -> list[str]:
    return sorted({part.strip() for part in str(text).split(";") if part.strip()})

def _teams(text: str) -> str:
    return ";".join(_split_teams(text))

def _split_assets(text: str) -> tuple[str, str]:
    cleaned = str(text).replace("[", "").replace("]", "")
    players: list[str] = []
    picks: list[str] = []
    for token in cleaned.split(";"):
        token = token.strip()
        if not token:
            continue
        if PICK_TOKEN.search(token):
            picks.append(token)
        else:
            players.append(token)
    return (";".join(sorted(set(players))), ";".join(sorted(set(picks))))

def _row(transaction_date: str, season: str, teams: str, players: str,
         picks: str, transaction_type: str, source: str,
         source_file: str, fetched_at: str) -> dict:
    return {
        "TRANSACTION_DATE": transaction_date,
        "SEASON": season,
        "TEAMS": _teams(teams),
        "PLAYERS": ";".join(sorted({p.strip() for p in players.split(";") if p.strip()})),
        "PICKS": ";".join(sorted({p.strip() for p in picks.split(";") if p.strip()})),
        "TRANSACTION_TYPE": transaction_type.strip(),
        "SOURCE": source,
        "SOURCE_FILE": source_file,
        "FETCHED_AT": fetched_at,
    }

def parse_csv(text: str, fetched_at: str | None = None, source_file: str = CSV_FILE
              ) -> pl.DataFrame:
    fetched_at = fetched_at or _now()
    rows: list[dict] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("date,"):
            continue
        parts = line.split(",")
        if len(parts) != 4:
            raise TransactionsSourceError(
                f"rossgraham-csv: row {line_number} is not 4 fields "
                f"(date,type,teams,assets)")
        transaction_date, transaction_type, teams, assets = parts
        players, picks = _split_assets(assets)
        rows.append(_row(transaction_date, season_label_from_date(transaction_date),
                         teams, players, picks, transaction_type, SOURCE_CSV,
                         source_file, fetched_at))
    if not rows:
        raise TransactionsSourceError(
            "rossgraham-csv: parsed 0 rows from Player_Trans.csv")
    return pl.DataFrame(rows, schema=SCHEMA).sort(
        ["TRANSACTION_DATE", "TEAMS", "PLAYERS"])

def parse_json(text: str, fetched_at: str | None = None, source_file: str = JSON_FILE
               ) -> pl.DataFrame:
    fetched_at = fetched_at or _now()
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TransactionsSourceError(
            f"stats-nba-json: NBA_Player_Movement.json is not JSON "
            f"({exc})")
    if isinstance(document, dict):
        payload = document.get("rows") or document.get("results") \
            or document.get("data") or document.get("resultSets") or []
        if payload and isinstance(payload[0], dict) and "rowSet" in payload[0]:
            headers = payload[0].get("headers", [])
            payload = [dict(zip(headers, row)) for row in payload[0].get("rowSet", [])]
        if isinstance(document.get("rows"), dict) is False and not payload:
            for value in document.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    payload = value
                    break
    else:
        payload = document
    if not isinstance(payload, list):
        raise TransactionsSourceError(
            "stats-nba-json: NBA_Player_Movement.json has no row list")
    aliases = {
        "TRANSACTION_DATE": ("date", "transaction_date", "DATE", "transactionDate", "TRANSACTION_DATE"),
        "SEASON": ("season", "SEASON", "season_label", "SEASON_LABEL"),
        "TEAMS": ("teams", "team", "TEAMS", "TEAM", "teamsInvolved"),
        "PLAYERS": ("players", "player", "PLAYERS", "PLAYER", "playersInvolved"),
        "PICKS": ("picks", "pick", "PICKS", "PICK"),
        "TRANSACTION_TYPE": ("type", "transaction_type", "TYPE", "transactionType", "TRANSACTION_TYPE"),
    }
    rows: list[dict] = []
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            raise TransactionsSourceError(
                f"stats-nba-json: row {index} is not an object")
        found: dict[str, str] = {}
        for canonical, names in aliases.items():
            for name in names:
                if name in record and record[name] not in (None, ""):
                    found[canonical] = str(record[name])
                    break
        missing = [key for key in ("TRANSACTION_DATE", "SEASON", "TEAMS",
                                   "PLAYERS", "TRANSACTION_TYPE") if key not in found]
        if missing:
            raise TransactionsSourceError(
                f"stats-nba-json: row {index} missing field(s) "
                f"{','.join(missing)}")
        players, extra_picks = _split_assets(found["PLAYERS"])
        picks = found.get("PICKS", "")
        picks = ";".join([p for p in [picks, extra_picks] if p])
        rows.append(_row(found["TRANSACTION_DATE"], found["SEASON"], found["TEAMS"],
                         players, picks, found["TRANSACTION_TYPE"], SOURCE_JSON,
                         source_file, fetched_at))
    if not rows:
        raise TransactionsSourceError(
            "stats-nba-json: parsed 0 rows from NBA_Player_Movement.json")
    return pl.DataFrame(rows, schema=SCHEMA).sort(
        ["TRANSACTION_DATE", "TEAMS", "PLAYERS"])

def dedupe_same_date_teams_players(csv_frame: pl.DataFrame,
                                   json_frame: pl.DataFrame) -> pl.DataFrame:
    combined = pl.concat([json_frame, csv_frame])
    return combined.group_by(["TRANSACTION_DATE", "TEAMS", "PLAYERS"]).agg([
        pl.col("TRANSACTION_TYPE").first(),
        pl.col("PICKS").first(),
        pl.col("SEASON").first(),
        pl.col("SOURCE").unique(),
        pl.col("SOURCE_FILE").unique(),
        pl.col("FETCHED_AT").min(),
    ]).with_columns(
        pl.col("SOURCE").list.eval(pl.element().sort()).list.join("+"),
        pl.col("SOURCE_FILE").list.eval(pl.element().sort()).list.join("+"),
    ).sort(["TRANSACTION_DATE", "TEAMS", "PLAYERS"])

def union(csv_frame: pl.DataFrame, json_frame: pl.DataFrame) -> pl.DataFrame:
    return dedupe_same_date_teams_players(csv_frame, json_frame)

def fetch(url: str, transport=None) -> str:
    get = transport or paced_transport()
    return get(url)

def paced_transport(min_interval_s: float = MIN_INTERVAL_S):
    last_request = [0.0]

    def get(url: str) -> str:
        wait = min_interval_s - (time.monotonic() - last_request[0])
        if wait > 0:
            time.sleep(wait)
        last_request[0] = time.monotonic()
        response = requests.get(url, headers={"User-Agent": "dime-seeder/1.0",
                                              "Accept": "*/*"}, timeout=TIMEOUT_S)
        response.raise_for_status()
        return response.content.decode("utf-8")
    return get
