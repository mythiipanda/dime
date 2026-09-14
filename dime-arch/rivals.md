# Dime vs rivals

Grounded 2026-09-13. Sources cited per claim. The point of this doc is
positioning honesty: where Dime wins, where it loses, and what the
benchmark pack must keep proving.

## The field

### 1. Generic LLM chat (ChatGPT / Claude / Gemini)
- Strengths: infinite topic range, fluent prose, free tiers.
- Weaknesses for NBA analytics: answers come from training data and web
  snippets, so numbers go stale mid-season and models confabulate
  plausible-looking stat lines. Documented failure mode in sports:
  AI-generated stat write-ups fail verification
  (brightsideofthesun.com/suns-features-profiles/109304/ai-generated-suns-statistics-verification-chatgpt).
- Dime's edge: pinned lanes answer deterministically from warehouse
  payloads - the numerals in an answer are the numerals in the database,
  never LLM-composed (v67 design law). Every answer carries receipts
  (tool, rows, latency) and cite/evidence links.
- Dime's gap: no browsing, no news, no non-NBA topics, coverage-bounded
  honesty ("not in coverage") where ChatGPT will always say something.

### 2. Stathead (Sports Reference)
- $9/month (sports-reference.com/stathead: "Plans start at just $9 per
  month").
- Strengths: the most complete historical database on the internet,
  trusted numbers, discovery query tools.
- Weaknesses: form/filter UI - the user must know which query tool,
  which filters, which output columns answer their question. No
  conversation, no follow-up carry ("who was their best player?" after
  "best record?"), no verdict prose.
- Dime's edge: natural-language chains with context carry (benchmark
  scenarios f62/f63/f64 prove carry works), plus opinionated synthesis
  (overpaid boards, verdicts) on top of raw retrieval.
- Dime's gap: Stathead's historical depth dwarfs ours - we hold
  2009-10 onward for gamelogs/shots/standings, 2014-15 onward for
  player-season aggregates; Stathead goes back to the 1940s-50s.

### 3. StatMuse
- NL stats search with shareable per-answer pages and art.
- Weaknesses: one question per page, no multi-turn context, shallow
  synthesis (returns the stat table, not an argument), no
  contract/value layer.
- Dime's edge: threads, carry, deterministic verdict lanes, contract
  value modeling (salary vs production-predicted value across 279
  qualified players).

### 4. NBA.com stats (SAP natural-language layer)
- Official data, natural-language query box live since 2016
  (techcrunch.com/2016/02/11/nba-bolsters-partnership-with-sap-to-bring-natural-language-queries-to-stats-site/).
- Weaknesses: the NL layer maps to canned stat views; no conversation,
  no cross-domain synthesis (stats + contracts + lineups in one
  answer).
- Dime's edge: cross-domain composition is the default path, not a
  special feature.

### 5. Betting/picks AI chats (Oracle Picks et al.)
- Oracle Picks runs a free NBA research chat (oraclepicks.ai/nba-chat).
- Weaknesses: picks-first framing, paywalled edges, accuracy claims
  without receipts.
- Dime's edge: receipts per answer - tool name, row count, latency -
  so a number can be checked instead of trusted.

## What the benchmark pack must keep proving

Positioning claims above are only true while the pack stays green:
- Determinism: canon scenarios (compare 61.6/66.5 TS, overpaid $29.6M
  LaVine, best record 64-18 OKC, record-when-plays 43-22, clutch 175
  SGA) fail the build if a numeral drifts.
- Carry: f62/f63/f64 chains fail if context breaks.
- Honesty: f61 fails if an out-of-coverage ask hangs or user-blames.
- Efficiency: per-turn and total budgets keep pinned lanes instant and
  agent lanes bounded.

## Where we lose today (honest list)

- Historical depth before 2009-10 (Stathead owns this).
- Live news, injuries freshness, and anything off-ball (no browsing).
- silver_four_factors (2 rows), silver_wowy (1 row), watchlists
  (0 rows) are stubs - see the more-data roadmap.
- No multiplayer: no shared threads, no export formats beyond copy/cite.
