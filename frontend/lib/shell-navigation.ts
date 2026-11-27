export const shellNavigation = [
  { id: "today", label: "Home" },
  { id: "chat", label: "Ask" },
  { id: "workflows", label: "Workflows" },
  { id: "boards", label: "Boards" },
  { id: "notebooks", label: "Notebooks" },
  { id: "briefs", label: "Library" },
  { id: "data", label: "Data" },
  { id: "trades", label: "Trades", group: "Tools" },
  { id: "compare", label: "Compare", group: "Tools" },
  { id: "draft", label: "Draft", group: "Tools" },
  { id: "cap", label: "Cap", group: "Tools" },
  { id: "planner", label: "Planner", group: "Tools" },
  { id: "history", label: "History", group: "Tools" },
  { id: "matchups", label: "Matchups", group: "Tools" },
  { id: "scout", label: "Scout", group: "Tools" },
  { id: "awards", label: "Awards", group: "Tools" },
] as const;
export type ShellTab = typeof shellNavigation[number]["id"];
export function parseShellTab(value: string | null): ShellTab {
  return shellNavigation.some(item => item.id === value) ? value as ShellTab : "chat";
}
export function validThread(value: string | null): value is string {
  return !!value && /^[A-Za-z0-9_-]{1,80}$/.test(value);
}
export function shellUrl(href: string, tab: ShellTab, thread: string): URL {
  const url = new URL(href);
  url.searchParams.set("tab", tab);
  url.searchParams.set("thread", thread);
  url.searchParams.delete("replay");
  if (tab !== "boards") url.searchParams.delete("board");
  if (tab !== "notebooks") url.searchParams.delete("nb");
  return url;
}
