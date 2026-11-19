
import argparse
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import polars as pl
from lxml import html as lxml_html

import seed_transactions as txn_seed
from shared import store
from shared.contracts import resolve_player_ids

SEASONS = [f"{year}-{str(year + 1)[2:]}" for year in range(2022, 2027)]
PROJECTION_YEARS = list(range(2022, 2027))

CONTRACTS_URL = (
    "https://huggingface.co/datasets/"
    "Mr-Bridge/nba-salary-cap-contracts-2016-2026/resolve/main/player_salaries.csv"
)
CONTRACTS_SOURCE = "huggingface:Mr-Bridge/nba-salary-cap-contracts-2016-2026"
PROJECTIONS_SOURCE = "teamrankings:betiq"
TRANSACTIONS_SOURCE = "nba_official"

TEAM_ABBR = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

PROJECTION_TEAM_ABBR = {
    "Atlanta": "ATL",
    "Boston": "BOS",
    "Brooklyn": "BKN",
    "Charlotte": "CHA",
    "Chicago": "CHI",
    "Cleveland": "CLE",
    "Dallas": "DAL",
    "Denver": "DEN",
    "Detroit": "DET",
    "Golden State": "GSW",
    "Houston": "HOU",
    "Indiana": "IND",
    "LA Clippers": "LAC",
    "LA Lakers": "LAL",
    "Memphis": "MEM",
    "Miami": "MIA",
    "Milwaukee": "MIL",
    "Minnesota": "MIN",
    "New Orleans": "NOP",
    "New York": "NYK",
    "Okla City": "OKC",
    "Orlando": "ORL",
    "Philadelphia": "PHI",
    "Phoenix": "PHX",
    "Portland": "POR",
    "Sacramento": "SAC",
    "San Antonio": "SAS",
    "Toronto": "TOR",
    "Utah": "UTA",
    "Washington": "WAS",
}

CONTRACT_COLUMNS = [
    "PLAYER_NAME", "PLAYER_ID", "TEAM", "TEAM_NAME", "SALARY",
    "PLAYER_OPTION", "TEAM_OPTION", "QUALIFYING_OFFER", "TWO_WAY",
    "TERMINATED", "SOURCE_PLAYER_ID", "SOURCE_TEAM_ID", "SEASON_YEAR",
    "NOTES", "CONTRACT_SOURCE",
]

PROJECTION_COLUMNS = [
    "TEAM", "TEAM_NAME", "DIVISION", "RATING", "ONE_WEEK_CHANGE",
    "PROJECTED_WINS", "PROJECTED_LOSSES", "WIN_DIVISION_PCT",
    "MAKE_PLAYOFFS_PCT", "MAKE_SECOND_ROUND_PCT", "MAKE_CONF_FINALS_PCT",
    "MAKE_NBA_FINALS_PCT", "WIN_TITLE_PCT", "PROJECTION_MODEL",
    "PROJECTION_SOURCE",
]


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


def _bool(value: object) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _int_or_none(value: object) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _pct(value: object) -> float | None:
    text = str(value or "").strip().replace("%", "")
    number = _float_or_none(text)
    return None if number is None else number / 100.0


def transform_contracts(df: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for row in df.to_dicts():
        season = str(row.get("season") or "")
        if season not in SEASONS:
            continue
        team_name = str(row.get("team") or "").strip()
        team = TEAM_ABBR.get(team_name)
        if not team:
            continue
        rows.append({
            "PLAYER_NAME": str(row.get("player") or "").strip(),
            "TEAM": team,
            "TEAM_NAME": team_name,
            "SALARY": _int_or_none(row.get("salary")),
            "PLAYER_OPTION": _bool(row.get("player_option")),
            "TEAM_OPTION": _bool(row.get("team_option")),
            "QUALIFYING_OFFER": _bool(row.get("qualifying_offer")),
            "TWO_WAY": _bool(row.get("two_way")),
            "TERMINATED": _bool(row.get("terminated")),
            "SOURCE_PLAYER_ID": _int_or_none(row.get("player_id")),
            "SOURCE_TEAM_ID": _int_or_none(row.get("team_id")),
            "SEASON_YEAR": _int_or_none(row.get("season_year")),
            "NOTES": str(row.get("notes") or "") or None,
            "CONTRACT_SOURCE": str(row.get("source") or "") or None,
            "_season": season,
        })
    if not rows:
        return pl.DataFrame(schema={c: pl.String for c in CONTRACT_COLUMNS})
    frame = pl.DataFrame(rows, infer_schema_length=None)
    return frame.with_columns([
        pl.col("PLAYER_ID").cast(pl.Int64) if "PLAYER_ID" in frame.columns else pl.lit(None, dtype=pl.Int64).alias("PLAYER_ID"),
        pl.col("SALARY").cast(pl.Int64),
        pl.col("SOURCE_PLAYER_ID").cast(pl.Int64),
        pl.col("SOURCE_TEAM_ID").cast(pl.Int64),
        pl.col("SEASON_YEAR").cast(pl.Int64),
        pl.col("PLAYER_OPTION").cast(pl.Boolean),
        pl.col("TEAM_OPTION").cast(pl.Boolean),
        pl.col("QUALIFYING_OFFER").cast(pl.Boolean),
        pl.col("TWO_WAY").cast(pl.Boolean),
        pl.col("TERMINATED").cast(pl.Boolean),
    ]).select(CONTRACT_COLUMNS + ["_season"])


def transform_projections(page: str, start_year: int) -> pl.DataFrame:
    season = f"{start_year}-{str(start_year + 1)[2:]}"
    document = lxml_html.fromstring(page)
    tables = document.xpath("//table")
    if not tables:
        raise ValueError("projection table missing")
    rows = []
    for tr in tables[0].xpath(".//tr")[2:]:
        cells = tr.xpath("./td|./th")
        if len(cells) < 12:
            continue
        values = [" ".join(c.text_content().split()) for c in cells[:12]]
        display = values[2]
        team = PROJECTION_TEAM_ABBR.get(display)
        if not team:
            continue
        rows.append({
            "TEAM": team,
            "TEAM_NAME": display,
            "DIVISION": values[3],
            "RATING": _float_or_none(values[0]),
            "ONE_WEEK_CHANGE": _float_or_none(values[1]),
            "PROJECTED_WINS": _float_or_none(values[4]),
            "PROJECTED_LOSSES": _float_or_none(values[5]),
            "WIN_DIVISION_PCT": _pct(values[6]),
            "MAKE_PLAYOFFS_PCT": _pct(values[7]),
            "MAKE_SECOND_ROUND_PCT": _pct(values[8]),
            "MAKE_CONF_FINALS_PCT": _pct(values[9]),
            "MAKE_NBA_FINALS_PCT": _pct(values[10]),
            "WIN_TITLE_PCT": _pct(values[11]),
            "PROJECTION_MODEL": "betiq_power_index",
            "PROJECTION_SOURCE": PROJECTIONS_SOURCE,
            "_season": season,
        })
    if not rows:
        return pl.DataFrame(schema={c: pl.String for c in PROJECTION_COLUMNS})
    return pl.DataFrame(rows, infer_schema_length=None).select(PROJECTION_COLUMNS + ["_season"])


def recent_transaction_parts(frame: pl.DataFrame) -> dict[str, pl.DataFrame]:
    parts = txn_seed.partition_by_season(frame)
    return {season: part for season, part in parts.items() if season in SEASONS}


def _write_partitioned(table: str, frame: pl.DataFrame, season_col: str,
                       source: str, entity: str, force: bool, dry_run: bool) -> int:
    written = 0
    for season in sorted(frame[season_col].unique().to_list()):
        part = frame.filter(pl.col(season_col) == season)
        if part.height == 0:
            continue
        entity_value = entity.format(season=season)
        if not force and not dry_run and unit_done(table, season, entity_value):
            continue
        if dry_run:
            print(f"{table} {season}: dry-run {part.height} rows")
            written += part.height
            continue
        n = store.write_unit(
            table, part, season, source, entity_value,
            "_season = ? AND _entity = ?", [season, entity_value],
        )
        written += n
        print(f"{table} {season}: {n} rows")
    return written


def unit_done(table: str, season: str, entity: str) -> bool:
    try:
        return bool(store.last_fetch(table, season, entity))
    except Exception:
        return False


def fetch_text(url: str) -> str:
    response = httpx.get(url, timeout=60, follow_redirects=True,
                         headers={"User-Agent": "dime/1.0"})
    response.raise_for_status()
    return response.text


def run_transactions(force: bool, dry_run: bool) -> int:
    frame = txn_seed.map_transactions(txn_seed.fetch_transactions())
    parts = recent_transaction_parts(frame)
    written = 0
    for season, part in sorted(parts.items()):
        part = part.with_columns([
            pl.col("player_id").cast(pl.Int64, strict=False),
            pl.col("team_id").cast(pl.Int64, strict=False),
        ])
        entity = f"season:{season}"
        if not force and not dry_run and unit_done("silver_transactions", season, entity):
            continue
        if dry_run:
            print(f"silver_transactions {season}: dry-run {part.height} rows")
            written += part.height
            continue
        n = store.write_unit(
            "silver_transactions", part, season, TRANSACTIONS_SOURCE, entity,
            "_season = ? AND _entity = ?", [season, entity],
        )
        written += n
        print(f"silver_transactions {season}: {n} rows")
    return written


def run_contracts(force: bool, dry_run: bool) -> int:
    text = fetch_text(CONTRACTS_URL)
    frame = transform_contracts(pl.read_csv(io.StringIO(text), infer_schema_length=None))
    if frame.height == 0:
        raise ValueError("no contract rows for requested seasons")
    if not dry_run:
        with store.connect(read_only=True) as con:
            frame = resolve_player_ids(frame, con)
    return _write_partitioned(
        "silver_contracts", frame, "_season", CONTRACTS_SOURCE, "season:{season}",
        force, dry_run,
    )


def run_projections(force: bool, dry_run: bool) -> int:
    frames = []
    for start_year in PROJECTION_YEARS:
        url = f"https://betiq.teamrankings.com/nba/predictions/{start_year}/"
        frames.append(transform_projections(fetch_text(url), start_year))
    frame = pl.concat(frames, how="diagonal_relaxed")
    if frame.height == 0:
        raise ValueError("no projection rows parsed")
    return _write_partitioned(
        "silver_preseason_projections", frame, "_season", PROJECTIONS_SOURCE,
        "league", force, dry_run,
    )


RUNNERS = {
    "transactions": run_transactions,
    "contracts": run_contracts,
    "preseason_projections": run_projections,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--datasets", default="transactions,contracts,preseason_projections")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    target = resolve_target(args.scratch_db)
    if target is None:
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)

    old_db = store.DB_PATH
    old_lock = store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()

    failures = []
    total = 0
    try:
        requested = [part.strip() for part in args.datasets.split(",") if part.strip()]
        unknown = [name for name in requested if name not in RUNNERS]
        if unknown:
            print(f"unknown datasets: {', '.join(unknown)}", file=sys.stderr)
            return 2
        for name in requested:
            try:
                total += RUNNERS[name](args.force, args.dry_run)
            except Exception as exc:
                failures.append(f"{name}: {exc}")
                print(f"{name}: FAILED ({exc})", file=sys.stderr)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()

    print(f"done: {total} rows {'would be ' if args.dry_run else ''}written, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
