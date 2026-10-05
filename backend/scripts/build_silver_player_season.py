import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult

TABLE = "silver_player_season"
ENTITY = "league"

DATA_COLS = [
    "PLAYER_ID", "PLAYER", "TEAM", "AGE", "GP", "GS", "MPG",
    "PPG", "RPG", "APG", "SPG", "BPG",
    "FG_PCT", "FG3_PCT", "FT_PCT", "TS_PCT",
]

HIST_SOURCE = "silver_hist_player_seasons"
ADV_SOURCE = "silver_advanced"
LEADERS_SOURCE = "silver_leaders_pts"

ABSENT = "absent:no_source"


class SeasonBuildError(RuntimeError):
    pass


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


def _num(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def loaded_seasons() -> set[str]:
    try:
        con = store.connect(read_only=True)
    except Exception:
        return set()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if TABLE not in tables:
            return set()
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {TABLE} WHERE _season IS NOT NULL"
        ).fetchall()
        return {r[0] for r in rows if r and r[0]}
    except Exception:
        return set()
    finally:
        try:
            con.close()
        except Exception:
            pass


def source_seasons() -> list[str]:
    found: set[str] = set()
    try:
        con = store.connect(read_only=True)
    except Exception:
        return []
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table in (HIST_SOURCE, ADV_SOURCE, LEADERS_SOURCE):
            if table not in tables:
                continue
            try:
                rows = con.execute(
                    f"SELECT DISTINCT _season FROM {table}"
                    " WHERE _season IS NOT NULL"
                ).fetchall()
            except Exception:
                continue
            found.update(r[0] for r in rows if r and r[0])
    except Exception:
        return sorted(found)
    finally:
        try:
            con.close()
        except Exception:
            pass
    return sorted(s for s in found if _start_year_safe(s) is not None)


def _start_year_safe(season: str):
    try:
        return _start_year(season)
    except ValueError:
        return None


def coverage_label() -> str:
    seasons = source_seasons()
    if not seasons:
        return "no source seasons on hand"
    if len(seasons) == 1:
        return seasons[0]
    return f"{seasons[0]} through {seasons[-1]}"


def _prov(value: str) -> str:
    return value


def build_season_frame(season: str) -> pl.DataFrame:
    hist = store.read_frame_optional(
        HIST_SOURCE, "_season = ?", [season])
    if hist.height > 0:
        return _from_hist(hist, season)
    leaders = store.read_frame_optional(
        LEADERS_SOURCE, "_season = ?", [season])
    advanced = store.read_frame_optional(
        ADV_SOURCE, "_season = ?", [season])
    if leaders.height > 0:
        return _from_totals(leaders, advanced, season)
    if advanced.height > 0:
        return _from_totals(leaders, advanced, season)
    raise SeasonBuildError(
        f"{TABLE} {season}: no source rows in {HIST_SOURCE}, "
        f"{LEADERS_SOURCE}, or {ADV_SOURCE}; "
        f"sources cover {coverage_label()}")


def _from_hist(hist: pl.DataFrame, season: str) -> pl.DataFrame:
    rows: list[dict] = []
    for h in hist.to_dicts():
        rows.append({
            "PLAYER_ID": h.get("player_id"),
            "PLAYER": h.get("player_name"),
            "TEAM": h.get("team_abbreviation"),
            "AGE": _num(h.get("age")),
            "GP": _num(h.get("gp")),
            "GS": None,
            "MPG": _num(h.get("min")),
            "PPG": _num(h.get("pts")),
            "RPG": _num(h.get("reb")),
            "APG": _num(h.get("ast")),
            "SPG": _num(h.get("stl")),
            "BPG": _num(h.get("blk")),
            "FG_PCT": _num(h.get("fg_pct")),
            "FG3_PCT": _num(h.get("fg3_pct")),
            "FT_PCT": _num(h.get("ft_pct")),
            "TS_PCT": _num(h.get("ts_pct")),
            "_prov_PLAYER_ID": _prov(HIST_SOURCE),
            "_prov_PLAYER": _prov(HIST_SOURCE),
            "_prov_TEAM": _prov(HIST_SOURCE),
            "_prov_AGE": _prov(HIST_SOURCE),
            "_prov_GP": _prov(HIST_SOURCE),
            "_prov_GS": _prov(ABSENT),
            "_prov_MPG": _prov(HIST_SOURCE),
            "_prov_PPG": _prov(HIST_SOURCE),
            "_prov_RPG": _prov(HIST_SOURCE),
            "_prov_APG": _prov(HIST_SOURCE),
            "_prov_SPG": _prov(HIST_SOURCE),
            "_prov_BPG": _prov(HIST_SOURCE),
            "_prov_FG_PCT": _prov(HIST_SOURCE),
            "_prov_FG3_PCT": _prov(HIST_SOURCE),
            "_prov_FT_PCT": _prov(HIST_SOURCE),
            "_prov_TS_PCT": _prov(HIST_SOURCE),
        })
    return pl.DataFrame(rows, strict=False)


def _from_totals(leaders: pl.DataFrame, advanced: pl.DataFrame,
                 season: str) -> pl.DataFrame:
    if leaders.height == 0:
        raise SeasonBuildError(
            f"{TABLE} {season}: no source rows in {HIST_SOURCE}, "
            f"{LEADERS_SOURCE}, or {ADV_SOURCE}; "
            f"sources cover {coverage_label()}")
    adv_by_id: dict[str, dict] = {}
    for r in advanced.to_dicts():
        if r.get("PLAYER_ID") is not None:
            adv_by_id[str(r.get("PLAYER_ID"))] = r
    rows: list[dict] = []
    for r in leaders.to_dicts():
        gp = _num(r.get("GP"))
        if not gp:
            continue
        adv = adv_by_id.get(str(r.get("PLAYER_ID")), {})
        age = _num(adv.get("AGE"))
        ts = _num(adv.get("TS_PCT"))
        rows.append({
            "PLAYER_ID": r.get("PLAYER_ID"),
            "PLAYER": r.get("PLAYER"),
            "TEAM": r.get("TEAM"),
            "AGE": age,
            "GP": gp,
            "GS": None,
            "MPG": _rate(r.get("MIN"), gp),
            "PPG": _rate(r.get("PTS"), gp),
            "RPG": _rate(r.get("REB"), gp),
            "APG": _rate(r.get("AST"), gp),
            "SPG": _rate(r.get("STL"), gp),
            "BPG": _rate(r.get("BLK"), gp),
            "FG_PCT": _num(r.get("FG_PCT")),
            "FG3_PCT": _num(r.get("FG3_PCT")),
            "FT_PCT": _num(r.get("FT_PCT")),
            "TS_PCT": ts,
            "_prov_PLAYER_ID": _prov(LEADERS_SOURCE),
            "_prov_PLAYER": _prov(LEADERS_SOURCE),
            "_prov_TEAM": _prov(LEADERS_SOURCE),
            "_prov_AGE": _prov(ADV_SOURCE if age is not None else ABSENT),
            "_prov_GP": _prov(LEADERS_SOURCE),
            "_prov_GS": _prov(ABSENT),
            "_prov_MPG": _prov(f"{LEADERS_SOURCE}:MIN/GP"),
            "_prov_PPG": _prov(f"{LEADERS_SOURCE}:PTS/GP"),
            "_prov_RPG": _prov(f"{LEADERS_SOURCE}:REB/GP"),
            "_prov_APG": _prov(f"{LEADERS_SOURCE}:AST/GP"),
            "_prov_SPG": _prov(f"{LEADERS_SOURCE}:STL/GP"),
            "_prov_BPG": _prov(f"{LEADERS_SOURCE}:BLK/GP"),
            "_prov_FG_PCT": _prov(LEADERS_SOURCE),
            "_prov_FG3_PCT": _prov(LEADERS_SOURCE),
            "_prov_FT_PCT": _prov(LEADERS_SOURCE),
            "_prov_TS_PCT": _prov(ADV_SOURCE if ts is not None else ABSENT),
        })
    if not rows:
        raise SeasonBuildError(
            f"{TABLE} {season}: {LEADERS_SOURCE} returned no usable rows; "
            f"sources cover {coverage_label()}")
    return pl.DataFrame(rows, strict=False)


def _rate(total: object, gp: float) -> float | None:
    value = _num(total)
    if value is None or not gp:
        return None
    return value / gp


def require_complete(season: str, frame: pl.DataFrame) -> None:
    if frame.height == 0:
        raise SeasonBuildError(
            f"{TABLE} {season}: builder produced no rows; "
            f"sources cover {coverage_label()}")


def seed_season(season: str, frame: pl.DataFrame | None = None) -> int:
    built = frame if frame is not None else build_season_frame(season)
    require_complete(season, built)
    res = FetchResult(
        frame=built,
        meta=FetchMeta(source="warehouse-union", season=season),
    )
    return store.save_frame(TABLE, res, entity=ENTITY, replace_season=True)


def run(seasons: list[str]) -> dict:
    done = loaded_seasons()
    skipped: list[str] = []
    loaded: dict[str, int] = {}
    for season in seasons:
        if season in done:
            skipped.append(season)
            continue
        loaded[season] = seed_season(season)
        done.add(season)
    return {"loaded": loaded, "skipped": skipped,
            "rows": sum(loaded.values())}


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
        description=f"Build {TABLE} from warehouse sources. "
                    "Seasons already in the table are skipped.")
    ap.add_argument("--seasons", default="")
    ap.add_argument("--first", default="")
    ap.add_argument("--last", default="")
    ap.add_argument("--scratch-db", default="")
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    target = resolve_target(ns.scratch_db)
    if target is None:
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    prior_db_path, prior_lock_path = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    try:
        return _run(ns)
    finally:
        store.DB_PATH, store.LOCK_PATH = prior_db_path, prior_lock_path


def _run(ns) -> int:
    if ns.seasons.strip():
        seasons = [s.strip() for s in ns.seasons.split(",") if s.strip()]
    elif ns.first.strip() or ns.last.strip():
        if not ns.first.strip() or not ns.last.strip():
            print("refusing: --first and --last must be paired")
            return 1
        try:
            seasons = season_slugs(ns.first.strip(), ns.last.strip())
        except ValueError as exc:
            print(f"refusing: {exc}")
            return 1
    else:
        seasons = source_seasons()
        if not seasons:
            print(f"refusing: no source seasons on hand ({coverage_label()})")
            return 1
    if ns.dry_run:
        for season in seasons:
            print(f"{TABLE} {season} {ENTITY}")
        print(f"units: {len(seasons)}")
        return 0
    try:
        report = run(seasons)
    except SeasonBuildError as exc:
        print(f"FAIL {exc}", flush=True)
        return 1
    for season in report["skipped"]:
        print(f"{TABLE} {season}: already loaded, skipped")
    for season in sorted(report["loaded"]):
        print(f"{TABLE} {season}: {report['loaded'][season]} rows")
    print(f"{TABLE}: {len(report['loaded'])} seasons loaded, "
          f"{report['rows']} rows, {len(report['skipped'])} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
