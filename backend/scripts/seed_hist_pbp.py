"""Seed play-by-play history from sportsdataverse-data parquet releases.

Usage: python -m scripts.seed_hist_pbp [--seasons 2021,2022,2023,2024,2025]
End-year keys: 2025 means 2024-25. End-year 2026 is never seeded here.
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

TAG = "nba_stats_pbp"
TABLE = "silver_hist_pbp"
PATTERN = "play_by_play_{y}.parquet"

MIN_ROWS = 100_000

EVENT_CHECKS = {
    "makes": ("Made Shot", "Made"),
    "misses": ("Missed Shot", "Missed"),
    "turnovers": ("Turnover", "turnover"),
    "fouls": ("Foul", "foul"),
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


def event_counts(frame: pl.DataFrame) -> dict[str, int]:
    cols = set(frame.columns)
    out: dict[str, int] = {}
    if "action_type" in cols:
        lowered = frame.get_column("action_type").cast(pl.String).str.to_lowercase()
        for key, (action, _) in EVENT_CHECKS.items():
            out[key] = lowered.eq(action.lower()).sum()
    else:
        out = {k: 0 for k in EVENT_CHECKS}
    if "shot_result" in cols:
        shot = frame.get_column("shot_result").cast(pl.String)
        if out.get("makes", 0) == 0:
            out["makes"] = shot.eq("Made").sum()
        if out.get("misses", 0) == 0:
            out["misses"] = shot.eq("Missed").sum()
    if "description" in cols:
        desc = frame.get_column("description").cast(pl.String).str.to_lowercase()
        for key, (_, keyword) in EVENT_CHECKS.items():
            if key in ("turnovers", "fouls") and out.get(key, 0) == 0:
                out[key] = desc.str.contains(keyword.lower(), literal=True).sum()
    return {k: int(v) for k, v in out.items()}


def parse_years(raw: str) -> list[int]:
    years = [int(y.strip()) for y in raw.split(",") if y.strip()]
    if 2026 in years:
        print("refusing end-year 2026: pbp seed covers 2021..2025 only")
        raise SystemExit(1)
    bad = [y for y in years if y < 2021 or y > 2025]
    if bad:
        print(f"season out of range {bad}: pbp seed covers 2021..2025 only")
        raise SystemExit(1)
    if not years:
        print("no seasons requested")
        raise SystemExit(1)
    return years


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--seasons", default="2021,2022,2023,2024,2025")
    ns = args.parse_args()
    years = parse_years(ns.seasons)
    DATA.mkdir(parents=True, exist_ok=True)

    from app.sources.base import FetchMeta, FetchResult

    staged: list[tuple] = []
    coverage: dict[int, dict[str, int]] = {}
    for y in years:
        name = PATTERN.format(y=y)
        dest = DATA / f"{TABLE}_{y}.parquet"
        if not fetch(f"{BASE}/{TAG}/{name}", dest):
            print(f"FAIL season {season_label(y)}: download failed for {name}")
            raise SystemExit(1)
        frame = pl.read_parquet(dest)
        if frame.height <= MIN_ROWS:
            print(f"FAIL season {season_label(y)}: {frame.height} rows <= {MIN_ROWS}")
            raise SystemExit(1)
        counts = event_counts(frame)
        missing = [k for k, v in counts.items() if v <= 0]
        if missing:
            print(f"FAIL season {season_label(y)}: missing event types {missing}")
            raise SystemExit(1)
        staged.append((y, frame))
        coverage[y] = counts

    unified = unify([f for _, f in staged])
    total = 0
    for (y, _), frame in zip(staged, unified):
        res = FetchResult(
            frame=frame,
            meta=FetchMeta(source=f"sportsdataverse:{TAG}",
                           season=season_label(y)),
        )
        n = store.save_frame(table=TABLE, result=res,
                             entity=f"season:{season_label(y)}",
                             replace_season=True)
        total += n
        print(f"{TABLE} {season_label(y)}: {n} rows")

    print("season rows makes misses turnovers fouls gaps")
    for y in years:
        c = coverage[y]
        rows = staged[[s[0] for s in staged].index(y)][1].height
        gaps = ",".join(k for k, v in c.items() if v <= 0) or "none"
        print(f"{season_label(y)} {rows} {c['makes']} "
              f"{c['misses']} {c['turnovers']} {c['fouls']} {gaps}")
    print(f"pbp rows loaded: {total}")


if __name__ == "__main__":
    main()
