import assert from "node:assert/strict";
import { test } from "node:test";
import { nimGuardedFetch } from "./dist/pi-context.js";

const BASE = "https://integrate.api.nvidia.com/v1";
const r429 = () => new Response('{"error":{"message":"rate limited"}}', { status: 429 });
const r503 = () => new Response('{"error":{"message":"unavailable"}}', { status: 503 });
const ok = () => new Response("ok", { status: 200 });

test("retries 429 within the window and passes the success through", async () => {
    let calls = 0;
    const realFetch = async () => { calls += 1; return calls < 2 ? r429() : ok(); };
    const fetch = nimGuardedFetch(BASE, realFetch);
    const res = await fetch(`${BASE}/chat/completions`, { method: "POST" });
    assert.equal(res.status, 200);
    assert.equal(calls, 2);
});

test("retries 503 within the window", async () => {
    let calls = 0;
    const realFetch = async () => { calls += 1; return calls < 2 ? r503() : ok(); };
    const fetch = nimGuardedFetch(BASE, realFetch);
    const res = await fetch(`${BASE}/chat/completions`, { method: "POST" });
    assert.equal(res.status, 200);
});

test("exhaustion returns an infra-labeled 429 naming the saturated lane", async () => {
    process.env.NIM_RETRY_WINDOW_MS = "1000";
    try {
        const realFetch = async () => r429();
        const fetch = nimGuardedFetch(BASE, realFetch);
        const res = await fetch(`${BASE}/chat/completions`, { method: "POST" });
        assert.equal(res.status, 429);
        const body = await res.text();
        assert.match(body, /saturated lane/);
        assert.match(body, /infra retries exhausted/);
    } finally {
        delete process.env.NIM_RETRY_WINDOW_MS;
    }
});

test("non-retryable statuses pass straight through without retry", async () => {
    let calls = 0;
    const realFetch = async () => { calls += 1; return new Response("bad", { status: 400 }); };
    const fetch = nimGuardedFetch(BASE, realFetch);
    const res = await fetch(`${BASE}/chat/completions`, { method: "POST" });
    assert.equal(res.status, 400);
    assert.equal(calls, 1);
});

test("non-matching urls pass straight through", async () => {
    let calls = 0;
    const realFetch = async () => { calls += 1; return r429(); };
    const fetch = nimGuardedFetch(BASE, realFetch);
    await fetch("https://other.test/v1/chat/completions", { method: "POST" });
    assert.equal(calls, 1);
});
