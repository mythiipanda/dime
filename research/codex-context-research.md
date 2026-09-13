# How codex gives the agent context for tools (Tony's question, answered from the repo)
"What makes codex so good at following instructions and planning, other than model quality?"

Sources read: codex-rs/core/gpt_5_codex_prompt.md (the WHOLE base prompt), core/src/context/ (base_instructions, user_instructions, environments_instructions, update_plan_instructions, mod.rs), core/src/context/world_state/tools.rs, core/src/session/mod.rs. All on github.com/openai/codex main, fetched Sep 12.

## Finding 1: context is typed FRAGMENTS, not one mega-prompt
Every piece of injected context is a ContextualUserFragment with four parts:
- content_kind: a typed label ("model.base_instructions", "agents_md.instructions", "environments.instructions")
- role: "developer" vs "user" - instruction hierarchy is STRUCTURAL. System rules and user/repo instructions never share a bucket, so they can't dilute each other.
- markers: explicit delimiters ("# AGENTS.md instructions" ... "</INSTRUCTIONS>") - the model can always tell where a context block starts and ends.
- requires_separate_message: some fragments ride as their own message instead of being concatenated.
Dime today: the planner gets one interpolated prompt blob. This is the biggest portable upgrade.

## Finding 2: the base prompt is SHORT and behavioral - 68 lines total
Sections: General (2 lines, one tool preference), Editing constraints (safety rails: never revert user changes, never destructive commands), Plan tool (3 rules), Special user requests (2), Presenting your work (~35 lines - HALF the prompt is final-answer format rules). Instruction-following comes from few, crisp, testable rules - not exhaustive coverage. Every rule is binary-checkable ("did you revert user changes? yes/no").

## Finding 3: planning is a TOOL, not prose
update_plan is a real checklist tool the model calls and maintains as it works. The prompt's plan rules are about WHEN NOT to plan (skip the easiest 25%, never single-step plans, update the checklist after each sub-task). And there's surgical machinery (without_update_plan_instructions) that STRIPS plan-tool guidance from the prompt when the tool isn't in the tool list: the context always exactly matches the offered tools. A model never sees instructions for a tool it doesn't have, and never lacks instructions for one it does. That consistency is a quiet, huge part of "good at following instructions".

## Finding 4: user/repo instructions steer as user-role messages
AGENTS.md content injects as a USER-role fragment with markers - it steers behavior without rewriting the developer-role operating rules. Tony's standing process notes are exactly this layer for Dime.

## Finding 5: environment + world-state are injected as structured context
<environment_context> describes the execution environments and their state (world_state/tools.rs puts the tool list itself into a world snapshot). The model plans against DECLARED capability, not guesses - a tool that's starting up is marked "starting", and the prompt says keep working with what's available instead of stalling.

## Finding 6: turns are first-class objects
Every turn gets a TurnContext + CancellationToken; turn start/items/errors are events. Combined with rollout_budget (session-wide token accounting with a hard stop), the loop always knows where it is - no invisible state.

## What this means for Dime v2 (added to the design doc)
1. Assemble planner context from typed fragments with markers + roles: question / thread ledger / tool catalog (each tool: what, when, ONE example) / coverage map / canon facts.
2. The tool catalog fragment is generated from the actual registry - context can never drift from the tool surface (finding 3).
3. Plan-as-tool for multi-step asks: planner maintains a checklist object, not free text.
4. Keep the rulebook short and binary-checkable; move phrasing-level fixes out of the prompt entirely (scrub/verify own those).

---

# ADDENDUM: DAIR.AI harness-engineering collection (Tony's 1:23 PM link)
Anchor paper: arxiv 2609.00006, "Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents - A Source-Code Study of Eleven Systems" (Barbaste et al., Jul 2026). Source-code anatomy of Claude Code, Codex CLI, Gemini CLI, Mistral Vibe, OpenHands, Aider, Mini-SWE-Agent, Hermes, Pi, OpenCode, OpenClaw + the Omnigent meta-harness. https://arxiv.org/abs/2609.00006

What's real and folds into v2:

1. "An agent is a model plus a harness" - the runtime is the discipline. Seven canonical subsystems: Interface Layer, Agent Loop, LLM Integration, Tool & Action Systems, Memory & Context, Safety & Permissions, Multi-Agent Orchestration (+ Extensibility). v2's six changes map: loop (watchdog), memory/context (thread ledger), tool systems (versatile catalog), orchestration (eval harness personas/reviewer).
2. VALIDATION for Dime's bones: 0/11 production harnesses import a general-purpose agentic framework (Rec 15: do NOT use LangChain/LangGraph/AutoGen...) and 0/11 use vector-embedding retrieval for code (Rec 16: deterministic retrieval wins - ripgrep/tree-sitter/glob/Markdown context files). Dime's hand-rolled graph + deterministic warehouse SQL is exactly the corpus pattern.
3. Rec 1: start with a linear while loop; graduate to a middleware pipeline only when 3+ independent turn policies emerge (turn limits, cost caps, auto-compaction, context-budget warnings). Dime now has budgets+breaker+verify+ledger - it has crossed that threshold; turn policies should become composable middleware, not branches in the loop body.
4. Rec 17: "Do not wrap every upstream SaaS API as a 1-to-1 tool" - the paper states Tony's versatility constraint verbatim-class. Tools should be capability-shaped, not endpoint-shaped.
5. Longitudinal finding: behavioral policy is migrating from prompt prose to configuration. Matches our v67/verify lesson: phrasing-level fixes live in scrub/verify code and config, never in the prompt.
6. Skills (SKILL.md) lead MCP 9/11 vs 8/11 - Dime's skills catalog is the right extensibility bet.
