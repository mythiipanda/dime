import assert from "node:assert/strict";
import test from "node:test";
import {
  briefStale,
  getBrief,
  listBriefs,
  packHashOf,
  removeBrief,
  rerunBrief,
  saveBrief,
  takeRerun,
  updateBrief,
} from "./briefs";

function installLocalStorage() {
  const makeStore = () => {
    const store = new Map<string, string>();
    return {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => {
        store.set(k, String(v));
      },
      removeItem: (k: string) => {
        store.delete(k);
      },
      clear: () => store.clear(),
    };
  };
  (globalThis as Record<string, unknown>).localStorage = makeStore();
  (globalThis as unknown as { window?: unknown }).window = {
    localStorage: (globalThis as Record<string, unknown>).localStorage,
    sessionStorage: makeStore(),
  };
}

const ROWS = {
  game: { away: "BOS", home: "NYK", date: "2026-10-09", arena: "Madison Square Garden" },
};

test("saved briefs persist and reload with their rows", () => {
  installLocalStorage();
  (globalThis as Record<string, unknown>).localStorage &&
    ((globalThis as Record<string, unknown>).localStorage as { clear: () => void }).clear();
  const doc = saveBrief({ title: "BOS at NYK", question: "How do Boston and New York match up?", rows: ROWS });
  assert.ok(doc.id.startsWith("b-"));
  assert.equal(listBriefs().length, 1);
  const loaded = getBrief(doc.id);
  assert.deepEqual(loaded?.rows, ROWS);
  assert.equal(loaded?.question, "How do Boston and New York match up?");
});

test("blank titles fall back to the question", () => {
  installLocalStorage();
  const doc = saveBrief({ title: "  ", question: "Preview Lakers vs Celtics", rows: null });
  assert.equal(doc.title, "Preview Lakers vs Celtics");
  removeBrief(doc.id);
  assert.equal(getBrief(doc.id), null);
});

test("rerun stores the question and takeRerun consumes it once", () => {
  installLocalStorage();
  (globalThis as unknown as { sessionStorage?: unknown }).sessionStorage = (
    globalThis as Record<string, unknown>
  ).localStorage;
  const doc = saveBrief({ title: "t", question: "Preview BOS at NYK", rows: null });
  assert.equal(rerunBrief(doc), "/?tab=chat");
  assert.equal(takeRerun(), "Preview BOS at NYK");
  assert.equal(takeRerun(), null);
});

test("throwing storage warns loudly and falls back to memory", () => {
  const warnings: unknown[][] = [];
  const orig = console.warn;
  (console as unknown as Record<string, unknown>).warn = (...a: unknown[]) => {
    warnings.push(a);
  };
  (globalThis as unknown as { window?: unknown }).window = {
    get localStorage(): never {
      throw new Error("denied");
    },
    get sessionStorage(): never {
      throw new Error("denied");
    },
  };
  try {
    const doc = saveBrief({ title: "t", question: "q?", rows: null });
    assert.equal(listBriefs().length, 1);
    assert.equal(getBrief(doc.id)?.question, "q?");
    assert.ok(warnings.length > 0);
    assert.ok(String(warnings[0][0]).includes("[briefs]"));
  } finally {
    (console as unknown as Record<string, unknown>).warn = orig;
    installLocalStorage();
  }
});

test("typed revision guard accepts matching writes, rejects stale ones", () => {
  installLocalStorage();
  const doc = saveBrief({ title: "t", question: "q?", rows: null });
  assert.equal(doc.rev, 1);
  const ok = updateBrief(doc.id, { title: "t2" }, 1);
  assert.equal(ok.ok, true);
  if (ok.ok) assert.equal(ok.doc.rev, 2);
  const stale = updateBrief(doc.id, { title: "t3" }, 1);
  assert.equal(stale.ok, false);
  if (!stale.ok && stale.current) assert.equal(stale.current.title, "t2");
  assert.equal(getBrief(doc.id)?.title, "t2");
  const missing = updateBrief("nope", { title: "x" }, 0);
  assert.equal(missing.ok, false);
  assert.equal(missing.current, null);
  removeBrief(doc.id);
});

test("legacy docs without a revision compare as zero", () => {
  installLocalStorage();
  const doc = saveBrief({ title: "t", question: "q?", rows: null });
  const raw = JSON.parse(
    ((globalThis as Record<string, unknown>).localStorage as { getItem: (k: string) => string }).getItem(
      "dime_briefs_v1",
    ),
  );
  delete raw[0].rev;
  ((globalThis as Record<string, unknown>).localStorage as { setItem: (k: string, v: string) => void }).setItem(
    "dime_briefs_v1",
    JSON.stringify(raw),
  );
  const first = updateBrief(doc.id, { title: "t2" }, 0);
  assert.equal(first.ok, true);
});

test("pack hash helpers read revision and compare staleness", () => {
  assert.equal(packHashOf({ revision: "abc123" }), "abc123");
  assert.equal(packHashOf({}), null);
  assert.equal(packHashOf(null), null);
  assert.equal(briefStale("abc", "abc"), false);
  assert.equal(briefStale("abc", "def"), true);
  assert.equal(briefStale(null, "def"), false);
  assert.equal(briefStale("abc", null), false);
});

test("saved briefs keep their pack hash", () => {
  installLocalStorage();
  const doc = saveBrief({ title: "t", question: "q?", rows: null, packHash: "abc123" });
  assert.equal(getBrief(doc.id)?.packHash, "abc123");
  removeBrief(doc.id);
});

test("corrupt storage reads as empty, never throws", () => {
  installLocalStorage();
  ((globalThis as Record<string, unknown>).localStorage as { setItem: (k: string, v: string) => void }).setItem(
    "dime_briefs_v1",
    "not-json{{{",
  );
  assert.deepEqual(listBriefs(), []);
});
