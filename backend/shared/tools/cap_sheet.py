SEASONS_HORIZON = ["2025-26", "2026-27", "2027-28", "2028-29",
                   "2029-30", "2030-31", "2031-32"]


def season_column(season: str) -> str:
    return "SALARY_" + season.replace("-", "_")


def option_column(season: str) -> str:
    return "OPTION_" + season.replace("-", "_")


def column_season(column: str) -> str | None:
    for prefix in ("SALARY_", "OPTION_"):
        if column.startswith(prefix):
            tail = column[len(prefix):]
            parts = tail.split("_")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return parts[0] + "-" + parts[1]
    return None


def horizon_seasons(rows: list[dict]) -> list[str]:
    found = set()
    for row in rows:
        for key in row:
            if key.startswith("SALARY_"):
                season = column_season(key)
                if season is not None:
                    found.add(season)
    return sorted(found)


def unroll_player_contract(row: dict, seasons: list[str],
                           start_season: str) -> dict:
    pool = int(row.get("GUARANTEED") or 0)
    walking = False
    broken = False
    years = []
    for season in seasons:
        salary = row.get(season_column(season))
        salary = int(salary) if salary is not None else None
        option = row.get(option_column(season))
        if option not in ("player", "team"):
            option = None
        if season < start_season:
            years.append({"season": season, "salary": salary,
                          "option": option, "guaranteed": None})
            continue
        walking = True
        if salary is None:
            years.append({"season": season, "salary": None,
                          "option": option, "guaranteed": None})
            continue
        if broken or salary > pool:
            broken = True
            guaranteed = False
        else:
            guaranteed = True
            pool -= salary
        years.append({"season": season, "salary": salary,
                      "option": option, "guaranteed": guaranteed})
    counts = row.get("_counts_as_standard_by_season")
    if isinstance(counts, dict):
        for year in years:
            year["counts_as_standard"] = bool(counts.get(year["season"], True))
    return {
        "player": row.get("PLAYER_NAME") or row.get("player") or "",
        "player_id": row.get("PLAYER_ID") or row.get("player_id"),
        "contract_type": row.get("contract_type"),
        "years": years,
    }


def year_committed(year: dict) -> int:
    if year.get("salary") is None or year.get("guaranteed") is None:
        return 0
    if year.get("option") == "team":
        return 0
    return int(year["salary"])


def year_pending_option(year: dict) -> int:
    if year.get("salary") is None or year.get("guaranteed") is None:
        return 0
    if year.get("option") == "team":
        return int(year["salary"])
    return 0


def _counts_as_standard_for_season(row: dict, season: str) -> bool:
    counts = row.get("_counts_as_standard_by_season")
    if not isinstance(counts, dict):
        return True
    return bool(counts.get(season, True))


def unroll_team_sheet(rows: list[dict], start_season: str,
                      seasons: list[str] | None = None) -> dict:
    if seasons is None:
        seasons = horizon_seasons(rows)
    players = [unroll_player_contract(row, seasons, start_season)
               for row in rows]
    totals = {}
    for season in seasons:
        committed = 0
        pending = 0
        for row, player in zip(rows, players, strict=False):
            year = next((y for y in player["years"]
                         if y["season"] == season), None)
            if year is None or not _counts_as_standard_for_season(row, season):
                continue
            committed += year_committed(year)
            pending += year_pending_option(year)
        totals[season] = {"committed": committed, "pending_option": pending}
    players.sort(key=lambda p: -(next((y["salary"] or 0 for y in p["years"]
                                       if y["season"] == start_season), 0)))
    return {"players": players, "totals": totals,
            "seasons": seasons, "start_season": start_season}
