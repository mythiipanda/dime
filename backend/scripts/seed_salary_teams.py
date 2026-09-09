"""Fix silver_salaries TEAM from 2024-25 salary sheet Tm column.

Usage: python3 scripts/seed_salary_teams.py (run from backend/)
Source: https://raw.githubusercontent.com/coder-data/NBA-Stats-Salaries-2024-2025/main/NBA%20Salaries%202024-2025.csv
Matches on upper(player name). Updates TEAM only. Idempotent.
"""

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app import store

URL = "https://raw.githubusercontent.com/coder-data/NBA-Stats-Salaries-2024-2025/main/NBA%20Salaries%202024-2025.csv"


def _parse_salary(raw: str) -> int | None:
    digits = "".join(c for c in (raw or "") if c.isdigit())
    return int(digits) if digits else None


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
    salaries: dict[str, int] = {}
    for row in reader:
        name = (row.get("Player") or "").strip()
        tm = (row.get("Tm") or "").strip().upper()
        sal = _parse_salary(row.get("2025-26") or "")
        if not name or not tm or tm == "TM":
            continue
        if name == "Player":
            continue
        mapping[name.upper()] = tm
        if sal:
            salaries[name.upper()] = sal
    return mapping, salaries


def main() -> None:
    mapping, salaries = load_mapping()
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            print("silver_salaries missing")
            return
        rows = con.execute(
            "SELECT PLAYER_NAME, TEAM, SALARY_2025_26 FROM silver_salaries").fetchall()
        matched = 0
        overridden = 0
        sal_fixed = 0
        with store.write_guard():
            for name, team, cur_sal in rows:
                key = str(name or "").strip().upper()
                want = mapping.get(key)
                if want is None:
                    continue
                matched += 1
                if (team or "").upper() != want:
                    con.execute(
                        "UPDATE silver_salaries SET TEAM = ? WHERE PLAYER_NAME = ?",
                        [want, name],
                    )
                    overridden += 1
                want_sal = salaries.get(key)
                if want_sal and cur_sal != want_sal:
                    con.execute(
                        "UPDATE silver_salaries SET SALARY_2025_26 = ? WHERE PLAYER_NAME = ?",
                        [want_sal, name],
                    )
                    sal_fixed += 1
        print(f"csv_players={len(mapping)} matched={matched} overridden={overridden} salaries_fixed={sal_fixed}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
