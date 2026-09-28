// On-demand panel registry (redesign Phase 3). Panels mount lazily on
// first expansion instead of all rendering in a scroll wall. The mounted
// set only grows; collapsing a panel hides it without unmounting, so its
// fetched data stays put and re-expanding is instant.

import type { ExplorePanelId } from "./exploreSearch";

export const EXPANDABLE_PANELS: ExplorePanelId[] = [
  "leaders",
  "shots",
  "trade",
  "draft",
  "lineups",
  "playoffs",
];

/** Add a panel id to the mounted set. Pure; the set only grows. */
export function markMounted(mounted: ExplorePanelId[], id: ExplorePanelId): ExplorePanelId[] {
  return mounted.includes(id) ? mounted : [...mounted, id];
}

/** Toggle expansion: clicking the open panel closes it, else opens. */
export function toggleExpanded(
  current: ExplorePanelId | null,
  id: ExplorePanelId,
): ExplorePanelId | null {
  return current === id ? null : id;
}
