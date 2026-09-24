"""Closed team-rating metric vocabulary shared by planning and execution.

The metric and direction enums below are the single source of truth for ranked
team rating arguments. The tool schema (backend/app/tools/league.py), the v2
capability catalog (derived from the same schema), the prompts, and the
deterministic verifiers all consume these values. Nothing may infer a ranking
direction or metric from request text; both are model-authored typed values.
"""

TEAM_RATING_METRICS = {
    "OFF_RATING": "offensive rating",
    "DEF_RATING": "defensive rating",
    "NET_RATING": "net rating",
    "PACE": "pace",
    "TS_PCT": "true shooting percentage",
    "TM_TOV_PCT": "turnover percentage",
}

RANKING_DIRECTIONS = ("asc", "desc")
