"""Vendor salary data from the public cap engine repo into the warehouse.

Source: https://github.com/orojas119/nba-salary-cap
Normals: silver_cap_players (one row per player-season team).
No license file upstream; source URL rides provenance. Drop on objection.
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store
from app.sources.base import FetchMeta, FetchResult

URL = ("https://raw.githubusercontent.com/orojas119/nba-salary-cap"
       "/main/backend/data/teams_2026_27.json")

THRESHOLDS = {
    "season": "2026-27",
    "cap": 165_000_000,
    "tax": 201_048_000,
    "apron1": 209_661_000,
    "apron2": 222_372_000,
}


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "dime-seed/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        teams = json.load(r)
    rows = []
    for t in teams:
        for p in t.get("players", []):
            rows.append({
                "team": t.get("team_id", ""),
                "team_name": t.get("team_name", ""),
                "player": p.get("name", ""),
                "salary": p.get("salary_2026_27", 0) or 0,
                "contract_type": p.get("contract_type", ""),
                "player_option": bool(p.get("player_option")),
                "team_option": bool(p.get("team_option")),
                "guaranteed": bool(p.get("guaranteed", True)),
            })
    frame = pl.DataFrame(rows)
    res = FetchResult(
        frame=frame,
        meta=FetchMeta(source="orojas119/nba-salary-cap", season="2026-27"),
    )
    n = store.save_frame("silver_cap_players", res, entity="season:2026-27")
    print(f"cap players: {n}")
    print(f"thresholds: {THRESHOLDS}")


if __name__ == "__main__":
    main()
