---
name: game-prep-and-rotations
description: Scout an opponent's next game — lineup and rotation analysis, on/off impact, shot zones, four factors, injuries and news — with explicit small-sample labeling for in-progress seasons like 2026-27.
---

# Opponent Game Prep & Rotation Analysis Playbook

Guidance for reasoning about an upcoming game, an opponent's rotation, or
how a team actually functions — not a fixed procedure. Use whichever tools
answer the question. Every number is warehouse-sourced (never a live
endpoint at question time) and tools cite their own sources.

## 1. Tools and when they matter

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_matchup_preview` / `get_matchup_brief` / `get_opponent_scout` | Assembled head-to-head prep for a game, or a warehouse dossier on the opponent (form, four factors, shot profile, top lineups, injuries, season head-to-head). | Starting point for any "scouting report for X vs Y" ask — then drill into whatever claims it makes. |
| `get_team_daily_brief` | One team's dated brief: injuries, news, transactions, last result, standing, upcoming schedule. | The "what changed lately" pass on a team — cheaper than assembling injuries + news + results separately. |
| `get_lineups` / `get_lineup_stats` | Which five-man units play, how many minutes, and their results. | "What's their closing unit", "what do they start", rotation-structure questions. Filter by `season_type` for playoff prep. |
| `get_lineup_leaders` | Best/worst units league-wide or per team by minutes and net rating. | "Their best five" and unit-quality claims. Respect `min_minutes` — the default floor already prunes noise. |
| `get_on_off` / `get_wowy` | Possession-level impact of one player, or of a pair together vs apart. | "How much does X actually matter", "does the A+B pairing work". On/off is the sharpest signal for rotation value. |
| `get_rotation_check` / `get_stint_timeline` | Rotation patterns and stint structure. | "How does the coach stagger the stars", substitution-pattern questions. |
| `get_shot_zones` / `get_team_shot_zones` / `get_shot_compare` | Where shots come from and where they're efficient, player or team. | Scheme-relevant prep: where the opponent generates offense, where they can be pushed. |
| `get_team_four_factors` / `get_four_factors` | eFG/TOV/OREB/FTr team or on-off level — the mechanical drivers of results. | Explaining *why* a team or unit wins: e.g. a great net rating carried by offensive rebounding tells you the game plan lever. |
| `get_injuries` / `get_injury_impact` | Current injury report and its measured cost. | Every prep answer — availability changes everything downstream. Check first; a "weak bench" analysis that ignores three rotation players out is wrong, not just incomplete. |
| `get_news_feed` | Recent headlines per team/player. | Late-breaking context the numbers miss — trades, role changes, coach comments about rotations. |
| `get_head_to_head` / `get_season_series` / `get_matchup_splits` | Prior meetings and player-level splits vs this opponent. | "How did it go last time" and matchup-specific player performance. |

## 2. Building a prep answer

A useful prep read has three layers; lead with whichever changes the game.

**Availability first.** `get_injuries` on both teams, then
`get_injury_impact` for what each absence is worth, then `get_news_feed`
for anything the injury report hasn't caught up to. Re-derive everything
else under the available roster — the opponent's best five with a starter
out is a different unit than the season aggregate.

**How they play.** `get_team_shot_zones` + `get_team_four_factors` sketch
the offensive/defensive identity: rim-heavy vs perimeter, glass vs
transition, pace. `get_head_to_head`/`get_season_series` add the specific
opponent history. `get_matchup_preview` ties it together if you started
with individual tools instead.

**Who plays.** `get_lineups`/`get_lineup_leaders` name the real units —
starters, the closing five, the bench mob — with minutes and net rating.
`get_on_off`/`get_wowy` say who drives it: a unit's strong net rating that
fully overlaps one player's on/off is a player story, not a lineup story.

## 3. Reading lineups and on/off correctly

- **Minutes are the prior.** A lineup with 8 minutes and +15 net rating
  is trivia; 200+ minutes is a pattern. Always report the minute base with
  the rating, and prefer `min_minutes` filters over post-hoc caveats.
- **On/off ≠ causation, but it's the best single number.** `get_on_off`
  rows are possession-level (Stat / On / Off / On-Off). Use `get_wowy` to
  separate overlapping players: if A's on-off collapses when split by B's
  presence, the value belongs to the pairing or to B.
- **Per-possession before per-game.** Net rating and on/off values are
  per-100-possessions; say so, and never compare them directly to
  point-differential.
- **Four factors as the mechanism.** When a unit or team's rating stands
  out, `get_team_four_factors`/`get_four_factors` explain it (eFG, TOV%,
  OREB%, FTr) — that's the scouting-actionable part, e.g. "they win
  because they never turn it over, so pressure won't rattle them" vs
  "they live on OREB, so gang-rebound".

## 4. Small samples — label them, don't hide them

The in-progress 2026-27 season is the standing case study: tools now
return early-season rows with real provenance, but the sample is small.

- **Always attach the sample.** Every early-season number gets its
  qualifier: games played, minutes for lineups/on-off, attempts for shot
  zones. "Top-5 defense" in November is ~15 games, not a season.
- **Thresholds exist for a reason.** `get_lineup_leaders`' `min_minutes`
  floor and `get_shot_zones`' `min_attempts` floor are the sample guards —
  don't lower them to manufacture coverage; if a player's zone profile is
  under the floor, say the sample is too thin and give last season's
  number labeled as such instead.
- **Distinguish new signal from noise.** Early-season ranks move fast —
  flag conclusions that rest on <10 games or <50 lineup minutes as
  volatile; where a prior-season read exists, show both rather than
  silently choosing.
- **Playoff-prep caveat applies to everyone.** Regular-season on/off and
  lineup stats don't cover playoff rotations (`season_type="playoffs"`
  filters exist where the data does); say when prep rests on regular-
  season-only data.

## 5. Warehouse-grounded examples

*"Prep for BOS @ NYK."*
`get_injuries` both teams → available rosters; `get_news_feed("NYK")` →
late changes; `get_team_shot_zones` + `get_team_four_factors` both → NYK
eFG/OREB profile vs BOS's rim-frequency allowed; `get_lineups` NYK →
starting and closing units with minutes; `get_on_off` their two stars →
who the offense actually runs through; `get_season_series` → prior
meetings. Report names the units, the players, and the mechanism — with
each early-season number's game/minute count attached.

*"Their bench lineup keeps killing us — is it real?"*
`get_lineup_stats`/`get_lineup_leaders` for that unit → net rating on its
minute base; `get_wowy` on the pair that drives it → does it survive
splitting; `get_shot_zones`/`get_shot_compare` → where its points come
from (schematic leak vs variance); `get_four_factors` → which factor is
producing the margin. Small-sample labels go on every number.

*"Who should we actually scheme to stop?"*
`get_on_off` across the opponent's core → which player's absence moves
the rating most; `get_lineup_leaders` → the units he anchors;
`get_matchup_splits` → who produces specifically vs your team. The
scouting answer is a name plus the on/off and lineup evidence, not a
points-per-game list.

## 6. Reporting

- Verdict first: the units and players that matter, then the mechanism
  (four factors / shot zones), then availability caveats.
- Every early-season stat carries its sample (games, minutes, attempts);
  label volatile conclusions once instead of repeating caveats.
- Cite each tool's `meta.sources`/per-row source; disclose that on/off
  and lineup figures are per-100-possessions and which season_type they
  cover.
