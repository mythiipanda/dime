# Dime UI rehaul plan (rebuilt 2026-09-12, new sandbox)

Target: the live frontend (dime-fawn.vercel.app, Next.js, Tailwind v4
tokens in `frontend/app/globals.css`) moves to the X-link clean-UI
blueprint Tony supplied. Deploys only in the Vercel free-tier window
(resets ~11:12 PM ET) and to `main` only on Tony's explicit go.

## Blueprint tokens (X-link reference)

- Font: SF Pro, weights regular (400) + medium (500) only.
  Letter-spacing -0.15px on body text.
- Type ramp: 12 / 13 / 14 / 24px. Nothing else. 24px is the page/hero
  line, 14px default body, 13px secondary, 12px meta/labels.
- Greys: #292929 (primary text), #5D5D5D (secondary), #9E9E9E
  (meta/disabled). No other text colors.
- Icons: 14px inline, 20px standalone. Stroke 1.5.
- Radius: 8px cards/inputs, 16px panels/modals.
- Mapping note: current tokens live in `globals.css` under `@theme`
  (Inter + stone palette today); the rehaul swaps the palette and font
  tokens there first, then lets components inherit.

## File shape (qm repo convention)

One file per feature under `frontend/components/` - already mostly
true (ChatPanel, DataTable, CompareView, CourtHeatmap, ...). The
rehaul keeps that: token + spacing changes land in `globals.css` and
shared wrappers (`view-shared.tsx`, `DataArtifacts.tsx`) instead of
per-component rewrites. No new cross-cutting CSS files.

## Micro-animations (transitions.dev patterns)

- 150-200ms ease-out on card mount/hover; opacity + 4px translate only.
- Streaming text: no animation (it is already motion).
- Skeletons pulse at 1.2s; no spinners beside streaming answers.
- Respect prefers-reduced-motion.

## Frontend batch for the ~11:12 PM window

Committed on instinct/features (verified 3:31 PM): 15a9826 compare-card
debug rows, 410a7bd F29 restore evidence cards, 136cf4d leaders chart
sort, 123c10b F18 percent-aware tables, e33822f heat gradient,
6ebe895 3P% labels + card copy.

NOT committed (queued only - implement at the window, then deploy):
- F39 markdown pipes - literal `|` leaks into rendered answers.
  AnswerText.tsx already runs remark-gfm; suspect malformed table rows
  from the backend compose or stray pipes in prose. Reproduce against
  prod, then fix at the source (backend scrub if compose emits them,
  AnswerText fallback if malformed GFM).
- F2 shot-chart render - court viz zone-name mapping (QA round 1-3
  find: shades only the restricted area).
- F27 empty chrome - empty panels render nothing.
- Thought-process panel dupe/jargon scrub - from Tony's screenshot.

## Deploy gate (standing)

Vercel env vars confirmed (NEXT_PUBLIC_BACKEND_URL project-level),
live bundle grep for the Azure URL, then one real query smoke in a
browser before reporting live. Frontend deploys wait for the daily
reset (~11:12 PM ET); main push only on Tony's go.
