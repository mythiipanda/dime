from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from .._core import coerce_team_id
from ._helpers import _owned_connection, _warehouse_tables
from .news import _news_fetch, _news_match
from .standings import _injury_rows, _injury_team_rows

_NEWS_LIMIT = 10
_TXN_LIMIT = 15
_UPCOMING_LIMIT = 5
_DEFAULT_SINCE_DAYS = 14


def _team_abbr(team_id: int) -> str:
    from nba_api.stats.static import teams as _teams

    return next(
        (t["abbreviation"] for t in _teams.get_teams() if t["id"] == team_id),
        "",
    )


def _default_since() -> str:
    now = datetime.now(ZoneInfo("America/New_York"))
    return (now - timedelta(days=_DEFAULT_SINCE_DAYS)).strftime("%Y-%m-%d")


def _today() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _missing(section: str, table: str, seeder: str) -> dict[str, Any]:
    return {"ok": False,
            "error": f"{table} not in warehouse; run {seeder} to seed it.",
            "meta": {"table": table, "section": section}}


def _injuries_section(con, tables, abbr: str) -> dict[str, Any]:
    if "silver_injury_entries" in tables:
        rows = con.execute(
            """SELECT PLAYER, STATUS, ATHLETE_STATUS, INJURY, RETURN_ESTIMATE,
                      REPORT_DATE, SOURCE
               FROM silver_injury_entries WHERE TEAM_ABBR = ?
               ORDER BY REPORT_DATE DESC""",
            [abbr],
        ).fetchall()
        items = [
            {"player": r[0], "status": r[1], "athlete_status": r[2],
             "injury": r[3], "return_estimate": r[4],
             "date": str(r[5] or ""), "source": r[6]}
            for r in rows
        ]
        return {"ok": True, "rows": items,
                "meta": {"table": "silver_injury_entries",
                         "source": "warehouse"}}
    if "silver_injuries" in tables:
        raw = con.execute(
            "SELECT * FROM silver_injuries").fetchall()
        cols = [d[0] for d in con.description]
        rows = _injury_rows([dict(zip(cols, r)) for r in raw])
        items = _injury_team_rows(rows, abbr)
        out = []
        for row in items:
            for item in row.get("injuries") or []:
                athlete = item.get("athlete") or {}
                out.append({
                    "player": athlete.get("displayName", ""),
                    "status": item.get("status", ""),
                    "comment": item.get("shortComment", ""),
                    "date": str(item.get("date", "")),
                    "source": "espn",
                })
        return {"ok": True, "rows": out,
                "meta": {"table": "silver_injuries",
                         "source": "warehouse",
                         "note": "raw ESPN feed; silver_injury_entries gives the normalized view"}}
    return _missing("injuries", "silver_injury_entries", "seed_injury_news.py")


def _news_section(con, tables, abbr: str, since: str) -> dict[str, Any]:
    if "silver_news" not in tables:
        return _missing("news", "silver_news", "seed_injury_news.py")
    rows, meta = _news_fetch(con)
    items = [r for r in rows
             if _news_match(r, abbr, "")
             and (not since or str(r.get("published") or "")[:10] >= since)]
    for r in items:
        r["date"] = str(r.get("published") or "")
        r["source"] = r.get("source_feed")
    return {"ok": True, "rows": items[:_NEWS_LIMIT],
            "meta": {"table": "silver_news", "source": "warehouse",
                     "matched": len(items)}}


def _transactions_section(con, tables, abbr: str, team_id: int,
                          since: str) -> dict[str, Any]:
    if "silver_transactions" not in tables:
        return _missing("transactions", "silver_transactions",
                        "seed_recent_market.py")
    clauses = ["(team_id = ? OR upper(team) = ?)"]
    params: list[object] = [team_id, abbr]
    if since:
        clauses.append("txn_date >= ?")
        params.append(since)
    rows = con.execute(
        "SELECT txn_date, txn_type, player, detail FROM silver_transactions "
        "WHERE " + " AND ".join(clauses) + " ORDER BY txn_date DESC",
        params,
    ).fetchall()
    items = [{"date": str(r[0] or ""), "type": r[1], "player": r[2],
              "detail": r[3], "source": "warehouse:silver_transactions"}
             for r in rows]
    return {"ok": True, "rows": items[:_TXN_LIMIT],
            "meta": {"table": "silver_transactions", "source": "warehouse",
                     "matched": len(items)}}


def _last_result_section(con, tables, team_id: int) -> dict[str, Any]:
    if "silver_team_games" not in tables:
        return _missing("last_result", "silver_team_games", "seed_history.py")
    rows = con.execute(
        """SELECT GAME_DATE, MATCHUP, WL, PTS FROM silver_team_games
           WHERE Team_ID = ? AND WL IS NOT NULL
           ORDER BY GAME_DATE DESC LIMIT 1""",
        [team_id],
    ).fetchall()
    if not rows:
        return {"ok": True, "rows": [],
                "meta": {"table": "silver_team_games", "source": "warehouse",
                         "note": "no completed games on file"}}
    r = rows[0]
    return {"ok": True,
            "rows": [{"date": str(r[0] or ""), "matchup": r[1], "wl": r[2],
                      "pts": r[3], "source": "warehouse:silver_team_games"}],
            "meta": {"table": "silver_team_games", "source": "warehouse"}}


def _standings_section(con, tables, team_id: int) -> dict[str, Any]:
    if "silver_standings" not in tables:
        return _missing("standings", "silver_standings", "seed_history.py")
    rows = con.execute(
        """SELECT TeamCity, TeamName, Record, Conference, PlayoffRank,
                  LeagueRank, L10, strCurrentStreak
           FROM silver_standings WHERE TeamID = ? LIMIT 1""",
        [team_id],
    ).fetchall()
    if not rows:
        return {"ok": True, "rows": [],
                "meta": {"table": "silver_standings", "source": "warehouse",
                         "note": "team not in current standings"}}
    r = rows[0]
    return {"ok": True,
            "rows": [{"team": f"{r[0] or ''} {r[1] or ''}".strip(),
                      "record": r[2], "conference": r[3],
                      "playoff_rank": r[4], "league_rank": r[5],
                      "last_10": r[6], "streak": r[7],
                      "source": "warehouse:silver_standings"}],
            "meta": {"table": "silver_standings", "source": "warehouse"}}


def _after_date(con, tables, team_id: int) -> str:
    if "silver_team_games" not in tables:
        return _today()
    raw = con.execute(
        """SELECT GAME_DATE FROM silver_team_games
           WHERE Team_ID = ? AND WL IS NOT NULL
           ORDER BY GAME_DATE DESC LIMIT 1""",
        [team_id],
    ).fetchone()
    if not raw or not raw[0]:
        return _today()
    for fmt in ("%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(raw[0]), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return _today()


def _upcoming_section(con, tables, abbr: str,
                      after: str) -> dict[str, Any]:
    if "silver_schedule" not in tables:
        return _missing("upcoming", "silver_schedule", "seed_history.py")
    rows = con.execute(
        """SELECT date, name, season_display_name FROM silver_schedule
           WHERE team_abbreviation = ? AND date >= ?
           ORDER BY date LIMIT ?""",
        [abbr, after, _UPCOMING_LIMIT],
    ).fetchall()
    items = [{"date": str(r[0] or ""), "matchup": r[1], "season": r[2],
              "source": "warehouse:silver_schedule"} for r in rows]
    return {"ok": True, "rows": items,
            "meta": {"table": "silver_schedule", "source": "warehouse",
                     "after_date": after}}


@tool(description="GM morning brief for one team: injuries, news, transactions, "
                  "last result, standing, and upcoming schedule since a date. "
                  "Each item is dated and cited to its warehouse table. "
                  "Reads the warehouse only; never calls live endpoints.")
def get_team_daily_brief(team: str, since: str = "") -> dict[str, Any]:
    want = str(team or "").strip()
    if not want:
        return {"tool": "get_team_daily_brief", "ok": False,
                "error": "team is required (abbreviation, name, or id)"}
    try:
        team_id = coerce_team_id(want)
    except ValueError as exc:
        return {"tool": "get_team_daily_brief", "ok": False,
                "error": str(exc)[:200]}
    abbr = _team_abbr(team_id)
    since = str(since or "").strip() or _default_since()
    with _owned_connection(None, read_only=True) as con:
        tables = _warehouse_tables(con)
        sections = {
            "injuries": _injuries_section(con, tables, abbr),
            "news": _news_section(con, tables, abbr, since),
            "transactions": _transactions_section(con, tables, abbr, team_id,
                                                  since),
            "last_result": _last_result_section(con, tables, team_id),
            "standings": _standings_section(con, tables, team_id),
            "upcoming": _upcoming_section(
                con, tables, abbr, _after_date(con, tables, team_id)),
        }
    available = [k for k, s in sections.items() if s.get("ok")]
    unseeded = [k for k, s in sections.items() if not s.get("ok")]
    return {"tool": "get_team_daily_brief", "ok": True,
            "team": abbr, "team_id": team_id, "since": since,
            "rows": sections,
            "meta": {"source": "warehouse",
                     "generated_at": datetime.now(
                         ZoneInfo("America/New_York")).isoformat(),
                     "sections": available,
                     "unseeded_sections": unseeded}}
