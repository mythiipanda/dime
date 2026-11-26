---
name: trade-evaluation
description: Evaluate NBA trades end to end — legality, salary matching, asset pricing, roster fit, and team-context sanity checks — using the warehouse trade, draft capital, impact, roster fit, and expectations tools.
---

# Trade Evaluation Playbook

This playbook is guidance for reasoning about trades, not a fixed procedure.
Use whichever tools answer the question being asked; skip the rest. Every
number comes from the warehouse — never a live endpoint at question time —
and every tool reports its own sources, so cite them.

## 1. Tools and when they matter

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_trade_check` | Is a specific proposal CBA-legal? Salary matching bands, apron consequences. | The user names a concrete package ("Brown for George + 2 picks"). Always before grading a proposal's value — a grade on an illegal deal is meaningless. |
| `get_trade_legality` | Full legality verdict across 2+ teams: matching tiers, apron aggregation bans, sign-and-trade, TPE/cash, frozen picks, Stepien rules. | Multi-team or sign-and-trade proposals, or when picks/cash/exceptions are part of the package — `get_trade_check` handles the plain two-team player swap. |
| `get_cap_ledger` | One team's payroll, cap space, luxury tax and apron room under the CBA thresholds. | "How much room do they have" — the ledger is what constrains every move; check before proposing targets. |
| `get_contract_value` | Production-vs-salary residual per player — who outplays or underplays their deal. | Identifying which contracts are moveable or worth acquiring; a bad contract changes what a package must include. |
| `get_transactions` | Team signings, waivers and trades by date range. | "What have they done lately" — recent moves change the roster the next proposal lands on. |
| `get_trade_partners` | Which teams can legally match salary for one player, and with what packages? | The question is open-ended ("who could trade for X", "what's the market for X"). Produces candidate packages to then grade. |
| `get_trade_value` | Rough production-vs-salary grade per side, plus pick valuation. | Any "who wins" question. Runs after legality is established (it layers on `get_trade_check`). |
| `get_draft_capital` | What picks does a team own/owe, with protections and swaps, and what are slots worth? | Any deal involving picks, or a "can they even afford X" question — a team with no movable firsts can't offer the standard package. |
| `get_impact_rank` | Where does a player rank by WS, VORP, BPM for a season? | Calibrating whether the player at the center is actually a star, and comparing the pieces on each side. |
| `get_roster_fit` | Where is a team's roster thin (spacing, creation, rim, defense, depth) vs league and contender baselines? | "Does this trade fix their problem" or "what should they target" questions — it names the gap the player would fill. |
| `get_expectations` | How is a team doing vs its preseason projections (wins, net rating)? | Framing motivation: an underperforming "contender" buys differently than an overperforming rebuilder. |
| `get_free_agents` | Upcoming free-agent class by team or league-wide, cap holds, projected cap room and exceptions (estimates). | Offseason/team-building questions and "can they afford to keep/sign X" — cap room constrains what a team can actually do after a trade. |
| `get_prospect` | A draft prospect's board placement, college production, pick-slot comps, combine measurables. | Valuing picks inside a package or answering "who could they get at #N" — a pick's worth is the prospect it becomes. |

### Salary-matching quick reference

`get_trade_check` is the primary legality check for a concrete two-team player swap; use `get_trade_legality` when picks, cash, exceptions, sign-and-trade, or multiple teams are involved. Manual band math is verification/fallback, not the primary path. `cba-trade-analysis` owns the detailed CBA mechanics, inverse floors, and apron edge cases; load it when legality turns on those details.

For a non-apron over-cap team, maximum incoming salary is:

- outgoing <= $7,500,000: 200% of outgoing + $250,000
- $7,500,000 < outgoing <= $29,000,000: outgoing + $7,500,000
- outgoing > $29,000,000: 125% of outgoing + $250,000
- first apron: at most 100% of outgoing; second apron additionally cannot aggregate salaries

Anchor: outgoing $26,382,060 is in the mid band, so the ceiling is $26,382,060 + $7,500,000 = $33,882,060. The high-band rule is `125% + $250k`; never use `125% + $100k`.

## 2. Assembling the picture

A complete evaluation usually has three independent layers, and a strong
answer says which layer the conclusion rests on.

**Legality.** `get_trade_check` on the exact proposal, or
`get_trade_partners` to enumerate what is even possible. If the deal needs a
third team or pick swaps to be legal, say so explicitly — don't quietly
assume it away.

**Value.** `get_trade_value` grades each side's production-per-dollar and
prices picks off `silver_draft_value_curve`. Sanity-check it against
`get_impact_rank`: if the tool grades a player B+ but he ranks outside the
top 150 by WS/VORP, the contract is doing the work in the grade — that is a
salary-dump profile, not a star acquisition, and the pick return should be
priced accordingly (see §3).

**Context.** `get_roster_fit` and `get_expectations` tell you whether the
move makes sense for each team. A contender filling its biggest measured
gap (e.g. defense −0.22 vs contender baseline) justifies more than a team
buying a redundant skill. A team running well under its projected wins is a
seller or a desperate buyer — `get_expectations` quantifies exactly how far
under (e.g. −9 wins vs projection) instead of asserting it.

## 3. Weighing contracts, impact and picks

The recurring tension: a player can be negative-value on his contract yet
positive-value to a specific roster, and picks are worth different amounts
to different teams.

- **Contract vs impact.** `get_trade_value` already nets production against
  salary, but read the components: high production + high salary can grade
  the same as moderate production + small salary. A surplus-value grade is a
  statement about the *contract*, while `get_impact_rank` is a statement
  about the *player*. A max-contract player ranked ~40th by impact and a
  mid-level player ranked ~40th are not equivalent assets — the second is
  the better trade piece.
- **Picks are not fungible.** Use `get_draft_capital` both to price the
  picks changing hands (it values them by estimated slot on the draft value
  curve) and to check what each side can still move. A protected 2030 first
  from a capped-out team is worth less than the same year unprotected from
  a team likely to underperform — and `get_expectations` is the
  warehouse-grounded way to argue which is which. "2029 FRP top-4
  protected" is a different asset from "2029 FRP"; price the protection,
  don't elide it.
- **Fit can re-rank the winner.** The side that "loses" a `get_trade_value`
  grade can still win the deal if the player fills its measured biggest gap
  (`get_roster_fit`'s `biggest_gaps`) — say the specific dimension, not just
  "fit". Conversely, a B+ value grade that adds a sixth non-shooter to a
  spacing-thin roster is a paper win only.
- **Aggregate vs per-asset.** Multi-player packages change the math
  per-piece, not just in total. When `get_trade_partners` returns several
  legal packages, prefer grading two or three of the cheapest rather than
  only the first — the smallest legal salary match often leaves the buying
  team more future flexibility.

## 4. Flagging stale team premises

User framing drifts behind the data constantly ("the rebuilding Celtics",
"a win-now Pistons move"). Before answering from the premise, check it:

- `get_expectations` over the last 2–3 seasons shows whether the team's
  current window label matches its trajectory — e.g. a "rebuilding" team
  beating projections by +10 wins for two straight seasons is a buyer, and
  the answer should say the premise looks stale with the numbers.
- `get_roster_fit` contradicts stale weakness narratives: a team described
  as "needs shooting" may already sit above contender-baseline spacing
  share while its real gap is defense or depth. Name the measured gap; note
  the premise discrepancy in one line rather than building the whole answer
  on it.
- `get_draft_capital` contradicts "they have all their picks" or "no draft
  capital" claims — the ledger shows held, owed, protected and swapped
  picks explicitly.
- `get_impact_rank` and `get_news_feed` correct stale player premises:
  ranking outside expectations for the season, or an injury/availability
  headline in warehouse news, changes what an asset is worth today.

When a premise is stale, flag it once with the warehouse number, then
evaluate the trade on the current facts — don't silently answer the stale
question.

## 5. Warehouse-grounded examples

*Evaluate: "Jaylen Brown for Paul George and two firsts."*
`get_trade_check` on the proposal → legality under each team's apron
status. `get_trade_value` → per-side grade with the FRPs priced from the
value curve (PHI B+, BOS B− on the 2026-27 books). `get_impact_rank` for
both players, 2025-26 → whether the grades reflect player quality or
contract. `get_draft_capital("PHI")` and `("BOS")` → which firsts are
actually movable and what the returned slots are worth. `get_roster_fit`
both teams → does George address Boston's measured biggest gap? State the
answer per side with the tools' cited sources.

*"Who can trade for a $45M wing?"*
`get_trade_partners(player)` → legal packages league-wide; shortlist by
`get_trade_value` and by each partner's `get_roster_fit` gap (a package
from a defense-starved contender outbids a redundant one). `get_draft_capital`
per finalist → who can still attach picks if players alone don't grade out.

*"Should a fringe team trade a first for a rental?"*
`get_expectations(team)` → where the team actually sits vs projection;
`get_roster_fit` → whether the rental fills the top measured gap or a
smaller one; `get_draft_capital` → the cost of giving up the pick relative
to what's left; `get_impact_rank` → whether the rental is top-40 material
or a name. A rental priced like a star without the rank or the fit is the
answer, with numbers.

## 6. Reporting

- Lead with the verdict per side, then the three-layer support: legality →
  value → fit/motivation.
- Cite each tool's `meta.sources`/per-row source fields — every number is
  warehouse-sourced and traceable; do not cite anything not in the tool
  output.
- Disclose approximations the tools themselves flag (simplified CBA
  matching in v1, estimated pick slots, production-estimated values) in one
  line rather than inventing precision.
- Present vs historical: cap and trade books live on the current 2026-27
  season, while production stats come from completed seasons — pass
  `season` explicitly for historical asks (e.g. `get_expectations`
  2024-25) and name the season in the answer.
