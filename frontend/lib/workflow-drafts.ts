const draftKey = (thread: string) => `dime.workflow-draft:${thread}`;

export function loadWorkflowDraft(thread: string): string | null {
  try { return window.localStorage.getItem(draftKey(thread)); } catch { return null; }
}

export function saveWorkflowDraft(thread: string, text: string): void {
  try {
    if (text.trim()) window.localStorage.setItem(draftKey(thread), text);
    else window.localStorage.removeItem(draftKey(thread));
  } catch { }
}
