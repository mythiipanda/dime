---
name: dime-ui
description: Design or change Dime frontend screens and shared components. Use its library-backed design system, states and evidence-first analyst UX.
---

# Dime UI

Read `frontend/DESIGN_SYSTEM.md` and the affected feature before editing. Open
`/design-system` for the real components, including pending/error/disabled/long-text states.

## Design first

1. Name the user's task, primary action, evidence they need and possible failure.
2. Choose existing components from the registry. Inspect their implementation and real calls.
3. State loading, empty, error, disabled, pending, long-content and narrow-screen behavior.
4. Preserve the backend contract, Pi behavior, source rows, verification caveats and user input.

## Use the foundation

- Beautiful UI is the visual source; the old prototype is not a specification.
- Use Base UI behavior. Consult coss UI/shadcn Base UI recipes for missing composition.
- Reuse Button, TextField, SegmentedControl, Panel, StatusPill and existing overlays.
- Add a missing primitive once in the registry. Do not invent another local button or modal.
- Prefer a proven library over handcrafted behavior or animation; inspect its license and API.
- Do not add a second headless system, animation runtime, font or chat-state layer by default.
- Do not copy shadcn's `accent` hover recipe verbatim: Dime's accent token is brand blue.
- No bespoke keyframes, spring physics, decorative loops or animated selection thumbs.

## Interaction rules

- One primary action per task. Icon-only actions need an accessible name.
- Buttons default to type button. Submit is explicit. Loading keeps label, width and focus.
- A field has a connected label and help/error. Invalid is not the same as required.
- Use radio groups for filters, tabs for associated panels, links for navigation.
- Modal focus, Escape, scroll locking and return focus belong to Base UI, not effects.
- Keep small supporting copy readable; status includes words, never only a colored dot.
- Controls wrap on narrow screens. Touch targets are at least 44px.
- Use semantic theme tokens, shared sizing, named widths and library motion recipes.
- Preserve evidence. Mark illustrative data and replay states so they cannot imply live analysis.

## Validate

Run typecheck, frontend tests, build and the repo's zero-comment checker. Inspect the changed
flow at 390px and 1280px, light/dark, keyboard and reduced motion. Include focus after close,
retry with input preserved and the longest real content. UI-driven testing requires the
session's normal approval; do not claim browser verification from a unit test or screenshot.

Update the registry/reference when a public primitive changes. Keep APIs compatible with
platform work on dev. Branch from and target dev; leave the analyst backend untouched for UI work.
