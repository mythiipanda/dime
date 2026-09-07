"""Seed five seasons of history from sportsdataverse-data parquet releases.

Usage: python -m scripts.seed_history [--seasons 2022,2023,2024,2025,2026]
End-year keys: 2026 means 2025-26. Missing assets skip gracefully.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
DATA = Path(__file__).resolve().parent.parent / "data" / "history"

FILES = {
    "silver_hist_possessions": ("nba_stats_possessions", "nba_possessions_{y}.parquet"),
    "silver_hist_gamelogs": ("nba_stats_player_game_logs", "player_game_logs_{y}.parquet"),
    "silver_hist_shots": ("nba_stats_shots", "shots_{y}.parquet"),
    "silver_hist_standings": ("nba_stats_standings", "standings_{y}.parquet"),
    "silver_hist_lineups": ("nba_stats_lineups", "lineups_{y}.parquet"),
    "silver_hist_hustle": (
        "nba_stats_hustle",
        "leaguehustlestatsplayer_regular-season_pergame_{y}.parquet",
    ),
}


def season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def fetch(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dime-seed/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
        return True
    except Exception as exc:
        print(f"skip {url.split('/')[-1]}: {str(exc)[:80]}")
        return False


def unify(frames: list) -> list:
    """Resolve cross-season type conflicts toward VARCHAR."""
    order: dict[str, list[str]] = {}
    for f in frames:
        for name, dtype in f.schema.items():
            order.setdefault(name, []).append(str(dtype))
    target: dict[str, object] = {}
    for name, seen in order.items():
        kinds = set()
        for s in seen:
            kinds.add("num" if s.startswith(("Int", "UInt", "Float", "Double")) else "other")
        target[name] = (
            frames[0].schema[name] if kinds == {"num"} else pl.String
        )
    out = []
    for f in frames:
        missing = [c for c in target if c not in f.columns]
        g = f
        for c in missing:
            g = g.with_columns(pl.lit(None).cast(target[c]).alias(c))
        out.append(g.select(list(target)).cast(
            {c: t for c, t in target.items()}, strict=False))
    return out


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--seasons", default="2022,2023,2024,2025,2026")
    ns = args.parse_args()
    years = [int(y) for y in ns.seasons.split(",")]
    DATA.mkdir(parents=True, exist_ok=True)

    from app.sources.base import FetchMeta, FetchResult

    con = store.connect()
    try:
        existing = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table in FILES:
            if table in existing:
                con.execute(f"DROP TABLE {table}")
    finally:
        con.close()

    total = 0
    for table, (tag, pattern) in FILES.items():
        staged: list[tuple] = []
        for y in years:
            name = pattern.format(y=y)
            dest = DATA / f"{table}_{y}.parquet"
            if not fetch(f"{BASE}/{tag}/{name}", dest):
                continue
            staged.append((y, pl.read_parquet(dest)))
        if not staged:
            continue
        unified = unify([f for _, f in staged])
        for (y, _), frame in zip(staged, unified):
            res = FetchResult(
                frame=frame,
                meta=FetchMeta(source=f"sportsdataverse:{tag}",
                               season=season_label(y)),
            )
            n = store.save_frame(table, res, entity=f"season:{season_label(y)}",
                                 replace_season=False)
            total += n
            print(f"{table} {season_label(y)}: {n} rows")
    print(f"history rows loaded: {total}")


if __name__ == "__main__":
    main()
