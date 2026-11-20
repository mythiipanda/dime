import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createAnalyst } from "./dist/analyst.js";
import { createProductServer } from "./dist/http.js";

test("Boards route contract: registry, typed dispatch, bounds, failures and OpenAPI", async () => {
  const root = mkdtempSync(join(tmpdir(), "dime-boards-"));
  const env = { ...process.env, DIME_CONVERSATION_STORE: join(root, "chat.sqlite"), DIME_PROJECT_STORE: join(root, "projects.sqlite"), DIME_WORKSPACE_STORE: join(root, "workspaces.sqlite") };
  const calls = [];
  const data = { close: async () => {}, call: async (name, args) => {
    calls.push({ name, args });
    if (name === "product_board_metrics") return { ok: true, metrics: [{ id: "ppg" }] };
    if (args.payload.season === "2099-00") return { ok: false, status: 503, error: "Boards warehouse unavailable" };
    if (args.payload.metric_id === "unknown") return { ok: false, status: 422, error: "unknown_metric" };
    return { ok: true, cells: {}, players: {}, ...(name === "product_board_seed" ? { player_ids: [] } : {}) };
  } };
  const analyst = createAnalyst({ env, resolveModel: () => { throw new Error("No provider required"); }, saveChat: async () => {}, saveRun: async () => {} });
  const server = createProductServer({ env, data, analyst, manifest: {} });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const post = (path, payload) => fetch(url + "/api/boards/" + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
  try {
    const metrics = await fetch(url + "/api/boards/metrics");
    assert.equal(metrics.status, 200);
    assert.deepEqual((await metrics.json()).metrics, [{ id: "ppg" }]);
    assert.deepEqual(calls.pop(), { name: "product_board_metrics", args: {} });
    const payload = { season: "2025-26", player_ids: [201939], metric_ids: ["ppg"] };
    const filled = await post("fill", payload);
    assert.equal(filled.status, 200);
    assert.deepEqual(await filled.json(), { ok: true, cells: {}, players: {} });
    assert.deepEqual(calls.pop(), { name: "product_board_fill", args: { payload } });
    assert.deepEqual(await (await post("fill", { player_ids: [], metric_ids: [] })).json(), { ok: true, cells: {}, players: {} });
    assert.deepEqual(calls.pop().args.payload, { player_ids: [], metric_ids: [] });
    assert.equal((await post("seed", { metric_id: "ppg", n: 10, min_gp: 20, min_mpg: 15 })).status, 200);
    assert.equal(calls.pop().name, "product_board_seed");
    const before = calls.length;
    for (const bad of [{}, { ...payload, season: "bad" }, { ...payload, player_ids: ["1"] }, { ...payload, player_ids: [true] }, { ...payload, player_ids: [1.5] }, { ...payload, player_ids: Array(51).fill(1) }, { ...payload, metric_ids: Array(31).fill("ppg") }, { ...payload, extra: 1 }]) assert.equal((await post("fill", bad)).status, 422);
    for (const bad of [{ metric_id: "ppg", n: 26 }, { metric_id: "ppg", min_mpg: -1 }, { metric_id: "ppg", min_gp: 2.5 }]) assert.equal((await post("seed", bad)).status, 422);
    assert.equal(calls.length, before);
    assert.equal((await post("seed", { metric_id: "unknown" })).status, 422);
    const unavailable = await post("fill", { ...payload, season: "2099-00" });
    assert.equal(unavailable.status, 503);
    assert.equal((await unavailable.json()).detail, "Boards warehouse unavailable");
    const spec = await (await fetch(url + "/openapi.json")).json();
    for (const path of ["metrics", "fill", "seed"]) assert.ok(spec.paths["/api/boards/" + path]);
    assert.equal(spec.components.schemas.BoardFillBody.properties.player_ids.maxItems, 50);
    console.log("Boards route contracts: registry, fill/seed dispatch, empty values, validation, 422/503 errors and OpenAPI passed");
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); rmSync(root, { recursive: true, force: true }); }
});
