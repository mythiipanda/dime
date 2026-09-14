"""Fix silver_salaries TEAM from 2024-25 salary sheet Tm column.

Usage: python3 scripts/seed_salary_teams.py (run from backend/)
Source: https://raw.githubusercontent.com/coder-data/NBA-Stats-Salaries-2024-2025/main/NBA%20Salaries%202024-2025.csv
Matches on accent-folded upper(player name). Updates TEAM only, never
touches scrape salary values. Idempotent.
"""

import csv
import io
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app import store

URL = "https://raw.githubusercontent.com/coder-data/NBA-Stats-Salaries-2024-2025/main/NBA%20Salaries%202024-2025.csv"


def _fold(name: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(name or ""))
        if not unicodedata.combining(c)
    ).strip().upper()


def load_mapping() -> dict[str, str]:
    r = httpx.get(URL, timeout=60, follow_redirects=True)
    r.raise_for_status()
    inner: list[str] = []
    for line in io.StringIO(r.text):
        line = line.strip()
        if not line:
            continue
        fields = next(csv.reader([line]))
        if len(fields) == 1 and "," in fields[0]:
            inner.append(fields[0])
        else:
            inner.append(line.strip('"'))
    reader = csv.DictReader(io.StringIO("\n".join(inner[1:])))
    mapping: dict[str, str] = {}
    for row in reader:
        name = (row.get("Player") or "").strip()
        tm = (row.get("Tm") or "").strip().upper()
        if not name or not tm or tm == "TM":
            continue
        if name == "Player":
            continue
        mapping[_fold(name)] = tm
    return mapping


def main() -> None:
    from datetime import datetime, timezone

    mapping = load_mapping()
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            print("silver_salaries missing")
            return
        rows = con.execute(
            "SELECT PLAYER_NAME, TEAM FROM silver_salaries").fetchall()
        matched = 0
        overridden = 0
        with store.write_guard():
            for name, team in rows:
                key = _fold(name)
                want = mapping.get(key)
                if want is None:
                    continue
                matched += 1
                if not (team or "").strip():
                    con.execute(
                        "UPDATE silver_salaries SET TEAM = ? WHERE PLAYER_NAME = ?",
                        [want, name],
                    )
                    overridden += 1
            con.execute(
                "INSERT INTO fetch_log VALUES (?,?,?,?,?,?)",
                ["silver_salaries", "", "team-patch", "csv-teams",
                 datetime.now(timezone.utc).isoformat(), overridden],
            )
        print(f"csv_players={len(mapping)} matched={matched} overridden={overridden}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
