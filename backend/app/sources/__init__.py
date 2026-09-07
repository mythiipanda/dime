"""Source registry. One import point for the warehouse."""

from . import espn, nba_stats, pbpstats
from .base import FetchMeta, FetchResult

__all__ = ["espn", "nba_stats", "pbpstats", "FetchMeta", "FetchResult"]
