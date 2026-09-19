"""Closed team-rating metric vocabulary shared by planning and execution."""

TEAM_RATING_METRICS = {
    "OFF_RATING": {"off rating", "offensive", "offensive rating", "offense"},
    "DEF_RATING": {"def rating", "defensive", "defensive rating", "defense"},
    "NET_RATING": {"net", "net rating"},
    "PACE": {"pace"},
    "TS_PCT": {"ts pct", "true shooting", "true shooting percentage"},
    "TM_TOV_PCT": {"tm tov pct", "turnover percentage", "turnover rate"},
}


def canonical_team_rating_metric(value: object) -> str | None:
    """Return the tool's canonical enum member for a supported synonym."""
    key = str(value or "").strip().casefold().replace("-", " ").replace("_", " ")
    key = " ".join(key.split())
    for metric, aliases in TEAM_RATING_METRICS.items():
        if key == metric.casefold().replace("_", " ") or key in aliases:
            return metric
    return None


RANKING_DIRECTION_ALIASES = {
    "asc": "asc", "ascending": "asc", "lowest": "asc", "minimum": "asc",
    "desc": "desc", "descending": "desc", "highest": "desc", "maximum": "desc",
}


def canonical_ranking_direction(value: object) -> str | None:
    """Return the closed ranking-direction enum for a supported synonym."""
    return RANKING_DIRECTION_ALIASES.get(str(value or "").strip().casefold())


class RankedTeamConstraintError(ValueError):
    """Trusted ranked-team intent is ambiguous or conflicts with review."""


def ranked_team_constraints(text: str, *, season: str | None = None) -> dict[str, str] | None:
    """Project an unambiguous ranked team metric from trusted typed text.

    The vocabulary is the same closed contract consumed by planning and the
    team_ratings tool.  No model-owned alias can extend it.
    """
    import re

    folded = " ".join(str(text or "").casefold().replace("-", " ").replace("_", " ").split())
    def phrase(value: str) -> bool:
        value = " ".join(value.casefold().replace("-", " ").replace("_", " ").split())
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(value)}(?![a-z0-9])", folded))

    metrics = {
        metric for metric, aliases in TEAM_RATING_METRICS.items()
        if any(phrase(alias) for alias in aliases)
    }
    if len(metrics) > 1:
        raise RankedTeamConstraintError("ambiguous ranked-team metric")
    if not metrics:
        return None
    metric = next(iter(metrics))
    low = any(phrase(value) for value in ("lowest", "fewest", "minimum"))
    high = any(phrase(value) for value in ("highest", "most", "maximum"))
    if metric == "DEF_RATING":
        low = low or any(phrase(value) for value in ("best defense", "best defensive rating"))
        high = high or any(phrase(value) for value in ("worst defense", "worst defensive rating"))
    if low == high:
        if low:
            raise RankedTeamConstraintError("conflicting ranked-team extrema")
        return None
    projected = {"requested_metric": metric,
                 "ranking_direction": "asc" if low else "desc"}
    if season is not None:
        projected["season"] = season
    return projected
