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

## Frozen commit batch (already on instinct/features, awaiting deploy)

1. 15a9826 - compare-card debug rows filtered (QA #71)
2. F39 markdown pipes - literal `|` pipes no longer leak into rendered
   answers (verify in AnswerText.tsx)
3. F29 restore-strips-cards - 410a7bd
4. F2 shot-chart render - court viz zone mapping
5. F27 empty chrome - empty panels render nothing
6. Thought-process panel dupe/jargon scrub - from Tony's screenshot
7. Leaders chart sort - 136cf4d (verify against list at deploy)

## Deploy gate (standing)

Vercel env vars confirmed (NEXT_PUBLIC_BACKEND_URL project-level),
live bundle grep for the Azure URL, then one real query smoke in a
browser before reporting live. Frontend deploys wait for the daily
reset (~11:12 PM ET); main push only on Tony's go.
