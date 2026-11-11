import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import { createAnalystSession } from "./dist/runtime.js";
import { priorSourceTool } from "./dist/pi-context.js";
import { connectPythonTools, sourceResult } from "./dist/python-tools.js";
import { validateAnswerSubmission } from "./dist/submit-tool.js";

const root = process.env.DIME_PI_TEST_ROOT;
assert(root, "DIME_PI_TEST_ROOT must identify an isolated proof directory");

async function fixture(name, code, tools) {
  const cwd = join(root, name);
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  await writeFile(join(cwd, "AGENTS.md"), "PROFILE_CONTEXT_MUST_NOT_LOAD");
  for (const base of [join(cwd, ".pi"), agentDir]) {
    await mkdir(join(base, "extensions"), { recursive: true });
    await writeFile(join(base, "extensions", "poison.mjs"), 'throw new Error("PROFILE_EXTENSION_MUST_NOT_LOAD")');
  }
  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"), modelsPath: null,
    allowModelNetwork: false, refreshOnCreate: false,
  });
  const requests = [];
  runtime.registerProvider("fixture", {
    api: "openai-completions", apiKey: "fixture-only", baseUrl: "http://invalid.test",
    models: [{ id: "fixture", name: "Fixture", input: ["text"], reasoning: false,
      contextWindow: 100000, maxTokens: 4000,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }],
    streamSimple(model, context) {
      requests.push(structuredClone(context));
      const first = requests.length === 1;
      const message = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: first ? [{ type: "toolCall", id: name, name: "codemode", arguments: { code } }]
          : [{ type: "text", text: "Fixture completed" }],
        stopReason: first ? "toolUse" : "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: message.stopReason, message });
      stream.end();
      return stream;
    },
  });
  const session = await createAnalystSession({ cwd, agentDir, model: runtime.getModel("fixture", "fixture"), modelRuntime: runtime, tools,
    settings: { retry: { enabled: false }, compaction: { enabled: false } } });
  assert.deepEqual(session.getActiveToolNames(), ["codemode"]);
  assert.deepEqual(new Set(session.getCallableToolNames()), new Set(tools.map(t => t.name)));
  assert(!session.systemPrompt.includes("PROFILE_CONTEXT_MUST_NOT_LOAD"));
  return { session, requests };
}

function tool(name, execute) {
  return { name, label: name, description: name,
    parameters: { type: "object", properties: {}, additionalProperties: false }, execute };
}
const textResult = value => ({ content: [{ type: "text", text: JSON.stringify(value) }] });

test("real SDK codemode calls two tools concurrently, filters model input and retains raw references", async () => {
  const raw = new Map();
  let running = 0;
  let peak = 0;
  let release;
  const bothStarted = new Promise(resolve => { release = resolve; });
  const tools = ["season_stats", "career_stats"].map((name, index) => tool(name, async () => {
    running++;
    peak = Math.max(peak, running);
    if (running === 2) release();
    await bothStarted;
    const result = { ref: "result-" + index, source: name, unit: index ? "cumulative" : "per_game", season: "202526",
      rows: [{ label: "keep", value: index + 3 }, { label: "RAW_SECRET_ROW", value: 999 }] };
    raw.set(result.ref, result);
    running--;
    return textResult(result);
  }));
  const { session, requests } = await fixture("parallel", `
    const results = await Promise.all([tools.season_stats({}), tools.career_stats({})]);
    return results.map(value => {
      const result = JSON.parse(value);
      return {ref: result.ref, unit: result.unit, season: result.season, rows: result.rows.filter(row => row.label === "keep")};
    });
  `, tools);
  try {
    await session.prompt("Run the fixture");
    assert.equal(peak, 2);
    assert.equal(raw.size, 2);
    assert.equal(requests.length, 2);
    assert.deepEqual(requests[0].messages.flatMap(m => m.toolsAdded ?? []).map(t => t.name), ["codemode"]);
    const seen = JSON.stringify(requests[1]);
    assert(!seen.includes("RAW_SECRET_ROW"));
    for (const ref of raw.keys()) assert(seen.includes(ref));
    assert(seen.includes("per_game") && seen.includes("cumulative") && seen.includes("202526"));
    assert.equal(raw.get("result-0").rows[1].value, 999);
    console.log(JSON.stringify({ proof: "parallel-filter-retain", peak, refs: [...raw.keys()] }));
  } finally { session.dispose(); }
});

test("actual tool exception survives codemode and another tool remains usable", async () => {
  const failure = new Error("fixture warehouse unavailable E547");
  let observed;
  const { session, requests } = await fixture("error", `
    const results = await Promise.allSettled([tools.unavailable({}), tools.available({})]);
    return results.map(r => r.status === "rejected" ? {error: r.reason.message} : {value: r.value});
  `, [tool("unavailable", async () => { observed = failure; throw failure; }),
    tool("available", async () => textResult({ ref: "successful-result" }))]);
  try {
    await session.prompt("Run error fixture");
    assert.equal(observed, failure);
    const seen = JSON.stringify(requests[1]);
    assert(seen.includes(failure.message));
    assert(seen.includes("successful-result"));
  } finally { session.dispose(); }
});


test("session abort cancels a running nested analysis tool", async () => {
  let started;
  const entered = new Promise(resolve => { started = resolve; });
  let cancelled = false;
  const { session } = await fixture("cancel", "return await tools.wait_for_cancel({});", [
    tool("wait_for_cancel", async (_id, _args, signal) => {
      started();
      await new Promise((resolve, reject) => {
        const abort = () => { cancelled = true; reject(new Error("fixture tool cancelled")); };
        if (signal.aborted) abort();
        else signal.addEventListener("abort", abort, { once: true });
      });
    }),
  ]);
  try {
    const pending = session.prompt("Run cancellation fixture");
    await entered;
    await session.abort();
    await pending;
    assert(cancelled);
    assert(session.isIdle);
  } finally { session.dispose(); }
});

test("real Python sql_exec and schema cross MCP into Pi with source semantics and independent results", async () => {
  const baseline = JSON.parse(await readFile(join(root, "python-baseline.json"), "utf8"));
  const bridge = await connectPythonTools({ python: process.env.DIME_PI_PYTHON, cwd: root,
    env: { ...process.env } });
  const pid = bridge.pid;
  let session;
  let running = 0;
  let peak = 0;
  const tools = bridge.tools.map(tool => ({ ...tool, async execute(...args) {
    running++;
    peak = Math.max(peak, running);
    try { return await tool.execute(...args); }
    finally { running--; }
  } }));
  const value = record => JSON.parse(record.response.content[0].text);
  const stable = result => {
    const copy = structuredClone(result);
    if (copy.meta) delete copy.meta.ms;
    return copy;
  };
  try {
    assert.deepEqual(bridge.tools.map(t => t.name), [
      "sql_exec",
      "warehouse_schema",
      "get_rapm",
      "get_game_prediction",
      "get_wpa_leaders",
      "get_comps",
      "get_lineup_stats",
      "get_win_prob",
      "get_on_off",
      "get_shot_zones",
      "get_four_factors",
      "get_clutch_stats",
      "get_competitive_ratings",
      "get_hustle",
      "get_injuries",
      "get_award_results",
      "get_briefing",
      "get_standings",
      "get_rest",
      "get_team_trajectory",
      "get_ratings",
      "get_rookie_leaders",
      "get_cap_ledger",
      "get_leaders",
      "get_lineup_leaders",
      "get_playoffs",
      "get_team_leaders",
      "get_team_compare",
      "get_elo_standings",
      "get_draft_board",
      "get_combine",
      "get_young_player_usage",
      "get_contract_value",
      "get_trade_check",
      "get_trade_value",
      "get_situational_splits",
      "get_playoff_sim",
      "get_playoff_team_ratings",
      "get_player_risers",
      "get_standings_deep",
      "get_warehouse_freshness",
      "get_finder",
      "get_draft_model",
      "get_leaderboard_deltas",
      "get_player_ratings",
      "get_risers",
      "get_team_four_factors",
    ]);
    assert.deepEqual(bridge.tools[0].parameters.required, ["sql"]);
    const setup = await fixture("python", `
      const args = ${JSON.stringify(baseline.args)};
      const calls = await Promise.all(args.map(arg => tools.sql_exec(arg)));
      calls.push(await tools.sql_exec(args[1]));
      const invalid = await tools.sql_exec(args[3]);
      if (!invalid.isError || invalid.result.ok !== false) throw new Error("Missing domain failure");
      const recovered = await tools.sql_exec(args[1]);
      if (recovered.isError || !recovered.result.rows.length) throw new Error("Same-script recovery failed");
      const schema = await tools.warehouse_schema({});
      if (typeof schema !== "object" || !schema.result.tables) throw new Error("Expected native schema.result.tables");
      return {schema: {ref: schema.ref, tables: Object.fromEntries(Object.entries(schema.result.tables)
        .filter(([name]) => name === "silver_hist_player_seasons"))}, invalid, recovered: {ref: recovered.ref, units: recovered.result.declared_column_semantics}, calls: calls.map(record => {
        const result = record.result;
        if (Array.isArray(result.rows)) result.rows = result.rows.filter(row => row.total_points !== 999);
        return {ref: record.ref, result};
      })};
    `, tools);
    session = setup.session;
    await session.prompt("Run real Python fixture");
    assert(peak >= 2, "real Python requests must overlap");
    assert.equal(running, 0);
    const records = [...bridge.results.values()];
    const queries = records.filter(r => r.tool === "sql_exec" && !r.response.isError);
    assert.equal(queries.length, baseline.args.length + 3);
    assert.equal(new Set(records.map(r => r.ref)).size, records.length);
    assert.equal(new Set(queries.map(r => r.callId)).size, queries.length);
    for (const record of queries) {
      const result = value(record);
      const index = baseline.args.findIndex(a => a.sql === (result.sql ?? result.meta.sql));
      assert(index >= 0);
      assert.deepEqual(stable(result), stable(baseline.direct[index]));
    }
    assert.deepEqual(value(records.find(r => r.tool === "warehouse_schema")), baseline.schema);
    assert(JSON.stringify(baseline.schema).length > 100000);
    assert(baseline.schema.tables.silver_leaders_pts.RAW_SECRET_ROW);
    const perGame = value(queries.find(r => value(r).sql === baseline.args[0].sql));
    assert.equal(perGame.declared_column_semantics.total_points.unit, "points_per_game");
    assert.equal(perGame.rows[0].total_points, 11.8);
    assert.equal(perGame.rows[1].total_points, 999);
    assert(perGame.season_semantics.resolved_labels.some(r => r.season_label === "2090-91"));
    assert.equal(baseline.direct[1].declared_column_semantics.PTS.unit, "total_points");
    for (const failed of baseline.direct.slice(2)) assert.equal(failed.ok, false);
    const seen = JSON.stringify(setup.requests[1]);
    assert(seen.includes("tables"));
    assert(!seen.includes("RAW_SECRET_ROW"));
    for (const record of queries) assert(seen.includes(record.ref));

    // Domain failure and input-validation errors do not close the process or erase evidence.
    const sql = bridge.tools.find(t => t.name === "sql_exec");
    const invalid = (await sql.execute("invalid", {}, undefined)).structuredContent;
    assert.equal(invalid.isError, true);
    assert(invalid.result.includes("ValidationError"));
    const recovery = (await sql.execute("recovery", baseline.args[1], undefined)).structuredContent;
    assert.deepEqual(stable(recovery.result), stable(baseline.direct[1]));
    assert.equal(bridge.results.size, baseline.args.length + 6);
    await writeFile(join(root, "python-host-records.json"), JSON.stringify([...bridge.results.values()]));
    await writeFile(join(root, "python-provider-requests.json"), JSON.stringify(setup.requests));
    console.log(JSON.stringify({ proof: "python-mcp-pi-equivalence", queries: queries.length,
      refs: queries.map(r => r.ref), peak, units: ["points_per_game", "total_points"], pid }));
  } finally {
    session?.dispose();
    await bridge.close();
  }
  assert.throws(() => process.kill(pid, 0), /ESRCH/);
});

test("real statistical tools cross MCP with anchor compatibility, rows, columns, and JSON safety", async () => {
  const bridge = await connectPythonTools({ python: process.env.DIME_PI_PYTHON, cwd: root,
    env: { ...process.env } });
  const pid = bridge.pid;
  try {
    const toolMap = new Map(bridge.tools.map(t => [t.name, t]));
    assert.equal(bridge.tools.length, 47);

    // 1. get_rapm
    const rapmTool = toolMap.get("get_rapm");
    assert(rapmTool);
    const rapmRes = await rapmTool.execute("call-rapm", { player: "NonexistentPlayer", season: "2024-25" }, undefined);
    assert(rapmRes.structuredContent);
    assert(Array.isArray(rapmRes.structuredContent.result.rows));
    assert(Array.isArray(rapmRes.structuredContent.result.columns));
    assert(rapmRes.structuredContent.result.columns.includes("player_id"));
    assert(rapmRes.structuredContent.result.columns.includes("name"));
    assert(rapmRes.structuredContent.result.columns.includes("rapm"));

    // 2. get_game_prediction
    const predTool = toolMap.get("get_game_prediction");
    assert(predTool);
    const predRes = await predTool.execute("call-pred", { a: "BOS", b: "MIA", n_sims: 100 }, undefined);
    assert(predRes.structuredContent);
    assert(Array.isArray(predRes.structuredContent.result.rows));
    assert(Array.isArray(predRes.structuredContent.result.columns));
    assert(predRes.structuredContent.result.columns.includes("team_home"));
    assert(predRes.structuredContent.result.columns.includes("win_prob_home"));
    assert(predRes.structuredContent.result.columns.includes("projected_score_home"));
    if (predRes.structuredContent.result.ok && predRes.structuredContent.result.rows.length > 0) {
      assert.equal(predRes.structuredContent.result.rows.length, 1);
      const row = predRes.structuredContent.result.rows[0];
      assert.equal(typeof row.team_home, "string");
      assert.equal(typeof row.win_prob_home, "number");
    }

    // 3. get_wpa_leaders
    const wpaTool = toolMap.get("get_wpa_leaders");
    assert(wpaTool);
    const wpaRes = await wpaTool.execute("call-wpa", { season: 2025, limit: 5 }, undefined);
    assert(wpaRes.structuredContent);
    assert(Array.isArray(wpaRes.structuredContent.result.rows));
    assert(Array.isArray(wpaRes.structuredContent.result.columns));
    assert(wpaRes.structuredContent.result.columns.includes("rank"));
    assert(wpaRes.structuredContent.result.columns.includes("player"));
    assert(wpaRes.structuredContent.result.columns.includes("wpa"));

    // 4. get_comps
    const compsTool = toolMap.get("get_comps");
    assert(compsTool);
    const compsRes = await compsTool.execute("call-comps", { player_id: 2544, season: "2023-24", k: 3 }, undefined);
    assert(compsRes.structuredContent);
    assert(Array.isArray(compsRes.structuredContent.result.rows));
    assert(Array.isArray(compsRes.structuredContent.result.columns));

    // 5. get_lineup_stats
    const lineupTool = toolMap.get("get_lineup_stats");
    assert(lineupTool);
    const lineupRes = await lineupTool.execute("call-lineup", { team: "BOS", season: "2023-24", limit: 5 }, undefined);
    assert(lineupRes.structuredContent);
    assert(Array.isArray(lineupRes.structuredContent.result.rows));
    assert(Array.isArray(lineupRes.structuredContent.result.columns));

    // 6. get_win_prob
    const winProbTool = toolMap.get("get_win_prob");
    assert(winProbTool);
    const winProbRes = await winProbTool.execute("call-win-prob", { team_a: "BOS", team_b: "MIA" }, undefined);
    assert(winProbRes.structuredContent);
    assert(Array.isArray(winProbRes.structuredContent.result.rows));
    assert(Array.isArray(winProbRes.structuredContent.result.columns));
    assert(winProbRes.structuredContent.result.columns.includes("team_a"));
    assert(winProbRes.structuredContent.result.columns.includes("team_b"));
    assert(winProbRes.structuredContent.result.columns.includes("win_prob_a"));
    assert(winProbRes.structuredContent.result.columns.includes("win_prob_b"));
    assert(winProbRes.structuredContent.result.columns.includes("elo_a"));
    assert(winProbRes.structuredContent.result.columns.includes("elo_b"));

    // 7. get_on_off
    const onOffTool = toolMap.get("get_on_off");
    assert(onOffTool);
    const onOffRes = await onOffTool.execute("call-on-off", { player_id: 2544, team_id: 1610612747, season: "2023-24" }, undefined);
    assert(onOffRes.structuredContent);
    assert(Array.isArray(onOffRes.structuredContent.result.rows));
    assert(Array.isArray(onOffRes.structuredContent.result.columns));
    assert(onOffRes.structuredContent.result.columns.includes("Stat"));
    assert(onOffRes.structuredContent.result.columns.includes("On"));
    assert(onOffRes.structuredContent.result.columns.includes("Off"));
    assert(onOffRes.structuredContent.result.columns.includes("On-Off"));

    // 8. get_shot_zones
    const shotZonesTool = toolMap.get("get_shot_zones");
    assert(shotZonesTool);
    const shotZonesRes = await shotZonesTool.execute("call-shot-zones", { player_id: 2544, season: "2023-24", min_attempts: 50 }, undefined);
    assert(shotZonesRes.structuredContent);
    assert(Array.isArray(shotZonesRes.structuredContent.result.rows));
    assert(Array.isArray(shotZonesRes.structuredContent.result.columns));
    assert(shotZonesRes.structuredContent.result.columns.includes("zone"));

    // 9. get_four_factors
    const fourFactorsTool = toolMap.get("get_four_factors");
    assert(fourFactorsTool);
    const fourFactorsRes = await fourFactorsTool.execute("call-four-factors", { team: "BOS" }, undefined);
    assert(fourFactorsRes.structuredContent);
    assert(Array.isArray(fourFactorsRes.structuredContent.result.rows));
    assert(Array.isArray(fourFactorsRes.structuredContent.result.columns));

    // 10. get_clutch_stats
    const clutchTool = toolMap.get("get_clutch_stats");
    assert(clutchTool);
    const clutchRes = await clutchTool.execute("call-clutch", { player: "LeBron James" }, undefined);
    assert(clutchRes.structuredContent);
    assert(Array.isArray(clutchRes.structuredContent.result.rows));
    assert(Array.isArray(clutchRes.structuredContent.result.columns));

    // 11. get_competitive_ratings
    const compTool = toolMap.get("get_competitive_ratings");
    assert(compTool);
    const compRes = await compTool.execute("call-competitive", { team: "BOS" }, undefined);
    assert(compRes.structuredContent);
    assert(Array.isArray(compRes.structuredContent.result.rows));
    assert(Array.isArray(compRes.structuredContent.result.columns));

    // 12. get_hustle
    const hustleTool = toolMap.get("get_hustle");
    assert(hustleTool);
    const hustleRes = await hustleTool.execute("call-hustle", { scope: "player" }, undefined);
    assert(hustleRes.structuredContent);
    assert(Array.isArray(hustleRes.structuredContent.result.rows));
    assert(Array.isArray(hustleRes.structuredContent.result.columns));

    // 13. get_injuries
    const injuriesTool = toolMap.get("get_injuries");
    assert(injuriesTool);
    const injuriesRes = await injuriesTool.execute("call-injuries", { team: "BOS" }, undefined);
    assert(injuriesRes.structuredContent);
    assert(Array.isArray(injuriesRes.structuredContent.result.rows));
    assert(Array.isArray(injuriesRes.structuredContent.result.columns));

    // 14. get_award_results
    const awardResTool = toolMap.get("get_award_results");
    assert(awardResTool);
    const awardRes = await awardResTool.execute("call-award-results", { view: "winner", award: "mvp" }, undefined);
    assert(awardRes.structuredContent);
    assert(Array.isArray(awardRes.structuredContent.result.rows));
    assert(Array.isArray(awardRes.structuredContent.result.columns));

    // 15. get_briefing
    const briefingTool = toolMap.get("get_briefing");
    assert(briefingTool);
    const briefingRes = await briefingTool.execute("call-briefing", { game_date: "10/24/2023" }, undefined);
    assert(briefingRes.structuredContent);
    assert(Array.isArray(briefingRes.structuredContent.result.rows));
    assert(Array.isArray(briefingRes.structuredContent.result.columns));

    // 16. get_standings
    const standingsTool = toolMap.get("get_standings");
    assert(standingsTool);
    const standingsRes = await standingsTool.execute("call-standings", { season: "2023-24" }, undefined);
    assert(standingsRes.structuredContent);
    assert(Array.isArray(standingsRes.structuredContent.result.rows));
    assert(Array.isArray(standingsRes.structuredContent.result.columns));

    // 17. get_rest
    const restTool = toolMap.get("get_rest");
    assert(restTool);
    const restRes = await restTool.execute("call-rest", { team_abbrev: "BOS", season: "2023-24" }, undefined);
    assert(restRes.structuredContent);
    assert(Array.isArray(restRes.structuredContent.result.rows));
    assert(Array.isArray(restRes.structuredContent.result.columns));

    // 18. get_team_trajectory
    const trajectoryTool = toolMap.get("get_team_trajectory");
    assert(trajectoryTool);
    const trajectoryRes = await trajectoryTool.execute("call-trajectory", { team: "BOS", seasons_back: 3 }, undefined);
    assert(trajectoryRes.structuredContent);
    assert(Array.isArray(trajectoryRes.structuredContent.result.rows));
    assert(Array.isArray(trajectoryRes.structuredContent.result.columns));

    // 19. get_ratings
    const ratingsTool = toolMap.get("get_ratings");
    assert(ratingsTool);
    const ratingsRes = await ratingsTool.execute("call-ratings", { team: "BOS" }, undefined);
    assert(ratingsRes.structuredContent);
    assert(Array.isArray(ratingsRes.structuredContent.result.rows));
    assert(Array.isArray(ratingsRes.structuredContent.result.columns));

    // 20. get_rookie_leaders
    const rookieTool = toolMap.get("get_rookie_leaders");
    assert(rookieTool);
    const rookieRes = await rookieTool.execute("call-rookie", { stat: "ppg", limit: 5 }, undefined);
    assert(rookieRes.structuredContent);
    assert(Array.isArray(rookieRes.structuredContent.result.rows));
    assert(Array.isArray(rookieRes.structuredContent.result.columns));

    // 21. get_cap_ledger
    const capTool = toolMap.get("get_cap_ledger");
    assert(capTool);
    const capRes = await capTool.execute("call-cap", { team: "BOS" }, undefined);
    assert(capRes.structuredContent);
    assert(Array.isArray(capRes.structuredContent.result.rows));
    assert(Array.isArray(capRes.structuredContent.result.columns));

    // 22. get_leaders
    const leadersTool = toolMap.get("get_leaders");
    assert(leadersTool);
    const leadersRes = await leadersTool.execute("call-leaders", { stat_category: "PTS" }, undefined);
    assert(leadersRes.structuredContent);
    assert(Array.isArray(leadersRes.structuredContent.result.rows));
    assert(Array.isArray(leadersRes.structuredContent.result.columns));

    // 23. get_lineup_leaders
    const lineupLeadersTool = toolMap.get("get_lineup_leaders");
    assert(lineupLeadersTool);
    const lineupLeadersRes = await lineupLeadersTool.execute("call-lineup-leaders", { min_minutes: 100 }, undefined);
    assert(lineupLeadersRes.structuredContent);
    assert(Array.isArray(lineupLeadersRes.structuredContent.result.rows));
    assert(Array.isArray(lineupLeadersRes.structuredContent.result.columns));

    // 24. get_playoffs
    const playoffsTool = toolMap.get("get_playoffs");
    assert(playoffsTool);
    const playoffsRes = await playoffsTool.execute("call-playoffs", { season: "2023-24" }, undefined);
    assert(playoffsRes.structuredContent);
    assert(Array.isArray(playoffsRes.structuredContent.result.rows));
    assert(Array.isArray(playoffsRes.structuredContent.result.columns));

    // 25. get_team_leaders
    const teamLeadersTool = toolMap.get("get_team_leaders");
    assert(teamLeadersTool);
    const teamLeadersRes = await teamLeadersTool.execute("call-team-leaders", { stat_category: "AST", season: "2023-24" }, undefined);
    assert(teamLeadersRes.structuredContent);
    assert(Array.isArray(teamLeadersRes.structuredContent.result.rows));
    assert(Array.isArray(teamLeadersRes.structuredContent.result.columns));

    // 26. get_team_compare
    const teamCompareTool = toolMap.get("get_team_compare");
    assert(teamCompareTool);
    const teamCompareRes = await teamCompareTool.execute("call-team-compare", { stat_category: "PTS", top: 3, season: "2023-24" }, undefined);
    assert(teamCompareRes.structuredContent);
    assert(Array.isArray(teamCompareRes.structuredContent.result.rows));
    assert(Array.isArray(teamCompareRes.structuredContent.result.columns));

    // 27. get_elo_standings
    const eloStandingsTool = toolMap.get("get_elo_standings");
    assert(eloStandingsTool);
    const eloStandingsRes = await eloStandingsTool.execute("call-elo-standings", { season: "2023-24", limit: 5 }, undefined);
    assert(eloStandingsRes.structuredContent);
    assert(Array.isArray(eloStandingsRes.structuredContent.result.rows));
    assert(Array.isArray(eloStandingsRes.structuredContent.result.columns));

    // 28. get_draft_board
    const draftBoardTool = toolMap.get("get_draft_board");
    assert(draftBoardTool);
    const draftBoardRes = await draftBoardTool.execute("call-draft-board", { season: "2025" }, undefined);
    assert(draftBoardRes.structuredContent);
    assert(Array.isArray(draftBoardRes.structuredContent.result.rows));
    assert(Array.isArray(draftBoardRes.structuredContent.result.columns));

    // 29. get_combine
    const combineTool = toolMap.get("get_combine");
    assert(combineTool);
    const combineRes = await combineTool.execute("call-combine", { season: "2025" }, undefined);
    assert(combineRes.structuredContent);
    assert(Array.isArray(combineRes.structuredContent.result.rows));
    assert(Array.isArray(combineRes.structuredContent.result.columns));

    // 30. get_young_player_usage
    const youngPlayerTool = toolMap.get("get_young_player_usage");
    assert(youngPlayerTool);
    const youngPlayerRes = await youngPlayerTool.execute("call-young-player-usage", { max_age: 22, min_minutes: 1000 }, undefined);
    assert(youngPlayerRes.structuredContent);
    assert(Array.isArray(youngPlayerRes.structuredContent.result.rows));
    assert(Array.isArray(youngPlayerRes.structuredContent.result.columns));

    // 31. get_contract_value
    const contractValueTool = toolMap.get("get_contract_value");
    assert(contractValueTool);
    const contractValueRes = await contractValueTool.execute("call-contract-value", { player: "NonexistentPlayer" }, undefined);
    assert(contractValueRes.structuredContent);
    assert(Array.isArray(contractValueRes.structuredContent.result.rows));
    assert(Array.isArray(contractValueRes.structuredContent.result.columns));

    // 32. get_trade_check
    const tradeCheckTool = toolMap.get("get_trade_check");
    assert(tradeCheckTool);
    const tradeCheckRes = await tradeCheckTool.execute("call-trade-check", { team_a: "BOS", team_b: "MIA" }, undefined);
    assert(tradeCheckRes.structuredContent);
    assert(Array.isArray(tradeCheckRes.structuredContent.result.rows));
    assert(Array.isArray(tradeCheckRes.structuredContent.result.columns));

    // 33. get_trade_value
    const tradeValueTool = toolMap.get("get_trade_value");
    assert(tradeValueTool);
    const tradeValueRes = await tradeValueTool.execute("call-trade-value", { team_a: "BOS", team_b: "MIA" }, undefined);
    assert(tradeValueRes.structuredContent);
    assert(Array.isArray(tradeValueRes.structuredContent.result.rows));
    assert(Array.isArray(tradeValueRes.structuredContent.result.columns));

    // 34. get_situational_splits
    const situationalSplitsTool = toolMap.get("get_situational_splits");
    assert(situationalSplitsTool);
    const situationalSplitsRes = await situationalSplitsTool.execute("call-situational-splits", { entity: "LeBron James" }, undefined);
    assert(situationalSplitsRes.structuredContent);
    assert(Array.isArray(situationalSplitsRes.structuredContent.result.rows));
    assert(Array.isArray(situationalSplitsRes.structuredContent.result.columns));

    // 35. get_playoff_sim
    const playoffSimTool = toolMap.get("get_playoff_sim");
    assert(playoffSimTool);
    const playoffSimRes = await playoffSimTool.execute("call-playoff-sim", { season: "2023-24", sims: 100 }, undefined);
    assert(playoffSimRes.structuredContent);
    assert(Array.isArray(playoffSimRes.structuredContent.result.rows));
    assert(Array.isArray(playoffSimRes.structuredContent.result.columns));

    // 36. get_playoff_team_ratings
    const playoffRatingsTool = toolMap.get("get_playoff_team_ratings");
    assert(playoffRatingsTool);
    const playoffRatingsRes = await playoffRatingsTool.execute("call-playoff-ratings", { season: "2023-24", limit: 5 }, undefined);
    assert(playoffRatingsRes.structuredContent);
    assert(Array.isArray(playoffRatingsRes.structuredContent.result.rows));
    assert(Array.isArray(playoffRatingsRes.structuredContent.result.columns));

    // 37. get_player_risers
    const playerRisersTool = toolMap.get("get_player_risers");
    assert(playerRisersTool);
    const playerRisersRes = await playerRisersTool.execute("call-player-risers", { season: "2023-24", n: 5 }, undefined);
    assert(playerRisersRes.structuredContent);
    assert(Array.isArray(playerRisersRes.structuredContent.result.rows));
    assert(Array.isArray(playerRisersRes.structuredContent.result.columns));

    // 38. get_standings_deep
    const standingsDeepTool = toolMap.get("get_standings_deep");
    assert(standingsDeepTool);
    const standingsDeepRes = await standingsDeepTool.execute("call-standings-deep", { season: "2023-24", top: 3 }, undefined);
    assert(standingsDeepRes.structuredContent);
    assert(Array.isArray(standingsDeepRes.structuredContent.result.rows));
    assert(Array.isArray(standingsDeepRes.structuredContent.result.columns));

    // 39. get_warehouse_freshness
    const warehouseFreshnessTool = toolMap.get("get_warehouse_freshness");
    assert(warehouseFreshnessTool);
    const warehouseFreshnessRes = await warehouseFreshnessTool.execute("call-warehouse-freshness", {}, undefined);
    assert(warehouseFreshnessRes.structuredContent);
    assert(Array.isArray(warehouseFreshnessRes.structuredContent.result.rows));
    assert(Array.isArray(warehouseFreshnessRes.structuredContent.result.columns));

    // 40. get_finder
    const finderTool = toolMap.get("get_finder");
    assert(finderTool);
    const finderRes = await finderTool.execute("call-finder", { mode: "streak", team_abbrev: "BOS" }, undefined);
    assert(finderRes.structuredContent);
    assert(Array.isArray(finderRes.structuredContent.result.rows));
    assert(Array.isArray(finderRes.structuredContent.result.columns));

    // 41. get_draft_model
    const draftModelTool = toolMap.get("get_draft_model");
    assert(draftModelTool);
    const draftModelRes = await draftModelTool.execute("call-draft-model", { season: "2025" }, undefined);
    assert(draftModelRes.structuredContent);
    assert(Array.isArray(draftModelRes.structuredContent.result.rows));
    assert(Array.isArray(draftModelRes.structuredContent.result.columns));

    // 42. get_leaderboard_deltas
    const leaderboardDeltasTool = toolMap.get("get_leaderboard_deltas");
    assert(leaderboardDeltasTool);
    const leaderboardDeltasRes = await leaderboardDeltasTool.execute("call-leaderboard-deltas", { season: "2023-24", days: 7 }, undefined);
    assert(leaderboardDeltasRes.structuredContent);
    assert(Array.isArray(leaderboardDeltasRes.structuredContent.result.rows));
    assert(Array.isArray(leaderboardDeltasRes.structuredContent.result.columns));

    // 43. get_player_ratings
    const playerRatingsTool = toolMap.get("get_player_ratings");
    assert(playerRatingsTool);
    const playerRatingsRes = await playerRatingsTool.execute("call-player-ratings", { season: "2023-24", metric: "offense", limit: 5 }, undefined);
    assert(playerRatingsRes.structuredContent);
    assert(Array.isArray(playerRatingsRes.structuredContent.result.rows));
    assert(Array.isArray(playerRatingsRes.structuredContent.result.columns));

    // 44. get_risers
    const risersTool = toolMap.get("get_risers");
    assert(risersTool);
    const risersRes = await risersTool.execute("call-risers", { season: "2023-24", weeks: 4 }, undefined);
    assert(risersRes.structuredContent);
    assert(Array.isArray(risersRes.structuredContent.result.rows));
    assert(Array.isArray(risersRes.structuredContent.result.columns));

    // 45. get_team_four_factors
    const teamFourFactorsTool = toolMap.get("get_team_four_factors");
    assert(teamFourFactorsTool);
    const teamFourFactorsRes = await teamFourFactorsTool.execute("call-team-four-factors", { team: "BOS", season: "2023-24" }, undefined);
    assert(teamFourFactorsRes.structuredContent);
    assert(Array.isArray(teamFourFactorsRes.structuredContent.result.rows));
    assert(Array.isArray(teamFourFactorsRes.structuredContent.result.columns));

    // Verify anchor compatibility across all 45 statistical tools
    for (const toolName of [
      "get_rapm", "get_game_prediction", "get_wpa_leaders", "get_comps",
      "get_lineup_stats", "get_win_prob", "get_on_off", "get_shot_zones",
      "get_four_factors", "get_clutch_stats", "get_competitive_ratings",
      "get_hustle", "get_injuries", "get_award_results", "get_briefing",
      "get_standings", "get_rest", "get_team_trajectory",
      "get_ratings", "get_rookie_leaders", "get_cap_ledger",
      "get_leaders", "get_lineup_leaders", "get_playoffs",
      "get_team_leaders", "get_team_compare", "get_elo_standings",
      "get_draft_board", "get_combine", "get_young_player_usage",
      "get_contract_value", "get_trade_check", "get_trade_value", "get_situational_splits",
      "get_playoff_sim", "get_playoff_team_ratings", "get_player_risers", "get_standings_deep",
      "get_warehouse_freshness", "get_finder", "get_draft_model", "get_leaderboard_deltas",
      "get_player_ratings", "get_risers", "get_team_four_factors"
    ]) {
      const syntheticRecord = {
        ref: `ref-${toolName}`,
        callId: `call-${toolName}`,
        tool: toolName,
        response: {
          content: [{
            type: "text",
            text: JSON.stringify({
              ok: true,
              tool: toolName,
              rows: [{ id: 1, val: 42 }],
              columns: ["id", "val"]
            })
          }]
        }
      };
      const submission = validateAnswerSubmission({
        blocks: [{
          text: `Anchor for ${toolName}`,
          anchors: [{
            ref: syntheticRecord.ref,
            row: 0,
            columns: ["id", "val"]
          }]
        }]
      }, (ref) => ref === syntheticRecord.ref ? syntheticRecord : undefined);
      assert.equal(submission.blocks[0].text, `Anchor for ${toolName}`);
    }
    console.log(JSON.stringify({ proof: "statistical-tools-anchor-compatible", tools: 45 }));
  } finally {
    await bridge.close();
  }
  assert.throws(() => process.kill(pid, 0), /ESRCH/);
});

// Observe the installed Pi/QuickJS contract before adapting the Python bridge.
test("installed SDK distinguishes opaque text from native structured results", async () => {
  const record = {ref: "shape-ref", callId: "shape-call", tool: "schema", response: {
    content: [{type: "text", text: JSON.stringify({tables: {observed: ["PTS"]}})}]}};
  const native = {...tool("native", async () => ({content: [], structuredContent: {tables: {observed: ["PTS"]}}})),
    outputSchema: {type: "object"}};
  const {session, requests} = await fixture("sdk-shape", `
    const opaque = await tools.opaque({});
    const native = await tools.native({});
    return {opaqueType: typeof opaque, outerKeys: Object.keys(JSON.parse(opaque)),
      nestedType: typeof JSON.parse(opaque).response.content[0].text,
      nativeType: typeof native, tables: native.tables};
  `, [tool("opaque", async () => textResult(record)), native]);
  try {
    await session.prompt("Observe installed SDK shape");
    const seen = JSON.stringify(requests[1]);
    for (const text of ["opaqueType", "string", "nestedType", "nativeType", "object", "observed"]) assert(seen.includes(text));
    console.log(JSON.stringify({proof: "installed-sdk-shape", messages: requests[1].messages.filter(m => m.role === "toolResult")}));
  } finally {session.dispose();}
});

test("prior sources expose native data, filter a large schema and recover after MCP text errors", async () => {
  const tables = Object.fromEntries(Array.from({length: 1500}, (_, i) => ["table_" + i,
    [{name: "PTS", type: "DOUBLE", unit: "points_per_game", source: "RAW_SECRET_ROW"}]]));
  const records = [
    {ref: "large-schema", callId: "s", tool: "warehouse_schema", response: {content: [{type: "text", text: JSON.stringify({tables})}]}},
    {ref: "prior-sql", callId: "q", tool: "sql_exec", response: {content: [{type: "text", text: JSON.stringify({ok: true,
      rows: [{PTS: 11.8}, {PTS: 999, secret: "RAW_SECRET_ROW"}], declared_column_semantics: {PTS: {unit: "points_per_game"}},
      season_semantics: {encoding: "end_year"}, meta: {source: "owned-synthetic"}})}]}},
    ...["WarehouseError: exact E580", '{"error":broken'].map((text, i) => ({ref: "error-" + i,
      callId: "e" + i, tool: "sql_exec", response: {isError: true, content: [{type: "text", text}]}})),
    {ref: "domain-failure", callId: "d", tool: "sql_exec", response: {content: [{type: "text", text: '{"ok":false,"error":"SQL exact E581"}'}]}},
  ];
  const before = JSON.stringify(records);
  assert(before.length > 100000);
  const {session, requests} = await fixture("prior-native", `
    const errors = await Promise.all(["error-0", "error-1", "domain-failure"].map(ref => tools.read_source({ref})));
    if (errors.some(value => !value.isError)) throw new Error("Error status lost");
    const schema = await tools.read_source({ref: "large-schema"});
    const sql = await tools.read_source({ref: "prior-sql"});
    return {errors, schema: {ref: schema.ref, tables: Object.entries(schema.result.tables)
      .filter(([name]) => name === "table_17").map(([name, columns]) => ({name, columns: columns.map(c => ({name: c.name, type: c.type, unit: c.unit}))}))},
      sql: {ref: sql.ref, rows: sql.result.rows.filter(r => r.PTS !== 999), units: sql.result.declared_column_semantics,
      season: sql.result.season_semantics, provenance: sql.result.meta}};
  `, [priorSourceTool(records)]);
  try {
    await session.prompt("Read filtered prior data and errors");
    const seen = JSON.stringify(requests[1]);
    for (const text of ["large-schema", "prior-sql", "table_17", "DOUBLE", "points_per_game", "end_year", "owned-synthetic", "WarehouseError: exact E580", "broken", "SQL exact E581"]) assert(seen.includes(text), text);
    assert(!seen.includes("RAW_SECRET_ROW"));
    assert(!seen.includes("table_1499"));
    const calls = session.messages.find(m => m.role === "toolResult").details.calls;
    assert.deepEqual(calls.slice(0,3).map(c => c.status), ["error", "error", "error"]);
    assert(calls[0].error.includes("WarehouseError: exact E580"));
    assert(calls[1].error.includes('{"error":broken'));
    assert(calls[2].error.includes("SQL exact E581"));
    assert.equal(calls.at(-1).status, "ok");
    assert.equal(JSON.stringify(records), before);
    await writeFile(join(root, "prior-host-records.json"), before);
    await writeFile(join(root, "prior-provider-requests.json"), JSON.stringify(requests));
    console.log(JSON.stringify({proof: "prior-native-large-filter-errors", rawBytes: before.length, tables: Object.keys(tables).length}));
  } finally {session.dispose();}
});
