"""Closed team-rating metric vocabulary; the single source of truth.

Each entry carries the display label and the deterministic-answer number
format, so no second metric-ID collection is needed anywhere.
"""

TEAM_RATING_METRICS = {
    "OFF_RATING": {"label": "offensive rating", "format": "general"},
    "DEF_RATING": {"label": "defensive rating", "format": "general"},
    "NET_RATING": {"label": "net rating", "format": "general"},
    "PACE": {"label": "pace", "format": "general"},
    "TS_PCT": {"label": "true shooting percentage", "format": "decimal3"},
    "TM_TOV_PCT": {"label": "turnover percentage", "format": "decimal3"},
}

RANKING_DIRECTIONS = ("asc", "desc")
