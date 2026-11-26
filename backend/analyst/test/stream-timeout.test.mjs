import test from "node:test";
import assert from "node:assert/strict";
import { withStreamTimeout } from "../dist/runtime.js";

test("withStreamTimeout injects the default timeout when options carry none", () => {
    let seen;
    const wrapped = withStreamTimeout((model, context, options) => { seen = options; }, 120000);
    wrapped({}, {}, { signal: "sig" });
    assert.equal(seen.timeoutMs, 120000);
    assert.equal(seen.signal, "sig");
});

test("withStreamTimeout preserves an explicit caller timeout", () => {
    let seen;
    const wrapped = withStreamTimeout((model, context, options) => { seen = options; }, 120000);
    wrapped({}, {}, { timeoutMs: 300000 });
    assert.equal(seen.timeoutMs, 300000);
});

test("withStreamTimeout default clamped at 15s floor", () => {
    let seen;
    const wrapped = withStreamTimeout((model, context, options) => { seen = options; }, 5000);
    wrapped({}, {}, {});
    assert.equal(seen.timeoutMs, 5000);
});
