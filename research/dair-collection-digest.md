# DAIR.AI Harness-Engineering Collection - per-paper digest for Dime v2
Tony's brief (1:27 PM): read each paper + the harness examples; v2 is the working draft, this pass validates or replaces it. Fetched today vs known-from-training marked per item. Collection page: https://academy.dair.ai/papers/collections/harness-engineering (24+ entries; the page is JS-paginated - the 2026 harness set + the classics canon below).

## The 2026 harness papers (the collection's core)

1. **Harness Engineering: Anatomy of 11 systems** (arxiv 2609.00006, FETCHED full HTML) - covered in Addendum A. Validates v2's bones: 0/11 frameworks, 0/11 vector retrieval, middleware turn policies (Rec 1), capability-shaped tools (Rec 17), prompt-prose -> configuration trend. VALIDATES v2.
2. **HarnessDev** (arxiv 2609.01437, abstract FETCHED): benchmark shifting evaluation from task outputs to RUNNABLE INFRASTRUCTURE - agents create + evolve their own harness, scored on capability (held-out tasks) and efficiency (token cost). Fold-in for Dime: our benchmark pack should score exactly these two axes (canon correctness + latency/token budget per chain), and the eval harness's reviewer is a baby version of harness-evolution feedback. VALIDATES benchmark-as-gate (Addendum B).
3. **Agentic Harness Engineering / observability-driven evolution** (arxiv 2604.25850, abstract FETCHED): closed-loop harness improvement needs THREE observability pillars - component (every editable part file-level + revertible), experience (trajectories distilled into drill-down evidence), decision (every edit paired with a predicted effect, verified next round). Fold-in: our deploy gate already does prediction->live-smoke verification informally; adopt the decision-observability habit in the status doc (each batch states its predicted effect, QA verifies). VALIDATES our ship-smoke-record loop; sharpen with explicit predictions.
4. **Meta-Harness** (DAIR page FETCHED): outer loop that searches over harness CODE, with the proposer reading source + scores + execution traces of prior candidates through a filesystem. Fold-in: this is the far end of the pin burn-down - an agent that proposes harness edits scored by the benchmark. NOT now; note as the v3 horizon. No redesign pull.
5. **Recursive Language Models** (FETCHED): treat long prompts as an external environment; the model programmatically decomposes and recursively calls itself over snippets - 100x context without giant windows. Fold-in: Dime's thread ledger + compaction is the cheap version; RLMs matter if Tony wants full-thread/long-document reasoning later. WATCH, don't adopt.
6. **Open-ended evolution / Darwin Gödel Machine** (FETCHED): self-modifying agents validated by benchmarks. Same horizon as Meta-Harness - the benchmark pack is the prerequisite for ANY of this. Sequence stands: benchmark first.

## The classics canon (known from training - the collection's foundations row)
- **ReAct** (reason+act loop): the loop Dime already runs; v2's verify node extends it (reason-act-VERIFY).
- **Reflexion / Self-Refine**: verbal self-feedback - the reviewer persona's ancestor; our deterministic verifier is stricter (code, not self-graded vibes).
- **Toolformer / WebGPT / InterCode**: tool use + retrieval + execution grounding - Dime's tool layer already exceeds these.
- **MemGPT**: memory as OS with tiered context - the thread ledger is the domain-shaped version; validates ledger-first design.
- **Voyager**: skill library accumulation - Dime's skills catalog (DAIR: skills beat MCP 9/11).
- **DSPy / GEPA**: prompt/program optimization by evaluation - again: benchmark pack is the prerequisite; GEPA-style evolution is how pins retire automatically later.
- **CoT, GPT-2/3, METR long-tasks**: historical grounding; METR's length-of-task measurement is a nice benchmark-pack axis (chain depth vs success).

## Harness examples (the 11 + Omnigent)
Covered via the anatomy paper's source-code study (Addendum A): Claude Code, Codex, Gemini CLI, Mistral Vibe, OpenHands, Aider, Mini-SWE-Agent, Hermes, Pi, OpenCode, OpenClaw, Omnigent. Pi + Codex read at source level by us directly (agent-session.ts, guardian/, rollout_budget.rs, context/). No harness in the corpus invalidates v2's shape; the strongest pull is middleware turn-policies (Rec 1) which is already queued.

## VERDICT: validate, don't replace
v2's spine (ledger -> verify -> watchdog -> payload-grounded compose -> benchmark-gated eval) matches where the field converged. What changes from this pass: (1) benchmark pack gains HarnessDev's two axes (held-out capability + token/latency efficiency); (2) deploy gate gets decision-observability discipline (predicted effect recorded per ship, verified by QA next round); (3) pin burn-down gains a far horizon: benchmark-scoped harness self-improvement (Meta-Harness/DGM class) AFTER the benchmark is trustworthy. Not fetched yet (JS-blocked, next run): continual-harness-2605, prime-agent-2608, openjarvis-2605, hero abstracts.
