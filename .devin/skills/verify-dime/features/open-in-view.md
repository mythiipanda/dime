# Artifact open-in-view seam

When a chat answer carries an artifact with single-tool provenance, an "Open in <View>" button hands the user from the chat into the matching Tools view with the right team pre-selected — the seam between asking and exploring.

## Sub-features

- `seam-render` shows the Open-in-view button on provenance-carrying artifacts.
- `seam-navigate` lands on the correct tab with the team pre-selected.
- `seam-honest-absence` renders no button when there is no honest single-tool attribution.

## How to get to it (user POV)

- Ask a question in chat that yields a player-card or team-card artifact (e.g. a cap or scouting question), then click "Open in Cap" / "Open in Scout" on the artifact.

## Driving it with dime-drive

Preconditions:

- Doctor passes. Live lane available and named (the seam requires a real artifact with provenance; the replay fixture does not emit warehouse provenance).

- **Render.** Live-run a cap question (e.g. "What is the Lakers cap situation?") through the UI: fill the composer `.composer-dock textarea`, press Enter, `{wait-text: "Open in"}` with generous timeout. Shot the artifact with the button visible.
- **Navigate.** `{click}` the Open-in-view button. Assert the URL now carries `tab=cap` (or the matching tab) and the target view renders with the team pre-selected — e.g. `{assert-text: "LAL"}`-equivalent observable in the view's team control, plus a shot.
- **Honest absence.** On an artifact synthesized from multiple sources (a compare or memo artifact), assert NO "Open in" button renders (`{assert-absent: "Open in"}`). Rendering nothing when there is no honest single-tool attribution is correct behavior — never "fix" this into a guess.

## Gotchas

- Provenance keying is on `provenance.capability`, not the display label — artifacts without host-resolved provenance (tables/charts/synthesized content) honestly render no button.
- Only player_card and team_card artifacts get host-resolved provenance today; coverage beyond cards is a known v2 design item, not a bug.
- Live runs are slow; budget minutes and prefer cap questions, which resolve provenance reliably.
- Navigation is client-side pushState — assert both the URL param AND the rendered view; a URL change without a view swap is a failure.
