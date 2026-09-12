"""Seed full 2025-26 player game logs from Basketball-Reference into the warehouse.

For every player page (https://www.basketball-reference.com/<player path>):
  - parses table #player_game_log_reg -> silver_player_gamelogs (regular season)
  - parses table #player_game_log_post -> silver_playoff_gamelogs (playoffs)

Resumable: progress is tracked in seed_bbref_gamelogs_progress.json (same dir);
already-done players are skipped on re-run. Per-player replacement makes re-runs
idempotent (that player's 2025-26 rows are deleted and re-inserted fresh).

Rate limit: 3s between pages; on HTTP 429 backs off to 60s + 10s delays and continues.

Usage: ./backend/.venv/bin/python backend/scripts/seed_bbref_gamelogs.py [--limit N]
"""

import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import polars as pl
import requests
from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.sources.base import FetchMeta, FetchResult

HERE = Path(__file__).resolve().parent
IDS_FILE = HERE / "seed_bbref_gamelogs_player_ids.txt"
PROGRESS_FILE = HERE / "seed_bbref_gamelogs_progress.json"
LOG_FILE = HERE / "seed_bbref_gamelogs.log"

SEASON = "2025-26"
SEASON_ID = "22025"
SOURCE = "basketball-reference"
BASE = "https://www.basketball-reference.com/"
DELAY_S = 3.0
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

# Target column order (matches existing silver tables; provenance added by store.save_frame)
COLS = [
    "SEASON_ID", "Player_ID", "Game_ID", "GAME_DATE", "MATCHUP", "WL",
    "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
    "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "STL",
    "BLK", "TOV", "PF", "PTS", "PLUS_MINUS", "VIDEO_AVAILABLE",
]


def log(msg: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as fh:
        fh.write(line + "\n")


def strip_suffix(name: str) -> str:
    """Remove a trailing generational suffix (Jr, Sr, II, III, IV, optional period)."""
    return re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", name.strip(), flags=re.IGNORECASE)


def norm_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


def loose_key(name: str) -> str:
    """Last-name + first-initial fallback key, e.g. 'Mo Bamba' -> 'bambam'."""
    base = strip_suffix(name)
    parts = base.split()
    if len(parts) < 2:
        return norm_name(base)
    return norm_name(parts[-1]) + norm_name(parts[0])[:1]


# bbref display name -> warehouse canonical name (both resolved suffix-stripped).
ALIAS_TARGETS = {
    "Jimmy Butler": "Jimmy Butler III",
    "Bobby Portis": "Bobby Portis Jr.",
    "Ron Holland": "Ronald Holland II",
    "DaRon Holmes": "DaRon Holmes II",
    "Trey Jemison": "Trey Jemison III",
    "Walter Clayton": "Walter Clayton Jr.",
    "Xavier Tillman Sr.": "Xavier Tillman",
    "Tre Scott": "Trevon Scott",
    "Adama-Alpha Bal": "Adama Bal",
}


def build_alias_map(name_map: dict) -> dict:
    """Resolve ALIAS_TARGETS to warehouse Player_IDs via the suffix-stripped map."""
    alias_map: dict = {}
    for alias, target in ALIAS_TARGETS.items():
        pid = name_map.get(norm_name(strip_suffix(target)))
        if pid is None:
            log(f"WARN alias target not in warehouse map: {target!r} (alias {alias!r}), skipping")
            continue
        alias_map[norm_name(strip_suffix(alias))] = pid
    log(f"alias map: {len(alias_map)} entries")
    return alias_map


def load_name_map() -> dict:
    """NBA Player_ID lookup from silver_hist_player_seasons (2025-26 season).

    NOTE: must NOT use read_only=True here. DuckDB caches the database
    instance per path within a process, so a read-only connect first
    poisons every later read-write connect in this process ("attached in
    read-only mode"). This script writes, so open read-write.
    """
    con = store.connect()
    try:
        rows = con.execute(
            "SELECT player_id, player_name FROM silver_hist_player_seasons WHERE season = 2026"
        ).fetchall()
    finally:
        con.close()
    if not rows:
        # Fallback: warehouse has no 2025-26 slice yet - use nba_api's
        # bundled static player list (local, no network).
        from nba_api.stats.static import players as _static_players
        rows = [(r["id"], r["full_name"]) for r in _static_players.get_players()]
        log(f"name map fallback: nba_api static list ({len(rows)} players, all-time)")
    mapping: dict = {}
    for pid, name in rows:
        key = norm_name(strip_suffix(name or ""))
        if not key:
            continue
        if key in mapping and mapping[key] != pid:
            log(f"WARN duplicate normalized name {name!r} -> {pid} (kept {mapping[key]})")
            continue
        mapping[key] = pid
    # Loose last-name+initial keys for nickname mismatches (bbref 'Mo Bamba'
    # vs nba_api 'Mohamed Bamba'). Collision-safe: ambiguous keys dropped.
    loose: dict = {}
    collide: set = set()
    for pid, name in rows:
        lk = loose_key(name or "")
        if lk in mapping or lk in loose and loose[lk] != pid:
            collide.add(lk)
            loose.pop(lk, None)
            continue
        if lk not in collide:
            loose[lk] = pid
    for lk in collide:
        loose.pop(lk, None)
    mapping.update(loose)
    log(f"name map: {len(mapping)} entries ({len(loose)} loose keys)")
    return mapping


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"done": [], "failed": {}}


def save_progress(prog: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(prog, indent=1))


def parse_int(text: str):
    text = (text or "").strip().replace("+", "")
    if text in ("", "—", "-"):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_float(text: str):
    text = (text or "").strip()
    if text in ("", "—", "-"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_minutes(text: str):
    text = (text or "").strip()
    m = re.match(r"(\d+):(\d+)", text)
    if not m:
        return None
    return int(m.group(1))  # floor minutes; target column is BIGINT


def nba_date(iso: str) -> str:
    """2025-11-18 -> 'Nov 18, 2025' (matches existing GAME_DATE format)."""
    try:
        dt = datetime.strptime(iso.strip(), "%Y-%m-%d")
        return dt.strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return iso


def cell(row, stat: str) -> str:
    tds = row.xpath(f'./td[@data-stat="{stat}"]|./th[@data-stat="{stat}"]')
    return tds[0].text_content().strip() if tds else ""


def parse_gamelog_table(table, nba_id: int) -> list:
    """Parse one bbref player gamelog table into target-schema rows.

    Skips header-repeat rows and Inactive (partial_table) rows which have no stats.
    """
    rows_out = []
    for row in table.xpath("./tbody/tr"):
        if row.get("class") == "thead":
            continue
        mp_txt = cell(row, "mp")
        if ":" not in mp_txt:
            continue  # Inactive / no-stat row
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


def fetch_page(session: requests.Session, url: str, delay_holder: dict) -> str | None:
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


def page_player_name(doc) -> str | None:
    h1 = doc.xpath("//h1")
    if not h1:
        return None
    name = h1[0].text_content().strip()
    # bbref h1: "LeBron James 2025-26 Game Log"
    name = re.sub(r"\s+\d{4}-\d{2}\s+Game Log$", "", name).strip()
    return name or None


def save_rows(rows: list, table: str, nba_id: int, season: str) -> int:
    if not rows:
        return 0
    frame = pl.DataFrame(rows, schema=COLS)
    result = FetchResult(frame=frame, meta=FetchMeta(source=SOURCE, season=season))
    return store.save_frame(table, result, entity=f"player:{nba_id}")


def main() -> None:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    player_paths = [l.strip() for l in IDS_FILE.read_text().splitlines() if l.strip()]
    if limit:
        player_paths = player_paths[:limit]

    name_map = load_name_map()
    alias_map = build_alias_map(name_map)
    prog = load_progress()
    done = set(prog.get("done", []))
    failed = prog.get("failed", {})

    session = requests.Session()
    delay_holder = {"delay": DELAY_S}
    counts = {"ok": 0, "rs_rows": 0, "po_rows": 0, "no_name_match": 0,
              "no_tables": 0, "fetch_fail": 0}

    for i, path in enumerate(player_paths, 1):
        pid = path.rsplit("/", 1)[-1].replace(".html", "")
        if pid in done:
            continue
        # bbref gamelog pages: /players/x/xxxxxx01/gamelog/2026  (2026 = 2025-26 season)
        url = BASE + path[:-len(".html")] + "/gamelog/2026"
        page_text = fetch_page(session, url, delay_holder)
        try:
            if page_text is None:
                failed[pid] = "fetch failed or 404"
                counts["fetch_fail"] += 1
                log(f"[{i}/{len(player_paths)}] {pid}: fetch failed, skipping")
                continue
            doc = html.fromstring(page_text)
            pname = page_player_name(doc)
            if not pname:
                failed[pid] = "no h1 player name"
                counts["no_name_match"] += 1
                log(f"[{i}/{len(player_paths)}] {pid}: no player name found, skipping")
                continue
            nba_id = name_map.get(norm_name(strip_suffix(pname)))
            if nba_id is None:
                nba_id = alias_map.get(norm_name(strip_suffix(pname)))
            if nba_id is None:
                nba_id = name_map.get(loose_key(pname))
            if nba_id is None:
                failed[pid] = f"name mismatch: {pname!r}"
                counts["no_name_match"] += 1
                log(f"[{i}/{len(player_paths)}] {pid}: name {pname!r} not in warehouse map, skipping")
                continue
            rs_tables = doc.xpath('//table[@id="player_game_log_reg"]')
            po_tables = doc.xpath('//table[@id="player_game_log_post"]')
            if not rs_tables and not po_tables:
                # e.g. did not play in 2025-26 (Achiuwa) - not an error, mark done
                done.add(pid)
                counts["no_tables"] += 1
                log(f"[{i}/{len(player_paths)}] {pid} ({pname}): no 2025-26 gamelog tables, skipping")
                continue
            rs_rows = parse_gamelog_table(rs_tables[0], nba_id) if rs_tables else []
            po_rows = parse_gamelog_table(po_tables[0], nba_id) if po_tables else []
            n_rs = save_rows(rs_rows, "silver_player_gamelogs", nba_id, SEASON)
            n_po = save_rows(po_rows, "silver_playoff_gamelogs", nba_id, SEASON)
            counts["ok"] += 1
            counts["rs_rows"] += n_rs
            counts["po_rows"] += n_po
            done.add(pid)
            failed.pop(pid, None)  # clear stale failure on successful retry
            if i % 25 == 0 or i == len(player_paths):
                log(f"[{i}/{len(player_paths)}] {pid} ({pname}): rs={n_rs} po={n_po} "
                    f"(totals: ok={counts['ok']} rs={counts['rs_rows']} po={counts['po_rows']})")
        except Exception as exc:  # never crash the whole run on one player
            failed[pid] = f"exception: {exc!r}"[:200]
            counts["fetch_fail"] += 1
            log(f"[{i}/{len(player_paths)}] {pid}: EXCEPTION {exc!r}")
        prog["done"] = sorted(done)
        prog["failed"] = failed
        save_progress(prog)

    log(f"DONE. ok={counts['ok']} rs_rows={counts['rs_rows']} po_rows={counts['po_rows']} "
        f"name_mismatch={counts['no_name_match']} no_tables={counts['no_tables']} "
        f"fetch_fail={counts['fetch_fail']}")
    if failed:
        log(f"failed list ({len(failed)}): " + json.dumps(failed)[:2000])


if __name__ == "__main__":
    main()
