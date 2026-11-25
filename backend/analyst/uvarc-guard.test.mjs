import assert from "node:assert/strict";
import { test } from "node:test";
import { uvarcGuardedFetch } from "./dist/pi-context.js";

const BASE = "https://relay.test/v1";
const res400 = (body) => new Response(body, { status: 400 });
const ok = () => new Response("ok", { status: 200 });

test("retries the relay 'messages' bug 400 and passes the response through", async () => {
    let calls = 0;
    const realFetch = async () => { calls += 1; return calls < 3 ? res400(`{"detail":"'messages'"}`) : ok(); };
    const fetch = uvarcGuardedFetch(BASE, realFetch);
    const res = await fetch(`${BASE}/chat/completions`, { method: "POST" });
    assert.equal(res.status, 200);
    assert.equal(calls, 3);
});

test("does not retry a real 400", async () => {
    let calls = 0;
    const realFetch = async () => { calls += 1; return res400(`{"detail":"bad request"}`); };
    const fetch = uvarcGuardedFetch(BASE, realFetch);
    const res = await fetch(`${BASE}/chat/completions`, { method: "POST" });
    assert.equal(res.status, 400);
    assert.equal(calls, 1);
});

test("non-matching urls pass straight through", async () => {
    let calls = 0;
    const realFetch = async () => { calls += 1; return res400(`{"detail":"'messages'"}`); };
    const fetch = uvarcGuardedFetch(BASE, realFetch);
    await fetch("https://other.test/v1/chat/completions", { method: "POST" });
    assert.equal(calls, 1);
});

test("null message content is rewritten to an empty string before sending", async () => {
    const bodies = [];
    const realFetch = async (_url, init) => { bodies.push(init.body); return ok(); };
    const fetch = uvarcGuardedFetch(BASE, realFetch);
    const payload = { model: "m", messages: [
        { role: "user", content: null },
        { role: "assistant", content: [null, { type: "text", text: "kept" }] },
        { role: "user", content: "fine" },
    ] };
    await fetch(`${BASE}/chat/completions`, { method: "POST", body: JSON.stringify(payload) });
    const sent = JSON.parse(bodies[0]);
    assert.equal(sent.messages[0].content, "");
    assert.deepEqual(sent.messages[1].content, [{ type: "text", text: "kept" }]);
    assert.equal(sent.messages[2].content, "fine");
});

test("clean payloads pass through byte-identical", async () => {
    const bodies = [];
    const realFetch = async (_url, init) => { bodies.push(init.body); return ok(); };
    const fetch = uvarcGuardedFetch(BASE, realFetch);
    const body = JSON.stringify({ model: "m", messages: [{ role: "user", content: "hi" }] });
    await fetch(`${BASE}/chat/completions`, { method: "POST", body });
    assert.equal(bodies[0], body);
});

test("caps in-flight requests at four", async () => {
    let inFlight = 0;
    let peak = 0;
    const realFetch = async () => {
        inFlight += 1;
        peak = Math.max(peak, inFlight);
        await new Promise(r => setTimeout(r, 20));
        inFlight -= 1;
        return ok();
    };
    const fetch = uvarcGuardedFetch(BASE, realFetch);
    await Promise.all(Array.from({ length: 12 }, () => fetch(`${BASE}/chat/completions`, { method: "POST" })));
    assert.ok(peak <= 4, `peak ${peak}`);
});
