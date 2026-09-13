# Keep-vs-rebuild verdict: Dime harness vs Ax / frameworks (Sep 12, 2026)

Tony's question, his words: "our harness should be high quality see codex pi all
these tools - if that's too hard maybe we should build it on LangGraph or one of
these frameworks" + "this should decrease a lot of incessant code."

Criteria: (1) quality vs the codex/pi bar, (2) maintenance burden
(lines-of-scaffolding per fix), (3) bake-off evidence, not vibes.

## Bake-off: Ax (dosco's framework) vs our graph.py, same model, same data

Setup: axllm v23.0.14 (the Python port - "generated Ax runtime", Apache 2.0),
same Inception mercury-2.5 model, same warehouse.duckdb, generic
list_tables/describe_table/run_sql toolkit. The harness is the only variable.

| Question (canon) | Dime harness (6de2f73) | Ax Python port |
| --- | --- | --- |
| Best record (OKC 64-18) | PASS, deterministic lane | 0 completed answers; loop blowouts |
| "their best player" carry (SGA) | PASS 3/3, pin fires, 0 Wizards | exceeded max steps |
| Finals + MVP (NYK 4-1, Brunson) | PASS | answered from memory / refused |
| Luka vs SGA efficiency | PASS, markdown intact | hallucinated ("Boston 64-18, Tatum 32.5") |
| Wemby playoffs carry | PASS, full game log | refused |

Control: raw API call proves mercury-2.5 emits clean tool_calls natively - the
model was never the problem. The port's tool-result feedback loop is broken
(list_tables called 4x in a loop; results never reach the actor). AxAgent's
code mode also requires a QuickJS runtime sidecar. Ax's reference
implementation is TypeScript; the Python port is auto-generated and it shows.
~45 min of integration work produced zero completed warehouse answers.

The testable claim - "Ax matches our quality with dramatically less
scaffolding" - is REFUTED on evidence. If anything the framework tax arrived
before the first tool call.

## Where our harness stands vs the codex/pi bar

From research/codex-context-research.md (codex-rs read at source level) and
research/dair-collection-digest.md (Harness Engineering, arxiv 2609.00006 -
source-code study of 11 production harnesses):

The decisive external fact: **0 of 11 production harnesses (Claude Code,
Codex, Gemini CLI, Mistral Vibe, OpenHands, Aider, Mini-SWE-Agent, Hermes, Pi,
OpenCode, OpenClaw) import a general-purpose agent framework.** Recommendation
15 of the paper is literally "do not use LangChain/LangGraph/AutoGen." The
codex/pi bar is hand-rolled harnesses. We are already in the corpus pattern:
own loop + deterministic retrieval (warehouse SQL) + capability-shaped tools.

Graded against codex's six mechanics:
1. Typed context fragments with roles/markers - GAP (planner gets one blob;
   v2 design already specifies the fragment assembler)
2. Short binary-checkable rulebook - PARTIAL, improving (phrasing fixes moved
   to scrub/verify code per the v67 law)
3. Plan-as-tool - GAP (queued in v2)
4. World-state/tool-declared context - PARTIAL
5. First-class turns, budgets, cancellation - YES (watchdog, rollout budget,
   breaker)
6. Deterministic grounding - YES, ahead of the bar (payload-composed answers
   on pinned lanes; no production harness in the study does this for data QA)

## Maintenance burden, honestly

The pin/patch treadmill is real: today F67 needed two follow-up fixes
(~80 LOC + 2 regression tests). But the failures were domain edge cases
(entity carry semantics, SSE visibility) - no framework solves "the word 'was'
matching the Wizards abbreviation." Frameworks move scaffolding from OUR code
into THEIR abstraction leaks; the bake-off is that cost made visible (a day of
debugging a generated port instead of a 40-line pin with a test).

What actually reduces incessant code, in order:
1. The verify layer + benchmark gate (catches classes, not instances) - specced
2. Middleware turn-policies (Rec 1) - collapses loop branches into composable
   units; queued in v2
3. Pin burn-down with the benchmark as the safety net - pins retire as
   general lanes prove out
4. The cleanup/refactor lane (queued): vestigial langgraph dep out, dead
   scaffolding out, callers migrated then legacy deleted

## Steal-worthy patterns

- OpenHarness (HKUDS, 15.6k stars, MIT, Python): parallel tool execution,
  per-turn token/cost tracking, streaming tool-call cycle, retry w/ backoff.
  We have retry+streaming; parallel tool execution and per-turn cost telemetry
  are the two worth lifting (codex's rollout_budget is the same idea).
- OpenHands: covered via the anatomy paper; its contribution to the field norm
  is the middleware/turn-policy pipeline - already queued.
- Ax: the DSPy-style eval-driven optimization loop is the one idea to steal
  LATER - GEPA-style prompt/program evolution is how pins retire automatically.
  Prerequisite is a trustworthy benchmark pack. That's the v3 horizon.

## Recommendation

KEEP the hand-rolled harness. Cut the unused langgraph dep (it was never
imported; langchain-core stays - the tool registry is built on it). Do not port
anything to Ax. Spend the framework budget on the verify layer, middleware
turn-policies, and the cleanup lane. Revisit only if a future TS rewrite of the
stack happens - Ax's reference implementation is TS, and that is the only
version worth evaluating again.
