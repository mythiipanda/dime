from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CAPABILITY_SUBSUMPTIONS: dict[str, frozenset[str]] = {
    "player_report": frozenset({"shooting_efficiency"}),
    "game_prediction": frozenset({
        "team_ratings", "injuries", "injury_impact",
    }),
}


def capability_subsumes(broader: str, narrower: str) -> bool:
    return narrower in CAPABILITY_SUBSUMPTIONS.get(broader, ())


def arguments_share_subject(
    broader: Mapping[str, Any], narrower: Mapping[str, Any],
) -> bool:
    aliases = (("player_id", "player"), ("team_id", "team"))
    for keys in aliases:
        left = next((broader[key] for key in keys if key in broader), None)
        right = next((narrower[key] for key in keys if key in narrower), None)
        if left is None or right is None:
            continue
        if str(left).strip().casefold() != str(right).strip().casefold():
            return False
        left_season = broader.get("season")
        right_season = narrower.get("season")
        return (left_season is None or right_season is None
                or left_season == right_season)
    return False
