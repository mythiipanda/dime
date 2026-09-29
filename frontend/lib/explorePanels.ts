




import type { ExplorePanelId } from "./exploreSearch";

export const EXPANDABLE_PANELS: ExplorePanelId[] = [
  "leaders",
  "shots",
  "trade",
  "draft",
  "lineups",
  "playoffs",
];


export function markMounted(mounted: ExplorePanelId[], id: ExplorePanelId): ExplorePanelId[] {
  return mounted.includes(id) ? mounted : [...mounted, id];
}


export function toggleExpanded(
  current: ExplorePanelId | null,
  id: ExplorePanelId,
): ExplorePanelId | null {
  return current === id ? null : id;
}
