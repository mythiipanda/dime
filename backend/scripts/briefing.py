
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import tools

def _team(r):
    city = r.get("TeamCity") or r.get("TEAM_CITY") or ""
    name = r.get("TeamName") or r.get("TEAM_NAME") or ""
    full = f"{city} {name}".strip()
    return full or r.get("TEAM") or r.get("Team") or r.get("TEAM_ABBREVIATION") or "?"

def _conf(r):
    return str(r.get("Conference") or r.get("CONFERENCE") or r.get("conference") or "")

def _rank(r):
    try:
        return int(r.get("PlayoffRank", r.get("PLAYOFF_RANK", 99)))
    except (TypeError, ValueError):
        return 99

def _net(r):
    try:
        return float(r.get("NET_RATING", r.get("NetRtg", r.get("net_rating", 0))))
    except (TypeError, ValueError):
        return 0.0

def _pts(r):
    try:
        return float(r.get("PTS", r.get("Pts", r.get("points", 0))))
    except (TypeError, ValueError):
        return 0.0

def _player(r):
    return r.get("PLAYER") or r.get("Player") or r.get("PLAYER_NAME") or "?"

def _bteam(r):
    return r.get("TEAM") or r.get("Team") or r.get("TEAM_ABBREVIATION") or ""

def _gid(r):
    return str(r.get("GAME_ID", r.get("GameId", r.get("game_id", ""))))

def _standings_lines(srows) -> list:
    east = sorted([r for r in srows if _conf(r).lower().startswith("east")], key=_rank)[:4]
    west = sorted([r for r in srows if _conf(r).lower().startswith("west")], key=_rank)[:4]
    if not east and not west:
        raise ValueError("no conference rows")
    lines = ["East:"]
    for r in east:
        lines.append(f"- {_rank(r)}. {_team(r)}")
    lines.append("West:")
    for r in west:
        lines.append(f"- {_rank(r)}. {_team(r)}")
    return lines

def _ratings_lines(rrows) -> list:
    top = sorted(rrows, key=_net, reverse=True)[:5]
    if not top:
        raise ValueError("no rating rows")
    lines = []
    for r in top:
        team = r.get("TEAM") or r.get("Team") or r.get("team") or "?"
        lines.append(f"- {team}: {_net(r):.1f}")
    return lines

def _title_lines(sim) -> list:
    probs = {}
    if isinstance(sim, dict):
        probs = sim.get("title_probs") or sim.get("rows", {}).get("title_probs", {}) or {}
    if not probs:
        raise ValueError("no title_probs")
    top5 = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:5]
    lines = []
    for team, p in top5:
        try:
            pct = float(p) * 100 if float(p) <= 1 else float(p)
        except (TypeError, ValueError):
            pct = 0.0
        lines.append(f"- {team}: {pct:.1f}%")
    return lines

def _boxscore_rows(brief) -> list:
    bdict = brief.get("rows", {}) if isinstance(brief.get("rows"), dict) else {}
    for key in ("boxscore", "boxscores", "box", "player_box"):
        v = bdict.get(key, [])
        if isinstance(v, list) and v:
            return v
    return []

def _scorer_lines(brief, games) -> list:
    brows = _boxscore_rows(brief)
    if not brows:
        return ["- Boxscore data not available in briefing payload."]
    by_game = {}
    for r in brows:
        by_game.setdefault(_gid(r), []).append(r)
    lines = []
    shown = 0
    for g in games[:15]:
        gid = str(g.get("GAME_ID", g.get("GameId", g.get("game_id", ""))))
        pool = by_game.get(gid, []) if gid else []
        if not pool:
            continue
        best = max(pool, key=_pts)
        matchup = f"{g.get('VISITOR_TEAM_ABBREVIATION', '')} @ {g.get('HOME_TEAM_ABBREVIATION', '')}".strip()
        lines.append(f"- {matchup}: {_player(best)} ({_bteam(best)}) - {_pts(best):.0f} PTS")
        shown += 1
    if shown == 0:
        best_all = max(brows, key=_pts)
        lines.append(f"- Top: {_player(best_all)} ({_bteam(best_all)}) - {_pts(best_all):.0f} PTS")
    return lines

def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--date", default="")
    ns = args.parse_args()
    day = ns.date.strip() or (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")

    brief = tools.get_briefing.invoke({"game_date": day})
    games = brief.get("rows", {}).get("games", []) if brief.get("ok") else []
    lines = [f"# Morning briefing {day}", ""]
    if not games:
        lines.append("No games on this date (offseason or off day).")
    for g in games[:15]:
        lines.append(
            f"- {g.get('VISITOR_TEAM_ABBREVIATION')} {g.get('VISITOR_TEAM_PTS', '?')} "
            f"@ {g.get('HOME_TEAM_ABBREVIATION')} {g.get('HOME_TEAM_PTS', '?')} "
            f"({g.get('GAME_STATUS_TEXT', '')})"
        )
    lines += ["", "## Top scorers (season)"]
    for s in (brief.get("rows", {}).get("top_scorers", []) or [])[:5]:
        lines.append(f"- {s.get('PLAYER')} ({s.get('TEAM')}): {s.get('PTS')}")
    inj = tools.get_injuries.invoke({})
    rows = inj.get("rows", []) if inj.get("ok") else []
    lines += ["", f"## Injury report ({len(rows)} teams listed)"]
    for r in rows[:10]:
        lines.append(f"- {r.get('display_name')}: {str(r.get('injuries', ''))[:120]}")

    try:
        st = tools.get_standings.invoke({})
        srows = st.get("rows", []) if st.get("ok") else []
        lines += ["", "## Standings top-4 per conference"]
        lines.extend(_standings_lines(srows))
    except Exception as e:
        if "## Standings top-4 per conference" not in "\n".join(lines[-3:]):
            lines += ["", "## Standings top-4 per conference"]
        lines.append(f"- Standings unavailable ({e})")

    try:
        rt = tools.get_ratings.invoke({})
        rrows = rt.get("rows", []) if rt.get("ok") else []
        lines += ["", "## Net-rating top-5"]
        lines.extend(_ratings_lines(rrows))
    except Exception as e:
        if "## Net-rating top-5" not in "\n".join(lines[-3:]):
            lines += ["", "## Net-rating top-5"]
        lines.append(f"- Ratings unavailable ({e})")

    try:
        sim = asyncio.run(tools.get_playoff_sim.ainvoke({}))
        lines += ["", "## Title odds top-5"]
        lines.extend(_title_lines(sim))
    except Exception as e:
        if "## Title odds top-5" not in "\n".join(lines[-3:]):
            lines += ["", "## Title odds top-5"]
        lines.append(f"- Title odds unavailable ({e})")

    try:
        lines += ["", "## Last-night biggest scorer per game"]
        lines.extend(_scorer_lines(brief, games))
    except Exception as e:
        if "## Last-night biggest scorer per game" not in "\n".join(lines[-3:]):
            lines += ["", "## Last-night biggest scorer per game"]
        lines.append(f"- Biggest scorer unavailable ({e})")

    out = Path(__file__).resolve().parent.parent / "data" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"briefing-{day.replace('/', '-')}.md"
    path.write_text("\n".join(lines) + "\n")
    print(f"wrote {path} ({len(lines)} lines)")

if __name__ == "__main__":
    main()
