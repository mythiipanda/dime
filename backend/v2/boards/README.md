# Boards API

All reads use the configured warehouse in read-only mode. No provider, live
source, tool runtime, or SQL-generation model is invoked. Each distinct metric
table is queried once per request, with a bound season parameter; player-season
rows are also used for identity and qualification. Identifiers come only from
the immutable metric registry. Conflicting rows are not resolved by row order.

- `GET /api/boards/metrics` returns `{ok, metrics}` (25 metric definitions).
- `POST /api/boards/fill` accepts `{season?, player_ids, metric_ids}` (50 players,
  30 metrics maximum). It returns `{ok, cells, players}` with string player-ID
  keys. Empty inputs are valid. Unknown IDs, missing values, conflicting rows,
  and unresolved salaries produce null cells with machine-readable reasons.
- `POST /api/boards/seed` accepts `{season?, metric_id, n?, min_gp?, min_mpg?,
  position?}` and returns `{ok, player_ids, cells, players, filters}`. `n` defaults
  to 10 and is bounded to 1–25. Null values are excluded, sorting follows
  `higher_is_better`, and ties are broken by ascending player ID. Unknown metrics
  are rejected with HTTP 422. The default performance season is `2025-26`.

`position` accepts `G`, `F`, or `C`: a player must have at least one boxscore
start recorded at exactly that position in `silver_boxscores` in the requested
season. It is not an inferred roster position or a PG/SG/SF/PF classification.
Players without that coverage are excluded; no matching coverage yields an empty
seed. Qualification query/parameters are included in `filters`.

Every cell carries table, column, season, query/parameters, row key, source, and
fetch timestamp. Missing cells preserve the attempted query and leave unknown
source fields null. Percentage values are returned on a 0–100 scale: stored
fractions are multiplied by 100, except `TM_TOV_PCT`, already per 100 possessions.
The raw SQL replay plus the metric definition explains that transformation.

`salary_2026_27` always reads the 2026–27 salary vintage, independently of the
performance season. A salary name must match exactly one player ID in the
selected player-season population after Unicode NFC, case and whitespace
normalization. Multiple salary rows are also rejected. There is no fuzzy match,
suffix removal, accent removal, or team-based tie-breaker. The citation carries
the salary vintage and the separate player-name resolution query. This is not
a guarantee of salary coverage for every player.

Validation errors use HTTP 422; warehouse read failures use HTTP 503 rather than
appearing as successful empty results.
