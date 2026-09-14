# Dime Agent Architecture v2 - the online coding-agent harness for NBA
Tony's north star (Sep 12, 12:23 PM): "codex/claude code but online, already has the relevant skills for nba work, data already preloaded and online for ease of use."
Spec (12:21 PM): eliminate hangs/unfinished queries, test follow-ups multi-turn, reviewer + user-persona sub-agents, DDG web fallback when data is missing, harness SOTA from codex + pi.
HARD CONSTRAINT (1:15 PM): "I don't want to be hard doing scenarios with regents or explicit tools designed for a specific scenario our agent should be very versatile." No hardcoded scenario handlers, no single-scenario tools. The v2 design makes the GENERAL plan-execute-verify path strong enough that tonight's pins become scaffolding with an exit plan - a burn-down list, not a growth strategy.

## What we verified in the actual repos (not from memory)

**OpenAI Codex (github.com/openai/codex, codex-rs/core/src):**
- guardian/review_session.rs: a separate REVIEWER session bound to the parent action with captured context + authorization snapshots. Review runs as its own thread with its own rollout; the extension owns review policy. This is codex's /review: a second agent whose only job is grading the first.
- rollout_budget.rs: session-tree-wide token budget with per-thread threshold reminders; record_usage() flips to exhausted and the loop hard-stops. Budgets are infrastructure, not prompt text.
- session/mod.rs + context/turn_aborted.rs: every turn gets a TurnContext + CancellationToken; turns are first-class, cancellable, event-emitting units (emit_turn_started, per-item events).
- compact_token_budget.rs + compact_remote_history.rs: compaction is automatic on token thresholds, not user-triggered.

**pi (github.com/badlogic/pi-mono, packages/coding-agent/src/core/agent-session.ts, 3187 lines):**
- AgentSession: one event-sourced core shared by interactive/print/rpc modes; every state change is an AgentEvent subscribers can persist.
- Auto-compaction with three triggers: manual | threshold | overflow (isContextOverflow recovery after a provider error).
- Bounded auto-retry as EVENTS (auto_retry_start/end with attempt numbers and backoff via retryDelayMs); retry only fires for isRetryableAssistantError; the counter resets on the first successful assistant message. A retry storm is impossible by construction.
- Steering vs followUp: a message mid-stream queues as "steer" (interrupt) or "followUp" (wait) - the harness owns interruption semantics.

## Why Dime breaks today (QA acceptance chains)

- F61 (P1): "Compare that to his season average." -> 27s, 4 tools, dead-end "the warehouse query for it did not run. Try a narrower ask." A stall shipped as an infra admission that blames the user.
- F62 (P2): follow-up claims "evidence does not contain Game 5 details" two turns after the thread produced them + playoff average mislabeled as regular-season. False claims ship because nothing checks them.
- F63 (P1): switch away and back -> "records do not show the Spurs participating in the Finals", denying the matchup the thread established at T1. A degenerate re-fetch "proved" a falsehood.
- v67 lesson (live, 4 failed regex rounds): instructing the LLM to interpolate a value failed 4 times; building the answer deterministically from the payload has not failed once. LLM-composed numerals are untrusted on pinned lanes.

Root cause, one sentence: Dime resolves ENTITIES across turns (pronouns work) but not EVIDENCE (each turn re-fetches a fresh subset), and nothing VERIFIES the draft against what the thread already knows before it ships.

## v2: the five changes

### 1. Thread ledger (kills F62/F63)
Per-thread structured state, carried across turns:
- entity ledger (exists: players/teams from last 6 turns)
- NEW evidence ledger: salient facts from each turn's tool payloads + shipped answer (e.g. "Finals = NYK 4-1 SAS", "Brunson G5: 45/3/3"). Extracted deterministically from payload meta at ship time, not re-derived by the LLM.
- NEW canon guard: any draft claim that contradicts a ledger fact ("Spurs not in Finals") is a verify failure, not a ship.
Cap: last ~20 facts, thread-scoped, free.

### 2. Verify node between analytics and presentation (kills F62, catches F61-class)
codex-guardian pattern, adapted: a cheap deterministic checker (not a second LLM call on the hot path) that runs three checks on the draft:
a. Numeral provenance: every number in the draft must appear in this turn's payloads or the thread ledger. (v67 lesson generalized.)
b. Coverage-claim provenance: "not in the dataset / evidence does not contain" may only ship when a known-gap taxonomy entry or an empty-result-with-coverage proof backs it - never because a fetch missed.
c. Ledger consistency: no contradiction of thread-ledger facts.
Outcomes: pass -> present; fail -> ONE bounded re-route (the pin/tool that owns the phrasing class); still failing -> honest dead-end that names what IS covered. The verifier owns the "figure out what to do, how to do better" loop Tony asked for, in harness code.

### 3. Watchdog honest-ends (kills F61 and the hang class)
pi's bounded-retry + codex's CancellationToken, adapted:
- per-NODE wall-clock budget (triage 5s, tools 8s each, synthesis 20s, total turn 45s) enforced by the harness, with SSE heartbeats so the UI never looks dead.
- Budget exhaustion or circuit-breaker trip forces the honest end: "I couldn't get X - the dataset covers Y" from the coverage map. "Try a narrower ask" and "the query did not run" are banned phrases in ship text (scrub-enforced).

### 4. Payload-grounded composition for EVERY answer + a pin exit plan (v67 lesson, generalized)
The v67 lesson is not "pin more" - it is "numbers come from payloads, never from LLM narration". v2 moves that into the general path: the composer assembles every answer from structured payload data (rows, meta, canon keys) with the LLM writing connective prose only, and the verifier's numeral-provenance check enforces it on every turn, pinned or not.
The existing pins are SCAFFOLDING: they stabilize the phrasings that were bleeding while the general path gets strong. Each pin carries a burn-down status; the reviewer measures its phrasing class on the general route in CI, and when that class passes green without the pin, the pin is deleted. No new pins without a failing-class report and a retirement condition. The versatile agent Tony asked for is the destination; pins are how we get there without bleeding users on the way.

### 5. Offline eval harness: user personas + reviewer (Tony's "run subagents to review work and to be a user")
Extends backend/tests/holdout_eval.py + scenarios.py (no new framework):
- USER-PERSONA driver: scripted multi-turn chains (follow-ups, pronouns, switch-back, ambiguous references) run against staging post-deploy. F61/F62/F63 chains are the first three personas.
- REVIEWER grader (codex guardian): grades each chain answer against canon numbers + the three verify checks; produces pass/fail + the failing check. Runs in CI on dev merges and as a scheduled live probe.
- Ship gate: a deploy is "verified" only when the persona suite is green - this is the 3x-smoke rule growing up.

### 6. DDG web fallback (Tony's "if there isn't data maybe web search")
get_web_fallback (DuckDuckGo HTML, free, no key): fires ONLY after an honest dead-end; answer is labeled "from web search, not the dataset" with the source link; <4s budget inside the turn watchdog. The canon-vs-web line stays explicit - warehouse answers never silently mix web data.

## What does not change
Triage-first routing (0-LLM pins for known phrasings), desk sub-agents, the scrub, season-line discipline, the warehouse + release-asset pipeline, the deploy gate (pytest -> dev merge -> GH build -> forced Azure revision -> 3x live smokes).

## Rollout order (each independently shippable, pytest + smokes per Tony's gate)
1. Verify node v0: numeral provenance + banned-phrase scrub (pure code, no schema change).
2. Thread evidence ledger + ledger-consistency check (kills F62/F63; biggest user-visible win).
3. Watchdog budgets + SSE heartbeats (kills F61 hang class).
4. Eval harness personas + reviewer in CI (F61/F62/F63 go green and stay green) + PIN BURN-DOWN: per-class general-route pass rates decide each pin's retirement.
5. DDG fallback.
6. Coverage roadmap intake: reviewer dead-end reports feed the demand-driven warehouse roadmap in the status doc.
