# Competitor teardown: Stathead, Cleaning the Glass, PBPStats

Date: 2026-09-10. Mode: explanation. Read this to decide what Dime builds next, not to copy any one competitor.

## What Dime has today

Dime is a chat-first NBA analyst. The tools in `backend/app/tools/` cover matchup splits, situational splits with regression checks, trade value and fit, player comps, an award race and debate kit, matchup previews, streaks, lineup ratings with sample floors, a 10k-sim game predictor, a playoff simulator, head-to-head histories, team shot-zone diets, impact estimates, game-log search, ELO standings, rotation checks, and rest advantage (in progress). Data is warehouse-first (polars), with play-by-play cached. A salary scraper holds 461 real contracts, which powers the trade checker.

The pattern: Dime answers questions about the current season well, explains its answers, and simulates forward. It does not yet clean its inputs the way analysts demand, does not query arbitrary history, and does not expose possession-level structure.

## Stathead

The query engine for the Basketball Reference database. Plans start at $9 per month with a one-month free trial.

### Analyst questions it answers that Dime cannot

Stathead ships a family of finders: Season and Career, Game, Streak, Span, Versus, Shot, and Quarter. Data runs from 1946-47 to the present across NBA/BAA, ABA, and WNBA, plus college hoops. Filters combine stats with team success (finals, playoffs, win totals), biography (age, height, college, shooting hand, draft round and pick and team, year of career), and status (active, All-Star, Hall of Fame, awards). Output can be totals, per game, per 36, per 48, per 75 possessions, or per 100 possessions.

So it answers questions like: every 50-point game against the Celtics since 1990. Rookie seasons with 20-plus points per game on 60 percent true shooting. The longest 30-point streaks in playoff history. Shots matching arbitrary criteria. Nobody else offers this combinatorial depth across eight decades.

Dime has streak finders and game-log search, but only over its warehouse seasons, with no biographical or draft filters and no shot-level finder. It cannot do cross-era leaderboards at all.

### UX and data strengths

Depth is the moat. Eighty years of consistent data with one query language. Shareable result URLs. Sample searches and tutorials that teach the tool. CSV export. It sits next to the site analysts already live on.

### Gaps Dime could own

Stathead is a form, not a conversation. Every question means learning its filter panels. It has no garbage-time filtering, no lineup finder, no shot quality, no tracking data, and no predictive layer. Its numbers arrive bare, with no explanation and no percentile context. It is paywalled and its UI has barely changed in a decade. The entire product assumes the analyst knows exactly what to ask and where to click.

## Cleaning the Glass

Ben Falk's subscription stats site (former Sixers VP of Basketball Strategy, Blazers analytics). Insider stats are $5 per month after a one-week free trial.

### Analyst questions it answers that Dime cannot

Cleaning the Glass scrubs garbage time from every number, using quarter, score margin, and starters on the floor as the definition. It also removes end-of-quarter heaves. It replaces 1-through-5 positions with Point, Wing, Big, Combo, and Forward. It splits per-possession stats into halfcourt, transition, and putbacks. Team pages show efficiency, the four factors, and shooting by location (rim, short mid, long mid, corner three, non-corner three) plus location-adjusted eFG. Lineup pages show lineups with at least 15 possessions, percentile ranks against lineups with 100-plus possessions, on-court and off-court filters with all-or-any player logic, and shooting by location on offense and defense.

So it answers questions like: is this offense actually good, or is it padded by garbage time. How does this lineup shoot from every zone, on both ends. Which five-man units should close games, with percentile context doing the interpreting. Dime reports raw net ratings and zone diets that include garbage time. It has no clean-minutes mode, no halfcourt and transition splits, and no percentile framing.

### UX and data strengths

Every number carries its context. Percentiles and ranks sit next to raw stats, so the reader never has to guess whether a number is good. The stat taxonomy matches how modern analysts think: four factors, shot location diet, play context. The garbage-time scrub is the trust moat. Analysts cite its numbers because they know what was excluded. Falk documents the process behind each stat, so users learn the tool's judgment as they use it.

### Gaps Dime could own

Everything is a fixed view. There is no arbitrary query builder, no game finder, no cross-season spans, and no shot charts. History starts in the mid-2010s, so it cannot touch Stathead's eighty years. It is paywalled, NBA-only, and it has no predictions, no trade tools, and no narrative layer. It tells you what is true but never what to do about it. You still have to know what to look for.

## PBPStats

Darryl Blackport's free play-by-play explorer, built on an open-source parser that annotates every event with the lineups on the floor and full possession detail.

### Analyst questions it answers that Dime cannot

The possession finder filters by the initiating action: what a player or team produces when a possession starts with a defensive rebound versus a made basket versus a steal. Team stats split by scoring margin. Assist networks show who creates shots for whom. Lineup-specific shot charts. With-or-without-you on and off numbers. Shot Quality, an expected effective field goal percentage built from court location and play context, with teammate shot quality compared on versus off the court. It also carries G-League data.

So it answers questions like: Jokic's points per possession after defensive rebounds versus after makes. Which teammates get better shots when this player sits. Whether a hot shooting stretch is luck or shot diet. Dime has play-by-play in its cache but exposes none of this structure. It has no possession finder, no assist networks, no margin splits, and no expected-eFG model.

### UX and data strengths

It is the only free possession-level explorer, and it exposes the building blocks instead of hiding them: possession details, shot coordinates, lineup IDs, documented SQL. Analysts trust it because they can see the machinery. The open-source parser means the methodology is auditable, which no paid competitor offers.

### Gaps Dime could own

The UI is sparse and dated. Views are single-season. There is no narrative or explanation layer, no predictions, no cross-season query builder, and no trade, prop, or debate tooling. Discoverability is poor: the site assumes you already know the question. It gives you the raw material for an argument and leaves the arguing to you.

## Top 5 feature opportunities for Dime

Ranked by analyst value against build cost, given Dime's stack (warehouse-first polars, cached play-by-play, chat interface, existing regression check and matchup previews).

| Rank | Opportunity | Analyst value | Build cost | Why now |
| --- | --- | --- | --- | --- |
| 1 | Clean-minutes mode: garbage-time filter on every tool | Very high | Low to medium | Dime already caches play-by-play and computes lineup stats. Add a classifier on quarter, margin, and starters on the floor, then a default-on toggle every tool respects. This is Cleaning the Glass's moat, and it is the fastest way to make every Dime number trustworthy. |
| 2 | Conversational Season, Game, and Span finder | Very high | Medium | Dime has game-log search and streak finders. Add season aggregates plus biographical filters (age, draft info) to the warehouse, then let the chat planner turn plain questions into filter queries. Stathead charges $9 a month for forms. Dime answers in one sentence. |
| 3 | Shot Quality: expected eFG from location and play context | High | Medium | The play-by-play parser already emits zone fields (at rim, short mid, long mid, arc three, corner three) and shot context (putback, heave, assisted). Dime has team shot zones. Build a zone-and-context expected eFG model and report actual versus expected. It plugs directly into the existing regression check and separates luck from skill. |
| 4 | Possession finder by initiating action | High | Low to medium | Possession start types already live in play-by-play. Expose filters on start type and scoring margin. It feeds matchup previews with tactical specifics that no competitor surfaces conversationally. |
| 5 | Lineup-versus-lineup matchup matrix | Very high for playoff analysis | Medium | No competitor does this. Cleaning the Glass has lineup pages, PBPStats has lineup stats, neither answers which of our five-man units beats their closing lineup. Dime has lineup ratings with sample floors and matchup previews. Cross opposing units head to head with the same sample-floor discipline. This becomes the playoff-series weapon. |

## Honorable mentions

- **Team stats by scoring margin.** Cheap PBPStats parity. Fold into the possession finder rather than shipping alone.
- **Assist networks.** Medium cost, real value for playmaking debates, narrower audience than the top five.
- **Leverage-weighted clutch.** The NBA's clutch definition (last five minutes, margin within five) is crude. A win-probability leverage weight is the better version. Medium cost.
- **CBA-accurate trade validation.** Dime has 461 real salaries and a trade checker. Adding real salary-matching rules is low to medium cost and high value for the debate audience. It ranks below the top five on pure analyst value.
- **Cross-season historical depth.** Do not chase Stathead's 1946-47. The scraping and cleaning cost is high and the moat is eighty years deep.

## What not to copy

Do not copy Stathead's forms. The conversational interface is Dime's structural advantage; a finder that takes a sentence beats one that takes ten clicks. Do not copy Cleaning the Glass's fixed views. Steal the garbage-time scrub and the percentile context, not the page layout. Do not copy PBPStats's UI. Steal the possession structure and the open methodology, not the sparse tables. Every competitor assumes the analyst knows the question. Dime's edge is answering the question and explaining the answer in the same turn.
