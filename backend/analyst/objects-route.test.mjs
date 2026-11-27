import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createAnalyst } from "./dist/analyst.js";
import { createProductServer } from "./dist/http.js";

const scenario = {
  team: "BOS",
  season: "2026-27",
  moves: [
    { kind: "waive", player: "Player One", stretch: true },
    { kind: "sign", label: "minimum signing", amount: 2300000 },
  ],
};

function fixture() {
  const root = mkdtempSync(join(tmpdir(), "dime-objects-"));
  const env = {
    ...process.env,
    DIME_CONVERSATION_STORE: join(root, "chat.sqlite"),
    DIME_PROJECT_STORE: join(root, "projects.sqlite"),
    DIME_WORKSPACE_STORE: join(root, "workspaces.sqlite"),
    DIME_OBJECT_STORE: join(root, "objects.sqlite"),
  };
  const data = { close: async () => {}, call: async () => ({ ok: true }) };
  const analyst = createAnalyst({ env, resolveModel: () => { throw new Error("No provider required"); }, saveChat: async () => {}, saveRun: async () => {} });
  const server = createProductServer({ env, data, analyst, manifest: {} });
  return { server, root };
}

test("objects route contract: trade_scenario kind validates legs payload", async () => {
  const { server, root } = fixture();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const owner = "client-trade-owner";
  const post = (path, payload, headers = {}) => fetch(url + path, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  const trade = {
    legs: [
      { from: "DAL", to: "NYK", players: "Player One, Player Two", picks: [{ year: 2027, round: 1 }] },
      { from: "NYK", to: "DAL", players: "Player Three" },
    ],
    season: "2026-27",
  };
  try {
    for (const bad of [
      { kind: "trade_scenario", title: "t" },
      { kind: "trade_scenario", title: "t", payload: {} },
      { kind: "trade_scenario", title: "t", payload: { legs: [], season: "2026-27" } },
      { kind: "trade_scenario", title: "t", payload: { legs: [{ from: "DAL" }], season: "2026-27" } },
      { kind: "trade_scenario", title: "t", payload: { ...trade, extra: 1 } },
      { kind: "trade_scenario", title: "t", payload: { legs: [{ ...trade.legs[0], bogus: 1 }], season: "2026-27" } },
    ]) {
      const response = await post("/api/objects", bad, { "x-dime-owner": owner });
      assert.equal(response.status, 422, JSON.stringify(bad));
    }
    const created = await post("/api/objects", { kind: "trade_scenario", title: "DAL/NYK construction", payload: trade }, { "x-dime-owner": owner });
    assert.equal(created.status, 201);
    const object = await created.json();
    assert.ok(object.object_id);
    const share = await fetch(`${url}/s/${object.read_token}`);
    assert.equal(share.status, 200);
    const shared = await share.json();
    assert.equal(shared.kind, "trade_scenario");
    assert.equal(shared.payload.legs.length, 2);
    assert.equal(shared.payload.season, "2026-27");
  }
  finally {
    server.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("objects route contract: create, ownership, update, share rotation, public read", async () => {
  const { server, root } = fixture();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const owner = "client-test-owner";
  const post = (path, payload, headers = {}) => fetch(url + path, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  const patch = (path, payload, headers = {}) => fetch(url + path, { method: "PATCH", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  try {
    const noOwner = await post("/api/objects", { kind: "cap_scenario", title: "t", payload: scenario });
    assert.equal(noOwner.status, 401);

    for (const bad of [
      {},
      { kind: "cap_scenario", title: "t" },
      { kind: "board", title: "t", payload: scenario },
      { kind: "cap_scenario", title: "", payload: scenario },
      { kind: "cap_scenario", title: "t", payload: {} },
      { kind: "cap_scenario", title: "t", payload: { ...scenario, moves: [] } },
      { kind: "cap_scenario", title: "t", payload: { ...scenario, moves: [{}] } },
      { kind: "cap_scenario", title: "t", payload: scenario, extra: 1 },
    ]) {
      const response = await post("/api/objects", bad, { "x-dime-owner": owner });
      assert.equal(response.status, 422, JSON.stringify(bad));
    }

    const created = await post("/api/objects", { kind: "cap_scenario", title: "Waiver wire plan", payload: scenario }, { "x-dime-owner": owner });
    assert.equal(created.status, 201);
    const object = await created.json();
    assert.match(object.object_id, /^obj-[a-f0-9]{32}$/);
    assert.equal(object.kind, "cap_scenario");
    assert.equal(object.title, "Waiver wire plan");
    assert.equal(object.schema_version, 1);
    assert.ok(object.read_token.length >= 32);
    assert.ok(object.owner_token.length >= 48);
    assert.notEqual(object.read_token, object.object_id);
    assert.notEqual(object.owner_token, object.read_token);
    assert.ok(object.created_at && object.updated_at);
    assert.deepEqual(object.payload, scenario);

    const id = object.object_id;

    const noToken = await fetch(url + "/api/objects/" + id);
    assert.equal(noToken.status, 401);
    const wrongToken = await fetch(url + "/api/objects/" + id, { headers: { "x-owner-token": "deadbeef".repeat(8) } });
    assert.equal(wrongToken.status, 403);
    const malformed = await fetch(url + "/api/objects/notanobject", { headers: { "x-owner-token": object.owner_token } });
    assert.equal(malformed.status, 422);

    const owned = await fetch(url + "/api/objects/" + id, { headers: { "x-owner-token": object.owner_token } });
    assert.equal(owned.status, 200);
    const record = await owned.json();
    assert.deepEqual(record.payload, scenario);
    assert.equal(record.owner_token_hash, undefined);
    assert.equal(record.owner_token, undefined);
    assert.equal(record.object_id, id);

    const listMine = await fetch(url + "/api/objects?kind=cap_scenario", { headers: { "x-dime-owner": owner } });
    assert.equal(listMine.status, 200);
    const mine = (await listMine.json()).objects;
    assert.equal(mine.length, 1);
    assert.equal(mine[0].object_id, id);
    assert.equal(mine[0].payload, undefined);
    assert.equal(mine[0].owner_token, undefined);
    assert.equal(mine[0].read_token, undefined);
    const listOther = await fetch(url + "/api/objects?kind=cap_scenario", { headers: { "x-dime-owner": "someone-else" } });
    assert.deepEqual((await listOther.json()).objects, []);
    const listNoOwner = await fetch(url + "/api/objects");
    assert.equal(listNoOwner.status, 401);

    const patchWrong = await patch("/api/objects/" + id, { title: "stolen" }, { "x-owner-token": "deadbeef".repeat(8) });
    assert.equal(patchWrong.status, 403);
    const patchBadPayload = await patch("/api/objects/" + id, { payload: { team: "BOS" } }, { "x-owner-token": object.owner_token });
    assert.equal(patchBadPayload.status, 422);
    const patched = await patch("/api/objects/" + id, { title: "Waiver plan v2", payload: { ...scenario, waiver_date: "2026-07-06" } }, { "x-owner-token": object.owner_token });
    assert.equal(patched.status, 200);
    const patchRecord = await patched.json();
    assert.equal(patchRecord.title, "Waiver plan v2");
    assert.deepEqual(patchRecord.payload.moves, scenario.moves);
    assert.equal(patchRecord.payload.waiver_date, "2026-07-06");
    assert.ok(Date.parse(patchRecord.updated_at) >= Date.parse(object.updated_at));

    const sharedBefore = await fetch(url + "/s/" + object.read_token);
    assert.equal(sharedBefore.status, 200);
    const sharedBody = await sharedBefore.json();
    assert.deepEqual(sharedBody.payload, patchRecord.payload);
    assert.equal(sharedBody.title, "Waiver plan v2");
    assert.equal(sharedBody.kind, "cap_scenario");
    assert.equal(sharedBody.owner, undefined);
    assert.equal(sharedBody.owner_token_hash, undefined);
    assert.equal(sharedBody.read_token, undefined);
    assert.equal(sharedBody.archived, false);

    const malformedShare = await fetch(url + "/s/x");
    assert.equal(malformedShare.status, 422);
    const unknownShare = await fetch(url + "/s/" + "a".repeat(40));
    assert.equal(unknownShare.status, 404);

    const rotated = await post("/api/objects/" + id + "/rotate-share", {}, { "x-owner-token": object.owner_token });
    assert.equal(rotated.status, 200);
    const rotation = await rotated.json();
    assert.ok(rotation.read_token.length >= 32);
    assert.notEqual(rotation.read_token, object.read_token);
    const staleShare = await fetch(url + "/s/" + object.read_token);
    assert.equal(staleShare.status, 404);
    const freshShare = await fetch(url + "/s/" + rotation.read_token);
    assert.equal(freshShare.status, 200);
    const rotateWrong = await post("/api/objects/" + id + "/rotate-share", {}, { "x-owner-token": "deadbeef".repeat(8) });
    assert.equal(rotateWrong.status, 403);

    const archived = await patch("/api/objects/" + id, { archived: true }, { "x-owner-token": object.owner_token });
    assert.equal(archived.status, 200);
    const archivedShare = await fetch(url + "/s/" + rotation.read_token);
    assert.equal((await archivedShare.json()).archived, true);

    const spec = await (await fetch(url + "/openapi.json")).json();
    for (const path of ["/api/objects", "/api/objects/{object_id}", "/api/objects/{object_id}/rotate-share", "/s/{read_token}"])
      assert.ok(spec.paths[path], `openapi missing ${path}`);

    console.log("Objects route contract: create validation, owner-token auth, metadata listing, patch, share rotation, archived flag and public read passed");
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    rmSync(root, { recursive: true, force: true });
  }
});
