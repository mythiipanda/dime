const draftKey = (thread: string) => `dime.chat-draft:${thread || "new"}`;

export function loadChatDraft(thread: string): string | null {
  try {
    const value = window.localStorage.getItem(draftKey(thread));
    return typeof value === "string" && value.length > 0 ? value : null;
  } catch {
    return null;
  }
}

export function saveChatDraft(thread: string, text: string): void {
  try {
    if (text) window.localStorage.setItem(draftKey(thread), text);
    else window.localStorage.removeItem(draftKey(thread));
  } catch { }
}

export function clearChatDraft(thread: string): void {
  try { window.localStorage.removeItem(draftKey(thread)); } catch { }
}
