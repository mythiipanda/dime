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
