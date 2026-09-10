# NBA Data Analyst Market — Research Brief
**Date:** September 10, 2026 | **Prepared for:** Dime product strategy

---

## 1. Who Are NBA Data Analysts?

Five distinct segments, each with different workflows and willingness to pay:

### 1a. Team Front Offices (30 NBA teams)
- Every team has an analytics department. All 30 use Second Spectrum's tracking data (via the league deal); most also pay for Synergy video tagging.
- Workflow: proprietary models + internal dashboards. Daryl Morey (76ers, at 2025 Sloan): **"We absolutely use models as a vote in any decision. We'll treat them almost as one scout."**
- Dean Oliver (ex-Wizards/Kings/Nuggets/Sonics analytics): teams are using AI to **mine years of documented scouting reports** — "Are there pieces of information in their scouts' brains that they can use to make better predictions?"
- The Orlando Magic got exclusive access to **AutoStats** (AI player-tracking derived from game broadcasts, no arena sensors) after a 2022 tech-expo demo — and used it to see college movement data other teams couldn't. Edge-seeking is the culture.
- They build, not buy: Python/R pipelines on top of tracking + PBP data. Will not switch to a consumer tool, but their staff are the tastemakers everyone else copies.

### 1b. Media (ESPN, The Athletic, The Ringer, independents)
- Need: **fast, citable answers** for articles and on-air segments. Screenshot culture is real — the databallr creator (interview, DNVR, ~Mar 2026) said he built his site because **"Stathead screenshots were popular"** and that on-off screenshots spread because they let people **"go 'dunk' on somebody else in an internet argument."**
- The Ringer's analytics-discourse piece (Aug 2026) lists the daily-driver stack of a working NBA writer: **CourtSketch, Dunks and Threes, Bball-Index, Cleaning the Glass, Databallr, Hoops Junkie, Basketball-Reference, PBPstats, CraftedNBA, Inpredictable** — a dozen tabs open at once.
- Thinking Basketball (podcast, 380+ episodes) regularly dissects LEBRON/EPM; BBall Index runs its own metrics podcast (213 episodes).

### 1c. Independent Creators (YouTube, podcasts, Twitter/X, newsletters)
- Same stack as media but free-tier constrained. Heavy users of free tools: StatMuse, CraftedNBA, databallr, PBP Stats free tier.
- They need shareable visuals and "did-you-know" stat hooks. StatMuse's indexed Q&A pages (e.g. "Mark Williams has averaged 12.8 points, 10.5 rebounds and 1.3 assists in 4 games against the Thunder") are SEO machines.

### 1d. Bettors & Props Analysts (large, technical, DIY)
- This segment **builds its own tooling** because nothing off-the-shelf answers their questions. Representative GitHub workflows (all active 2025–2026):
  - **SmartAI-NBA**: Monte Carlo sims (10k sims), XGBoost + CatBoost + Ridge ensemble, EV/parlay builder. Data: `nba_api` + API-NBA + Odds API + PrizePicks/Underdog/DK lines + injury PDFs.
  - **nba-prop-correlation**: SGP (same-game parlay) correlation via conditional hit rates, 15-game rolling medians, statistical lift tests.
  - **Prop_Betting_Regression_Project**: linear regression vs. BettingPros lines, features from Stathead.
  - **Bobby Bets**: LangChain + GPT-4o agent with Mem0 memory, "sports bettor persona."
- Commercial: **FantasyLabs Player Props Tool** (projections vs. sportsbook lines), **StatSharp** (possession-based player stats for handicappers, launched Jan 2025), **Sourcetable** (AI spreadsheet for betting data).
- Core question pattern: *"How has Player X performed vs. [defensive context] over the last N games, and is the line mispriced?"* — requires joining game logs + matchup data + lines. Nobody sells this as a simple product; everyone hand-rolls it.

### 1e. Fantasy Players
- Tools: RotoWire (z-score cheat sheets), Basketball Monster, Hashtag Basketball, Yahoo/ESPN platforms.
- Workflow advice (athlenow, 2026): Basketball-Reference for PER/USG%/TS%, NBA.com for usage/shot charts, **Cleaning the Glass for "in-depth analytical insights,"** ESPN Hollinger for PER. Regression-spotting via expected FG% vs. actual.
- Less technical than bettors; want rankings, waiver-wire hooks, and trade targets — not raw tables.

---

## 2. Competitive Landscape

| Tool | What it is | Price | Strengths | Gaps |
|---|---|---|---|---|
| **Cleaning the Glass** (Ben Falk, ex-76ers VP Basketball Strategy / Blazers analytics) | Contextualized stats site: garbage-time filtered, positional designations (Point/Wing/Big/Combo/Forward instead of 1–5), halfcourt vs. transition splits, percentiles on everything | Subscription (~$7.50/mo at 2018 launch; current pricing behind account wall) | Most trusted "thinking fan's" stats; used by fans, front offices, media, coaches, podcasters, agents. Best-in-class stat contextualization. | Paywalled; one person's product (bus factor); no API; no NL interface; no combining with other sources |
| **Dunks & Threes** | Home of **EPM** (Estimated Plus-Minus); ML projection system; interactive dashboards for every game/player/team | Subscription (free top-5 EPM teaser) | EPM is arguably the best public all-in-one metric; predictive framing ("true skill at each point in time"); current 2025-26 data | Paywalled; metric is a black box to casual users; no NL |
| **PBP Stats** | Open-source Python package (`pip install pbpstats`) + website: on/off, WOWY, lineup, possession, shot-zone data | Free site; **subscriber API** available | Deepest free lineup/on-off tool; programmatic access; WNBA/G-League too | Dated UI; API is paid and low-profile; no analysis layer — just tables |
| **NBA.com Stats** | Official league stats, box scores back to 1946-47, tracking data, shot charts | Free | Authoritative; most complete single source; "4.5 quadrillion computations" marketing | **No official API** — the `stats.nba.com` endpoints are unofficial, break 2–4×/year, block datacenter IPs (AWS etc.), and throttle aggressively. Every indie project documents workarounds. Clunky UI. |
| **Basketball-Reference / Stathead** | Deepest historical DB (1946–present); Stathead = query builder (Game/Streak/Span/Versus finders, leaderboards) | BRef free (ad-supported); **Stathead $9/mo one sport, $16/mo all sports**, 1st month free | The historical record; Stathead answers "who had X in a season" questions nothing else can; explicit segments: fans, creators, betting & fantasy, media, team pros | Stathead requires learning a query UI — no natural language; BRef tables wrapped in HTML comments break scrapers; no impact metrics (that's what EPM/LEBRON are for) |
| **Second Spectrum** (Genius Sports, $200M acq. 2021) | Optical tracking in all 29 arenas; EPV, matchup detection, off-ball movement | Enterprise (league/team deals) | The raw truth — 25fps positional data; powers NBA's official tracking stats; all 30 teams are clients | Not available to the public at any price |
| **Synergy Sports** | Video tagging: play types, defensive coverages, shot charts linked to film | ~€15–40k/yr per team (Euroleague datapoint) | Film + data in one place; the scouting standard | Enterprise; no public tier; video-first, stats-second |
| **StatMuse** | **Natural-language sports Q&A** — "lebron stats vs sas" → answered with table + illustration; indexed Q&A pages | Free | Only incumbent with NL interface; massive SEO footprint; covers NBA/NFL/MLB/NHL | Answers are **lookup-only** — no analysis, no comparisons across metrics, no "why"; can't do multi-step reasoning ("who's most clutch" → just a table) |
| **BBall Index** | **LEBRON** metric + role/talent grades, matchup data, defensive playmaking | Freemium (some paid) | Rich skill/role taxonomy; matchup data (e.g. "93rd percentile guarding athletic finishers"); podcast content engine | Fragmented free/paid; site UX is dense; no NL |
| **CraftedNBA** | Free aggregator: DARKO, DRIP, LEBRON, RAPTOR, CraftedPM side-by-side; comparisons, roles | Free | Only place comparing all-in-one metrics head-to-head | No original data; thin analysis; one-maintainer risk |
| **databallr** | Free dashboard + on/off/WOWY views | Free | Dashboard is the most-used feature (creator interview); built for the screenshot/debate use case | Solo dev; dashboard "not optimal yet" (creator's own words); no NL |
| **NBAstuffer / Inpredictable / 82games / nbarapm.com** | Long-tail specialists (win probability, lineup archives, RAPM) | Free | Deep in their niche | Narrow; aging UIs (82games); no integration |

**Pricing summary:** a serious analyst's stack runs **$25–40/mo** across 3–4 subscriptions (CTG + D&T + Stathead + BBI/PBP API) — before touching enterprise tools.

---

## 3. Pain Points (with receipts)

1. **Subscription fatigue / paywall fragmentation.** The Ringer's working writer keeps **a dozen paid/free tabs open** because no single tool covers history (Stathead) + context (CTG) + impact (EPM/LEBRON) + lineups (PBP). Sports-Reference's Sean Forman admitted the economics forced the Play Index behind a paywall: *"a subscription model aligns our interests much better... we can't continue to support the products without a viable revenue stream."*

2. **No official NBA API.** The entire indie ecosystem builds on undocumented `stats.nba.com` endpoints that **break 2–4× per year** (per the nba-api-go maintainers' runbook: "Fix NBA.com API Changes — Trigger: users report endpoint errors, Frequency: 2-4 times/year") and **blacklist cloud IPs** ("requests from these IPs seem to just hang" — lawderp/nba). One 2026 project's CLAUDE.md warns: *"nba_api and stats.nba.com are unofficial — handle failures and rate limits gracefully... never let a single game failure abort the whole backfill."* Another runs its loader **locally because stats.nba.com blocks datacenter IPs.**

3. **Can't combine sources.** EPM lives behind D&T's paywall, LEBRON behind BBI's, history behind Stathead's, lineups on PBP. Cross-metric questions ("where do EPM and LEBRON disagree on Wemby and why?") require manual export + spreadsheet.

4. **No natural-language analysis.** Stathead's power requires learning its finder UI. StatMuse takes NL but only does **lookups** — ask "who's the most clutch player this season and is it sustainable?" and you get a table, not an answer. The **text-to-SQL gap is being filled by hobbyists**: `rjhxu/can-he-shoot` (2026) is literally "statmuse clone + shotmap" with Cohere NL→SQL.

5. **Metric wars with no referee.** EPM vs. LEBRON vs. DARKO vs. DRIP vs. RAPTOR vs. RAPM — each on its own site, each with its own methodology page, no neutral comparison with explanations. CraftedNBA aggregates numbers but doesn't adjudicate.

6. **Trust/hallucination barrier for AI.** Analysts won't trust an LLM that cites stats without sources — the entire culture is "screenshot the table." Any AI product must show its work or it's dead on arrival.

7. **Stale data anxiety.** Bettors and fantasy players need *today's* numbers; several tools update on unclear schedules. The NBA's own AWS partnership (below) is a response to fans wanting real-time insight.

---

## 4. Emerging Trends (2024–2026)

1. **NBA + AWS "Inside the Game" (Oct 2025).** The league's official AI stats push: **Gravity** (quantified defensive attention via 60fps optical tracking), **Defensive Box Score** (primary defender assigned to every stat in real time), **Shot Difficulty / Expected FG%** (shooter orientation, contest details), and an **AI Play Finder** (Bedrock/SageMaker similarity search over thousands of games' worth of player movement). Available in the NBA App and on Prime broadcasts. *Signal: the league itself is productizing the exact "context stats" layer CTG pioneered — the bar for everyone else just rose.*

2. **Front offices treat models as staff.** Morey (Sloan 2025): models get "a vote in any decision... almost as one scout." Dean Oliver: AI mining of historical scouting reports to extract signal from scouts' documented (and undocumented) knowledge.

3. **AI tracking without hardware.** Orlando Magic's AutoStats deal (game-broadcast-derived tracking for *college* players) shows the edge is moving to whoever can generate novel data, not just analyze public data.

4. **NLP on qualitative data.** Academic work (Luo, Li & Li; Nguyen et al.): BERT embeddings of scouting reports for player similarity and strength/weakness extraction; multimodal models (stats + text) beating single-source models.

5. **Betting AI agents.** Sportradar runs AI season simulations off tens of thousands of data points; open-source "Bobby Bets" (LangChain + GPT-4o + Mem0) shows the agent pattern reaching retail bettors.

6. **Text-to-SQL goes mainstream in the niche.** The can-he-shoot project (Cohere NL→validated SELECT, read-only role, hallucination guards) is the template: analysts want to *ask*, not *click through finders*.

7. **Interpretability research.** Nature Scientific Reports (2025): stacked ensembles + SHAP for lineup optimization and tactical design — the research frontier is *explainable* models, not just accurate ones.

---

## 5. Opportunity Gaps — Where Dime Wins

**Thesis:** Every incumbent is either a *database with a query UI* (Stathead, NBA.com), a *metric with a dashboard* (D&T, BBI, CTG), or a *lookup bot* (StatMuse). Nobody is an **analyst**: nobody takes a question, gathers evidence across sources, reasons about it, and answers with receipts. That's the gap.

### Concrete wedges

1. **Natural language over everything, with evidence.** StatMuse proved NL demand; it stops at lookups. Dime's 60+ tool agent that *reasons* ("clutch = last-5-min-close + efficiency + volume, here's the table, here's the caveat") and cites every number is a category jump. The trust requirement (#6 above) is exactly what the evidence-grounded architecture solves.

2. **Cross-metric adjudication.** "EPM says X, LEBRON says Y — who's right and why?" No tool answers this. Dime can, because it can pull both and explain methodological differences in plain English. This is the single most differentiated query class.

3. **The debate/social loop.** The databallr creator's insight — on-off screenshots exist to **win internet arguments** — is a growth strategy: shareable debate cards turn every analysis into distribution. None of the incumbents do this natively.

4. **Personalization incumbents can't copy easily.** Watchlists + morning briefings + leaderboard deltas = "your analyst." CTG/D&T/Stathead are pull-only; Dime pushes.

5. **Bettor-adjacent Q&A without giving picks.** The props-analyst DIY segment spends hours on `nba_api` wrangling to answer contextual questions ("last 15 vs. top-10 defenses," "with/without splits," "back-to-back splits"). Dime answers these in seconds. (Position carefully: analysis tool, not tout service.)

6. **Free-tier wedge vs. $25–40/mo stack.** A generous free NL tier undercuts the subscription-fatigue complaint directly. The incumbents *must* paywall (Forman said so); an AI-native entrant can subsidize with cheap inference.

7. **Freshness as a feature.** Real-time-feeling answers during the season (tonight's games, last night's movers, streaks) vs. tools with opaque update schedules.

### What would make analysts switch
- **One tab instead of twelve.** The Ringer writer's stack is the target: if Dime answers the CTG question *and* the Stathead question *and* the EPM question in one chat, the subscriptions start lapsing.
- **Answers they can cite.** Screenshots/tables with source + timestamp. Analysts' currency is credibility; give them citable artifacts.
- **Speed on the long tail.** The questions that currently require a Python script ("every 30-point game by a rookie vs. winning teams since 2010") should take 10 seconds.
- **Don't fight the metric priests.** Support EPM/LEBRON/DARKO/RAPTOR side-by-side; explain, don't replace. The community decides winners — Dime just referees.

### Risks to watch
- **Data licensing.** Scraping BRef at scale violates their data-use policy; stats.nba.com is unofficial. Dime's warehouse strategy (cache + refresh) is the right call but needs a compliance review before any commercial step.
- **The league is coming downmarket.** NBA+AWS "Inside the Game" puts Gravity/Defensive Box Score/Shot Difficulty in the free app. The "context stats" moat shrinks; the **reasoning + personalization** moat matters more.
- **StatMuse could add LLMs.** They have the brand, the SEO, and the data. Dime's window is *depth of analysis* before they move.
