"""Append-only early-history backfill for seasons 2015-16..2020-21.

Usage: python -m scripts.seed_history_early [--seasons 2010,...,2021]
End-year keys: 2021 means 2020-21. Reuses the URL scheme, unify() logic,
and save pattern from seed_history.py without dropping any table.

Safety rules, enforced in code:
- NEVER removes a table. No table-removal statement exists in this file, and each
  incoming frame is aligned to the live table schema (ALTER ADD for new
  columns, NULL fill for missing ones) so store.save_frame never sees a
  column-set mismatch that would trigger its recreate path.
- NEVER writes a 2025-26 (end-year 2026) row. Seasons are validated at
  the CLI boundary and asserted again before every save.
- Per-season replace scope (entity season:<label>) so reruns converge
  instead of duplicating rows.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from seed_history import BASE, DATA, FILES, fetch, season_label, unify
except ImportError:  # pragma: no cover
    from scripts.seed_history import (  # type: ignore[no-redef]
        BASE,
        DATA,
        FILES,
        fetch,
        season_label,
        unify,
    )

import polars as pl

from app import store


def unify(frames: list) -> list:
    """Cross-season union that tolerates columns missing from frames[0].

    The shared seed_history.unify indexes frames[0].schema, which throws
    KeyError when an early-year parquet lacks a column a later year has
    (seen: hustle return_to_play flags). Dtype for each column comes from
    the first frame that carries it; numeric-only columns keep their
    dtype, mixed ones fall back to String.
    """
    order: dict[str, list[str]] = {}
    for f in frames:
        for name, dtype in f.schema.items():
            order.setdefault(name, []).append(str(dtype))
    target: dict[str, object] = {}
    for name, seen in order.items():
        kinds = set()
        for s in seen:
            kinds.add("num" if s.startswith(("Int", "UInt", "Float", "Double")) else "other")
        holder = next(f for f in frames if name in f.schema)
        target[name] = holder.schema[name] if kinds == {"num"} else pl.String
    out = []
    for f in frames:
        missing = [c for c in target if c not in f.columns]
        g = f
        for c in missing:
            g = g.with_columns(pl.lit(None).cast(target[c]).alias(c))
        out.append(g.select(list(target)).cast(
            {c: t for c, t in target.items()}, strict=False))
    return out

EARLIEST = 2010
LATEST = 2021
FORBIDDEN = 2026
HUSTLE_EARLIEST = 2016  # tracking data starts 2015-16; earlier years 404 upstream
KNOWN_GAPS = {("silver_hist_hustle", y) for y in range(EARLIEST, HUSTLE_EARLIEST)}
META_COLS = ("_source", "_season", "_fetched_at", "_entity")


def parse_seasons(raw: str) -> list[int]:
    years: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            y = int(part)
        except ValueError:
            raise SystemExit(f"bad --seasons entry: {part!r}")
        if y == FORBIDDEN:
            raise SystemExit("refusing to backfill end-year 2026 (2025-26)")
        if not (EARLIEST <= y <= LATEST):
            raise SystemExit(
                f"season {y} outside append-only window {EARLIEST}..{LATEST}"
            )
        if y not in years:
            years.append(y)
    if not years:
        raise SystemExit("no seasons requested")
    return sorted(years)


def _duckdb_to_polars(dtype: str):  # type: ignore[no-untyped-def]
    t = dtype.upper()
    if "INT" in t:
        return pl.Int64
    if any(k in t for k in ("FLOAT", "DOUBLE", "DECIMAL", "REAL")):
        return pl.Float64
    if "BOOL" in t:
        return pl.Boolean
    return pl.String


def _polars_to_duckdb(dtype: object) -> str:
    s = str(dtype)
    if s.startswith(("Int", "UInt")):
        return "BIGINT"
    if s.startswith(("Float", "Double", "Decimal")):
        return "DOUBLE"
    if s == "Boolean":
        return "BOOLEAN"
    return "VARCHAR"


def _live_columns(table: str) -> dict[str, str] | None:
    con = store.connect()
    try:
        existing = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if table not in existing:
            return None
        info = con.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1]: row[2] for row in sorted(info, key=lambda r: r[0])}
    finally:
        con.close()


def align_to_live(table: str, frame: pl.DataFrame) -> pl.DataFrame:
    live = _live_columns(table)
    if live is None:
        return frame
    live_data = {k: v for k, v in live.items() if k not in META_COLS}
    frame_cols = set(frame.columns)
    for col in frame.columns:
        if col not in live_data:
            con = store.connect()
            try:
                with store.write_guard():
                    cols_now = {
                        r[1]
                        for r in con.execute(
                            f"PRAGMA table_info({table})"
                        ).fetchall()
                    }
                    if col not in cols_now:
                        con.execute(
                            f'ALTER TABLE {table} ADD COLUMN "{col}" '
                            f"{_polars_to_duckdb(frame.schema[col])}"
                        )
            finally:
                con.close()
            live_data[col] = _polars_to_duckdb(frame.schema[col])
    out = frame
    for col, dtype in live_data.items():
        if col not in frame_cols:
            out = out.with_columns(
                pl.lit(None).cast(_duckdb_to_polars(dtype)).alias(col)
            )
    ordered = [c for c in live_data if c in out.columns]
    ordered += [c for c in out.columns if c not in live_data]
    return out.select(ordered)


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument(
        "--seasons", default="2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021"
    )
    ns = args.parse_args()
    years = parse_seasons(ns.seasons)
    DATA.mkdir(parents=True, exist_ok=True)

    from app.sources.base import FetchMeta, FetchResult

    counts: dict[tuple[str, str], int] = {}
    problems: list[str] = []
    documented: list[str] = []
    total = 0
    for table, (tag, pattern) in FILES.items():
        staged: list[tuple] = []
        for y in years:
            label = season_label(y)
            assert y != FORBIDDEN and label != "2025-26", label
            if (table, y) in KNOWN_GAPS:
                documented.append(f"{table} {label}: no upstream tracking data before 2015-16")
                counts[(table, label)] = 0
                continue
            name = pattern.format(y=y)
            dest = DATA / f"{table}_{y}.parquet"
            if not fetch(f"{BASE}/{tag}/{name}", dest):
                problems.append(f"{table} {label}: missing upstream asset")
                counts[(table, label)] = 0
                continue
            try:
                staged.append((y, pl.read_parquet(dest)))
            except Exception as exc:
                problems.append(f"{table} {label}: unreadable parquet ({exc})")
                counts[(table, label)] = 0
        if not staged:
            continue
        unified = unify([f for _, f in staged])
        for (y, _), frame in zip(staged, unified):
            label = season_label(y)
            assert y != FORBIDDEN and label != "2025-26", label
            ready = align_to_live(table, frame)
            res = FetchResult(
                frame=ready,
                meta=FetchMeta(source=f"sportsdataverse:{tag}", season=label),
            )
            n = store.save_frame(
                table,
                res,
                entity=f"season:{label}",
                replace_season=True,
            )
            counts[(table, label)] = n
            total += n
            print(f"{table} {label}: {n} rows")
            if n <= 0:
                problems.append(f"{table} {label}: loaded 0 rows")
    print("table | " + " | ".join(season_label(y) for y in years))
    for table in FILES:
        row = " | ".join(
            str(counts.get((table, season_label(y)), 0)) for y in years
        )
        print(f"{table} | {row}")
    print(f"early history rows loaded: {total}")
    missing = [
        f"{table} {season_label(y)}"
        for table in FILES
        for y in years
        if counts.get((table, season_label(y)), 0) <= 0
        and (table, y) not in KNOWN_GAPS
    ]
    if documented:
        print("DOCUMENTED GAPS (expected, non-failing):")
        for item in documented:
            print(f"  gap {item}")
    if missing or problems:
        print("COVERAGE GAPS:", file=sys.stderr)
        for item in problems + [
            f"{m}: no rows counted" for m in missing if m not in problems
        ]:
            print(f"  gap {item}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
