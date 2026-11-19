# Dime product design

This is the design contract for **all work**, not a one-off screen brief. Read it
with [AGENTS.md](AGENTS.md) before changing the product. Update the relevant
decision here when behavior, architecture, or visual rules change; implementation
details belong in the [component guide](frontend/DESIGN_SYSTEM.md).

## The job

Dime helps an NBA analyst move from a basketball question to a defensible decision.
The work is a question, an analysis, inspectable evidence, and a useful next step.
It is not a collection of dashboards or an imitation of another product's features.
Harvey is a quality bar, not a specification.

Priority order: truthful data and accessible behavior → clear workflow → consistent
components and tokens → visual polish → optional motion. Polish must never hide a
failed query, missing coverage, unassessed verification, or a slow provider.

## One coherent visual language

Keep Beautiful UI's restrained analyst workbench: cool neutral fields, a readable
surface for the answer, compact pill actions, and a small blue action accent.
Use space to separate ideas; use rules for tables and structural boundaries.
Panels do not all need shadows. Depth means an overlay or a selected control.
Warm color means attention or failure, not decoration.

| Layer | Owner | Constraint |
| --- | --- | --- |
| Visual foundation | Beautiful UI, `frontend/app/globals.css` | Semantic light/dark colors, existing typefaces and shadow roles. Keep the MIT attribution. |
| Shared density and detail | `frontend/app/system.css` | 4px spacing rhythm, with 2px optical adjustments; 28/32/36px pointer controls, 44px touch targets; 8px controls, 12px panels. |
| Component foundation | shadcn/ui (Radix variant) | Source-owned React/Tailwind recipes; Radix owns radio selection, forms, focus trapping, overlays, dismissal and portals. Native buttons and inputs retain platform semantics. |
| Composition | `frontend/components/ds`, existing `ui` adapters | Compose existing primitives; don't fork a second Button, dialog, field or motion system. |
| Analysis | Dime's Pi integration and Python tools | Preserve streaming, units, source records, errors and provenance; do not alter Pi itself to style a feature. |

Inter is for reading, JetBrains Mono for SQL and identifiers. Numeric table columns
use tabular figures and right alignment, not a mono paragraph. The shared scale is
12px metadata, 13px interface, 14px body, 28px page titles. The component-reference
hero can use the 40px display role; ordinary app panels cannot.

New color literals belong only in the foundation palette. `line` separates regions;
`control-edge` identifies a field against its surface at 3:1 contrast. Do not use
the low-contrast divider token as the only indication that an input exists.
Body text needs 4.5:1; focus indicators need 3:1. Test both themes.

## Workflows and interaction detail

1. **Ask:** Keep the question and composer prominent. Model selection and tools
   support the task; they must not overwhelm it. Keyboard actions respond immediately.
2. **Run:** Distinguish queued, running, canceled and failed. Keep the draft on an
   error. Show activity only for actual work, not permanent animated decoration.
3. **Read:** Keep conclusions legible at the reading width (760px), with evidence
   adjacent to the claims. Workspaces can grow to 1200px. Do not stretch prose to
   fill an ultrawide screen.
4. **Inspect:** Tables keep their title, count, units and source. Missing is a dash,
   not zero. Overflow scrolls inside a keyboard-focusable region; never shrink the
   entire page or clip the last column. Source overlays preserve the user's place.
5. **Continue:** Name the next action precisely. Saving, exporting and sharing are
   different operations. Do not show a fictional success for a missing endpoint.

Every feature considers normal, hover, focus-visible, pressed, pending, disabled,
empty, error, long-content and narrow-width states. Field labels are persistent;
placeholders are examples, not labels. `FormField` inside `Form` composes Radix's label,
description and error associations around `TextField`; standalone inputs still
need explicit accessible names. A loading button keeps its label and geometry and
blocks repeat activation. Status uses words as well as color.

## Motion policy

Apply [Emil Kowalski's design-engineering skill](https://github.com/emilkowalski/skills/blob/main/skills/emil-design-eng/SKILL.md)
as a craft checklist, not a request for more animation. Ask whether motion helps
before choosing its implementation. Frequent/keyboard-initiated command search
opens immediately; do not delay navigation, data changes or typing. Hover feedback
is short (150ms); any occasional transition uses the shared 200ms role and an
existing library recipe. Popovers use Radix's trigger-relative transform origin. Reduced motion
stops nonessential movement and loading rotation without removing the status text.

Do not hand-roll animation components, keyframes, gesture physics or focus traps.
Existing Tailwind / `tw-animate-css` recipes are sufficient here. A new behavior
requires a concrete gap in the installed stack and a deliberate library decision,
not a dependency added for one effect. Tony's no-bespoke-motion rule overrides
examples in third-party skills that suggest custom effects.

## Research applied, not mixed themes

| Reference | What Dime takes | What Dime does not take |
| --- | --- | --- |
| [Beautiful UI harness](https://beautifului.dev/harness) | Quiet surfaces, chat proportions, compact actions. | Marketing content or fake analyst outcomes. |
| [design.how Quartz](https://design.how/systems/quartz.md), [space](https://design.how/systems/quartz/foundations/space.md), [motion](https://design.how/systems/quartz/foundations/motion.md) | Accessibility first, components before markup, role tokens, consistent rows, restrained feedback. | A second Quartz provider/theme or conflicting token vocabulary. |
| [design.how systems](https://design.how/systems.md) | Compare the actual system fit before selecting a component. | Mixing Glaze glass, Sodium square mono and Beautiful UI geometry on one screen. |
| [shadcn/ui (Radix)](https://ui.shadcn.com/docs/components/radix), [design.how library directory](https://design.how/directory/ui-libraries) | Mature SaaS-style components, owned Tailwind source, accessible Radix behavior, no competing provider/theme. Preserve upstream MIT attribution. | Base UI recipes, a second behavior stack or an unreviewed whole-theme replacement. |
| [Emil's skills](https://aiforui.dev/skills), [library selection](https://github.com/emilkowalski/skills/blob/main/skills/pick-ui-library/SKILL.md) | Invisible detail, responsiveness, cva and Recharts; evaluate library fit before building. | Custom springs, novelty interactions or overriding Tony's library preference. |
| [Meng To's reference list](https://x.com/mengto/status/2122984275566076395) | Concrete craft resources, including Emil; critique and compare actual output. | Installing every suggested skill or inheriting a generic visual theme. |
| [Kosta's tactile-design](https://kosta.fyi/skills/tactile-design) | A reference for tangible control affordance and detail. | Making the analytical workbench skeuomorphic. |
| [Gui Vilela's reference-first advice](https://x.com/guivilelaa_/status/2120298976419238016), [Rico](https://x.com/_heyrico) | Use concrete visual references and one project-specific system rather than generic style prompts. | Treating a social post or an unread reference as implementation proof. |

The gated design.how skill bundle is optional; the public system/foundation pages
above are sufficient to inspect these decisions. Do not claim a gated skill or a
social profile was inspected when only its link was available.

## Fidelity review for this foundation

| Before | After | Why |
| --- | --- | --- |
| Very quiet field edges | Dedicated contrast-tested control edge and explicit focus ring | An input must remain discoverable in both themes. |
| Repeated label/help/error markup | Radix `FormField` composition | Associations travel with the component. |
| Generic left-aligned source rows | Named table, numeric alignment, missing-value labels, source footer | Analysts scan values and inspect provenance without guessing. |
| Reference showed palette and controls only | Live shape, spacing, depth, source overlay and empty/filled table examples | Judge a system by real compositions and states, not swatches alone. |
| Animated command-dialog entry | Immediate shared dialog entry | Frequently repeated keyboard actions must feel immediate. |

## Architecture and verification boundaries

The product host is Node under `backend/analyst`; Python provides the data engine.
Keep domain operations, route validation, public contracts and frontend transport
separate. UI work does not change provider settings, warehouse semantics or the
agent harness. Synthetic design examples must say they are fixtures and make no
provider calls. Numerical/agent changes need targeted tests and measured answer-
quality evidence, not screenshots. Never tune on held-out eval tasks.

The live contract is `/design-system`, using real exports rather than parallel
mock components. Check both themes, keyboard/focus return, mobile overflow,
reduced motion, field recovery and actual existing consumers. Component and token
tests support this; they do not replace UI checks. Record what was untested.
Legacy views are migrated as touched; this document does not assert full adoption.
