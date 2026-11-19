# Packets

Raw KPI `value`, table `rows`, and chart `data` remain numeric. Shared model
formatting supplies KPI `display`, table `display_rows`, and chart `display_data`
for presentation (whole ages/counts, compact dollars, percentages, signed impact).
Tables have optional `title`/`note` and `collapsed` (default false); identifiers
are omitted. Impact highlights are capped at eight rows; full on/off statistics
are the final, collapsed appendix. Supported sections include cited summaries.

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

## Trade evaluation

`POST /api/packets/trade_evaluation` accepts `{team_a, team_b, a_sends,
b_sends, season="2025-26", notes?}`. Teams accept exact NBA abbreviations,
full names or nicknames (including BRef BRK/CHO/PHO aliases). Players accept
exact accent-normalized names or ids. A player must have an unambiguous
season row on the stated team; otherwise 422 includes `team_found` for a
team mismatch. Multi-team aggregate rows do not establish team membership.
Duplicate players and an entirely empty deal are rejected; one empty side
is supported without assigning value to any picks mentioned in notes.

Five sections cover the deal, cap, production, rotation and contracts.
Warehouse reads are bounded. Existing `_payroll`/`_payroll_source` helpers run
on an in-memory copy of bounded **2026-27** source rows, retaining their source
precedence (salary sheet before cap-player fallback) without mixing vintages.
Deal dollars use that same roster source. Missing, negative or ambiguous
salaries produce nulls with reasons, never zero-filled outgoing/incoming sums.
Recorded payroll is not a certified complete cap ledger. Contract terms use
`silver_cap_players`, whose salaries can differ from the preferred payroll sheet.

Cap constants are imported from `shared.tools.league.CAP` and cited to that
helper. A simplified rule implementation already exists in `get_trade_check`:
the packet reuses `_allowed_incoming` and `_apron_state` for its salary band,
and reports the same second-apron aggregation restriction. This is a snapshot
check using 2026-27 salaries, not legality for the production season, and omits
the same exceptions/other CBA rules. No call to the fuzzy/live-capable trade-value
tool is made. Source citations retain replayable warehouse SQL; constant
citations contain a parameterized SELECT of the imported values and code origin.

Production rates are weighted by GP × MPG, an estimate based on rounded rates;
games are summed. These are weighted rates, not additive projected production.
Rotation uses summed player-game minutes by MATCHUP team. Incoming minutes
reflect observed origin-team usage divided by destination-team season minutes,
not a forecast. Missing logs/on-off components stay visible as nulls/Callouts.
Notes (including picks) are explicitly user-provided, unverified and unvalued.

Run: `python -m pytest tests/test_packets.py tests/test_packets_trade.py tests/test_boards.py -q`.
