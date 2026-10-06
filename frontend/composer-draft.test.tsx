import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { Profiler, memo } from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import ChatComposer from "./components/ChatComposer";
import {
  clearComposerDraft,
  getComposerDraft,
  setComposerDraft,
  subscribeComposerDraft,
} from "./lib/composer";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const gx = globalThis as unknown as Record<string, unknown>;
gx.window = dom.window;
gx.document = dom.window.document;
gx.HTMLElement = dom.window.HTMLElement;
gx.Element = dom.window.Element;
gx.Node = dom.window.Node;
gx.DocumentFragment = dom.window.DocumentFragment;
gx.Text = dom.window.Text;
gx.Comment = dom.window.Comment;
gx.Event = dom.window.Event;
gx.MouseEvent = dom.window.MouseEvent;
gx.CustomEvent = dom.window.CustomEvent;
gx.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
gx.requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0);
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
gx.IS_REACT_ACT_ENVIRONMENT = true;

function props(over: Record<string, unknown> = {}) {
  return {
    busy: false,
    elapsed: 0,
    models: [],
    model: null,
    modelStatus: "ready" as const,
    onModelChange: () => {},
    onRetryModels: () => {},
    onSend: () => {},
    onStop: () => {},
    variant: "hero" as const,
    placeholder: "Ask...",
    ...over,
  };
}

const Probe = memo(function Probe({ turns }: { turns: string[] }) {
  return (
    <div data-testid="transcript">
      {turns.map((t, i) => (
        <div key={i}>{t}</div>
      ))}
    </div>
  );
});

test("composer store holds subscribes and clears the draft", () => {
  clearComposerDraft();
  assert.equal(getComposerDraft(), "");
  let notes = 0;
  const stop = subscribeComposerDraft(() => {
    notes++;
  });
  setComposerDraft("luka");
  assert.equal(getComposerDraft(), "luka");
  assert.equal(notes, 1);
  setComposerDraft("luka");
  assert.equal(notes, 1);
  clearComposerDraft();
  assert.equal(getComposerDraft(), "");
  assert.equal(notes, 2);
  stop();
  setComposerDraft("shai");
  assert.equal(notes, 2);
  clearComposerDraft();
});

test("fifty keystrokes re-render zero transcript turns", async () => {
  clearComposerDraft();
  const commits = { n: 0 };
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(
      <>
        <Profiler id="transcript" onRender={() => commits.n++}>
          <Probe turns={["turn one", "turn two"]} />
        </Profiler>
        <ChatComposer {...props()} />
      </>,
    );
  });
  const base = commits.n;
  await act(async () => {
    for (let i = 0; i < 50; i++) {
      setComposerDraft("a".repeat(i + 1));
    }
  });
  assert.equal(getComposerDraft(), "a".repeat(50));
  assert.equal(commits.n, base);
  await act(async () => {
    root.unmount();
  });
  container.remove();
  clearComposerDraft();
});

test("draft survives remount and send clears it", async () => {
  clearComposerDraft();
  const sent: string[] = [];
  const first = document.createElement("div");
  document.body.appendChild(first);
  const root1 = createRoot(first);
  const composerProps = () =>
    props({
      onSend: (t: string) => {
        sent.push(t);
        clearComposerDraft();
      },
    });
  await act(async () => {
    root1.render(<ChatComposer {...composerProps()} />);
  });
  await act(async () => {
    setComposerDraft("Who leads in assists?");
  });
  await act(async () => {
    root1.unmount();
  });
  first.remove();
  const second = document.createElement("div");
  document.body.appendChild(second);
  const root2 = createRoot(second);
  await act(async () => {
    root2.render(<ChatComposer {...composerProps()} />);
  });
  const area = second.querySelector('textarea[aria-label="Chat message"]') as HTMLTextAreaElement;
  assert.ok(area);
  assert.equal(area.value, "Who leads in assists?");
  assert.equal(getComposerDraft(), "Who leads in assists?");
  const sendButton = second.querySelector('button[aria-label="Send"]') as HTMLElement;
  assert.ok(sendButton);
  await act(async () => {
    sendButton.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  });
  assert.deepEqual(sent, ["Who leads in assists?"]);
  assert.equal(getComposerDraft(), "");
  await act(async () => {
    root2.unmount();
  });
  second.remove();
  clearComposerDraft();
});

test("external preset lands in the composer while unfocused", async () => {
  clearComposerDraft();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<ChatComposer {...props()} />);
  });
  const area = container.querySelector('textarea[aria-label="Chat message"]') as HTMLTextAreaElement;
  await act(async () => {
    setComposerDraft("Compare Luka and Shai");
  });
  assert.equal(area.value, "Compare Luka and Shai");
  await act(async () => {
    root.unmount();
  });
  container.remove();
  clearComposerDraft();
});
