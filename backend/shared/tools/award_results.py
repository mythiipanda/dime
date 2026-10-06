from typing import Any, Literal

from langchain_core.tools import tool

from .. import store

TABLE = "silver_award_winners"
TOOL = "get_award_results"
VIEWS = ("winner", "field", "player_awards")
VOTE_COLUMNS = ("votes_first", "votes_second", "votes_third")

AWARDS: dict[str, dict[str, Any]] = {
    "MVP": {
        "label": "Most Valuable Player",
        "subject": "player",
        "honors_teams": 1,
        "projectable": True,
        "aliases": ("mvp", "most valuable player",
                    "most valuable player of the year", "league mvp"),
    },
    "DPOY": {
        "label": "Defensive Player of the Year",
        "subject": "player",
        "honors_teams": 1,
        "projectable": True,
        "aliases": ("dpoy", "defensive player of the year",
                    "defensive player", "best defender"),
    },
    "ROY": {
        "label": "Rookie of the Year",
        "subject": "player",
        "honors_teams": 1,
        "projectable": True,
        "aliases": ("roy", "rookie of the year", "best rookie", "top rookie"),
    },
    "6MOY": {
        "label": "Sixth Man of the Year",
        "subject": "player",
        "honors_teams": 1,
        "projectable": True,
        "aliases": ("6moy", "smoy", "sixth man of the year", "sixth man",
                    "sixthman", "best sixth man", "best bench"),
    },
    "MIP": {
        "label": "Most Improved Player",
        "subject": "player",
        "honors_teams": 1,
        "projectable": True,
        "aliases": ("mip", "most improved player",
                    "most improved player of the year", "most improved"),
    },
    "COY": {
        "label": "Coach of the Year",
        "subject": "coach",
        "honors_teams": 1,
        "projectable": False,
        "aliases": ("coy", "coach of the year", "best coach"),
    },
    "ALL_NBA": {
        "label": "All-NBA Team",
        "subject": "player",
        "honors_teams": 3,
        "projectable": False,
        "aliases": ("all nba", "all nba team", "all nba teams",
                    "all nba selections"),
    },
    "ALL_DEFENSE": {
        "label": "All-Defensive Team",
        "subject": "player",
        "honors_teams": 3,
        "projectable": False,
        "aliases": ("all defense", "all defensive", "all defensive team",
                    "all defensive teams", "all defense selections"),
    },
    "ALL_ROOKIE": {
        "label": "All-Rookie Team",
        "subject": "player",
        "honors_teams": 2,
        "projectable": False,
        "aliases": ("all rookie", "all rookie team", "all rookie teams",
                    "all rookies"),
    },
}


def _squash(value: object) -> str:
    return "".join(
        character for character in str(value or "").upper()
        if character.isalnum())


AWARD_LOOKUP: dict[str, str] = {
    _squash(key): code
    for code, spec in AWARDS.items()
    for key in (code, *spec["aliases"])
}


def normalize_award(name: object) -> str | None:
    return AWARD_LOOKUP.get(_squash(name))


def published_awards() -> str:
    return ", ".join(sorted(AWARDS))


RANK_SEMANTICS = (
    "rank is always 1: every row is a recorded winner, never a ballot "
    "placement; vote counts, vote shares, and ranked fields are not in the "
    "dataset")


class AwardResultError(RuntimeError):
    pass


def _table_on_hand() -> bool:
    try:
        connection = store.connect(read_only=True)
    except Exception:
        return False
    try:
        return bool(connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = ?", [TABLE]).fetchone()[0])
    except Exception:
        return False
    finally:
        connection.close()


def _seasons_on_hand() -> tuple[str, ...]:
    from v2.adapters.coverage import table_seasons

    return tuple(sorted(table_seasons(TABLE)))


def _season_guard(requested: object) -> str:
    if not _table_on_hand():
        raise AwardResultError(
            f"warehouse table missing: {TABLE}; no award result can be read")
    seasons = _seasons_on_hand()
    raw = str(requested or "").strip()
    if not seasons:
        raise AwardResultError(
            f"{TABLE} holds no award winners, so no season can be answered")
    if not raw:
        return seasons[-1]
    if raw not in seasons:
        raise AwardResultError(
            f"no {TABLE} winners for the {raw} season; award winners on hand "
            f"cover {seasons[0]} through {seasons[-1]} "
            f"({len(seasons)} seasons recorded). Dime never estimates a "
            f"missing winner.")
    return raw


def _award_guard(award: object, *, required: bool) -> str | None:
    raw = str(award or "").strip()
    if not raw:
        if not required:
            return None
        raise AwardResultError(
            "the winner and field views need an award; published awards: "
            f"{published_awards()}")
    canon = normalize_award(raw)
    if canon is None:
        raise AwardResultError(
            f"unknown award '{raw}'; published awards: {published_awards()}")
    return canon


_SELECT = """
    SEASON, AWARD, RANK, RANK_LABEL, PLAYER, COACH, TEAM, AGE,
    POINTS_WON, POINTS_MAX, AWARD_SHARE,
    VOTES_FIRST, VOTES_SECOND, VOTES_THIRD
"""


def _name_match(column: str) -> str:
    return f"strip_accents(lower({column})) = strip_accents(lower(?))"


def _read(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    try:
        return store._read_df(sql, params)
    except Exception as exc:
        raise AwardResultError(
            f"warehouse read of {TABLE} failed: {str(exc)[:200]}") from exc


def _winner_rows(season: str, player: str | None
                 ) -> tuple[list[dict[str, Any]], str | None]:
    params: list[Any] = [season]
    clauses = ["_season <= ?"]
    order = "ORDER BY SEASON DESC, RANK NULLS LAST, AWARD, POINTS_WON DESC"
    if player is None:
        clauses[0] = "_season = ?"
        order = "ORDER BY RANK NULLS LAST, POINTS_WON DESC, PLAYER"
    else:
        clauses.append(_name_match("PLAYER"))
        params.append(player)
    rows = _read(
        f"SELECT {_SELECT} FROM {TABLE} WHERE {' AND '.join(clauses)} {order}",
        params)
    observed = _read(
        f"SELECT MAX(_fetched_at) AS fetched_at FROM {TABLE} "
        f"WHERE {' AND '.join(clauses)}", params)
    return rows, (observed[0]["fetched_at"] if observed else None)


def _null(value: Any) -> Any:
    return None if value is None or value != value else value


def _tied(rank: Any, rank_label: Any) -> bool:
    text = str(rank_label or "")
    return rank is not None and text.endswith("T") \
        and text[:-1].isdigit()


def _placement(row: dict[str, Any]) -> dict[str, Any]:
    rank = _null(row["RANK"])
    age = _null(row["AGE"])
    return {
        "season": row["SEASON"],
        "award": row["AWARD"],
        "player": _null(row["PLAYER"]),
        "coach": _null(row["COACH"]),
        "team": _null(row["TEAM"]),
        "age": None if age is None else int(age),
        "rank": None if rank is None else int(rank),
        "rank_label": row["RANK_LABEL"],
        "tied": _tied(rank, row["RANK_LABEL"]),
        "award_share": _null(row["AWARD_SHARE"]),
        "points_won": _null(row["POINTS_WON"]),
        "points_max": _null(row["POINTS_MAX"]),
        "votes_first": _null(row["VOTES_FIRST"]),
        "votes_second": _null(row["VOTES_SECOND"]),
        "votes_third": _null(row["VOTES_THIRD"]),
    }


def _placements(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_placement(row) for row in raw]


def _career_note(placements: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[str]] = {}
    for row in placements:
        grouped.setdefault(row["award"], []).append(row["season"])
    return "; ".join(
        f"{award} in {', '.join(sorted(set(seasons)))}"
        for award, seasons in sorted(grouped.items()))


def _absent_subject(player: str, season: str) -> str:
    return (f"no award winner through the {season} season is a player "
            f"named {player}")


def _resolve(placement_rows: list[dict[str, Any]], view: str, canon: str | None,
             season: str, subject: str) -> list[dict[str, Any]]:
    if view == "player_awards":
        if canon is None:
            return placement_rows
        narrowed = [row for row in placement_rows if row["award"] == canon]
        if not narrowed:
            raise AwardResultError(
                f"no {canon} winner row for {subject} through the {season} "
                f"season; {subject} is on record for "
                f"{_career_note(placement_rows)}")
        return narrowed
    if canon is not None:
        placement_rows = [row for row in placement_rows
                          if row["award"] == canon]
        if not placement_rows:
            raise AwardResultError(
                f"no {canon} winner recorded for the {season} season")
    leading = min((row["rank"] for row in placement_rows
                   if row["rank"] is not None), default=None)
    if leading is None:
        raise AwardResultError(
            f"the {canon} winners for the {season} season carry no rank")
    return [row for row in placement_rows if row["rank"] == leading]


def _coverage(view: str, spec: dict[str, Any] | None, season: str) -> str:
    scope = spec["label"] if spec is not None else "every recorded award"
    what = {
        "winner": "the recorded winner",
        "field": "ballot detail, which this dataset does not carry",
        "player_awards": "every winner row the subject appears on",
    }[view]
    return (f"Recorded NBA award winner from nba_api PlayerAwards for {scope}: "
            f"{what} in {season}, read from {TABLE}. This is a recorded "
            f"outcome, never a model score, projection, or live race.")


@tool
def get_award_results(
    view: Literal["winner", "field", "player_awards"],
    award: str | None = None,
    season: str | None = None,
    player: str | None = None,
) -> dict[str, Any]:
    """Recorded NBA award winners read from the warehouse.

    view=winner returns the recorded winner for one award in one season.
    view=player_awards returns one player's award-winner record through the
    named season. view=field is not served: the nba_api winners dataset
    records winners only, with no ballot detail (no vote counts, shares, or
    ranked fields). Use get_award_race for a model score, never for a result.
    """
    try:
        if view not in VIEWS:
            raise AwardResultError(
                f"unknown view '{view}'; valid views: {', '.join(VIEWS)}")
        if view == "field":
            raise AwardResultError(
                "the field view needs full ballot detail (vote counts, vote "
                "shares, ranked field); the nba_api winners dataset records "
                "winners only")
        history = view == "player_awards"
        named = str(player or "").strip()
        if history and not named:
            raise AwardResultError(
                "the player_awards view needs a player name")
        if not history and named:
            raise AwardResultError(
                "a player name is only accepted by the player_awards view")
        canon = _award_guard(award, required=not history)
        if canon == "COY":
            raise AwardResultError(
                "Coach of the Year is not in the nba_api player awards "
                "dataset, which covers players only")
        season = _season_guard(season)
        raw, fetched_at = _winner_rows(season, named if history else None)
        placements = _placements(raw)
        if history and not placements:
            raise AwardResultError(_absent_subject(named, season))
        rows = _resolve(placements, view, canon, season, named or canon or "")
    except AwardResultError as exc:
        return {"tool": TOOL, "ok": False, "rows": {}, "meta": {},
                "error": str(exc)}

    spec = AWARDS[canon] if canon is not None else None
    vote_columns = [name for name in VOTE_COLUMNS
                    if any(row[name] is not None for row in rows)]
    meta: dict[str, Any] = {
        "source": "warehouse",
        "dataset": "nba_api",
        "season": season,
        "view": view,
        "count": len(rows),
        "award": canon,
        "award_label": spec["label"] if spec is not None else "every recorded award",
        "award_subject": spec["subject"] if spec is not None else "player",
        "honors_teams": spec["honors_teams"] if spec is not None else None,
        "ballot": False,
        "vote_columns": vote_columns,
        "result_type": "official_award_result",
        "model_projection": False,
        "method": f"winner rows recorded from nba_api PlayerAwards into {TABLE} with no scoring",
        "method_kind": "official",
        "rank_semantics": RANK_SEMANTICS,
        "history_through": season,
        "seasons_covered": sorted({str(row["season"]) for row in placements}),
        "coverage": _coverage(view, spec, season),
        "fetched_at": fetched_at,
        "projection_tool": "get_award_race",
    }
    return {"tool": TOOL, "ok": True, "rows": {"placements": rows}, "meta": meta}