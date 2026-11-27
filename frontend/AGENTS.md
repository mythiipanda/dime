# Frontend guidance

Read the root [AGENTS.md](../AGENTS.md) and [DESIGN.md](../DESIGN.md) first.
[DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) is the import registry; `/design-system` is
the live reference. Keep all three aligned when changing the shared foundation.

- Extend `components/ds` and existing `components/ui` adapters, not local clones.
- Use shadcn/ui's Radix variant, not Base UI. Radix owns field associations, radio keyboard behavior, focus trapping and overlays; buttons and inputs use native semantics.
  `FormField` inside `Form` wraps one `TextField` for persistent label, description and error text.
- Palette roles live in `app/globals.css`; shared sizing/detail in `app/system.css`.
  Tailwind utilities can override component-layer defaults. Unlayered legacy CSS
  can override layered rules: explicitly verify computed focus rings, not class names.
- Existing `dime.css` aliases support imported recipes. Dime's `accent` is blue,
  not shadcn's neutral hover fill. Adapt recipes instead of changing the global role.
- New controls use semantic tokens in both themes. No literal colors in screens,
  bespoke keyframes, gesture engines, focus traps or second component system.
- Tables keep units/source and missing values. Use `RecordsTable` for static
  evidence records; it is not an editable grid or a substitute for domain tables.
- Keep source inspection and streamed-answer contracts intact. Clearly mark
  fixtures; component-reference interactions must not call live providers.

Run `npm run typecheck`, `npm test`, and `npm run build` for frontend changes.
Radix overlay DOM tests need the DOM installed before importing components; query
portaled content through `document`, not only the React root. Use the existing replay
fixtures for provider-free UI checks; do not burn model quota to inspect layout.

## Design skills

Two craft skills are part of the frontend workflow; invoke them at their gates,
not retroactively:

- `plan-design-review` — the design gate BEFORE opening a UI PR. Run its
  seven passes (information architecture, interaction states, user journey,
  AI-slop risk, design-system alignment, responsive/accessibility, unresolved
  decisions) against the diff or plan; unresolved findings block opening, not
  just merge. Zero-finding passes are reported, never skipped.
- `impeccable` (vendored in `.devin/skills/impeccable/`, upstream
  pbakaus/impeccable) — the polish pass AFTER build correctness is green.
  Read its SKILL.md and the `polish`/`harden`/`audit` references before the
  pass; its craft-floor reference applies to every UI edit.

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
