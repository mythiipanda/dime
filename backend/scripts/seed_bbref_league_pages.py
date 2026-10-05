import argparse
import io
import os
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import polars as pl
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store  # noqa: E402
from shared.sources.base import FetchMeta, FetchResult  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
BASE = "https://www.basketball-reference.com/leagues/NBA_%d_%s.html"
BBREF = "basketball-reference:per_game"
ABSENT_TS = "absent:no_ts_on_per_game_page"
TABLE = "silver_player_season"
ZONES_TABLE = "silver_zone_splits"
ENTITY = "league"


class SeasonFetchError(RuntimeError):
    pass


def norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", ascii_only.strip(),
                  flags=re.IGNORECASE)


def _start_year(season: str) -> int:
    year, _, tail = str(season).partition("-")
    if len(year) != 4 or not year.isdigit():
        raise ValueError(f"season must read YYYY-YY, got {season!r}")
    if len(tail) != 2 or not tail.isdigit() or int(tail) != (int(year) + 1) % 100:
        raise ValueError(f"season must span consecutive years, got {season!r}")
    return int(year)


def season_slugs(first: str, last: str) -> list[str]:
    start, end = _start_year(first), _start_year(last)
    if end < start:
        raise ValueError(f"empty season range: {first} to {last}")
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(start, end + 1)]


def bbref_year(season: str) -> int:
    return _start_year(season) + 1


def name_map() -> dict:
    from nba_api.stats.static import players as sp
    m = {}
    for r in sp.get_players():
        m.setdefault(norm(r["full_name"]), r["id"])
    return m


def fetch(page: str, year: int) -> pd.DataFrame:
    r = requests.get(BASE % (year, page), headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    df = pd.read_html(io.StringIO(r.text))[0]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["|".join(str(x) for x in tup if "Unnamed" not in str(x))
                      for tup in df.columns]
    df = df[df[df.columns[1]] != "Player"]
    return df


def loaded_seasons(table: str = TABLE) -> set[str]:
    try:
        con = store.connect(read_only=True)
    except Exception:
        return set()
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if table not in tables:
            return set()
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {table} WHERE _season IS NOT NULL"
        ).fetchall()
        return {row[0] for row in rows if row and row[0]}
    except Exception:
        return set()
    finally:
        try:
            con.close()
        except Exception:
            pass


def build_per_game_rows(pg: pd.DataFrame, nm: dict) -> list[dict]:
    staged: list[dict] = []
    for _, r in pg.iterrows():
        pid = nm.get(norm(str(r.get("Player", ""))))
        if not pid:
            continue
        staged.append({
            "PLAYER_ID": pid, "PLAYER": str(r["Player"]),
            "TEAM": str(r.get("Team", "")), "AGE": _f(r.get("Age")),
            "_TEAMORDER": 0 if str(r.get("Team", "")) == "TOT" else 1,
            "GP": _f(r.get("G")), "GS": _f(r.get("GS")),
            "MPG": _f(r.get("MP")), "PPG": _f(r.get("PTS")),
            "RPG": _f(r.get("TRB")), "APG": _f(r.get("AST")),
            "SPG": _f(r.get("STL")), "BPG": _f(r.get("BLK")),
            "FG_PCT": _f(r.get("FG%")), "FG3_PCT": _f(r.get("3P%")),
            "FT_PCT": _f(r.get("FT%")),
        })
    best: dict = {}
    for row in staged:
        k = row["PLAYER_ID"]
        if k not in best or row["_TEAMORDER"] < best[k]["_TEAMORDER"]:
            best[k] = row
    rows: list[dict] = []
    for row in best.values():
        row.pop("_TEAMORDER", None)
        row["TS_PCT"] = None
        for col in ("PLAYER_ID", "PLAYER", "TEAM", "AGE", "GP", "GS",
                    "MPG", "PPG", "RPG", "APG", "SPG", "BPG",
                    "FG_PCT", "FG3_PCT", "FT_PCT"):
            row[f"_prov_{col}"] = BBREF
        row["_prov_TS_PCT"] = ABSENT_TS
        rows.append(row)
    return rows


def require_complete(season: str, rows: list[dict]) -> None:
    if not rows:
        raise SeasonFetchError(
            f"{TABLE} {season}: basketball-reference per_game returned "
            "no usable rows")


def save_season(table: str, rows: list[dict], season: str,
                source: str = BBREF) -> int:
    frame = pl.DataFrame(rows, strict=False) if rows else pl.DataFrame()
    res = FetchResult(frame=frame,
                      meta=FetchMeta("basketball-reference", season))
    return store.save_frame(table, res, ENTITY, replace_season=True)


def build_zone_rows(pg: pd.DataFrame, sh: pd.DataFrame, nm: dict) -> list[dict]:
    fga_by_pid: dict = {}
    for _, r in pg.iterrows():
        pid = nm.get(norm(str(r.get("Player", ""))))
        if not pid or str(r.get("Team", "")) == "TOT" and pid in fga_by_pid:
            continue
        try:
            fga_by_pid[pid] = float(r.get("FGA") or 0) * float(r.get("G") or 0)
        except (TypeError, ValueError):
            pass
    cols = list(sh.columns)
    bucket_pct: dict = {}
    bucket_fg: dict = {}
    for c in cols:
        m = re.search(r"(\d+-\d+P?|3P)", str(c))
        if not m:
            continue
        bucket = m.group(1)
        bucket = {"16-3P": "16ft-3P", "0-3": "0-3ft", "3-10": "3-10ft",
                  "10-16": "10-16ft"}.get(bucket, bucket)
        if "%" in str(c) and "FG" not in str(c).upper()[:6]:
            bucket_pct.setdefault(bucket, c)
        if "FG%" in str(c):
            bucket_fg.setdefault(bucket, c)
    zrows: list[dict] = []
    for _, r in sh.iterrows():
        pid = nm.get(norm(str(r.get("Player", ""))))
        if not pid:
            continue
        fga_tot = fga_by_pid.get(pid, 0.0)
        if fga_tot <= 0:
            continue
        for bucket, pc in bucket_pct.items():
            fc = bucket_fg.get(bucket)
            if fc is None:
                continue
            try:
                share = float(r.get(pc) or 0)
                fgpct = float(r.get(fc) or 0)
            except (TypeError, ValueError):
                continue
            fga = share * fga_tot
            zrows.append({
                "PLAYER_ID": pid, "ZONE": bucket, "FGA": round(fga, 1),
                "FGM": round(fga * fgpct, 1), "FGA_PCT": round(share, 3),
                "FG_PCT": round(fgpct, 3),
            })
    return zrows


def seed_season(season: str, nm: dict | None = None,
                fetch_page=None) -> dict[str, int]:
    fetch_page = fetch_page or fetch
    year = bbref_year(season)
    nm = nm if nm is not None else name_map()
    pg = fetch_page("per_game", year)
    rows = build_per_game_rows(pg, nm)
    require_complete(season, rows)
    n = save_season(TABLE, rows, season)
    try:
        sh = fetch_page("shooting", year)
        zrows = build_zone_rows(pg, sh, nm)
    except Exception:
        zrows = []
    z = save_season(ZONES_TABLE, zrows, season) if zrows else 0
    return {TABLE: n, ZONES_TABLE: z}


def run(seasons: list[str], nm: dict | None = None,
        fetch_page=None) -> dict:
    done = loaded_seasons()
    skipped: list[str] = []
    loaded: dict[str, int] = {}
    for season in seasons:
        if season in done:
            skipped.append(season)
            continue
        report = seed_season(season, nm=nm, fetch_page=fetch_page)
        loaded[season] = report[TABLE]
        done.add(season)
    return {"loaded": loaded, "skipped": skipped,
            "rows": sum(loaded.values())}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


DEV_ENVS = frozenset({"dev", "local", "test"})


def resolve_target(scratch_db: str):
    raw = scratch_db or os.environ.get("DIME_WAREHOUSE", "")
    if not raw:
        print("refusing: DIME_WAREHOUSE is not set")
        return None
    target = Path(raw).expanduser().resolve()
    print(f"target: {target}")
    if target == store.CANONICAL_DB_PATH:
        print("refusing: target is the canonical warehouse")
        return None
    env = (os.environ.get("DIME_ENV") or "").strip().lower()
    if env not in DEV_ENVS and not scratch_db:
        print("refusing: set DIME_ENV=dev or pass --scratch-db")
        return None
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=f"Scrape basketball-reference league pages into {TABLE}. "
                    "Seasons already in the table are skipped.")
    ap.add_argument("--seasons", default="2025-26")
    ap.add_argument("--scratch-db", default="")
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    try:
        seasons = [s.strip() for s in str(ns.seasons).split(",") if s.strip()]
        for season in seasons:
            _start_year(season)
    except ValueError as exc:
        print(f"refusing: {exc}")
        return 1
    if ns.dry_run:
        for season in seasons:
            print(f"{TABLE} {season} {ENTITY}")
        print(f"units: {len(seasons)}")
        return 0
    target = resolve_target(ns.scratch_db)
    if target is None:
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    prior_db_path, prior_lock_path = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    try:
        try:
            report = run(seasons)
        except SeasonFetchError as exc:
            print(f"FAIL {exc}", flush=True)
            return 1
        for season in report["skipped"]:
            print(f"{TABLE} {season}: already loaded, skipped")
        for season in sorted(report["loaded"]):
            print(f"{TABLE} {season}: {report['loaded'][season]} rows")
        print(f"{TABLE}: {len(report['loaded'])} seasons loaded, "
              f"{report['rows']} rows, {len(report['skipped'])} skipped")
        return 0
    finally:
        store.DB_PATH, store.LOCK_PATH = prior_db_path, prior_lock_path


if __name__ == "__main__":
    raise SystemExit(main())
