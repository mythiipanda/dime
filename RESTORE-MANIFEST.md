# #24 Restore Manifest

## What happened

The zero-comment strip (#24) removed every comment from backend/ and
frontend/ in two strip commits, then Tony refined the directive
(2026-09-29): strip slop comments and unneeded comments, but KEEP
needed ones — substantive invariants, incident explanations,
operational warnings, API contracts. Reviewed case-by-case; no
dumbing-down. This manifest records the restore passes that followed
the refinement.

## Strip commits (kept below, not reverted)

- `e482e1e` / `b11865b` — scripted strip of backend/**.py (224 files, ast-based)
  + config files (.gitignore x2, backend/.dockerignore, .env.example,
  requirements.txt, infra/budget.sh, infra/deploy.sh)
- `81c09c0e` — lexer-based strip of frontend ts/tsx/js/jsx/css (61 files)
- `ba80c471` — restored operational rationale wrongly stripped from
  backend/requirements.txt, infra/budget.sh, infra/deploy.sh

## Restore batches

- `879bd9d1` — backend restore (86 .py files). AST-verified zero
  behavior change across all files (docstring-stripped AST dumps
  identical old vs new). Examples restored: function contracts,
  failure-mode notes, incident explanations (DESK_CALL_TIMEOUT_S
  sizing vs LLM_ROUND_TIMEOUT_S, watchdog rationale), .gitignore
  section headers. Gates: py_compile 86/86, 21/21 neighbor hermetic
  tests green.
- `a652d193` — frontend restore (48 files). TSDoc contracts on
  interfaces/helpers, incident explanations (ChatPanel QA-2d error
  banner, api.test.ts deploy-wipe history, Explore feed binding
  rules, stream-shape compatibility), globals.css design.md line now
  points at dime-internal/design.md. Gates: tsc clean, npm test
  132/132 green.

## Keep policy (what counts as "needed")

- Function contracts: what a unit consumes and returns, binding rules
  (exploreFeed: no item without data, every item carries a ranked
  number), test-group rationale (deploy-wipe cache durability).
- Failure modes: mid-run error vs fallback/partial final, scoreboard
  read-failure vs "no games", first-token watchdog semantics.
- Operational warnings: brotli wheel note in requirements.txt,
  script usage headers, DESK_CALL_TIMEOUT_S sizing arithmetic.
- Lean KEEP when unsure.

## What stays stripped

- Narration ("fetch the rows", "iterate and filter"), banner
  separators with no meaning, harness-provenance notes, mechanical
  test annotations ("assert x equals y"), dead code commentary.

## Mode fixes

- `2108bcde` — restored 100755 on infra/budget.sh +
  infra/deploy.sh on the remote (gh-push-commit.py hardcodes 100644;
  the fix goes through hidden_files/restore-exec-bit.py via the
  GitHub Data API).

## Bug found during the strip

- backend/scripts/backfill.py:375 referenced the stripped module
  docstring (`description=__doc__.splitlines()[0]` -> AttributeError
  at CLI startup). Fixed with a literal description string; no
  comment re-added. Zero remaining `__doc__`/`getdoc` uses in
  backend.
