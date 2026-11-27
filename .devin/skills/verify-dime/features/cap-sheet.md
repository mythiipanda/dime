# Cap sheet

The Cap view is an interactive year-columned grid (2026-27 through 2031-32) of a team's roster contracts, with clickable option toggles, client-side committed/pending arithmetic, apron/tax threshold lines, a scenario bar, and the CBA restrictions panel.

## Sub-features

- `cap-load` renders the grid for a selected team with real warehouse salary data.
- `cap-toggle` flips a player option between committed and pending and updates totals.
- `cap-thresholds` shows apron/tax lines against the totals.
- `cap-pin` saves the scenario to a board and re-evaluates it on load.
- `cap-ask` preloads a chat draft about the scenario ("ask about this scenario").

## How to get to it (user POV)

- Open `/?tab=cap` directly, click Cap in the Tools section of the sidebar, or arrive through the open-in-view seam from a cap artifact.

## Driving it with dime-drive

Preconditions:

- Doctor passes. `/api/cap/sheet` and `/api/cap/scenario` respond 200 — spot-check with `curl "localhost:9910/api/cap/sheet?team=LAL"` before browser work.

- **Load.** `shot --url "http://localhost:3010/?tab=cap" --wait-text "2026-27"` — the year columns render. `text` dump must contain real player names for the default/selected team, dollar figures, and no fixture-style placeholders.
- **Team select.** Pick a team in the team control, `{wait-text}` a known player of that team, shot.
- **Toggle.** Click a player option toggle (a cell control in the player row); assert the totals row arithmetic changes — capture before/after `text` dumps and diff the totals lines. This is client-side committed/pending arithmetic: no reload needed.
- **Pin.** Use the scenario bar to pin; assert the pinned state renders. Reload the page in a fresh context and assert the scenario persists (state.duckdb side effect — the mutation-proof standard).
- **Ask seam.** Click the ask-about-scenario control; assert navigation to `tab=chat` with a preloaded draft mentioning the team — shot the composer state.

## Gotchas

- Totals arithmetic is client-side and instantaneous — if a toggle produces a network-dependent delay or a totals mismatch, that is the defect, not slowness to tolerate.
- The restrictions panel is the analytical payload — its absence or an error state is a failure even when the grid renders.
- Verdict drift: re-evaluated pinned scenarios can legitimately differ after a warehouse refresh; a drift banner is correct behavior, not a bug.
- Pinning mutates shared dev state (state.duckdb) — note it in the report; do not attempt to reset the warehouse.
