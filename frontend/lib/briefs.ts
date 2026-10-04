export interface BriefDoc {
  id: string;
  title: string;
  question: string;
  createdAt: string;
  rows: unknown;
  meta?: Record<string, unknown> | null;
}

const KEY = "dime_briefs_v1";

function store(): Pick<Storage, "getItem" | "setItem" | "removeItem"> | null {
  try {
    if (typeof window === "undefined" || !window.localStorage) return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

function readAll(): BriefDoc[] {
  const s = store();
  if (!s) return [];
  try {
    const raw = s.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (b): b is BriefDoc =>
        typeof b === "object" &&
        b !== null &&
        typeof (b as Record<string, unknown>).id === "string" &&
        typeof (b as Record<string, unknown>).question === "string",
    );
  } catch {
    return [];
  }
}

function writeAll(docs: BriefDoc[]) {
  store()?.setItem(KEY, JSON.stringify(docs));
}

function newId(): string {
  try {
    if (typeof window !== "undefined" && window.crypto?.randomUUID) {
      return `b-${window.crypto.randomUUID().slice(0, 8)}`;
    }
  } catch {}
  return `b-${Date.now().toString(36)}-${Math.floor(Math.random() * 1296).toString(36)}`;
}

export function listBriefs(): BriefDoc[] {
  return readAll().sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}

export function getBrief(id: string): BriefDoc | null {
  return readAll().find((b) => b.id === id) ?? null;
}

export function saveBrief(input: {
  title: string;
  question: string;
  rows: unknown;
  meta?: Record<string, unknown> | null;
}): BriefDoc {
  const doc: BriefDoc = {
    id: newId(),
    title: input.title.trim() || input.question.trim().slice(0, 80) || "Brief",
    question: input.question,
    createdAt: new Date().toISOString(),
    rows: input.rows ?? null,
    meta: input.meta ?? null,
  };
  const docs = readAll().filter((b) => b.id !== doc.id);
  docs.push(doc);
  writeAll(docs);
  return doc;
}

export function removeBrief(id: string) {
  writeAll(readAll().filter((b) => b.id !== id));
}

function sessionStore(): Pick<Storage, "getItem" | "setItem" | "removeItem"> | null {
  try {
    if (typeof window === "undefined" || !window.sessionStorage) return null;
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function rerunBrief(doc: BriefDoc): string {
  try {
    sessionStore()?.setItem("dime_rerun", doc.question);
  } catch {}
  return "/?tab=chat";
}

export function takeRerun(): string | null {
  try {
    const q = sessionStore()?.getItem("dime_rerun");
    if (q) {
      sessionStore()?.removeItem("dime_rerun");
      return q;
    }
  } catch {}
  return null;
}
