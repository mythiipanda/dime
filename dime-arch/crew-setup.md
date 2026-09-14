# Crew setup (opencode) - steering from Tony, Sep 13 2026

"edit the crews n stuff to use both potetomode open code crew and those
design skills for the design agents."

## Skill packs

All packs are vendored in research/design-skills/ (survives sandbox
rebuilds). Install into opencode with:

    research/design-skills/install.sh           # project: .opencode/skills/
    research/design-skills/install.sh --global  # user: ~/.config/opencode/skills/

## Desk wiring

- Every desk runs /poteto-mode (already the crew rule; unchanged).
- frontend / design agents additionally load, in order:
  1. ui-skills-root (routes to baseline-ui / improve-ui /
     fixing-accessibility / fixing-motion-performance as the task needs)
  2. ponytail (cleanup/refactor discipline)
  3. beautifului tokens - research/design-skills/beautifului/foundation.css
     is THE visual reference (:root/.dark oklch tokens, spacing
     primitives, keyframes). Match it; do not invent a parallel palette.
- qa/bench runs superpowers/verification-before-completion +
  test-driven-development on every feature.
- research desk uses superpowers/brainstorming for exploration tasks.

## Standing rules (unchanged)

Coordinator owns git; one commit per feature; never commit secrets or
agent-only files (OPENCODE.md/AGENTS.md, roadmap, readme); main merges
are Tony's call only; consultant persona feedback enters the queue as
real tasks.
