"""Morning briefing report. Last night scores plus standouts plus injuries.

Usage: python -m scripts.briefing [--date 09/07/2026]
Writes backend/data/reports/briefing-<date>.md (gitignored).
Pair with cron for daily delivery.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools


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

    out = Path(__file__).resolve().parent.parent / "data" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"briefing-{day.replace('/', '-')}.md"
    path.write_text("\n".join(lines) + "\n")
    print(f"wrote {path} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
