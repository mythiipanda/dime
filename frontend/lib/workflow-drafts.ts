export interface WorkflowDraft {
  threadId: string;
  request: string;
  text: string;
  edited: boolean;
  createdAt: number;
}

const draftKey = (thread: string) => `dime.workflow-draft:${thread}`;

export function loadWorkflowDraft(thread: string): WorkflowDraft | null {
  try {
    const draft = JSON.parse(window.localStorage.getItem(draftKey(thread)) || "null");
    return draft && draft.threadId === thread && typeof draft.request === "string" && typeof draft.text === "string" && typeof draft.edited === "boolean" && typeof draft.createdAt === "number" && Number.isFinite(draft.createdAt) ? draft : null;
  } catch { return null; }
}

export function saveWorkflowDraft(draft: WorkflowDraft): void {
  try { window.localStorage.setItem(draftKey(draft.threadId), JSON.stringify(draft)); } catch { }
}

export function createWorkflowDraft(threadId: string, request: string): WorkflowDraft {
  const draft = { threadId, request, text: request, edited: false, createdAt: Date.now() };
  saveWorkflowDraft(draft);
  return draft;
}

export function workflowDraftWasSent(draft: WorkflowDraft, messages: readonly { role: string; text: string }[]): boolean {
  const text = draft.text.trim();
  return !!text && messages.some(message => message.role === "user" && message.text.trim() === text);
}

export function clearWorkflowDraft(thread: string): void {
  try { window.localStorage.removeItem(draftKey(thread)); } catch { }
}
