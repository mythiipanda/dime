import json
from typing import Any

from langchain_core.tools import tool

from ._helpers import _owned_connection, _pkg, _warehouse_tables


def _loads(raw: object) -> list:
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        return []
    return parsed if isinstance(parsed, list) else []


def _news_fetch(con) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = con.execute(
        """SELECT HEADLINE, PUBLISHED, URL, SOURCE_FEED, SUMMARY,
                  PLAYERS, TEAMS, _fetched_at
           FROM silver_news
           ORDER BY PUBLISHED DESC""").fetchall()
    out: list[dict[str, Any]] = []
    fetched_at = ""
    feeds = set()
    for headline, published, url, feed, summary, players, teams, f_at in rows:
        fetched_at = fetched_at or str(f_at or "")
        feeds.add(str(feed or ""))
        out.append({
            "headline": headline,
            "published": str(published or ""),
            "url": url,
            "source_feed": feed,
            "summary": summary or "",
            "players": _loads(players),
            "teams": _loads(teams),
        })
    meta = {"feeds": sorted(feeds), "fetched_at": fetched_at,
            "items": len(out)}
    return out, meta


def _news_match(row: dict[str, Any], team: str, player: str) -> bool:
    if player:
        low = player.lower()
        if not any(low in str(p).lower() for p in row["players"]) \
                and low not in str(row["headline"]).lower() \
                and low not in str(row["summary"]).lower():
            return False
    if team:
        want = team.strip().upper()
        if want not in row["teams"] \
                and team.lower() not in str(row["headline"]).lower() \
                and team.lower() not in str(row["summary"]).lower():
            return False
    return True


@tool(description="Recent NBA news items from warehouse-seeded RSS feeds "
                  "(headline, published, url, players/teams mentioned). "
                  "Optional team abbreviation or player-name filter. "
                  "Reads the warehouse only; refresh with "
                  "seed_injury_news.py.")
def get_news_feed(team: str = "", player: str = "",
                  limit: int = 15) -> dict[str, Any]:
    _pkg()
    try:
        limit = max(1, min(int(limit or 15), 100))
    except (TypeError, ValueError):
        limit = 15
    with _owned_connection(None, read_only=True) as con:
        if "silver_news" not in _warehouse_tables(con):
            return {"tool": "get_news_feed", "ok": False,
                    "error": "silver_news not in warehouse; run "
                             "seed_injury_news.py to load RSS feeds."}
        rows, feed_meta = _news_fetch(con)
    rows = [r for r in rows if _news_match(r, team, player)]
    meta = {"source": "warehouse", "table": "silver_news",
            **feed_meta, "matched": len(rows)}
    if not rows:
        meta["warning"] = ("no news items matched; feed coverage ends at "
                           "the last ingest")
    return {"tool": "get_news_feed", "ok": True,
            "rows": rows[:limit], "meta": meta}
