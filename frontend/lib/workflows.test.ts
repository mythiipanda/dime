import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { workflows, validateWorkflow } from "./workflows";

describe("workflow registry", () => {
  it("has six unique guided tasks", () => {
    assert.equal(workflows.length, 6);
    assert.equal(new Set(workflows.map((w) => w.id)).size, 6);
  });
  for (const workflow of workflows) {
    it(`${workflow.title} builds a sourced request with ordered sections and all inputs`, () => {
      const values = Object.fromEntries(workflow.fields.map((f) => [f.id, f.options?.[0] || `value-${f.id}`]));
      const text = workflow.buildRequest(values);
      for (const value of Object.values(values)) assert.ok(text.includes(value));
      let previous = -1;
      for (const section of workflow.deliverable) {
        const index = text.indexOf(section);
        assert.ok(index > previous);
        previous = index;
      }
      assert.match(text, /2025-26/);
      assert.match(text, /warehouse.*citations/);
      assert.match(text, /data is missing instead of guessing/);
      assert.deepEqual(validateWorkflow(workflow, values), []);
      assert.equal(workflow.buildRequest(values), text);
    });
    it(`${workflow.title} rejects empty and whitespace-only required fields`, () => {
      const required = workflow.fields.filter((f) => f.required);
      assert.deepEqual(validateWorkflow(workflow, {}), required);
      assert.deepEqual(validateWorkflow(workflow, Object.fromEntries(workflow.fields.map((f) => [f.id, "  "]))), required);
      const values = Object.fromEntries(required.map((f) => [f.id, "filled"]));
      assert.deepEqual(validateWorkflow(workflow, values), []);
      assert.doesNotMatch(workflow.buildRequest({}), /undefined|null/);
    });
  }
});
