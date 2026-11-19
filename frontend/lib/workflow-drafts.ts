const draftKey = (thread: string) => `dime.workflow-draft:${thread}`;
const pendingKey = (thread: string) => `dime.workflow-pending:${thread}`;

export function hasPendingWorkflowDraft(thread: string): boolean {
  try { return window.localStorage.getItem(pendingKey(thread)) === "1"; } catch { return false; }
}

export function loadWorkflowDraft(thread: string): string | null {
  try { return window.localStorage.getItem(draftKey(thread)); } catch { return null; }
}

export function saveWorkflowDraft(thread: string, text: string): void {
  try {
    window.localStorage.setItem(pendingKey(thread), "1");
    if (text.trim()) window.localStorage.setItem(draftKey(thread), text);
    else window.localStorage.removeItem(draftKey(thread));
  } catch { }
}

export function clearWorkflowDraft(thread: string): void {
  try {
    window.localStorage.removeItem(draftKey(thread));
    window.localStorage.removeItem(pendingKey(thread));
  } catch { }
}
