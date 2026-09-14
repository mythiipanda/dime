# Dime design refresh - direction draft (Sep 12, 2026)

Tony's steering: "esp the design and functionality need a refresh, i feel
like u got alot more taste." This expands dime-arch/ui-rehaul-plan.md
(tokens, file shape, motion) into a real direction. Direction only -
implementation slices wait for Tony's pick.

## The diagnosis

Current UI is competent but generic: stone palette, cards, left rail,
artifact pane. It reads "dashboard template." Dime's moat is evidence -
every number traced to a payload - but the UI treats evidence as an
afterthought below the fold. The design should make the evidence the
product.

## Direction: "the broadcast desk"

The feeling of a great broadcast analytics segment: the take, the
receipts, the next question. Not a BI dashboard, not a chatbot.

1. **The answer is the hero.** Full-width reading column, 14px body,
   24px verdict line. Datasets become inline evidence cards anchored to
   the sentence they support ("Source: warehouse - 3 of 3" is already
   our best UI idea; make it the pattern everywhere). Tables stop being
   dumps below the answer - they ARE the citation, expandable in place.
2. **Receipts, not a thought panel.** The chain-of-thought panel
   becomes a collapsed "receipts" affordance per answer: tools used,
   ms, rows. Tony already flagged the thought panel's jargon/dupes
   (queued fix) - the rehaul fixes it by changing the metaphor, not the
   wording. Engineers can expand; everyone else sees a clean answer
   with a provenance badge.
3. **Numbers get typography.** Tabular numerals everywhere, right-
   aligned stat columns, the 12/13/14/24 ramp from the plan. A player
   line (31.1 PTS / 5.5 REB / 6.5 AST) should read like a broadcast
   lower-third, not a spreadsheet row.
4. **One accent.** Keep the greys from the blueprint; pick a single
   accent (the current blue Ask button is close) and reserve it for
   action + live data. Everything else is ink and paper.

## Functionality refresh (the other half of his ask)

1. **Compare tray.** Pin players/teams from any answer into a persistent
   tray; one tap opens the compare view. Compare is our most-loved lane
   (F66 got a dedicated lane) - the UI should match its status.
2. **Debate cards one click away.** "Shareable cards settle arguments"
   is on the onboarding screen but buried in product. Every verdict line
   gets a share affordance that mints the card.
3. **Session memory surfaced.** The ledger already remembers; the UI
   never shows it. A subtle "picking up from earlier - OKC's record"
   chip when carry context fires. This is the feature that makes Dime
   feel like it pays attention.
4. **Command palette as primary nav.** Already exists (CommandPalette) -
  elevate it: every panel, every compare, every debate card reachable by
   keyboard. The rail becomes recents-only.

## Implementation slices (each independently shippable)

S1. Receipts metaphor swap (collapse thought panel into per-answer
    receipts) + token pass from the existing plan. Smallest, highest
    visible taste delta.
S2. Answer-hero layout + evidence-card anchoring + number typography.
S3. Compare tray + debate-card share affordances.
S4. Memory chips + palette elevation.

All slices keep the one-file-per-feature shape and the deploy gate
(Vercel window, main on Tony's go).
