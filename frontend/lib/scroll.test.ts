import assert from "node:assert/strict";
import test from "node:test";
import {
  findScroller,
  glideToBottom,
  isAtBottom,
  jumpToTop,
  scrolledUp,
  shouldFollow,
} from "./scroll";

function box(over: Record<string, unknown> = {}) {
  const calls: unknown[][] = [];
  return {
    calls,
    el: {
      scrollHeight: 1000,
      clientHeight: 400,
      scrollTop: 0,
      scrollTo: (...args: unknown[]) => {
        calls.push(args);
      },
      ...over,
    } as unknown as Element,
  };
}

test("follows only while generating at the bottom", () => {
  assert.equal(shouldFollow(true, true), true);
  assert.equal(shouldFollow(true, false), false);
  assert.equal(shouldFollow(false, true), false);
  assert.equal(shouldFollow(false, false), false);
});

test("only upward moves clear the bottom latch", () => {
  assert.equal(scrolledUp(500, 200), true);
  assert.equal(scrolledUp(200, 500), false);
  assert.equal(scrolledUp(200, 198), false);
});

test("bottom detection uses a 120px tolerance band", () => {
  assert.equal(isAtBottom({ scrollHeight: 1000, clientHeight: 400, scrollTop: 600 }), true);
  assert.equal(isAtBottom({ scrollHeight: 1000, clientHeight: 400, scrollTop: 400 }), false);
});

test("glide scrolls smooth to the end, jump goes straight to top", () => {
  const g = box();
  assert.equal(glideToBottom(g.el), true);
  assert.deepEqual(g.calls, [[{ top: 1000, behavior: "smooth" }]]);
  const j = box();
  assert.equal(jumpToTop(j.el), true);
  assert.deepEqual(j.calls, [[0, 0]]);
  assert.equal(glideToBottom(null), false);
  assert.equal(jumpToTop(null), false);
});

test("findScroller skips ancestors that cannot scroll", () => {
  const prev = (globalThis as Record<string, unknown>).getComputedStyle;
  (globalThis as Record<string, unknown>).getComputedStyle = (el: unknown) =>
    ({
      overflowY: (el as Record<string, unknown>).tag === "tall" ? "visible" : "auto",
    }) as CSSStyleDeclaration;
  try {
    const fake = { scrollHeight: 700, clientHeight: 100, tag: "tall", parentElement: null };
    const pane = { scrollHeight: 700, clientHeight: 257, tag: "pane", parentElement: null };
    (fake as Record<string, unknown>).parentElement = pane;
    assert.equal(findScroller({ parentElement: fake }), pane);
  } finally {
    if (prev === undefined) delete (globalThis as Record<string, unknown>).getComputedStyle;
    else (globalThis as Record<string, unknown>).getComputedStyle = prev;
  }
});

test("findScroller climbs to the first scrollable ancestor", () => {
  const inner = { scrollHeight: 100, clientHeight: 100, parentElement: null };
  const pane = { scrollHeight: 700, clientHeight: 257, parentElement: null };
  const leaf = { parentElement: inner };
  (inner as Record<string, unknown>).parentElement = pane;
  assert.equal(findScroller(leaf), pane);
  assert.equal(findScroller(null), null);
  assert.equal(findScroller({}), null);
});
