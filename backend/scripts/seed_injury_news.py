import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store
from shared.sources.base import FetchMeta, FetchResult

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
NEWS_FEEDS = [
    ("espn:nba-rss", "https://www.espn.com/espn/rss/nba/news"),
    ("cbssports:nba-rss", "https://www.cbssports.com/rss/headlines/nba/"),
    ("yahoo:nba-rss", "https://sports.yahoo.com/nba/rss/"),
]
NEWS_TABLE = "silver_news"
NEWS_SEASON = "news"
ENTITY = "league"
SLEEP_S = 2.0
MAX_ITEMS = 200


def norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", ascii_only.strip(),
                  flags=re.IGNORECASE).lower()


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


def _player_terms() -> list[tuple[str, str]]:
    from nba_api.stats.static import players
    terms = []
    for p in players.get_players():
        if not p.get("is_active"):
            continue
        full = str(p.get("full_name") or "").strip()
        if len(full) < 6:
            continue
        terms.append((norm(full), full))
    return terms


def _team_terms() -> list[tuple[str, str]]:
    from nba_api.stats.static import teams
    terms = []
    for t in teams.get_teams():
        abbr = str(t.get("abbreviation") or "")
        terms.append((norm(str(t.get("full_name") or "")), abbr))
        terms.append((norm(str(t.get("nickname") or "")), abbr))
    return terms


def _mentions(text: str, player_terms, team_terms):
    hay = " ".join(
        norm(re.sub(r"[^a-zA-Z0-9 ]", " ", text or "")).split())
    players_found = sorted({disp for key, disp in player_terms
                            if key and f" {key} " in f" {hay} "})
    teams_found = sorted({abbr for key, abbr in team_terms
                          if key and f" {key} " in f" {hay} "})
    return players_found, teams_found


def fetch_feed(feed_name: str, url: str) -> list[dict]:
    req = urllib.request.Request(url, headers=UA)
    raw = b""
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            res = urllib.request.urlopen(req, timeout=30)
            if res.status != 200:
                last_exc = RuntimeError(
                    f"feed {url} answered HTTP {res.status}")
                time.sleep(5 * (attempt + 1))
                continue
            raw = res.read()
            if raw.strip():
                break
        except Exception as exc:
            last_exc = exc
        time.sleep(5 * (attempt + 1))
    if not raw.strip():
        raise last_exc or RuntimeError(f"empty feed {url}")
    root = ET.fromstring(raw)
    player_terms = _player_terms()
    team_terms = _team_terms()
    rows = []
    for item in root.findall(".//item")[:MAX_ITEMS]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "")
        desc = " ".join(desc.split())
        pub = item.findtext("pubDate") or item.findtext("date") or ""
        try:
            published = parsedate_to_datetime(pub).astimezone(
                timezone.utc).isoformat()
        except (TypeError, ValueError):
            published = str(pub).strip()
        if not title:
            continue
        players_found, teams_found = _mentions(
            f"{title} {desc}", player_terms, team_terms)
        rows.append({
            "HEADLINE": title,
            "PUBLISHED": published,
            "URL": link,
            "SOURCE_FEED": feed_name,
            "SUMMARY": desc,
            "PLAYERS": json.dumps(players_found),
            "TEAMS": json.dumps(teams_found),
        })
    return rows


def load_news(dry_run: bool) -> int:
    rows: list[dict] = []
    for i, (name, url) in enumerate(NEWS_FEEDS):
        if i:
            time.sleep(SLEEP_S)
        try:
            got = fetch_feed(name, url)
        except Exception as exc:
            print(f"{name}: fetch failed {exc!r}")
            continue
        print(f"{name}: {len(got)} items")
        rows.extend(got)
    seen = set()
    deduped = []
    for r in rows:
        key = (norm(r["HEADLINE"]), r["SOURCE_FEED"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    frame = pl.DataFrame(deduped) if deduped else pl.DataFrame(
        schema={"HEADLINE": pl.Utf8, "PUBLISHED": pl.Utf8, "URL": pl.Utf8,
                "SOURCE_FEED": pl.Utf8, "SUMMARY": pl.Utf8,
                "PLAYERS": pl.Utf8, "TEAMS": pl.Utf8})
    if dry_run:
        print(f"news: {frame.height} rows (dry-run)")
        return 0
    fetched = datetime.now(timezone.utc).isoformat()
    res = FetchResult(frame=frame, meta=FetchMeta(
        source="rss:" + "+".join(n for n, _ in NEWS_FEEDS),
        season=NEWS_SEASON, fetched_at=fetched))
    n = store.save_frame(NEWS_TABLE, res, entity=ENTITY, replace_season=True)
    print(f"silver_news: {n} rows")
    return n


def load_injuries(season: str, dry_run: bool) -> int:
    from shared.sources import espn
    res = espn.injuries(season)
    if not res.ok:
        print("injuries fetch failed:", res.error)
        return 0
    if dry_run:
        print(f"silver_injuries: {res.frame.height} rows (dry-run)")
        return 0
    n = store.save_frame("silver_injuries", res, replace_season=True)
    print(f"silver_injuries: {n} rows")
    try:
        from scripts.normalize_injuries import save as _norm_save
        with store.connect() as _con:
            _norm_save(_con)
    except Exception as exc:
        print("injury entries normalize failed:", exc)
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-injuries", action="store_true")
    parser.add_argument("--skip-news", action="store_true")
    args = parser.parse_args(argv)

    target = resolve_target(args.scratch_db)
    if target is None:
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)

    old_db, old_lock = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    total = 0
    try:
        if not args.skip_injuries:
            total += load_injuries(args.season, args.dry_run)
        if not args.skip_news:
            total += load_news(args.dry_run)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
    print(f"rows loaded: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
