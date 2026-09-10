"""Seed 2024-25 player game logs from Basketball-Reference into the warehouse.

Writes ONLY silver_bbref_gamelogs_2024_25 (regular season). Stays off the
2025-26 crew's tables (silver_player_gamelogs, silver_playoff_gamelogs) and
off the 2025-26 season entirely.

Season mapping: bbref gamelog/2025 is the 2024-25 season. SEASON label is
2024-25, SEASON_ID is 22024 (matches clamp_season("22024") == "2024-25"),
and NBA Player_IDs resolve from silver_hist_player_seasons where
season = 2025.

Pure parse helpers (cell, parse_int, parse_float, parse_minutes, nba_date,
norm_name, COLS) are reused from seed_bbref_gamelogs. Two pieces are local
on purpose: parse_gamelog_table stamps its module SEASON_ID so the base
version would tag rows with the wrong season, and fetch_page logs to its
module LOG_FILE so the base version would write into the 2025-26 crew log.

Resumable: progress lives in seed_bbref_gamelogs_2024_25_progress.json;
done players are skipped on re-run. Per-player DELETE+INSERT via
store.save_frame(entity) makes re-runs idempotent.

Rate limit: 3s between pages; on HTTP 429 backs off to 60s + 10s delays.

Player URL list: uses seed_bbref_gamelogs_player_ids.txt when present
(shared with the 2025-26 crew), else --ids-file, else stops with an
honest log instead of fabricating bbref slugs.

The coordinator schedules the live run. This script never runs here.

Usage: ./backend/.venv/bin/python backend/scripts/seed_bbref_gamelogs_2024_25.py [--limit N] [--ids-file PATH]
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import polars as pl
import requests
from lxml import html

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from seed_bbref_gamelogs import (  # noqa: E402
    COLS,
    HEADERS,
    cell,
    nba_date,
    norm_name,
    parse_float,
    parse_int,
    parse_minutes,
)

from app import store  # noqa: E402
from app.sources.base import FetchMeta, FetchResult  # noqa: E402

IDS_FILE = HERE / "seed_bbref_gamelogs_player_ids.txt"
PROGRESS_FILE = HERE / "seed_bbref_gamelogs_2024_25_progress.json"
LOG_FILE = HERE / "seed_bbref_gamelogs_2024_25.log"

SEASON = "2024-25"
SEASON_ID = "22024"
BBREF_YEAR = "2025"
HIST_SEASON = 2025
TABLE = "silver_bbref_gamelogs_2024_25"
SOURCE = "basketball-reference"
BASE = "https://www.basketball-reference.com/"
DELAY_S = 3.0

LEGACY_TABLES = ("silver_player_gamelogs", "silver_playoff_gamelogs")
assert TABLE not in LEGACY_TABLES


def log(msg: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as fh:
        fh.write(line + "\n")


def load_name_map_2024_25() -> dict:
    """NBA Player_ID lookup from silver_hist_player_seasons season 2025.

    Opens read-write like the base script: a read-only connect first would
    poison later read-write connects in this process.
    """
    con = store.connect()
    try:
        rows = con.execute(
            "SELECT player_id, player_name FROM silver_hist_player_seasons WHERE season = 2025"
        ).fetchall()
    finally:
        con.close()
    mapping: dict = {}
    for pid, name in rows:
        key = norm_name(name or "")
        if not key:
            continue
        if key in mapping and mapping[key] != pid:
            log(f"WARN duplicate normalized name {name!r} -> {pid} (kept {mapping[key]})")
            continue
        mapping[key] = pid
    log(f"name map: {len(mapping)} entries")
    return mapping


def load_player_paths(ids_file: Path | None = None) -> list:
    """bbref player paths, shared file first, explicit override, else empty."""
    candidates = [Path(ids_file)] if ids_file else [IDS_FILE]
    for cand in candidates:
        if cand.exists():
            return [l.strip() for l in cand.read_text().splitlines() if l.strip()]
    return []


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"done": [], "failed": {}}


def save_progress(prog: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(prog, indent=1))


def parse_gamelog_table_2024_25(table, nba_id: int) -> list:
    """Parse one bbref regular-season gamelog table into target rows.

    Same shape as the base parser with this season's SEASON_ID. Skips
    header-repeat rows and Inactive rows which carry no stats.
    """
    rows_out = []
    for row in table.xpath("./tbody/tr"):
        if row.get("class") == "thead":
            continue
        mp_txt = cell(row, "mp")
        if ":" not in mp_txt:
            continue
        iso_date = cell(row, "date")
        team = cell(row, "team_name_abbr")
        loc = cell(row, "game_location")
        opp = cell(row, "opp_name_abbr")
        matchup = f"{team} @ {opp}" if loc == "@" else f"{team} vs. {opp}"
        result = cell(row, "game_result")
        wl = result[:1] if result[:1] in ("W", "L") else None
        hrefs = row.xpath('./td[@data-stat="date"]/a/@href')
        if hrefs:
            game_id = hrefs[0].rsplit("/", 1)[-1].replace(".html", "")
        else:
            game_id = f"bbref-{iso_date}-{team}-{opp}"
        rows_out.append({
            "SEASON_ID": SEASON_ID,
            "Player_ID": nba_id,
            "Game_ID": game_id,
            "GAME_DATE": nba_date(iso_date),
            "MATCHUP": matchup,
            "WL": wl,
            "MIN": parse_minutes(mp_txt),
            "FGM": parse_int(cell(row, "fg")),
            "FGA": parse_int(cell(row, "fga")),
            "FG_PCT": parse_float(cell(row, "fg_pct")),
            "FG3M": parse_int(cell(row, "fg3")),
            "FG3A": parse_int(cell(row, "fg3a")),
            "FG3_PCT": parse_float(cell(row, "fg3_pct")),
            "FTM": parse_int(cell(row, "ft")),
            "FTA": parse_int(cell(row, "fta")),
            "FT_PCT": parse_float(cell(row, "ft_pct")),
            "OREB": parse_int(cell(row, "orb")),
            "DREB": parse_int(cell(row, "drb")),
            "REB": parse_int(cell(row, "trb")),
            "AST": parse_int(cell(row, "ast")),
            "STL": parse_int(cell(row, "stl")),
            "BLK": parse_int(cell(row, "blk")),
            "TOV": parse_int(cell(row, "tov")),
            "PF": parse_int(cell(row, "pf")),
            "PTS": parse_int(cell(row, "pts")),
            "PLUS_MINUS": parse_int(cell(row, "plus_minus")),
            "VIDEO_AVAILABLE": 0,
        })
    return rows_out


def assert_player_batch(rows: list, nba_id: int) -> None:
    """Row-count and identity checks for one player's batch, before save."""
    ids = [r["Game_ID"] for r in rows]
    assert len(ids) == len(set(ids)), f"duplicate Game_ID for player {nba_id}"
    for r in rows:
        assert r["SEASON_ID"] == SEASON_ID, f"wrong season {r['SEASON_ID']}"
        assert r["Player_ID"] == nba_id, f"wrong player {r['Player_ID']}"
        assert r["Game_ID"] and r["GAME_DATE"] and r["MATCHUP"]


def fetch_page_2024_25(session: requests.Session, url: str, delay_holder: dict) -> str | None:
    # Local copy of the base backoff loop; the base version logs into the
    # 2025-26 crew's log file, so reuse would pollute their run log.
    for attempt in range(4):
        time.sleep(delay_holder["delay"])
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as exc:
            log(f"WARN fetch error on {url} (attempt {attempt + 1}): {exc!r}")
            time.sleep(10 * (attempt + 1))
            continue
        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 429:
            log(f"429 on {url}; backing off 60s, future delays -> 10s")
            time.sleep(60)
            delay_holder["delay"] = 10.0
            continue
        if resp.status_code == 404:
            return None
        log(f"WARN {resp.status_code} on {url} (attempt {attempt + 1})")
        time.sleep(10)
    return None


def page_player_name_2024_25(doc) -> str | None:
    h1 = doc.xpath("//h1")
    if not h1:
        return None
    name = h1[0].text_content().strip()
    if name.endswith(" Game Log"):
        name = name[: -len(" Game Log")].strip()
    if name.endswith("2024-25"):
        name = name[: -len("2024-25")].strip()
    return name or None


def save_rows_2024_25(rows: list, nba_id: int) -> int:
    """Per-player replace into the 2024-25 table. Returns rows written."""
    if not rows:
        return 0
    assert TABLE not in LEGACY_TABLES
    frame = pl.DataFrame(rows, schema=COLS)
    result = FetchResult(frame=frame, meta=FetchMeta(source=SOURCE, season=SEASON))
    return store.save_frame(TABLE, result, entity=f"player:{nba_id}")


def build_coverage(targets: list, saved: dict, failed: dict, no_tables: set) -> list:
    gap = []
    for pid in targets:
        if pid in saved:
            gap.append({"player": pid, "status": "ok", "rows": saved[pid]})
        elif pid in no_tables:
            gap.append({"player": pid, "status": "no-gamelog-table", "rows": 0})
        elif pid in failed:
            gap.append({"player": pid, "status": failed[pid][:120], "rows": 0})
        else:
            gap.append({"player": pid, "status": "not-run", "rows": 0})
    return gap


def log_coverage(gap: list) -> None:
    missing = [g for g in gap if g["rows"] == 0]
    log(f"coverage: {len(gap) - len(missing)}/{len(gap)} players with rows")
    for g in missing:
        log(f"  gap {g['player']}: {g['status']}")


def main() -> None:
    limit = None
    ids_override = None
    if "--limit" in sys.argv:
        raw = sys.argv[sys.argv.index("--limit") + 1]
        limit = int(raw)
        if limit < 1:
            raise SystemExit("--limit must be >= 1")
    if "--ids-file" in sys.argv:
        ids_override = Path(sys.argv[sys.argv.index("--ids-file") + 1])
        if not ids_override.exists():
            raise SystemExit(f"--ids-file not found: {ids_override}")

    player_paths = load_player_paths(ids_override)
    if not player_paths:
        log("no player-id list file found (shared seed_bbref_gamelogs_player_ids.txt "
            "or --ids-file); nothing to fetch, stopping honestly")
        return
    if limit:
        player_paths = player_paths[:limit]

    name_map = load_name_map_2024_25()
    prog = load_progress()
    done = set(prog.get("done", []))
    failed = prog.get("failed", {})

    session = requests.Session()
    delay_holder = {"delay": DELAY_S}
    saved: dict = {}
    no_tables: set = set()
    counts = {"ok": 0, "rows": 0, "no_name_match": 0,
              "no_tables": 0, "fetch_fail": 0}

    for i, path in enumerate(player_paths, 1):
        pid = path.rsplit("/", 1)[-1].replace(".html", "")
        if pid in done:
            continue
        url = BASE + path[: -len(".html")] + f"/gamelog/{BBREF_YEAR}"
        page_text = fetch_page_2024_25(session, url, delay_holder)
        try:
            if page_text is None:
                failed[pid] = "fetch failed or 404"
                counts["fetch_fail"] += 1
                log(f"[{i}/{len(player_paths)}] {pid}: fetch failed, skipping")
                continue
            doc = html.fromstring(page_text)
            pname = page_player_name_2024_25(doc)
            if not pname:
                failed[pid] = "no h1 player name"
                counts["no_name_match"] += 1
                log(f"[{i}/{len(player_paths)}] {pid}: no player name found, skipping")
                continue
            nba_id = name_map.get(norm_name(pname))
            if nba_id is None:
                failed[pid] = f"name mismatch: {pname!r}"
                counts["no_name_match"] += 1
                log(f"[{i}/{len(player_paths)}] {pid}: name {pname!r} not in warehouse map, skipping")
                continue
            rs_tables = doc.xpath('//table[@id="player_game_log_reg"]')
            po_tables = doc.xpath('//table[@id="player_game_log_post"]')
            if po_tables:
                log(f"[{i}/{len(player_paths)}] {pid} ({pname}): playoff table present, out of scope, skipped")
            if not rs_tables:
                done.add(pid)
                no_tables.add(pid)
                counts["no_tables"] += 1
                log(f"[{i}/{len(player_paths)}] {pid} ({pname}): no 2024-25 regular-season table, skipping")
                continue
            rows = parse_gamelog_table_2024_25(rs_tables[0], nba_id)
            assert_player_batch(rows, nba_id)
            n = save_rows_2024_25(rows, nba_id)
            counts["ok"] += 1
            counts["rows"] += n
            saved[pid] = n
            done.add(pid)
            failed.pop(pid, None)
            if i % 25 == 0 or i == len(player_paths):
                log(f"[{i}/{len(player_paths)}] {pid} ({pname}): rows={n} "
                    f"(totals: ok={counts['ok']} rows={counts['rows']})")
        except Exception as exc:
            failed[pid] = f"exception: {exc!r}"[:200]
            counts["fetch_fail"] += 1
            log(f"[{i}/{len(player_paths)}] {pid}: EXCEPTION {exc!r}")
        prog["done"] = sorted(done)
        prog["failed"] = failed
        save_progress(prog)

    gap = build_coverage([p.rsplit("/", 1)[-1].replace(".html", "") for p in player_paths],
                         saved, failed, no_tables)
    prog["done"] = sorted(done)
    prog["failed"] = failed
    prog["coverage"] = gap
    save_progress(prog)
    log(f"DONE. ok={counts['ok']} rows={counts['rows']} "
        f"name_mismatch={counts['no_name_match']} no_tables={counts['no_tables']} "
        f"fetch_fail={counts['fetch_fail']}")
    log_coverage(gap)
    if failed:
        log(f"failed list ({len(failed)}): " + json.dumps(failed)[:2000])


if __name__ == "__main__":
    main()
