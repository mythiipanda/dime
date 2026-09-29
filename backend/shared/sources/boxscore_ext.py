
import re
from typing import Any

import polars as pl

from .base import FetchResult, safe

SOURCE = "nba_api_boxscore_ext"


def _endpoint(view: str) -> Any:
    from nba_api.stats import endpoints as E

    return {
        "advanced": E.BoxScoreAdvancedV3,
        "four_factors": E.BoxScoreFourFactorsV3,
        "misc": E.BoxScoreMiscV3,
        "scoring": E.BoxScoreScoringV3,
        "usage": E.BoxScoreUsageV3,
    }[view]


VIEWS = ("advanced", "four_factors", "misc", "scoring", "usage")

PREFIX = {
    "advanced": "ADV",
    "four_factors": "FF",
    "misc": "MISC",
    "scoring": "SCORE",
    "usage": "USG",
}


def _pl(df: Any) -> pl.DataFrame:
    try:
        return pl.from_pandas(df)
    except Exception:
        return pl.DataFrame()


def fetch_view(view: str, game_id: str, season: str) -> FetchResult:
    cls = _endpoint(view)

    def run() -> pl.DataFrame:
        ep = cls(game_id=game_id, timeout=30)
        return _pl(ep.get_data_frames()[0])

    return safe(SOURCE, season, run)


def _snake(name: str) -> str:
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()
    return re.sub(r"__+", "_", s)


_KEY_RENAME = {
    "gameId": "GAME_ID",
    "teamId": "TEAM_ID",
    "teamTricode": "TEAM_ABBREVIATION",
    "personId": "PLAYER_ID",
}


def to_silver(view: str, frame: pl.DataFrame) -> pl.DataFrame:
    if frame.height == 0:
        return frame
    prefix = PREFIX[view]
    df = frame.filter(pl.col("personId").is_not_null())
    if df.height == 0:
        return df.clear()
    df = df.drop([c for c in ("teamCity", "teamName", "teamSlug")
                  if c in df.columns])
    names = [str(c) for c in df.columns]
    if "firstName" in names and "familyName" in names:
        df = df.with_columns(
            (pl.col("firstName").cast(pl.String) + pl.lit(" ")
             + pl.col("familyName").cast(pl.String)).alias("PLAYER_NAME")
        )
    rename = {}
    for c in df.columns:
        c = str(c)
        if c in _KEY_RENAME:
            rename[c] = _KEY_RENAME[c]
        elif c in ("firstName", "familyName"):
            rename[c] = "__drop__" + c
        elif c == "PLAYER_NAME":
            continue
        elif c == "minutes" and view == "advanced":
            rename[c] = "MINUTES"
        else:
            rename[c] = f"{prefix}_{_snake(c)}"
    df = df.rename({k: v for k, v in rename.items()
                    if not v.startswith("__drop__")})
    df = df.drop([c for c in df.columns if c.startswith("__drop__")])
    return df


def join_views(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    keys = ["GAME_ID", "PLAYER_ID"]
    out: pl.DataFrame | None = None
    for view in VIEWS:
        df = frames.get(view)
        if df is None or df.height == 0:
            continue
        if out is None:
            out = df
            continue
        shared = [c for c in df.columns if c in out.columns
                  and c not in keys]
        right = df.drop(shared)
        out = out.join(right, on=keys, how="full", coalesce=True)
    if out is None:
        return pl.DataFrame()
    return out
