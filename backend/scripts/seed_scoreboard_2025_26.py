"""Seed silver_scoreboard for the full 2025-26 season from ESPN.

stats.nba.com is unreachable from the build sandbox (read timeouts), so
the nba_api scoreboard path cannot seed. ESPN's public scoreboard JSON
covers every date and is reachable. Rows are written in the nba_api
column shape the rest-advantage tool and datasets API already read:
GAME_ID is synthesized with nba prefix semantics (002=regular,
005=play-in, 004=playoffs) because rest.py classifies season_type from
that prefix; regular/playoff boundary is derived from the warehouse's
own seeded rows (last regular game 2026-04-12, playoffs from 04-18).

Resumable: each date replaces its own entity rows (date:MM/DD/YYYY).
    python scripts/seed_scoreboard_2025_26.py
"""
import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store

SEASON = "2025-26"
START = dt.date(2025, 10, 21)
END = dt.date(2026, 6, 21)
REGULAR_END = dt.date(2026, 4, 12)   # last seeded regular game (0022501186)
PLAYOFF_START = dt.date(2026, 4, 18)  # play-in sits between, prefix 005

ABBR = {"GS": "GSW", "SA": "SAS", "NY": "NYK", "NO": "NOP",
        "WSH": "WAS", "UTAH": "UTA"}

NBA30 = {"ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET",
         "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN",
         "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS",
         "TOR", "UTA", "WAS"}

# Stable nba_api team ids (verified against the warehouse's original
# rows, e.g. BOS=1610612738). preview.py matches games on these.
TEAM_IDS = {"ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751,
            "CHA": 1610612766, "CHI": 1610612741, "CLE": 1610612739,
            "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765,
            "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
            "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763,
            "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750,
            "NOP": 1610612740, "NYK": 1610612752, "OKC": 1610612760,
            "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
            "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759,
            "TOR": 1610612761, "UTA": 1610612762, "WAS": 1610612764}

COLS = ["GAME_DATE_EST", "GAME_SEQUENCE", "GAME_ID", "GAME_STATUS_ID",
        "GAME_STATUS_TEXT", "GAMECODE", "HOME_TEAM_ID", "VISITOR_TEAM_ID",
        "SEASON", "LIVE_PERIOD", "LIVE_PC_TIME",
        "NATL_TV_BROADCASTER_ABBREVIATION", "HOME_TV_BROADCASTER_ABBREVIATION",
        "AWAY_TV_BROADCASTER_ABBREVIATION", "LIVE_PERIOD_TIME_BCAST",
        "ARENA_NAME", "WH_STATUS", "WNBA_COMMISSIONER_FLAG",
        "HOME_TEAM_PTS", "VISITOR_TEAM_PTS", "HOME_TEAM_ABBREVIATION",
        "VISITOR_TEAM_ABBREVIATION", "_source", "_season", "_fetched_at",
        "_entity"]


def fetch_day(d: dt.date) -> list[dict]:
    url = ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/"
           f"scoreboard?dates={d:%Y%m%d}&limit=100")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    out = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed"):
            continue
        home = next((c for c in comp.get("competitors", [])
                     if c.get("homeAway") == "home"), None)
        away = next((c for c in comp.get("competitors", [])
                     if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        # All-Star weekend events (STARS/STRIPES/WORLD/USA) are not
        # regular-season games; the NBA Cup final (neutral-site,
        # mid-December) does not count in the standings either.
        _ha0 = ABBR.get(home["team"]["abbreviation"],
                        home["team"]["abbreviation"])
        _aa0 = ABBR.get(away["team"]["abbreviation"],
                        away["team"]["abbreviation"])
        if _ha0 not in NBA30 or _aa0 not in NBA30:
            continue
        if ((comp.get("venue") or {}).get("fullName") == "T-Mobile Arena"
                and ev.get("date", "")[:10] == "2025-12-16"):
            continue
        ha = ABBR.get(home["team"]["abbreviation"],
                      home["team"]["abbreviation"])
        aa = ABBR.get(away["team"]["abbreviation"],
                      away["team"]["abbreviation"])
        try:
            hp, ap = int(home["score"]), int(away["score"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({"home": ha, "away": aa, "hp": hp, "ap": ap,
                    "arena": (comp.get("venue") or {}).get("fullName")})
    return out


def prefix_for(d: dt.date) -> str:
    if d <= REGULAR_END:
        return "002"
    if d >= PLAYOFF_START:
        return "004"
    return "005"


def main() -> None:
    days = (END - START).days + 1
    total_games = 0
    seq = {"002": 0, "004": 0, "005": 0}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for i in range(days):
        d = START + dt.timedelta(days=i)
        try:
            games = fetch_day(d)
        except Exception as exc:  # noqa: BLE001 - log and continue
            print(f"ERR {d}: {exc}", flush=True)
            continue
        entity = f"date:{d:%m/%d/%Y}"
        with store.connect() as con:
            with store.write_guard():
                con.execute(
                    "DELETE FROM silver_scoreboard "
                    "WHERE _season = ? AND _entity = ?", [SEASON, entity])
                for gi, g in enumerate(games, 1):
                    # 2025-12-16 NBA Cup Final (NYK vs SAS, T-Mobile Arena):
                    # played but excluded from standings - not a regular-season game.
                    if d == dt.date(2025, 12, 16) and {g['home'], g['away']} == {'NYK', 'SAS'}:
                        continue
                    pf = prefix_for(d)
                    seq[pf] += 1
                    gid = f"{pf}25{seq[pf]:05d}"
                    con.execute(
                        f"INSERT INTO silver_scoreboard ({', '.join(COLS)})"
                        f" VALUES ({', '.join(['?'] * len(COLS))})",
                        [f"{d.isoformat()}T00:00:00", gi, gid, 3, "Final",
                         f"{d:%Y%m%d}/{g['away']}{g['home']}",
                         TEAM_IDS.get(g["home"]), TEAM_IDS.get(g["away"]),
                         "2025", None, None, None, None, None, None,
                         g["arena"], None, None, g["hp"], g["ap"],
                         g["home"], g["away"], "espn:scoreboard", SEASON,
                         now, entity])
        total_games += len(games)
        if (i + 1) % 30 == 0:
            print(f"{i + 1}/{days} days, {total_games} games", flush=True)
        time.sleep(0.15)
    print(f"DONE days={days} games={total_games} "
          f"regular_seq={seq['002']} playoff_seq={seq['004']}", flush=True)


if __name__ == "__main__":
    main()
