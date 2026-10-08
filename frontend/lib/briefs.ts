import { TEAM_IDS, isTeamAbbr } from "./teams";

export interface BriefDoc {
  id: string;
  title: string;
  question: string;
  createdAt: string;
  rows: unknown;
  meta?: Record<string, unknown> | null;
  packHash?: string | null;
  rev?: number;
}

export function docRev(doc: BriefDoc | null): number {
  return doc && typeof doc.rev === "number" ? doc.rev : 0;
}

const KEY = "dime_briefs_v1";
const RERUN_KEY = "dime_rerun";
const SEEN_KEY = "dime_brief_viewer_seen";

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function warn(area: string, error: unknown) {
  try {
    console.warn(`[briefs] ${area}, using memory fallback`, error);
  } catch {}
}

const memoryAreas = new Map<string, Map<string, string>>();

function memoryStore(ns: string): Store {
  let area = memoryAreas.get(ns);
  if (!area) {
    area = new Map<string, string>();
    memoryAreas.set(ns, area);
  }
  return {
    getItem: (k: string) => (area!.has(k) ? area!.get(k)! : null),
    setItem: (k: string, v: string) => {
      area!.set(k, String(v));
    },
    removeItem: (k: string) => {
      area!.delete(k);
    },
  };
}

function webStore(kind: "localStorage" | "sessionStorage"): Store | null {
  try {
    if (typeof window === "undefined") return null;
    const s = window[kind];
    if (!s) return null;
    return s;
  } catch (e) {
    warn(`${kind} unavailable`, e);
    return null;
  }
}

function store(): Store {
  return webStore("localStorage") ?? memoryStore(KEY);
}

function session(): Store {
  return webStore("sessionStorage") ?? memoryStore(RERUN_KEY);
}

function readAll(): BriefDoc[] {
  let raw: string | null = null;
  try {
    raw = store().getItem(KEY);
  } catch (e) {
    warn(`read ${KEY}`, e);
    raw = memoryStore(KEY).getItem(KEY);
  }
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (b): b is BriefDoc =>
        typeof b === "object" &&
        b !== null &&
        typeof (b as Record<string, unknown>).id === "string" &&
        typeof (b as Record<string, unknown>).question === "string",
    );
  } catch (e) {
    warn(`parse ${KEY}`, e);
    return [];
  }
}

function writeAll(docs: BriefDoc[]) {
  try {
    store().setItem(KEY, JSON.stringify(docs));
  } catch (e) {
    warn(`write ${KEY}`, e);
    memoryStore(KEY).setItem(KEY, JSON.stringify(docs));
  }
}

function newId(): string {
  try {
    if (typeof window !== "undefined" && window.crypto?.randomUUID) {
      return `b-${window.crypto.randomUUID().slice(0, 8)}`;
    }
  } catch (e) {
    warn("randomUUID", e);
  }
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
  packHash?: string | null;
}): BriefDoc {
  const doc: BriefDoc = {
    id: newId(),
    title: input.title.trim() || input.question.trim().slice(0, 80) || "Brief",
    question: input.question,
    createdAt: new Date().toISOString(),
    rows: input.rows ?? null,
    meta: input.meta ?? null,
    packHash: input.packHash ?? null,
    rev: 1,
  };
  const docs = readAll().filter((b) => b.id !== doc.id);
  docs.push(doc);
  writeAll(docs);
  return doc;
}

export function removeBrief(id: string) {
  writeAll(readAll().filter((b) => b.id !== id));
}

export const MATCHUP_TEAM_ABBRS = Object.keys(TEAM_IDS).sort();

export interface MatchupBriefInput {
  title: string;
  question: string;
  rows: unknown;
  meta: Record<string, unknown>;
}

export function matchupBriefInput(away: string, home: string): MatchupBriefInput | null {
  const a = away.trim().toUpperCase();
  const h = home.trim().toUpperCase();
  if (!a || !h || a === h || !isTeamAbbr(a) || !isTeamAbbr(h)) return null;
  return {
    title: `${a} at ${h}`,
    question: `Preview ${a} at ${h}: ratings, key matchups, decisive stats`,
    rows: { game: { away: a, home: h } },
    meta: { template: "matchup" },
  };
}

export function updateBrief(
  id: string,
  patch: { title?: string; question?: string },
  expectedRev: number,
): { ok: true; doc: BriefDoc } | { ok: false; current: BriefDoc | null } {
  const docs = readAll();
  const at = docs.findIndex((b) => b.id === id);
  if (at < 0) return { ok: false, current: null };
  const current = docs[at];
  if (docRev(current) !== expectedRev) return { ok: false, current };
  const next: BriefDoc = {
    ...current,
    ...(patch.title !== undefined ? { title: patch.title } : null),
    ...(patch.question !== undefined ? { question: patch.question } : null),
    rev: expectedRev + 1,
  };
  docs[at] = next;
  writeAll(docs);
  return { ok: true, doc: next };
}

export function briefFieldDiff(
  prev: { title: string; question: string },
  next: { title: string; question: string },
): string[] {
  const out: string[] = [];
  if (prev.title !== next.title) out.push("title");
  if (prev.question !== next.question) out.push("question");
  return out;
}

export function briefViewerSeen(): boolean {
  try {
    return store().getItem(SEEN_KEY) === "1";
  } catch (e) {
    warn(`read ${SEEN_KEY}`, e);
    return false;
  }
}

export function markBriefViewerSeen() {
  try {
    store().setItem(SEEN_KEY, "1");
  } catch (e) {
    warn(`write ${SEEN_KEY}`, e);
  }
}

export function shouldAutoOpenBrief(viewerSeen: boolean, panelOpen: boolean): boolean {
  return !viewerSeen && !panelOpen;
}

export function rerunBrief(doc: BriefDoc): string {
  try {
    session().setItem(RERUN_KEY, doc.question);
  } catch (e) {
    warn(`write ${RERUN_KEY}`, e);
    memoryStore(RERUN_KEY).setItem(RERUN_KEY, doc.question);
  }
  return "/?tab=chat";
}

export function takeRerun(): string | null {
  try {
    const q = session().getItem(RERUN_KEY);
    if (q) {
      session().removeItem(RERUN_KEY);
      return q;
    }
  } catch (e) {
    warn(`read ${RERUN_KEY}`, e);
  }
  return null;
}

export function packHashOf(data: unknown): string | null {
  if (typeof data !== "object" || data === null) return null;
  const revision = (data as Record<string, unknown>).revision;
  return typeof revision === "string" && revision ? revision : null;
}

export function briefStale(packHash: string | null | undefined, current: string | null): boolean {
  return !!packHash && !!current && packHash !== current;
}
