# Competitor teardown: Stathead, Cleaning the Glass, Basketball-Reference, NBA.com stats

Date: 2026-09-10. This refreshes the earlier same-day draft: it adds the
missing Basketball-Reference and NBA.com stats sections and expands the
opportunity list to 10 ranked question-types, grounded in the competitors'
actual public feature sets (verified via web search today, not guessed).
Dime is a chat-first NBA analyst on `muse/backend`. Mode: explanation —
read this to decide what Dime builds next, not to copy any one competitor.

## What Dime has today

The tools in `backend/app/tools/` cover matchup splits, situational splits
with a regression check, trade value and fit (461 real salaries power the
trade checker), player comps, an award race and debate kit, matchup previews,
streaks, lineup ratings with sample floors, a 10k-sim game predictor, a
playoff simulator, head-to-head histories, team shot-zone diets, impact
estimates, game-log search, ELO standings, rotation checks, rest advantage,
and hustle leaderboards (`get_hustle` in `league.py:261`,
`get_hustle_boards` in `player.py:1574`). Data is warehouse-first (polars),
with play-by-play cached. DimeBench scores tool_f1, numeric accuracy,
groundedness, and latency against runtime-generated tasks.

The pattern: Dime answers current-season questions well, explains its
answers, and simulates forward. It does not scrub garbage time, does not
query arbitrary history, does not touch tracking/defensive-matchup data, and
exposes none of its play-by-play structure conversationally.

## Stathead

The query engine for the Basketball Reference database. Plans start at $9
per month with a one-month free trial. Data runs 1946-47 to the present
across NBA/BAA, ABA, and WNBA, plus men's and women's college hoops (a new
addition: Game and Season Finders for college).

### Analyst questions it answers that Dime cannot

Stathead ships a family of finders: Season and Career, Game, Streak, Span,
Versus, Shot, and Quarter. Filters combine stats with team success (finals,
playoffs, win totals, division finish), biography (age as of game day, height,
college, position, draft round/pick/team, year of career, shooting hand,
Hall of Fame, active status), and game context (started, birthday,
double-double/triple-double). Output can be totals, per game, per 36, per 48,
or per 100 possessions. Plus/minus was added to the Game, Streak, and Span
finders (coverage back to 1996-97).

So it answers questions like: every 50-point game against the Celtics since
1990. Rookie seasons with 20-plus points per game on 60 percent true
shooting. The longest 30-point streaks in playoff history. Shots matching
arbitrary criteria, with the shooter, quarter, and game situation attached.
No other public product offers this combinatorial depth across eight
decades.

Dime has streak finders and game-log search, but only over its warehouse
seasons (2025-26 fully; history via sportsdataverse backfills), with no
biographical or draft filters and no shot-level finder. It cannot do
cross-era leaderboards at all.

### Strengths and gaps

Depth is the moat: eighty years of consistent data, one query language,
shareable result URLs, CSV export. The gaps Dime can own: Stathead is a
form, not a conversation — every question means learning filter panels. It
has no garbage-time filtering, no lineup finder, no shot quality, no
tracking data, no predictions, and no explanation layer. Its numbers arrive
bare, with no percentile context. The entire product assumes the analyst
knows exactly what to ask and where to click.

## Cleaning the Glass

Ben Falk's subscription stats site (former Sixers VP of Basketball Strategy).
Insider stats are $5 per month after a one-week free trial.

### Analyst questions it answers that Dime cannot

Cleaning the Glass scrubs garbage time from every number. Its published
definition: 4th quarter, margin >25 with 9–12 minutes left, >20 with 6–9
minutes left, >10 with 0–6 minutes left, and two or fewer starters combined
on the floor — and once a game goes garbage, it can never come back. It
also removes end-of-quarter heaves. It replaces 1-through-5 positions with
Point, Wing, Big, Combo, and Forward. It splits per-possession stats into
halfcourt, transition, and putbacks. Team pages show efficiency, the four
factors, and shooting by location (rim, short mid, long mid, corner three,
non-corner three) with location-adjusted eFG. Lineup pages show units with
at least 15 possessions, percentile ranks against lineups with 100-plus
possessions, on-court/off-court filters with all-or-any player logic, and
shooting by location on offense and defense. Player on/off pages break the
team's efficiency, four factors, shooting, and context splits into with and
without that player.

So it answers questions like: is this offense actually good, or is it padded
by garbage time. How does this lineup shoot from every zone, on both ends.
Which five-man units should close games, with percentile context doing the
interpreting. Which teammates' shooting improves when this player sits.

Dime reports raw net ratings and zone diets that include garbage time. It
has no clean-minutes mode, no halfcourt/transition splits, no percentile
framing, and its on/off coverage is a single-season seed, not a product
surface.

### Strengths and gaps

Every number carries its context: percentiles and ranks sit next to raw
stats, so the reader never has to guess whether a number is good, and the
garbage-time scrub is the trust moat — analysts cite its numbers because
they know what was excluded. The gaps Dime can own: everything is a fixed
view. No arbitrary query builder, no game finder, no cross-season spans, no
shot charts. History starts in the mid-2010s. It is paywalled, NBA-only, has
no predictions, no trade tools, and no narrative layer. It tells you what is
true but never what to do about it.

## Basketball-Reference (free tier)

The free site behind Stathead: the lookup workflow every serious fan and
writer lives in. Dense player pages (per-game, totals, advanced, shooting,
play-by-play splits, game logs, salaries), team season pages with team and
opponent ratings including adjusted net ratings, year-by-year playoff
breakdowns, draft pages with franchise and school and pick-slot views, league
leaders in dozens of categories, franchise history indexes, and the daily
scores page with standings on that date. The old Play Index finders moved
behind the Stathead paywall, but the reference depth — eighty years,
cross-linked, instantly navigable — remains free.

### Analyst questions it answers that Dime cannot

Cross-era lookup at zero cost: who won MVP in 1988, what did the '86 Celtics
shoot as a team, every draft pick from Duke, a franchise's all-time leaders.
Dime's history tables are thin sportsdataverse backfills; it cannot answer
"before 2010" questions with any authority. BRef also gives analysts the
adjusted team ratings (schedule-strength-adjusted net ratings) that Dime's
ELO standings approximate but don't publish as reference.

### Strengths and gaps

Speed and trust: it's the fastest lookup in the sport and the default
citation. The gaps Dime can own: it's pages, not answers — no conversation,
no simulation, no cross-page reasoning, no predictions. Finding anything
non-obvious still requires knowing which page to open.

## NBA.com stats

The league's official portal (nba.com/stats): box scores, play-by-play,
shooting, tracking summaries, lineups (2-man through 5-man, team or
league-wide), Hustle (deflections, screen assists, loose balls recovered,
charges drawn, shots contested, at player and team level), the Defense hub
with matchup data (who guards whom, points allowed to the primary matchup),
clutch filters, shot charts, and the tracking shot dashboard — every shot
sliced by closest defender distance (very tight to wide open), touch time,
and dribbles, plus catch-and-shoot vs pull-up splits. Filtering is the
standout: virtually every page filters by date range, home/road, opponent,
clutch, starter/bench, regular season vs playoffs, and more. Draft and
combine data goes back to 1947.

### Analyst questions it answers that Dime cannot

NBA.com is the only free source for who-guards-whom: when Dort guards
Edwards, what does Edwards score on how many shots. The only free source
for contested-shot data: how a shooter performs with a very-tight defender
versus wide open, catch-and-shoot versus pull-up efficiency, touch-time
splits. The only free source for hustle at scale across seasons: deflections,
loose balls, screen assists leaders. Dime has hustle leaderboards and zone
diets, but no defender-distance shooting, no matchup data, no touch-time or
dribble splits, and no playtype data (the Synergy-style playtype dashboards
also live here).

### Strengths and gaps

Official data, broadest free coverage, unmatched filter surface. The gaps
Dime can own: it's a maze of tabs — powerful filters buried in a UI nobody
loves, numbers with no interpretation, no percentile context, no
conversation, no predictions, and matchup-level data that exists but is
painful to extract. Analysts know the data is there and still open
Cleaning the Glass to understand what it means.

## Top 10 question-types as feature opportunities

Ranked by analyst value against build cost, given Dime's stack
(warehouse-first polars, cached play-by-play, chat interface, existing
regression check and matchup previews).

| Rank | Question-type | Example | Answered today by | Dime status | Build cost |
|---|---|---|---|---|---|
| 1 | Garbage-time-free efficiency | "Is this +4 net rating real or bench mob padding?" | Cleaning the Glass | Can't: Dime's ratings and zone diets include garbage time; it has cached PBP but no classifier | Low–medium: classify on quarter/margin/starters-on-floor (CTG's published rule), default-on toggle every tool respects |
| 2 | Combinatorial history finder, conversational | "Every 40-point game vs the Celtics since 1990" | Stathead (paywalled), BRef pages (manual) | Can't: gamelog search covers seeded seasons only; no bio/draft filters; no shot finder | Medium: season aggregates + bio filters in warehouse, planner turns sentences into filter queries. Stathead charges $9/mo for forms; Dime answers in one sentence |
| 3 | Who-guards-whom defensive matchups | "What does Edwards score when Dort guards him?" | NBA.com Defense hub | Can't: no matchup data at all | Medium: ingest the matchup endpoints (player-level, in Dime's `nba_stats` source family), expose as a tool. No free competitor does this conversationally |
| 4 | Lineup-vs-lineup head-to-head | "Which of our 5-man units beats their closing lineup?" | Nobody | Partial: lineup ratings with sample floors + matchup previews exist (`lineup.py`, `lineup_matrix.py`) | Medium: cross opposing units with the same sample-floor discipline. The playoff-series weapon |
| 5 | Contest-adjusted shot quality | "Is this hot stretch luck or diet — and is he actually getting open looks?" | NBA.com tracking (closest defender, touch time), Stathead shot finder | Can't: zone diets exist (`zone.py`) but no defender-distance, touch-time, or catch-and-shoot/pull-up splits | Medium: expected-eFG model from location + contest + context; plugs into the existing regression check |
| 6 | With/without-you, any span | "Team's halfcourt offense with and without Haliburton, last 20 games" | Cleaning the Glass on/off pages, Stathead Span Finder | Partial: `silver_on_off` is a single 2025-26 seed; no span control | Low–medium: on/off from cached PBP over arbitrary spans, with CTG-style context splits |
| 7 | Quarter and clutch splits | "Who actually takes over fourth quarters?" | Stathead Quarter Finder, NBA.com clutch filters | Can't: splits exist (`splits.py`) but no quarter/half finder | Low: quarter tags already live in PBP; expose as splits + a finder |
| 8 | Cross-era lookup and leaderboards | "Most 50-point games before age 25" | Stathead, BRef (free lookup) | Can't: history tables are thin backfills; nothing before ~2015 is trustworthy | High to chase fully; low for a curated slice (MVP/award/draft history) — don't chase the 80-year moat |
| 9 | Draft and college pipeline | "Best pick-and-roll passers in the 2027 class" | Stathead college tools, BRef draft pages | Partial: `seed_draft.py` is historical NBA only; no college stats | Medium: college season/game data is public; feeds the draft-debate audience |
| 10 | Shot-level search with context | "All his corner-3 attempts in 4th quarters of close games" | Stathead shot finder, NBA.com shot charts | Can't: `silver_shots` is seeded (`promote_2025_26.py --shots`) but no tool searches individual shots | Low–medium: shot table + PBP context already in warehouse; needs a query tool |

### Honorable mentions

- **Possession-by-initiation splits** (points per possession after defensive rebounds vs makes vs steals) — cheap once PBP structure is exposed; fold into #6 rather than shipping alone.
- **Assist networks** (who creates shots for whom) — medium cost, real playmaking-debate value, narrower audience.
- **CBA-accurate trade validation** — Dime has 461 real salaries and a trade checker (`league.py`); real salary-matching rules are low–medium cost and high value for the debate audience, but rank below on pure analyst value.
- **Leverage-weighted clutch** — the NBA's clutch definition (last 5 min, margin ≤5) is crude; win-probability leverage weighting is the better version. Medium cost.
- **Playtype (Synergy-style) data** — NBA.com has it; Dime has none. Real value for scheme questions, but the data licensing/shape work is the cost.

## What not to copy

Do not copy Stathead's forms. The conversational interface is Dime's
structural advantage; a finder that takes a sentence beats one that takes
ten clicks. Do not copy Cleaning the Glass's fixed views. Steal the
garbage-time scrub and the percentile context, not the page layout. Do not
copy BRef's page maze or NBA.com's tab labyrinth. Steal the data shapes —
matchup tables, contest splits, bio filters — not the navigation. Every
competitor assumes the analyst knows the question. Dime's edge is answering
the question and explaining the answer in the same turn.

## Sources

- Stathead feature set and pricing ($9/mo, finders family, 1946-47–present,
  college tools): https://stathead.com/sport/basketball/?utm_source=bbr&utm_medium=sr_xsite&utm_campaign=2023_01_topnav_stathead&utm_content=lnk_top&__hstc=180814520.758cab97f9c9e4ed5093b0cc03a1f0e1.1728534047817.1728534047817.1728534047817.1&__hssc=180814520.1.1728534047817&__hsfp=4241693014
- Stathead Game Finder filter surface (team success, age, draft, position):
  https://www.sports-reference.com/stathead/tiny/5aJOg
- Cleaning the Glass lineup pages (percentile framing, min-possession
  floors): https://cleaningtheglass.com/stats/lineups?season=2023&seasontype=regseason&min_possessions=400
- Cleaning the Glass garbage-time definition (4th quarter; margin >25/20/10
  at 9–12/6–9/0–6 min; ≤2 starters combined; one-way ratchet) and full
  feature tour (positions, halfcourt/transition/putbacks, on/off pages, box
  scores): https://www.basketballinsiders.org/news/an-nba-statistics-treatise/
- NBA.com stats portal feature surface (box scores, PBP, tracking summaries,
  2–5-man lineups, Hustle, Defense hub matchups, clutch, shot charts,
  defender-distance/touch-time/dribble splits, draft/combine back to 1947):
  https://www.basketballinsiders.org/news/an-nba-statistics-treatise/ and
  https://github.com/JovaniPink/awesome-nba-data
- Stathead vs BRef Play Index history, plus/minus finder coverage (1996-97):
  https://www.basketball-reference.com/blog/indexe32f.html?p=3214
- Lineup-data selection-bias analysis (why sample floors matter):
  https://www.theringer.com/2023/04/13/nba/2023-nba-playoff-preview-how-to-use-and-not-use-lineup-data
