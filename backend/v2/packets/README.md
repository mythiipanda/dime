# Packets

`POST /api/packets/player_deep_dive` accepts `player` (exact full name or NBA id)
and `season` (default `2025-26`). Returns a complete, descriptive six-section
packet without an LLM, network request or persistence. Names use Boards' NFKD,
accent removal, case folding and whitespace normalization. Ambiguous/unknown
identity returns 422 with candidates; missing optional sources yield callouts.
Duplicate single-player rows are not selected arbitrarily.

Queries use a read-only warehouse connection, parameter binding and row bounds.
The bound is read plus one; over-bound populations are omitted, never silently
ranked on a truncated cohort. Citations retain the exact bounded SQL and params,
source table/columns, scope, source and fetched timestamp. Aggregate displays
are deterministic transformations of those inputs, not fresh SQL execution.
Derived citations additionally carry `supporting_cites` for other input sources
and a `transformation` describing the calculation (including cohort joins).
Percentages are 0–100; differences are percentage points. Percentiles use
midrank ties among unique base-season players with GP >= 20 and MPG >= 15;
each metric excludes missing/ambiguous rows. Higher means more, not always better.

Shot league FG% is sum(FGM)/sum(FGA) among qualified players in each zone;
share uses all recorded buckets. Zero-attempt buckets contribute no attempts to
the league average and have null player FG%, not a fabricated zero percentage.
These are BRef distance buckets, not geometric
zones. Incomplete or duplicate buckets are coverage gaps. Form uses available
dated logs, not season-table rates. TS% = 100*sum(PTS)/(2*(sum(FGA)+.44*sum(FTA))).
Rolling average requires five games; earlier points are null. Clutch and hustle
are provider totals. On/off stat labels containing `%` are converted from
fractions; other units retain the provider label and are not guessed.

Salary is explicitly the separate 2026-27 vintage matched by an unambiguous
normalized full name; the warehouse does not contain a multi-year contract
schedule. Career history is bounded through 2024-25 and supplemented by the
requested season; current TS% comes from the advanced table.

`narrative` defaults to null and is not required for completeness.
`POST /api/packets/narrative` accepts `{packet, narrative}` and returns
`{packet_with_narrative, rejected}` without reading the warehouse or calling a
model. Validation drops claims with missing/unknown cites or unsupported numbers.
Numbers are checked against cited KPI values, table rows and chart data in their
display units, with half-a-last-written-digit rounding tolerance. This is a
numeric/citation guard, not semantic verification or a recommendation engine;
client-supplied packets are not authenticated warehouse attestations.
`narrative_prompt(packet)` supplies evidence and the JSON schema for a future
caller; it never invokes a model. Empty claim citation lists are accepted at
ingress only so they can be reported as rejected, never retained.

Run: `python -m pytest tests/test_packets.py tests/test_boards.py -q`.
