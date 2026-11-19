# Dime design system

Read [the product design contract](../DESIGN.md) and [frontend agent guidance](AGENTS.md).
The running reference is `/design-system`: actual shared components, not separate mockups.
Examples are labeled fixtures, never live warehouse claims or account saves.

## Library decision

**shadcn/ui's Radix variant** is the component foundation. Tony explicitly rejected
Base UI, which is removed from imports and dependencies. We adapt source-owned
[shadcn recipes](https://ui.shadcn.com/docs/components/radix) to Dime's semantic
tokens and public APIs, rather than installing a second theme. Button, input,
radio group, dialog and popover follow those recipes; Radix Form handles the
complete field's native validation and label/message associations.

The [design.how UI-library directory](https://design.how/directory/ui-libraries)
provided the candidates. This is a choice of one system, not permission to mix them.

| Candidate | Decision |
| --- | --- |
| [shadcn/ui](https://ui.shadcn.com/docs) + [Radix](https://www.radix-ui.com/primitives) | Chosen: mature SaaS component coverage, React/Tailwind fit, owned source and accessible overlay/selection behavior without a theme provider. Use the Radix recipes, not Base UI recipes. |
| [Untitled UI React](https://www.untitledui.com/react/docs/introduction) | Strong SaaS reference built on React Aria and Tailwind; not selected because importing another visual system and its broader source catalog is unnecessary for the existing shell. No paid components are copied. |
| [HeroUI](https://www.heroui.com) / [Mantine](https://mantine.dev) | Broad app kits, but their app-wide styling conventions add migration work beyond these shared primitives. |
| [React Aria Components](https://react-spectrum.adobe.com/react-aria/) | Credible accessible foundation; a second interaction stack alongside the selected Radix family is unnecessary. |
| [Beautiful UI](https://beautifului.dev/harness) | Retain its adopted MIT visual foundation: quiet surfaces, chat proportions, compact actions. Attribution remains in `components/ds/LICENSE`. |

The adapted shadcn components retain its MIT license in `components/ui/LICENSE`;
this attribution covers the shared Button/Input adaptations as well as overlays.
Reference source: the official `new-york` registry's
[button](https://ui.shadcn.com/r/styles/new-york/button.json),
[input](https://ui.shadcn.com/r/styles/new-york/input.json),
[radio group](https://ui.shadcn.com/r/styles/new-york/radio-group.json),
[dialog](https://ui.shadcn.com/r/styles/new-york/dialog.json) and
[popover](https://ui.shadcn.com/r/styles/new-york/popover.json).

Apply [Emil's design-engineering skill](https://github.com/emilkowalski/skills/blob/main/skills/emil-design-eng/SKILL.md)
for complete interaction states, stable geometry, interruptible feedback and
trigger-relative overlay origins. [Quartz spacing](https://design.how/systems/quartz/foundations/space.md)
and [motion](https://design.how/systems/quartz/foundations/motion.md) inform density
and restraint, not a competing Quartz theme. Project rules forbid bespoke motion,
even when a reference suggests custom animation.

## Foundations

| Role | Source | Rule |
| --- | --- | --- |
| Color | `app/globals.css` | Semantic light/dark roles only. `line` divides content; `control-edge` identifies fields at 3:1. Text requires 4.5:1; focus requires 3:1. |
| Theme aliases | `app/dime.css` | Dime's `accent` is blue, not shadcn's neutral hover. Adapt imported recipes, never replace the entire palette. |
| Type | `app/system.css` | UI 13px, body 14px, metadata 12px, page title 28px. Inter for prose, JetBrains Mono for SQL/identifiers; right-aligned tabular figures for numeric cells. |
| Density | `app/system.css` | Controls 28/32/36px; touch targets at least 44px. 4px spacing rhythm with small optical adjustments. |
| Shape | `app/globals.css`, `app/system.css` | 8px controls, 12px panels, 14px windows; pill-shaped actions. Depth only for selected controls and floating content. |
| Width | `app/system.css` | Workspace 1200px, reading width 760px. Wrap toolbars; scroll wide tables locally. |
| Motion | `tw-animate-css`, `app/system.css` | Feedback 150ms, general transition role 200ms. Instant command search. Library popover recipes only; reduced motion removes animation and spinner rotation. |

## Canonical component registry

| Family | Import | Contract |
| --- | --- | --- |
| Action | `components/ds/Button` | shadcn native button/Slot composition + cva. Existing variants, xs/sm/md/icon sizes, native `type="button"` default. `loading` preserves label/width/focus and blocks activation; explicit disabled uses native disabled. |
| Text input | `components/ds/TextField` | shadcn native input adaptation with forwarded ref. Standalone inputs need an explicit label, ID and help/error associations. |
| Complete field | `Form`, `FormField` from `components/ds/TextField` | Compose `FormField name="..."` inside `Form`; one `TextField` child. Radix connects label, description, validation and errors. Native required/disabled/readOnly props stay on the input. Keep form-level error state in the caller. |
| Single-choice filter | `components/ds/SegmentedControl` | Radix radio group/items, not tabs without panels. Group name, string options/value/onChange, optional labels and disabled. Selection follows library-managed focus, including rapid arrow presses; Space activates. |
| Modal | `components/ui/dialog` | shadcn/Radix portal, viewport-bounded scrollable content, focus trap and dismissal. Keep the scroll area inside Content so Radix's scroll lock allows wheel/touch access to tall dialogs. Supply Title, Description and an accessible Close. Command palette restores the invoking control using Radix auto-focus hooks because it also opens from a global shortcut. |
| Source overlay | `components/ui/popover` | shadcn/Radix click/keyboard popover with collision padding and viewport-bounded dimensions. Give Content an accessible name (`aria-label` or `aria-labelledby`). `PopoverTitle`/`Description` are visual text parts. No custom hover timers. |
| Command search | `components/site/DimeCommandPalette` | Shared dialog; input owns active result, arrow keys/Enter navigate and run; Escape/outside press close. Do not recreate a modal per screen. |
| Surface / heading | `components/ds/Panel` | Surface, Panel and PageHeader share spacing, hierarchy and corners. Do not clone card geometry. |
| Evidence table | `components/ds/RecordsTable` | Named scroll region, caption, scoped column headings, right-aligned numbers, honest missing values, count, source footer and meaningful empty state. Units belong in headings or source text. |
| Status / metadata | `components/ds/StatusPill`, `components/ds/Chip` | Label plus semantic tone. Color is never the sole meaning. |
| Analyst-specific | `PromptBar`, `CitationChip`, `ThinkingState`, `ToolChips` in `components/ds` | Preserve Pi/SSE state, evidence navigation and provenance. Domain composition is not a new component framework. |

## Interaction and data rules

- Compose the registry before adding a dependency. Keep one implementation per primitive.
- Pending actions keep their accessible name and reject repeated submission. Keep drafts on failure.
- Every field has a persistent label; placeholders are examples. Errors say how to recover.
- Citation details open deliberately on click, Enter or Space; Escape dismisses and returns focus.
- Tables preserve raw values and provenance. A missing value is a dash, not zero.
- All-numeric columns align right; mixed text columns remain readable. Overflow is focusable.
- Empty tables retain their title, record count, source and a next step. Do not invent records.
- New feature work uses the shared system; legacy screens are not automatically fully migrated.

## Verification

Run `npm run typecheck`, `npm test`, `npm run build` from `frontend`, plus
`python backend/scripts/no_comments.py` from the root. The focused suite is
`npx tsx --test design-system.test.tsx` (also included in `npm test`).

For shared changes, check `/design-system` and real Library/chat/command consumers
in light/dark, desktop/narrow, keyboard/focus-visible and reduced motion. Check
normal, pressed, pending, disabled, error, empty and long-content states. A build
or static markup test does not prove an interactive browser flow; record approved
UI checks and disclose any untested data/provider path.

## Fidelity review

| Before | After | Why |
| --- | --- | --- |
| Unwanted behavior foundation | shadcn/ui's Radix family throughout shared primitives | Honor Tony's preference while keeping one accessible stack. |
| Quiet field edges and repeated help/error markup | Contrast-tested edge, focus ring and Radix Form composition | Discoverable, labeled controls in both themes. |
| Generic left-aligned rows | Numeric alignment, caption, missing-value labels and source footer | Evidence stays inspectable, not decorative. |
| Palette and button-only reference | Complete form lifecycle, spacing/shape/depth specimens, full/empty evidence, source overlay | Agents can copy real states rather than guess. |
