# Working on Dime

## Before every change

Read [DESIGN.md](DESIGN.md), [ARCHITECTURE.md](ARCHITECTURE.md) and the nearest
directory guidance. Keep this file and DESIGN.md committed and current for all
work. Update decisions when they change; don't add a changelog paragraph for every
small fix. Feature design, backend boundaries and code placement are decided
before implementation, not after.

- Branch from current `origin/dev`; target `dev`, not `main`.
- Coordinate shared-file ownership with concurrent work before editing the shell
  or global tokens. Keep PRs focused. Do not overwrite another session's work.
- Main is a promotion branch. A promotion needs green CI, clean review, UI checks
  and no regression in the nightly DAB eval. Do not bypass these gates.
- Prefer existing abstractions and small named functions. Follow `cccc.toml`.
- No new code comments: CI runs `backend/scripts/no_comments.py`, including on
  frontend source and environment examples. Documentation belongs in Markdown.
- Never commit secrets, generated warehouses, local state, `.env` or screenshots
  unrelated to a requested deliverable.

## Architecture boundaries

The active backend is the Node/Pi host in `backend/analyst`; see its README for
build, configuration and fixture commands. Do not recreate the removed FastAPI
`backend/v2` architecture or follow obsolete uvicorn instructions from old setup.
Python domain tools live under `backend/analyst/tools` and the existing shared data
modules. Keep input validation, source rows, declared units, errors and provenance.
Never modify or fork `@earendil-works/pi-*`; improve Dime's tools, skills, prompts,
domain code and its own Pi configuration instead.

An API change includes its runtime validation, public contracts/OpenAPI, callers
and tests. Regenerate the asset manifest for the actual revision before running
the host. Synthetic fixtures and offline tests do not prove live answer quality.
Never tune on the held-out benchmark split or spend paid-provider quota on broad
evals without explicit approval. For DAB v1 dev spot checks, run history and trace
clustering, use `../dime-internal/agent-ops/hillclimb/runbook-dab.md`.

## UI work

Read [frontend/AGENTS.md](frontend/AGENTS.md) and the
[component registry](frontend/DESIGN_SYSTEM.md). Use shadcn/ui's Radix variant with
the Beautiful UI visual tokens. Do not reintroduce Base UI. Do not hand-roll components or animations: compose and style
the installed primitives; use an existing library for genuinely missing behavior.
Do not add a competing design system or chat runtime.

For interaction polish, invoke `emil-design-eng` when available, or read its
[official skill](https://github.com/emilkowalski/skills/blob/main/skills/emil-design-eng/SKILL.md)
and apply the relevant checklist. Use Emil's
[library-selection skill](https://github.com/emilkowalski/skills/blob/main/skills/pick-ui-library/SKILL.md)
before proposing dependencies. Inspect the relevant
[design.how system](https://design.how/systems/quartz.md) and component/foundation
page, not just a directory or a generic design prompt. Project rules win when a
reference suggests a different theme or bespoke motion.

Review visual changes with a **Before / After / Why** table. Show concrete states
in `/design-system` when changing a shared component. Do not use fictional data,
simulated saves or unimplemented buttons without labeling the example clearly.

## Verification

Run from the named directory; inspect its package scripts before assuming a
command. Node 22.19+ is required for the analyst host.

| Scope | Commands |
| --- | --- |
| Frontend (`frontend`) | `npm ci`, `npm run typecheck`, `npm test`, `npm run build` |
| Focused design suite (`frontend`) | `npx tsx --test design-system.test.tsx` |
| Analyst (`backend/analyst`) | `npm ci --ignore-scripts`, `npm run check`, `npm test` |
| Python (repo root, installed backend environment) | `python -m pytest backend/tests -q -m "not canonical_warehouse"` |
| Comment policy (repo root) | `python backend/scripts/no_comments.py` |

Use targeted suites while iterating, then the applicable CI scope. Some backend
tests need a real warehouse; canonical-warehouse tests are not the CI fixture set.
Compare a suspected pre-existing failure against the same base and environment.
Never infer that every backend failure is a missing warehouse.

For UI changes, exercise desktop and narrow widths, light/dark, keyboard and
focus-visible, touch targets, overflow, loading/error/empty/long-content and
reduced motion. Use an approved testing-agent handoff for recorded UI testing;
the testing agent owns servers, browser setup and recording. Don't describe a
build or static render as proof of a user flow. Disclose untested paths.

Generative answers use Dime's allowlisted artifact catalog, never generated JSX,
HTML or a second chat runtime. `player_card` input selects identity/metrics from
one source ref/row; the host resolves exact values and source-declared units.
Keep its input schema, frontend payload/parser, visual-artifacts skill and tests
aligned. The final stored submission restores artifacts without duplicating SSE
ones. Exercise `?replay=generative` in development for provider-free card/chart/
table checks; all example data must remain explicitly fictional.

## Finishing

Inspect the diff for unintended files, dead styles, duplicate components and
contract drift. Open a PR into `dev`, address CI and review findings, and preserve
the evidence and any remaining limitations in its description. Merge only under
the requester's grant and the repository's gates. Never force-push shared branches
or merge directly into `main` as a shortcut.
