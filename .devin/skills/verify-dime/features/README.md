# Dime verification map

This directory is the maintained source for verifying the user-facing behavior of Dime. Read the index before driving the app, then use the matching feature file as the recipe.

## Baseline preconditions

- Analyst host healthy at `http://localhost:9910`, frontend at `http://localhost:3010`, both launched from the checkout under test per the skill's Launch section.
- `node .devin/skills/verify-dime/helpers/dime-drive.cjs doctor` exits 0 and reports both processes owned by this checkout.
- Real warehouses present in `backend/data` (warehouse.duckdb + warehouse-runtime.duckdb) — the shared checkout already has them.
- Never drive an instance that was not started by this verification run, and never start a second host against the same `backend/data` files.
- Evidence goes under `artifacts/verify/<feature>/<run-id>/` outside the repo (or a gitignored scratch path); it survives cleanup.

## Driving conventions

- Start every recipe from the baseline state unless its preconditions say otherwise.
- Browser driving goes through `dime-drive.cjs shot|text|interact`; stream-contract proofs may `curl -N` the public `/api/v2/chat/stream` endpoint the UI itself consumes.
- Prefer stable handles documented in each feature file (URL params, aria-labels, class contracts like `.composer-dock`, `.suggestion-row`) over coordinates.
- Use `/?tab=chat&replay=generative` for provider-free streaming/artifact layout proofs. Live-model proofs are reserved for stream-contract verification and must name the lane used.
- Treat every command as literal. Restore mutated state where the feature file says to; never remove proof artifacts during cleanup.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final screen.
- A screenshot plus a `text` dump or interact transcript is the minimum proof bundle per journey.
- Mutation proof includes a read-only second observation (reload, or a fresh `text` dump in a new browser context).
- Record the feature ID and entry point used with every artifact.
- Report an unreachable path with the attempted command and the unmet precondition. Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order: `Sub-features`, `How to get to it (user POV)`, `Driving it with <harness>`, `Gotchas`.

## Features

- [Ask a question](./ask-chat.md) covers the chat composer, streaming states, tool visibility, artifacts, halt, and the replay fixture.
- [Artifact open-in-view seam](./open-in-view.md) covers the artifact-to-tools-view navigation handoff.
- [Cap sheet](./cap-sheet.md) covers the year-grid, option toggles, scenario arithmetic, and board pinning.
- [Trade machine](./trade-machine.md) covers multi-team trade construction, legality verdicts, and saved scenarios.
- [History explorer](./history-explorer.md) covers career arcs, era comps, and cross-era leaderboards.
