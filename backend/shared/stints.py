from typing import Any

PERIOD_SEC = 720.0
OT_SEC = 300.0

STINT_COLUMNS = [
    "game_id",
    "stint_number",
    "poss_start",
    "poss_end",
    "period_in",
    "clock_in",
    "period_out",
    "clock_out",
    "clock_in_sec",
    "clock_out_sec",
    "duration_sec",
    "home_team_id",
    "away_team_id",
    "home_abbr",
    "away_abbr",
    "home_player_1",
    "home_player_2",
    "home_player_3",
    "home_player_4",
    "home_player_5",
    "away_player_1",
    "away_player_2",
    "away_player_3",
    "away_player_4",
    "away_player_5",
    "score_home_in",
    "score_away_in",
    "score_home_out",
    "score_away_out",
    "home_swing",
]


def period_base(period: int) -> float:
    if period >= 5:
        return OT_SEC
    return PERIOD_SEC


def elapsed_sec(period: int, sec_remaining: float) -> float:
    base = period_base(period)
    if period >= 5:
        done = 4.0 * PERIOD_SEC + float(period - 5) * OT_SEC
    else:
        done = float(period - 1) * PERIOD_SEC
    return done + base - float(sec_remaining)


def clock_text(period: int, sec_remaining: float) -> str:
    total = int(float(sec_remaining))
    if total < 0:
        total = 0
    base = int(period_base(period))
    if total > base:
        total = base
    return f"{total // 60}:{total % 60:02d}"


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _floor(values: list) -> tuple | None:
    ids = []
    for v in values:
        pid = _as_int(v)
        if pid is None:
            return None
        ids.append(pid)
    if len(set(ids)) != 5:
        return None
    return tuple(sorted(ids))


def _norm_row(row: dict) -> dict | None:
    num = _as_int(row.get("possession_number"))
    period = _as_int(row.get("period"))
    start_sec = _as_float(row.get("start_seconds_remaining"))
    end_sec = _as_float(row.get("end_seconds_remaining"))
    offense = _as_int(row.get("offense_team_id"))
    points = _as_int(row.get("points"))
    if num is None or period is None or period < 1:
        return None
    if start_sec is None or end_sec is None or offense is None:
        return None
    if points is None:
        return None
    off = _floor([row.get(f"off_player_{i}") for i in range(1, 6)])
    deff = _floor([row.get(f"def_player_{i}") for i in range(1, 6)])
    return {
        "possession_number": num,
        "period": period,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "offense": offense,
        "points": points,
        "off": off,
        "deff": deff,
    }


def _sides(row: dict, home_id: int, away_id: int) -> tuple | None:
    if row["off"] is None or row["deff"] is None:
        return None
    if row["offense"] == home_id:
        return (row["off"], row["deff"])
    if row["offense"] == away_id:
        return (row["deff"], row["off"])
    return None


def _stint_row(game_id: str, number: int, home_id: int, away_id: int,
               home_abbr: str, away_abbr: str, floors: tuple,
               first: dict, last: dict,
               score_home_in: int, score_away_in: int,
               run_home: int, run_away: int) -> dict:
    home_floor, away_floor = floors
    out: dict[str, Any] = {
        "game_id": game_id,
        "stint_number": number,
        "poss_start": first["possession_number"],
        "poss_end": last["possession_number"],
        "period_in": first["period"],
        "clock_in": clock_text(first["period"], first["start_sec"]),
        "period_out": last["period"],
        "clock_out": clock_text(last["period"], last["end_sec"]),
        "clock_in_sec": float(first["start_sec"]),
        "clock_out_sec": float(last["end_sec"]),
        "duration_sec": elapsed_sec(last["period"], last["end_sec"])
        - elapsed_sec(first["period"], first["start_sec"]),
        "home_team_id": home_id,
        "away_team_id": away_id,
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
        "score_home_in": score_home_in,
        "score_away_in": score_away_in,
        "score_home_out": run_home,
        "score_away_out": run_away,
        "home_swing": (run_home - score_home_in)
        - (run_away - score_away_in),
    }
    for i, pid in enumerate(home_floor, 1):
        out[f"home_player_{i}"] = pid
    for i, pid in enumerate(away_floor, 1):
        out[f"away_player_{i}"] = pid
    return out


def build_stints(game_id: str, possessions: list, home_id: int,
                 away_id: int, home_abbr: str, away_abbr: str) -> list:
    home_id = int(home_id)
    away_id = int(away_id)
    normed = [_norm_row(r) for r in possessions or []]
    ordered = sorted(
        [r for r in normed if r is not None],
        key=lambda r: r["possession_number"])
    rows: list[dict] = []
    current: tuple | None = None
    first: dict | None = None
    last: dict | None = None
    score_home_in = 0
    score_away_in = 0
    run = {home_id: 0, away_id: 0}
    number = 0

    def close() -> None:
        nonlocal number
        if current is None or first is None or last is None:
            return
        number += 1
        rows.append(_stint_row(
            game_id, number, home_id, away_id, home_abbr, away_abbr,
            current, first, last, score_home_in, score_away_in,
            run[home_id], run[away_id]))

    for row in ordered:
        key = _sides(row, home_id, away_id)
        if key is None:
            close()
            current = None
            first = None
            last = None
            if row["offense"] == home_id:
                run[home_id] += row["points"]
            elif row["offense"] == away_id:
                run[away_id] += row["points"]
            continue
        if key != current:
            close()
            current = key
            first = row
            score_home_in = run[home_id]
            score_away_in = run[away_id]
        last = row
        if row["offense"] == home_id:
            run[home_id] += row["points"]
        elif row["offense"] == away_id:
            run[away_id] += row["points"]
    close()
    return rows
