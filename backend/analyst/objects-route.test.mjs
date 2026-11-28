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
  const now = Date.now();
  const runs = [
    { question: "older question", answer: "older answer", tables: [{ title: "t" }], suggestions: [], created_at: new Date(now - 10000).toISOString(), run_id: "r1" },
    { question: "post-grant question", answer: "post-grant answer", tables: [], suggestions: [], created_at: new Date(now + 100000).toISOString(), run_id: "r2" },
  ];
  const data = {
    close: async () => {},
    call: async (op, args) => {
      if (op === "product_runs") {
        if (args.thread === "thread-owned") return { ok: true, runs };
        return { ok: true, runs: [] };
      }
      return { ok: true };
    },
  };
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
    for (const badTpe of [
      { kind: "trade_scenario", title: "t", payload: { ...trade, tpes: [{ team: "DAL" }] } },
      { kind: "trade_scenario", title: "t", payload: { ...trade, tpes: [{ team: "DAL", amount: 0 }] } },
      { kind: "trade_scenario", title: "t", payload: { ...trade, tpes: [{ team: "DAL", amount: 1000, bogus: 1 }] } },
    ]) {
      const response = await post("/api/objects", badTpe, { "x-dime-owner": owner });
      assert.equal(response.status, 422, JSON.stringify(badTpe));
    }
    const created = await post("/api/objects", { kind: "trade_scenario", title: "DAL/NYK construction", payload: { ...trade, tpes: [{ team: "DAL", amount: 10_000_000, kind: "ordinary", exactness: "scenario_derived" }] } }, { "x-dime-owner": owner });
    assert.equal(created.status, 201);
    const object = await created.json();
    assert.ok(object.object_id);
    const share = await fetch(`${url}/s/${object.read_token}`);
    assert.equal(share.status, 200);
    const shared = await share.json();
    assert.equal(shared.kind, "trade_scenario");
    assert.equal(shared.payload.legs.length, 2);
    assert.equal(shared.payload.season, "2026-27");
    assert.equal(shared.payload.tpes.length, 1);
    assert.equal(shared.payload.tpes[0].amount, 10_000_000);
    assert.equal(shared.payload.tpes[0].exactness, "scenario_derived");
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

    const grouped = {
      ...scenario,
      moves: scenario.moves.map((move, index) => ({ ...move, ...(index === 0 ? { group: "trade-abc123" } : {}) })),
      groups: { "trade-abc123": { partner: "NYK", verdict: true, evaluated_at: "2026-11-27T00:00:00.000Z" } },
    };
    const groupedMint = await post("/api/objects", { kind: "cap_scenario", title: "g", payload: grouped }, { "x-dime-owner": owner + "-grouped" });
    assert.equal(groupedMint.status, 201, "group-tagged moves + groups metadata validate");
    const groupedObject = await groupedMint.json();
    assert.deepEqual(groupedObject.payload.groups, grouped.groups, "groups metadata round-trips verbatim");

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
test("objects route contract: thread_grant stamping, ownership, immutability, transcript resolution", async () => {
  const { server, root } = fixture();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const owner = "client-grant-owner";
  const post = (path, payload, headers = {}) => fetch(url + path, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  const patch = (path, payload, headers = {}) => fetch(url + path, { method: "PATCH", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  try {
    const unowned = await post("/api/objects", { kind: "thread_grant", title: "t", payload: { thread: "thread-not-owned" } }, { "x-dime-owner": owner });
    assert.equal(unowned.status, 422);

    const noThread = await post("/api/objects", { kind: "thread_grant", title: "t", payload: {} }, { "x-dime-owner": owner });
    assert.equal(noThread.status, 422);

    const created = await post("/api/objects", {
      kind: "thread_grant",
      title: "shared analysis",
      payload: { thread: "thread-owned", owner: "attacker-injected", granted_before: "1999-01-01T00:00:00.000Z" },
    }, { "x-dime-owner": owner });
    assert.equal(created.status, 201);
    const object = await created.json();
    assert.equal(object.payload.thread, "thread-owned");
    assert.equal(object.payload.owner, owner);
    assert.ok(Date.parse(object.payload.granted_before) > Date.now() - 60000);

    const immutable = await patch(`/api/objects/${object.object_id}`, { payload: { thread: "thread-owned", owner, granted_before: object.payload.granted_before } }, { "x-owner-token": object.owner_token });
    assert.equal(immutable.status, 422);

    const share = await fetch(`${url}/s/${object.read_token}`);
    assert.equal(share.status, 200);
    const shared = await share.json();
    assert.equal(shared.kind, "thread_grant");
    assert.ok(!("owner" in shared.payload), "public payload must strip owner identity");
    assert.ok(Array.isArray(shared.transcript));
    assert.equal(shared.transcript.length, 1, "post-grant runs are excluded");
    assert.equal(shared.transcript[0].question, "older question");
    assert.equal(shared.transcript[0].answer, "older answer");
    assert.ok(!("run_id" in shared.transcript[0]), "run internals stripped");
    assert.ok(!("owner" in shared.transcript[0]), "owner stripped from transcript rows");

    const capShare = await post("/api/objects", { kind: "cap_scenario", title: "c", payload: scenario }, { "x-dime-owner": owner });
    const capObject = await capShare.json();
    const capShared = await (await fetch(`${url}/s/${capObject.read_token}`)).json();
    assert.equal(capShared.kind, "cap_scenario");
    assert.ok(!("transcript" in capShared), "non-grant kinds carry no transcript");
  }
  finally {
    server.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("objects route contract: cap_scenario persists typed mechanism signing inputs", async () => {
  const { server, root } = fixture();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const owner = "client-typed-cap-owner";
  const typed = {
    team: "BOS",
    season: "2026-27",
    exception_state: { ntmle_used: 10000000, operating_mode: "over_cap" },
    moves: [
      {
        kind: "signing",
        player: "Minimum Example",
        amount: 1357763,
        years: 2,
        mechanism: "minimum",
        years_of_service: 0,
        salary_schedule: [1357763, 2294370],
      },
      {
        kind: "signing",
        player: "Exception Example",
        amount: 4000000,
        years: 1,
        mechanism: "ntmle",
        unlikely_bonus: 0,
        prior_salary: 2500000,
        signing_date: "2026-07-06",
        exception_state: { ntmle_used: 10000000 },
      },
    ],
  };
  try {
    const created = await fetch(url + "/api/objects", {
      method: "POST",
      headers: { "content-type": "application/json", "x-dime-owner": owner },
      body: JSON.stringify({ kind: "cap_scenario", title: "Mechanism plan", payload: typed }),
    });
    assert.equal(created.status, 201);
    const object = await created.json();
    assert.deepEqual(object.payload, typed);
    const patched = await fetch(url + "/api/objects/" + object.object_id, {
      method: "PATCH",
      headers: { "content-type": "application/json", "x-owner-token": object.owner_token },
      body: JSON.stringify({ payload: { ...typed, title: "drift" } }),
    });
    assert.equal(patched.status, 422);
  }
  finally {
    server.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("objects route contract: board kind validates intent payload", async () => {
  const { server, root } = fixture();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const owner = "client-board-owner";
  const post = (path, payload, headers = {}) => fetch(url + path, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  const intent = {
    season: "2026-27",
    rows: [{ player_id: 1628369 }, { player_id: 1627759 }],
    columns: [{ metric_id: "ppg" }, { metric_id: "ts_pct" }],
    template_id: "scoring-guards",
  };
  try {
    for (const bad of [
      { kind: "board", title: "t" },
      { kind: "board", title: "t", payload: {} },
      { kind: "board", title: "t", payload: { ...intent, rows: [] } },
      { kind: "board", title: "t", payload: { ...intent, columns: [] } },
      { kind: "board", title: "t", payload: { ...intent, rows: [{}] } },
      { kind: "board", title: "t", payload: { ...intent, rows: [{ player_id: "abc" }] } },
      { kind: "board", title: "t", payload: { ...intent, columns: [{}] } },
      { kind: "board", title: "t", payload: { ...intent, cells: {} } },
      { kind: "board", title: "t", payload: { ...intent, extra: 1 } },
    ]) {
      const response = await post("/api/objects", bad, { "x-dime-owner": owner });
      assert.equal(response.status, 422, JSON.stringify(bad));
    }
    const created = await post("/api/objects", { kind: "board", title: "Scoring guards", payload: intent }, { "x-dime-owner": owner });
    assert.equal(created.status, 201);
    const object = await created.json();
    const share = await fetch(`${url}/s/${object.read_token}`);
    assert.equal(share.status, 200);
    const shared = await share.json();
    assert.equal(shared.kind, "board");
    assert.equal(shared.payload.rows.length, 2);
    assert.equal(shared.payload.columns.length, 2);
    assert.equal(shared.payload.cells, undefined, "cells never persist — evaluated output is re-computed at open time");
  }
  finally {
    server.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("objects route contract: board pins validate references and resolve in the share payload", async () => {
  const { server, root } = fixture();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const owner = "client-pin-owner";
  const post = (path, payload, headers = {}) => fetch(url + path, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  const intent = {
    season: "2026-27",
    rows: [{ player_id: 1628369 }],
    columns: [{ metric_id: "ppg" }],
  };
  try {
    const scenario = await post("/api/objects", { kind: "cap_scenario", title: "scenario", payload: { team: "BOS", season: "2026-27", moves: [{ kind: "waive", player: "Fixture Player" }] } }, { "x-dime-owner": owner });
    assert.equal(scenario.status, 201);
    const scenarioObject = await scenario.json();
    const otherOwnerScenario = await post("/api/objects", { kind: "cap_scenario", title: "alien", payload: { team: "BOS", season: "2026-27", moves: [{ kind: "waive", player: "Fixture Player" }] } }, { "x-dime-owner": "client-other-owner" });
    const alienObject = await otherOwnerScenario.json();
    const trade = await post("/api/objects", { kind: "trade_scenario", title: "trade", payload: { season: "2026-27", legs: [{ from: "BOS", to: "DAL", players: ["Fixture Player"] }] } }, { "x-dime-owner": owner });
    const tradeObject = await trade.json();

    for (const bad of [
      { kind: "board", title: "t", payload: { ...intent, pins: [{}] } },
      { kind: "board", title: "t", payload: { ...intent, pins: [{ kind: "cap_scenario" }] } },
      { kind: "board", title: "t", payload: { ...intent, pins: [{ kind: "cap_scenario", object_id: "x", extra: 1 }] } },
      { kind: "board", title: "t", payload: { ...intent, pins: [{ kind: "board", object_id: scenarioObject.object_id }] } },
      { kind: "board", title: "t", payload: { ...intent, pins: [{ kind: "cap_scenario", object_id: "obj-nonexistent" }] } },
      { kind: "board", title: "t", payload: { ...intent, pins: [{ kind: "trade_scenario", object_id: scenarioObject.object_id }] } },
      { kind: "board", title: "t", payload: { ...intent, pins: [{ kind: "cap_scenario", object_id: alienObject.object_id }] } },
    ]) {
      const response = await post("/api/objects", bad, { "x-dime-owner": owner });
      assert.equal(response.status, 422, JSON.stringify(bad));
    }

    const pinned = {
      ...intent,
      pins: [
        { kind: "cap_scenario", object_id: scenarioObject.object_id, note: "summer sheet" },
        { kind: "trade_scenario", object_id: tradeObject.object_id },
      ],
    };
    const created = await post("/api/objects", { kind: "board", title: "Pinned board", payload: pinned }, { "x-dime-owner": owner });
    assert.equal(created.status, 201);
    const object = await created.json();

    const share = await fetch(`${url}/s/${object.read_token}`);
    assert.equal(share.status, 200);
    const shared = await share.json();
    assert.equal(shared.kind, "board");
    assert.equal(shared.pins.length, 2);
    assert.equal(shared.pins[0].status, "ok");
    assert.equal(shared.pins[0].kind, "cap_scenario");
    assert.equal(shared.pins[0].title, "scenario");
    assert.equal(shared.pins[0].note, "summer sheet");
    assert.equal(shared.pins[0].payload.team, "BOS");
    assert.equal(shared.pins[1].kind, "trade_scenario");
    assert.equal(shared.pins[1].note, undefined);

    const patch = await fetch(`${url}/api/objects/${object.object_id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json", "x-owner-token": object.owner_token },
      body: JSON.stringify({ payload: { ...intent, pins: [{ kind: "cap_scenario", object_id: alienObject.object_id }] } }),
    });
    assert.equal(patch.status, 422, "cross-owner pin rejected on update too");
  }
  finally {
    server.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("objects route contract: archived pin targets resolve honestly in the share payload", async () => {
  const { server, root } = fixture();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const owner = "client-archive-pin-owner";
  const post = (path, payload, headers = {}) => fetch(url + path, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(payload) });
  const intent = { season: "2026-27", rows: [{ player_id: 1628369 }], columns: [{ metric_id: "ppg" }] };
  try {
    const scenario = await post("/api/objects", { kind: "cap_scenario", title: "doomed", payload: { team: "BOS", season: "2026-27", moves: [{ kind: "waive", player: "Fixture Player" }] } }, { "x-dime-owner": owner });
    const scenarioObject = await scenario.json();
    const board = await post("/api/objects", { kind: "board", title: "b", payload: { ...intent, pins: [{ kind: "cap_scenario", object_id: scenarioObject.object_id }] } }, { "x-dime-owner": owner });
    const boardObject = await board.json();
    const archive = await fetch(`${url}/api/objects/${scenarioObject.object_id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json", "x-owner-token": scenarioObject.owner_token },
      body: JSON.stringify({ archived: true }),
    });
    assert.equal(archive.status, 200);
    const share = await fetch(`${url}/s/${boardObject.read_token}`);
    const shared = await share.json();
    assert.equal(shared.pins.length, 1);
    assert.equal(shared.pins[0].status, "archived");
    assert.equal(shared.pins[0].payload, undefined, "archived pins do not expose payloads");
  }
  finally {
    server.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("artifact_ref mint captures a snapshot that survives run-store loss", async () => {
  const root = mkdtempSync(join(tmpdir(), "dime-objects-"));
  const env = {
    ...process.env,
    DIME_CONVERSATION_STORE: join(root, "chat.sqlite"),
    DIME_PROJECT_STORE: join(root, "projects.sqlite"),
    DIME_WORKSPACE_STORE: join(root, "workspaces.sqlite"),
    DIME_OBJECT_STORE: join(root, "objects.sqlite"),
    DIME_PI_SOURCES_DIR: join(root, "pi-sources"),
  };
  const runId = "run-" + "d".repeat(32);
  const owner = "client-snap-owner";
  const thread = "thread-snap";
  const { ProductStore } = await import("./dist/product-store.js");
  const store = new ProductStore(env.DIME_CONVERSATION_STORE, env.DIME_PI_SOURCES_DIR);
  store.append({ owner, thread }, "q", "a", runId);
  store.saveSources(runId, [{
    ref: "ref-1",
    callId: "call-1",
    tool: "sql_exec",
    response: {
      content: [],
      structuredContent: { rows: [{ player: "Snap Player", pts: 31 }], meta: { season: "2025-26" } },
    },
  }], [{
    ref: "ref-1",
    callId: "call-1",
    tool: "sql_exec",
    response: {
      content: [],
      structuredContent: { rows: [{ player: "Snap Player", pts: 31 }], meta: { season: "2025-26" } },
    },
  }], {
    blocks: [{ text: "answer" }],
    artifacts: [{ kind: "player_card", title: "Snap Player card", sources: [{ ref: "ref-1", rows: [0] }] }],
  });
  const data = { close: async () => {}, call: async () => ({ ok: true, runs: [] }) };
  const analyst = createAnalyst({ env, resolveModel: () => { throw new Error("No provider required"); }, saveChat: async () => {}, saveRun: async () => {} });
  const server = createProductServer({ env, data, analyst, manifest: {} });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const { rmSync: rm, unlinkSync } = await import("node:fs");
  try {
    const created = await fetch(`${url}/api/objects`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-dime-owner": owner },
      body: JSON.stringify({ kind: "artifact_ref", title: "snap card", payload: { run_id: runId, thread, artifact_index: 0 } }),
    });
    assert.equal(created.status, 201, await created.clone().text());
    const object = await created.json();
    const first = await (await fetch(`${url}/s/${object.read_token}`)).json();
    assert.equal(first.artifact.title, "Snap Player card");
    assert.equal(first.evidence.length, 1);
    assert.equal(first.evidence[0].rows[0].player, "Snap Player");
    unlinkSync(join(env.DIME_PI_SOURCES_DIR, runId + ".json"));
    const second = await (await fetch(`${url}/s/${object.read_token}`)).json();
    assert.equal(second.unavailable, undefined);
    assert.equal(second.artifact.title, "Snap Player card");
    assert.equal(second.evidence[0].rows[0].player, "Snap Player");
  } finally {
    server.close();
    rm(root, { recursive: true, force: true });
  }
});
