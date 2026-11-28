import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

function freshDom() {
  const dom = new JSDOM("", { url: "http://localhost/" });
  Object.assign(globalThis, { window: dom.window, localStorage: dom.window.localStorage });
}

const context = {
  kind: "matchup",
  summary: "BOS @ NYK · 2026-11-27",
  entities: { teams: ["BOS", "NYK"], date: "2026-11-27" },
};

test("workflow drafts round-trip the attached view context", async () => {
  freshDom();
  const { createWorkflowDraft, loadWorkflowDraft } = await import("./lib/workflow-drafts");
  createWorkflowDraft("t-1", "Who has the edge?", context);
  const loaded = loadWorkflowDraft("t-1");
  assert.deepEqual(loaded?.context, context);
});

test("drafts without context load cleanly", async () => {
  freshDom();
  const { createWorkflowDraft, loadWorkflowDraft } = await import("./lib/workflow-drafts");
  createWorkflowDraft("t-2", "plain ask");
  const loaded = loadWorkflowDraft("t-2");
  assert.equal(loaded?.context, undefined);
});

test("workflowDraftWasSent matches the wire-format message the submit path appends", async () => {
  freshDom();
  const { createWorkflowDraft, workflowDraftWasSent } = await import("./lib/workflow-drafts");
  const { serializeViewContext } = await import("./lib/view-context");
  const draft = createWorkflowDraft("t-3", "Who has the edge?", context);
  const wire = serializeViewContext(context, "Who has the edge?");
  assert.equal(workflowDraftWasSent(draft, [{ role: "user", text: wire }]), true);
  assert.equal(workflowDraftWasSent(draft, [{ role: "user", text: "unrelated" }]), false);
});
