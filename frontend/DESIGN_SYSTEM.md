# Dime design system

The running reference is `/design-system`. It renders the actual shared components,
not separate mock implementations. Use it in light and dark themes before changing a primitive.

## Product direction

Dime is an analyst workbench, not a dashboard template. The question, answer and evidence
are the primary content. Keep neutral surfaces, readable secondary text, compact controls,
restrained color and ample space around the question. Beautiful UI's harness supplies the
visual direction; the old prototype is not a design specification.

The pilot adoption is Library search and filters, plus the command palette shared by every
workspace. This is a foundation release, not a claim that every legacy screen is migrated.
Platform work can consume these exports without replacing Dime's Pi agent or streaming API.

## Research and selection

Reviewed the [40-library design.how directory](https://design.how/directory/ui-libraries),
then compared the React/Next/Tailwind candidates with Dime's installed dependencies and
agent runtime. The directory is a discovery list, not a recommendation to combine systems.

| Source | Fit and decision |
| --- | --- |
| [Beautiful UI](https://beautifului.dev/harness) | Keep the adopted MIT visual foundation, quiet surfaces and chat proportions. The existing attribution remains in `components/ds/LICENSE`. |
| [Base UI](https://base-ui.com/react/overview/quick-start) | Chosen behavior layer, already installed. Button, Input, RadioGroup, Dialog and Popover own keyboard interaction, disabled semantics, focus and dismissal. |
| [coss UI](https://coss.com/ui/docs) | Chosen composition/reference layer: Base UI with Tailwind, small owned adapters, shared control sizing and complete states. Dime adapts the pattern, not its full theme or component inventory. |
| [shadcn/ui](https://ui.shadcn.com/docs) | Compatible registry/composition conventions. The existing Popover already follows them. Use its Base UI recipes, not a second Radix foundation. |
| [React Aria](https://react-spectrum.adobe.com/react-aria/) | Strong accessible interactions, but adopting it alongside the installed Base UI duplicates behavior and styling work. |
| [Ariakit](https://ariakit.org), [Ark UI](https://ark-ui.com), [Headless UI](https://headlessui.com), [Radix](https://www.radix-ui.com/primitives) | Credible alternatives, not additional dependencies for the same primitive families. |
| [Mantine](https://mantine.dev), [Chakra](https://chakra-ui.com), [Material UI](https://mui.com/material-ui/), [HeroUI](https://www.heroui.com) | Broad application kits; unnecessary provider/theme changes for this existing Tailwind shell. |
| [Kibo UI](https://www.kibo-ui.com/docs) | Useful future source for a genuinely missing complex feature. Do not install its whole catalog. |
| [AI Elements](https://elements.ai-sdk.dev) | Useful citation/reasoning composition references; its site announces migration to shadcn/ui at the end of November 2026. Do not introduce a soon-deprecated runtime dependency. |
| [assistant-ui](https://www.assistant-ui.com/docs) | Chat-specific runtime integration is unnecessary while Dime owns its Pi/SSE state. Its docs returned 403 during this review; no runtime claims were verified. |
| [Motion Primitives](https://motion-primitives.com/docs), [Magic UI](https://magicui.design), [Cult UI](https://www.cult-ui.com), [Kokonut UI](https://kokonutui.com) | Selective motion/marketing sources, not the workbench's behavior foundation. No animated decoration or new animation runtime. |
| [HextaUI](https://hextaui.com), [transitions.dev](https://transitions.dev), [Rare UI](https://rareui.com) | Named references, not verified implementation sources: requests returned 403, 403 and 429 respectively. No copied code or accessibility claims from them. |
| Other directory entries | Vue/Svelte/Solid-specific systems do not fit React; platform-specific and large themed kits add no capability needed by this pilot. |

[design.how](https://design.how/skills) was unlocked with the requested email. Its
`design-system-boss`, `build-design-system`, `ui-review`, glossary, taste and component
guidance informed the audit, registry, complete states and keyboard/focus checks. We use
the PR/minimal-footprint path: no whole-app migration, mass token rewrite, worker fan-out,
font generation, logo generation or new animation system. The stock scripts are not added
to the product; this repository keeps its own typecheck, tests and zero-comment check.
No before/after pixel-parity claim is made: changed control sizes, contrast and selection
semantics are intentional. A future migration needs a per-screen baseline first.

## Foundations

| Role | Source | Rule |
| --- | --- | --- |
| Color | `app/globals.css` | Use `page`, `canvas`, `surface`, `inset`, `ink`, `ink-2`, `ink-3`, `line`, `accent-ink`, and status roles, never literal palette values in a screen. |
| Theme aliases | `app/dime.css` | Existing shadcn aliases remain compatible. Dime's `accent` is a brand blue, not shadcn's neutral hover background; adapt imported recipes accordingly. |
| Type | `app/system.css` | UI 13px, body 14px, meta 12px, page title 28px. Inter for prose; JetBrains Mono for SQL, IDs and tabular numbers. Use semantic HTML, not another typography runtime. |
| Density | `app/system.css` | Button xs/sm/md = 28/32/36px minimum. Input = 36px. Touch controls = at least 44px. Never shrink a touch target to fit a row. |
| Corners | `app/globals.css` | Chip 6px, control 8px, card 10px, window 14px. Existing Surface uses 12px panels. Buttons retain Beautiful UI's pill shape. |
| Width | `app/system.css` | Workspace 1200px; reading content 760px. Fields shrink with their container and toolbar controls wrap. |
| Motion | `tw-animate-css`, `app/system.css` | Use library enter recipes and the existing spinner. Feedback 150ms, transitions 200ms. No custom spring, sliding selection indicator or bespoke keyframes. Respect reduced motion. |
| Elevation | `app/globals.css` | Hairline for selected controls, raised/overlay only when content actually floats. |

`ink-3` and the light-theme status colors were adjusted within their existing hue families
so supporting copy and statuses can meet normal-text contrast, rather than remaining decorative
low-contrast gray. `design-system.test.tsx` checks the actual token pairs in both themes.

## Canonical component registry

| Family | Import | Status / use |
| --- | --- | --- |
| Action | `components/ds/Button` | Base UI Button; preserves `primary`, `secondary`, `ghost`, `accent`, `success`, `quiet`; adds `destructive`, icon size and loading. |
| Text input | `components/ds/TextField` | Base UI Input; native input props/ref; explicitly connect a label and help/error text. |
| Single-choice filter | `components/ds/SegmentedControl` | Base UI RadioGroup/Radio; same string options/value/onChange API, optional labels, group label and disabled. It is a radio group, not tabs without panels. |
| Modal | `components/ui/dialog` | Base UI Dialog parts; portal, backdrop, viewport and popup. Add Title, Description and an accessible Close. |
| Source overlay | `components/ui/popover` | Existing Base UI Popover. Keep the library's collision handling and focus behavior. |
| Command search | `components/site/DimeCommandPalette` | Shared dialog composition. Input owns active option; arrow keys/Enter search results; Escape/outside press close. |
| Surface / heading | `components/ds/Panel` | Existing Surface, Panel and PageHeader. Use semantic text inside them; do not clone card geometry. |
| Status / metadata | `components/ds/StatusPill`, `components/ds/Chip` | Existing label-plus-tone components. Color never supplies the only meaning. |
| Analyst-specific | `components/ds/PromptBar`, `CitationChip`, `ThinkingState`, `ToolChips` | Keep domain composition, evidence and provider contracts. Use shared primitives when extending them; do not swap the agent runtime for a chat UI library. |

Existing domain views that still use raw controls are legacy consumers, not alternate
canonical components. Migrate them as their feature is touched; do not build another Button.

## Component contracts

### Button

`<Button variant="primary" loading={saving} type="submit">Save research</Button>`

The default type is `button`, so a secondary action cannot accidentally submit a form.
Only intended submit actions use `type="submit"`. Loading keeps the accessible label and
occupied box, sets `aria-busy`, stays focusable and prevents activation through Base UI.
Ordinary disabled controls are not focusable. Give icon-only buttons an `aria-label`.
The Base UI `render` prop is available for composition; set `nativeButton={false}` for a link.
Do not pass `loading` to a custom `render` element that ignores disabled semantics.

### TextField

Use `label[htmlFor]`, a stable `id`, `required` where appropriate, and `aria-describedby`
pointing to help or an inline error. Set `aria-invalid` only when invalid, not merely because
the field is required. Preserve the value on failed submission. The disabled style wins over
the invalid border. The reference demonstrates normal, required, invalid, read-only, disabled
and long-value states. Search fields use `type="search"` and an explicit accessible name.

### SegmentedControl

Use this for mutually exclusive filters, not navigation between separate documents.
`label` names the group; `labels` maps stored values to human-readable text. Arrow keys move
within the group, Tab enters/leaves it, selection has `aria-checked`, and disabled groups do
not change. There is no handcrafted animated thumb. Use Base UI Tabs directly for real tab
panels, including its panel associations, rather than making this component impersonate tabs.

### Dialog and command search

Base UI owns scroll locking, focus containment, Escape, outside dismissal and focus return.
Keep the root mounted while its `open` value changes. The command input receives initial
focus, result buttons are outside the Tab order, and the visible close control is keyboard
reachable. A no-match state does not run an arbitrary action on Enter.

| Event | Expected result |
| --- | --- |
| Open via search button | Focus enters the command input. |
| Tab / Shift+Tab while open | Focus stays inside the modal. |
| Arrow keys in input | Active result changes and scrolls into view. |
| Enter in input | Only the active result runs, once. |
| Enter on close control | Only closes; never executes a search result. |
| Escape or outside press | Closes and returns focus to the previous opener when it still exists. |
| Action navigates / opener removed | No detached element is focused; destination owns its focus policy. |
| Empty search result | Announces no matches; Enter does nothing. |

## Before shipping a UI change

Use the component contracts above. Inspect required, invalid,
disabled, loading, empty, no-match and long-text states. Check the actual feature at 390px
and 1280px, light/dark, keyboard, touch and reduced motion. Include real focus-ring captures,
not just computed CSS. Test the backend contract independently of the illustration.

Run `npm run typecheck`, `npm test`, `npm run build` and the repository zero-comment check.
The design-system tests check semantics and contrast, not subjective visual quality.
Do not describe a build or screenshot as proof of a flow that was not actually exercised.
