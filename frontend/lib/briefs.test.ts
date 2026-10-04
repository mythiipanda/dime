import assert from "node:assert/strict";
import test from "node:test";
import {
  getBrief,
  listBriefs,
  removeBrief,
  rerunBrief,
  saveBrief,
  takeRerun,
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

test("corrupt storage reads as empty, never throws", () => {
  installLocalStorage();
  ((globalThis as Record<string, unknown>).localStorage as { setItem: (k: string, v: string) => void }).setItem(
    "dime_briefs_v1",
    "not-json{{{",
  );
  assert.deepEqual(listBriefs(), []);
});
