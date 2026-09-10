"""Oct 1-3 preseason gate for 2026-27. Read-only live checks, no warehouse writes.

Usage: python3 backend/scripts/preseason_gate_2026_27.py
Rerun Oct 1-3 from the fetch environment. Exit 0 = READY, 1 = NOT-READY, 2 = error.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ESPN_TMPL = "https://site.api.espn.com/apis/site/v2/sports/nba/scoreboard?dates={}"
DATES = ("20261003", "20261020")
ESPN_TIMEOUT_S = 15
NBA_TIMEOUT_S = 8
ESPN_HEADERS = {"User-Agent": "Dime-preseason-gate/1.0", "Accept": "application/json"}

NBA_SCOREBOARDV2 = (
    "https://stats.nba.com/stats/scoreboardv2?GameDate=10/03/2026&LeagueID=00"
)
NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}
CDN_SCHEDULE = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"

CHECKLIST_FILES = [
    "backend/app/tools/_core.py",
    "backend/app/subagents.py",
    "backend/app/datasets.py",
    "backend/app/routes.py",
    "backend/app/tools/league.py",
    "backend/app/tools/sim.py",
    "backend/app/graph.py",
    "backend/app/skills/compare_players.md",
    "backend/app/sources/cdn.py",
    "backend/app/sources/pbpstats.py",
    "backend/app/tools/headtohead.py",
    "backend/app/tools/gamelog.py",
    "backend/app/tools/player.py",
    "backend/app/tools/zone.py",
    "backend/app/tools/team.py",
]


def fetch_json(url, timeout, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, {"_http_error": str(e)}
    except Exception as e:
        return -1, {"_error": f"{type(e).__name__}: {e}"}


def summarize_espn(date, payload):
    events = payload.get("events", []) if isinstance(payload, dict) else []
    rows = []
    for ev in events:
        name = ev.get("shortName") or ev.get("name") or "?"
        comp = (ev.get("competitions") or [{}])[0]
        st = comp.get("status", {}).get("type", {}) if isinstance(comp, dict) else {}
        rows.append(
            f"{name} [{st.get('shortDetail') or st.get('state') or 'unknown'}]"
        )
    season = ((payload.get("season") or {}) if isinstance(payload, dict) else {}) or {}
    return events, rows, season


def check_espn():
    out = {}
    ok_all = True
    for date in DATES:
        status, payload = fetch_json(ESPN_TMPL.format(date), ESPN_TIMEOUT_S, ESPN_HEADERS)
        if status != 200 or not isinstance(payload, dict):
            print(f"[espn] {date}: HTTP {status} FAIL {payload}")
            out[date] = (0, [], {}, False)
            ok_all = False
            continue
        events, rows, season = summarize_espn(date, payload)
        ok = len(events) > 0
        ok_all = ok_all and ok
        out[date] = (len(events), rows, season, ok)
        label = season.get("displayName") or season.get("year") or "?"
        print(f"[espn] {date}: HTTP 200 games={len(events)} season={label}")
        for r in rows[:8]:
            print(f"  - {r}")
    return out, ok_all


def probe_nba():
    results = {}
    status, payload = fetch_json(NBA_SCOREBOARDV2, NBA_TIMEOUT_S, NBA_HEADERS)
    if status == 200:
        state = "reachable"
    elif status == -1:
        err = str(payload.get("_error", ""))
        state = "blocked (timeout/hang)" if "imeout" in err or "imed out" in err else f"blocked ({err[:80]})"
    else:
        state = f"blocked (HTTP {status})"
    print(f"[stats.nba.com] scoreboardv2: {state}")
    results["stats.nba.com"] = state
    try:
        req = urllib.request.Request(CDN_SCHEDULE)
        with urllib.request.urlopen(req, timeout=NBA_TIMEOUT_S) as resp:
            resp.read(64)
            cdn_state = f"reachable (HTTP {resp.status})"
    except urllib.error.HTTPError as e:
        cdn_state = f"blocked (HTTP {e.code})"
    except Exception as e:
        cdn_state = f"blocked ({type(e).__name__}: {e}"[:100] + ")"
    print(f"[cdn.nba.com] schedule: {cdn_state}")
    results["cdn.nba.com"] = cdn_state
    return results


def grep_pins(repo_root):
    pat = re.compile(r"2025-26")
    hits = {}
    app_dir = repo_root / "backend" / "app"
    for path in sorted(app_dir.rglob("*.py")) + sorted(
        (app_dir / "skills").glob("*.md") if (app_dir / "skills").exists() else []
    ):
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        n = len(pat.findall(text))
        if n:
            hits[str(path.relative_to(repo_root))] = n
    total = sum(hits.values())
    print(f"[pins] files with '2025-26' in backend/app: {len(hits)} ({total} hits)")
    for rel in CHECKLIST_FILES:
        print(f"  - {rel}: {hits.get(rel, 0)}")
    extra = [k for k in hits if k not in CHECKLIST_FILES]
    for k in sorted(extra)[:10]:
        print(f"  - {k}: {hits[k]} (extra)")
    return hits


def main():
    repo_root = Path(__file__).resolve().parents[2]
    print("== preseason gate 2026-27 (read-only, no warehouse writes) ==")
    try:
        espn, espn_ok = check_espn()
        nba = probe_nba()
        hits = grep_pins(repo_root)
    except Exception as e:
        print(f"VERDICT: NOT-READY - gate script crashed: {type(e).__name__}: {e}")
        return 2
    pins_found = sum(hits.values())
    oct3 = espn.get("20261003", (0, [], {}, False))
    oct20 = espn.get("20261020", (0, [], {}, False))
    if not (oct3[3] and oct20[3]):
        missing = [d for d, v in (("20261003", oct3), ("20261020", oct20)) if not v[3]]
        print(f"VERDICT: NOT-READY - ESPN scoreboard missing games for {', '.join(missing)}")
        return 1
    stats_state = nba.get("stats.nba.com", "?")
    fallback = "stats.nba.com blocked, ESPN fallback stands" if "blocked" in stats_state else "stats.nba.com reachable"
    print(
        f"VERDICT: READY - ESPN serves Oct 3 ({oct3[0]} games) and Oct 20 ({oct20[0]} games); "
        f"{fallback}; {pins_found} pinned 2025-26 hits still present, cutover stays shut until October"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
