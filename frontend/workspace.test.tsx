import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { HomeContent, HomeView } from "./components/shell/WorkspaceViews";
import WarehouseView from "./components/dime/views/WarehouseView";
import { PromptBar } from "./components/ds/PromptBar";
import { ShotsExplorer } from "./components/shell/ShotsExplorer";
import TradesView from "./components/dime/views/TradesView";
import MorningPage from "./components/dime/views/MorningPage";
import CompareView from "./components/dime/views/CompareView";
import DraftView from "./components/dime/views/DraftView";
import type { HomeSnapshot } from "./lib/warehouse";
import { clearEnvelopeCache } from "./lib/api";

const snapshot: HomeSnapshot = { date: "2026-11-19", schedule: { available: false, table: "silver_scoreboard", games: [], next_date: null, seasons: [], last_fetch: null }, snapshot: { table: "silver_team_ratings", season: "2025-26", rows: [{ TEAM_NAME: "Boston", GP: 82, NET_RATING: 10.3 }], last_fetch: "2026-04-13" } };

async function mount(element: React.ReactElement, fetcher: typeof fetch, check: (host: HTMLElement, dom: JSDOM) => Promise<void>) {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {} });
  const previous = globalThis.fetch;
  globalThis.fetch = fetcher;
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  try { await act(async () => root.render(element)); await check(host, dom); }
  finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
}

test("Home distinguishes absent and empty schedules, renders next date and cites real snapshots", () => {
  const html = renderToStaticMarkup(<HomeContent data={snapshot} />);
  assert.match(html, /No games today/); assert.match(html, /No schedule source/); assert.match(html, /silver_team_ratings/); assert.match(html, /2025-26/); assert.match(html, /2026-04-13/); assert.match(html, /\+10.3/); assert.doesNotMatch(html, /Sample data|injur/i);
  const scheduled = { ...snapshot, schedule: { ...snapshot.schedule, available: true, next_date: "2026-11-20" } };
  assert.match(renderToStaticMarkup(<HomeContent data={scheduled} />), /Next scheduled date in the warehouse: 2026-11-20/);
  const games = { ...snapshot, schedule: { ...snapshot.schedule, available: true, games: [{ GAME_ID: "1", VISITOR_TEAM_ABBREVIATION: "BOS", HOME_TEAM_ABBREVIATION: "NYK", _season: "2026-27", GAME_STATUS_TEXT: "7:30 PM" }] } };
  const slate = renderToStaticMarkup(<HomeContent data={games} />);
  assert.match(slate, /BOS at NYK/); assert.match(slate, /silver_scoreboard/); assert.match(slate, /2026-27/); assert.doesNotMatch(slate, /No games today/);
  const calendar = { ...snapshot, schedule: { ...snapshot.schedule, available: true, table: "silver_schedule", games: [{ id: "2", name: "Atlanta Hawks at Toronto Raptors", date: "2026-11-20T01:30Z", _season: "2026-27" }] } };
  const calendarHtml = renderToStaticMarkup(<HomeContent data={calendar} />);
  assert.match(calendarHtml, /Atlanta Hawks at Toronto Raptors/); assert.match(calendarHtml, /8:30 PM ET/); assert.match(calendarHtml, /silver_schedule/);
  assert.match(renderToStaticMarkup(<HomeContent data={{ ...snapshot, snapshot: { ...snapshot.snapshot, rows: [] } }} />), /No team ratings are cached/);
});

test("Home errors never substitute invented data", async () => {
  await mount(<HomeView onAsk={() => {}} />, async () => new Response("offline", { status: 503 }), async host => {
    assert.match(host.textContent!, /Could not load the warehouse snapshot/); assert.match(host.textContent!, /No sample data is substituted/); assert.ok(host.querySelector('[role="alert"]'));
  });
});

test("Data uses actual schema and types for arbitrary silver tables, including empty and error states", async () => {
  const calls: string[] = [];
  await mount(<WarehouseView />, async input => {
    const url = String(input); calls.push(url);
    if (url.includes("freshness")) return Response.json({ ok: true, rows: ["silver_advanced", "silver_empty", "silver_broken"].map(table => ({ table, rows: 3, last_fetch: "2026-04-13", data_through: "2026-04-12" })) });
    if (url.includes("silver_broken")) return new Response("offline", { status: 500 });
    if (url.includes("/warehouse/tables/")) return Response.json({ ok: true, table: "silver_advanced", columns: [{ name: "NET_RATING", type: "DECIMAL(10,2)" }], count: 3, rows: url.includes("silver_empty") ? [] : [{ NET_RATING: 10.3 }], seasons: ["2025-26"], limit: 50 });
    return Response.json({ ok: true, revision: "revision" });
  }, async host => {
    assert.match(host.textContent!, /DECIMAL\(10,2\)/); assert.match(host.textContent!, /10.3/); assert.match(host.textContent!, /Data through 2026-04-12/);
    assert.ok(calls.some(url => url.includes("/warehouse/tables/silver_advanced"))); assert.ok(!calls.some(url => url.includes("/datasets/advanced")));
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent?.includes("silver_empty"))!.click());
    assert.match(host.textContent!, /No rows for this selection/); assert.match(host.textContent!, /DECIMAL/);
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent?.includes("silver_broken"))!.click());
    assert.match(host.textContent!, /Could not load this table/);
  });
});

test("Ask explains supported provider keys and prevents form and keyboard sends without models", async () => {
  let sent = 0;
  const props = { value: "Question", onChange() {}, onSend() { sent++; }, onStop() {}, busy: false, models: [], model: null, onModelChange() {}, onRetry() {}, providers: ["gemini", "nvidia", "openrouter", "mistral", "cerebras"] };
  await mount(<PromptBar {...props} />, async () => Response.json({}), async (host, dom) => {
    for (const key of ["GEMINI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_NIM_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY"]) assert.match(host.textContent!, new RegExp(key));
    assert.match(host.textContent!, /Restart the Node analyst backend/); assert.match(host.querySelector("a")!.href, /README.md#quickstart/);
    assert.equal(host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.disabled, true);
    await act(async () => { host.querySelector("textarea")!.focus(); host.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })); host.querySelector("textarea")!.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
    assert.equal(sent, 0);
  });
  const enabled = renderToStaticMarkup(<PromptBar {...props} models={[{ id: "gemini:flash", label: "Flash", available: true }]} model="gemini:flash" />);
  assert.doesNotMatch(enabled, /no models are configured/);
  const error = renderToStaticMarkup(<PromptBar {...props} modelError />); assert.match(error, /Models unavailable/); assert.doesNotMatch(error, /no models are configured/);
});

test("Shots explorer preserves zone data even if shot coordinates are unavailable", async () => {
  const previous = globalThis.fetch;
  await mount(<ShotsExplorer season="2025-26" initialPlayer="2544" />, async input => {
    const url = String(input);
    if (url.includes("zone_splits")) return Response.json({ ok: true, data: [{ zone: "rim", FGM: 1, FGA: 2, FG_PCT: 0.5, share: 1 }], meta: { source: "warehouse:silver_zone_splits" } });
    return Response.json({ ok: false, error: "No shot coordinates" });
  }, async (host, dom) => {
    await act(async () => host.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
    assert.match(host.textContent!, /No shot coordinates/); assert.match(host.textContent!, /50.0%/); assert.match(host.textContent!, /warehouse:silver_zone_splits/);
  });
  globalThis.fetch = previous;
});

test("Trades renders the backend's readable domain error on HTTP 422", async () => {
  await mount(<TradesView />, async input => {
    const url = String(input);
    if (url.includes("/trade/assets")) {
      const abbr = new URL(url).searchParams.get("team");
      const players = abbr === "DAL" ? [{ name: "Luka Doncic", salary: 49.8 }] : [{ name: "Karl-Anthony Towns", salary: 57.1 }];
      return Response.json({ ok: true, team: abbr, season: "2026-27", players, picks: [], meta: { source: "salary_records", season: "2026-27" } });
    }
    return Response.json({ ok: false, error: "Salary data lists Luka with LAL, not DAL" }, { status: 422 });
  }, async host => {
    await act(async () => [...host.querySelectorAll("button")].find(item => item.textContent?.includes("Luka"))!.click());
    await act(async () => [...host.querySelectorAll("button")].find(item => item.textContent?.includes("Towns"))!.click());
    await act(async () => new Promise(resolve => setTimeout(resolve, 50)));
    assert.match(host.textContent!, /Salary data lists Luka with LAL, not DAL/);
    assert.doesNotMatch(host.textContent!, /Could not reach the backend/);
  });
});

test("Trades hydrates a seeded construction into the interactive builder and evaluates it", async () => {
  const seed = {
    legs: [
      { from: "DAL", to: "MIL", players: ["Klay Thompson"], picks: [{ year: 2029, round: 1 }] },
      { from: "MIL", to: "DAL", players: ["Kyle Kuzma"] },
    ],
    season: "2026-27",
  };
  let legsPosted: unknown = null;
  await mount(<TradesView seed={seed} />, async input => {
    const url = String(input);
    if (url.includes("/trade/assets")) {
      const abbr = new URL(url).searchParams.get("team");
      return Response.json({ ok: true, team: abbr, season: "2026-27", players: [{ name: "Klay Thompson", salary: 16.6 }, { name: "Kyle Kuzma", salary: 15.0 }], picks: [], meta: { source: "salary_records", season: "2026-27" } });
    }
    if (url.includes("/trade/check")) {
      legsPosted = true;
      return Response.json({ ok: true, rows: { team_a: { team: "DAL", legal: true }, team_b: { team: "MIL", legal: true }, legal: true, issues: [] } });
    }
    return Response.json({ ok: false, error: "unexpected" }, { status: 422 });
  }, async host => {
    await act(async () => new Promise(resolve => setTimeout(resolve, 120)));
    assert.match(host.textContent!, /Klay Thompson/, "seeded player appears in the builder");
    assert.match(host.textContent!, /Kyle Kuzma/, "second-side player appears");
    assert.ok(legsPosted, "hydration triggers legality evaluation — recompute on load");
  });
});

test("Morning page renders blocks with provenance and degrades missing tables", async () => {
  const morning = {
    ok: true, team: "NYK", season: "2025-26",
    blocks: {
      last_result: { ok: true, game: { date: "2026-04-12", home: "NYK", away: "CHA", home_pts: 110, away_pts: 96, result: "W", opponent: "CHA" }, provenance: { table: "silver_scoreboard", as_of: "2026-09-11T05:50:59Z" } },
      next_game: { ok: true, game: { date: "2026-04-13T00:30Z", name: "Utah Jazz at New York Knicks", short_name: "UTAH @ NY", season_type: "Regular Season", opponent: "UTA" }, provenance: { table: "silver_schedule", as_of: "2026-09-10T05:37:42Z" } },
      opponent: { ok: true, row: { team: "Utah Jazz", wins: 22, losses: 60, win_pct: 0.268, playoff_rank: 15, l10: "1-9", conference: "West" }, name: "Utah Jazz", provenance: { table: "silver_standings", as_of: "2026-09-07T20:26:48Z" } },
      standings: { ok: true, row: { team: "New York Knicks", wins: 53, losses: 29, win_pct: 0.646, playoff_rank: 3, l10: "6-4", conference: "East" }, projection: { projected_wins: 44.5, projected_losses: 37.5, make_playoffs_pct: 0.92, win_title_pct: 0.03 }, pace_wins: 53.0, provenance: { table: "silver_standings + silver_preseason_projections", as_of: "2026-09-07T20:26:48Z" } },
      injuries: { ok: true, rows: [], provenance: { table: "silver_injuries", as_of: null } },
      news: { ok: false, rows: [], error: "silver_news not in warehouse", provenance: { table: "silver_news", as_of: null } },
      cap: { ok: true, row: { team: "NYK", payroll: 201332759, room_under_apron2: 5537241, over_tax: true }, meta: { apron1: 178132000, apron2: 206870000 }, provenance: { table: "silver_salaries", as_of: "2026-09-07" } },
    },
  };
  await mount(<MorningPage />, async input => {
    const url = String(input);
    if (url.includes("/morning")) return Response.json(morning);
    return Response.json({ ok: true });
  }, async host => {
    assert.match(host.textContent!, /W\s*CHA 96 @ NYK 110/);
    assert.match(host.textContent!, /Utah Jazz at New York Knicks/);
    assert.match(host.textContent!, /22-60, West #15/);
    assert.match(host.textContent!, /53 wins pace vs 44\.5 projected/);
    assert.match(host.textContent!, /\$201\.3M/);
    assert.match(host.textContent!, /silver_news not in warehouse/);
    assert.match(host.textContent!, /silver_scoreboard · as of 2026-09-11/);
    assert.match(host.textContent!, /salary|silver_salaries/);
    assert.ok(host.querySelectorAll("button").length > 3);
  });
});

test("Morning page shows the backend error without substituting data", async () => {
  await mount(<MorningPage />, async () => Response.json({ ok: false, error: "warehouse unreachable" }, { status: 422 }), async host => {
    assert.match(host.textContent!, /warehouse unreachable/);
    assert.match(host.textContent!, /No sample data is substituted/);
    assert.ok(host.querySelector('[role="alert"]'));
  });
});

const compareFixture = {
  ok: true, season: "2025-26",
  players: [
    {
      player_id: 2544, name: "LeBron James", season: "2025-26",
      season_line: { ok: true, row: { season: 2025, age: 40, team: "LAL", gp: 70, mpg: 34.9, ppg: 24.4, rpg: 7.8, apg: 8.2, spg: 1.0, bpg: 0.6, fg_pct: 0.513, fg3_pct: 0.376, ft_pct: 0.782, ts_pct: 0.604, usg_pct: 0.291, off_rating: 112.7, def_rating: 114.0, net_rating: -1.3 }, provenance: { table: "silver_hist_player_seasons", as_of: "2026-09-10T04:33:35Z" } },
      impact: { ok: false, error: "no impact row for 2025-26", provenance: { table: "silver_raptor_player", as_of: "2026-09-09T18:15:44Z" } },
      zones: { ok: true, zones: [{ zone: "Restricted Area", x: 0, y: 1.4, att: 680, makes: 514, pct: 75.6, league_pct: 76.7, delta_pp: -1.1 }], provenance: { table: "silver_shots", as_of: "2026-09-10T19:46:39Z" } },
      contract: { ok: true, row: { team: "LAL", salary: 52000000, contract_type: "MAX", guaranteed: true, player_option: false, team_option: false }, season: "2026-27", provenance: { table: "silver_cap_players", as_of: "2026-09-08T08:05:24Z" } },
      arc: { ok: true, rows: [{ season: 2024, age: 39, gp: 71, pts: 25.7, ts_pct: 0.63, usg_pct: 0.285 }, { season: 2025, age: 40, gp: 70, pts: 24.4, ts_pct: 0.604, usg_pct: 0.291 }], provenance: { table: "silver_hist_player_seasons", as_of: "2026-09-10T04:33:35Z" } },
    },
    {
      player_id: 1628983, name: "Shai Gilgeous-Alexander", season: "2025-26",
      season_line: { ok: true, row: { season: 2025, age: 27, team: "OKC", gp: 76, mpg: 34.2, ppg: 32.7, rpg: 5.0, apg: 6.4, spg: 1.7, bpg: 1.0, fg_pct: 0.519, fg3_pct: 0.375, ft_pct: 0.897, ts_pct: 0.637, usg_pct: 0.339, off_rating: 125.0, def_rating: 106.0, net_rating: 19.0 }, provenance: { table: "silver_hist_player_seasons", as_of: "2026-09-10T04:33:35Z" } },
      impact: { ok: true, raptor_total: 8.4, war_total: 17.2, mp: 2600, rank: 1, of: 450, provenance: { table: "silver_raptor_player", as_of: "2026-09-09T18:15:44Z" } },
      zones: { ok: true, zones: [{ zone: "Restricted Area", x: 0.2, y: 1.9, att: 412, makes: 250, pct: 60.7, league_pct: 76.7, delta_pp: -16.0 }], provenance: { table: "silver_shots", as_of: "2026-09-10T19:46:39Z" } },
      contract: { ok: true, row: { team: "OKC", salary: 40806150, contract_type: "DRK-EXT", guaranteed: true, player_option: false, team_option: false }, season: "2026-27", provenance: { table: "silver_cap_players", as_of: "2026-09-08T08:05:24Z" } },
      arc: { ok: true, rows: [{ season: 2024, age: 26, gp: 75, pts: 30.1, ts_pct: 0.653, usg_pct: 0.33 }, { season: 2025, age: 27, gp: 76, pts: 32.7, ts_pct: 0.637, usg_pct: 0.339 }], provenance: { table: "silver_hist_player_seasons", as_of: "2026-09-10T04:33:35Z" } },
    },
  ],
};

test("Compare view renders cited sections for two players", async () => {
  const picks = [
    { id: 2544, name: "LeBron James", season: "2025-26" },
    { id: 1628983, name: "Shai Gilgeous-Alexander", season: "2025-26" },
  ];
  await mount(<CompareView initialPicks={picks} />, async input => {
    const url = String(input);
    if (url.includes("/compare")) {
      assert.match(url, /players=2544%3A2025-26%2C1628983%3A2025-26/);
      return Response.json(compareFixture);
    }
    return Response.json({ ok: true });
  }, async host => {
    assert.match(host.textContent!, /LeBron James/);
    assert.match(host.textContent!, /Shai Gilgeous-Alexander/);
    assert.match(host.textContent!, /24\.4/);
    assert.match(host.textContent!, /32\.7/);
    assert.match(host.textContent!, /RAPTOR 8\.4 · #1 of 450 · WAR 17\.2/);
    assert.match(host.textContent!, /no impact row for 2025-26/);
    assert.match(host.textContent!, /\$52\.0M · MAX/);
    assert.match(host.textContent!, /silver_hist_player_seasons/);
    assert.match(host.textContent!, /silver_shots/);
    assert.match(host.textContent!, /Points per game by age/);
  });
});

test("Compare view requires at least two players", async () => {
  await mount(<CompareView initialPicks={[]} />, async () => Response.json({ ok: true }), async host => {
    assert.match(host.textContent!, /Add at least two players to compare/);
  });
});

test("Compare view surfaces the backend error", async () => {
  const picks = [
    { id: 2544, name: "LeBron James", season: "2025-26" },
    { id: 1628983, name: "Shai Gilgeous-Alexander", season: "2025-26" },
  ];
  await mount(<CompareView initialPicks={picks} />, async () => Response.json({ ok: false, error: "warehouse_unreachable" }, { status: 422 }), async host => {
    assert.match(host.textContent!, /warehouse_unreachable/);
    assert.match(host.textContent!, /No sample data is substituted/);
  });
});

const draftFixture = {
  ok: true, team: "NYK", season: "",
  blocks: {
    board: { ok: true, season: "2027-28", board: "big_board" as const, order_semantics: "rank" as const, rows: [
      { board_order: 1, pick: 1, name: "AJ Dybantsa", position: "F", school: "BYU", gp: 30, pts: 24.1, reb: 6.8, ast: 3.2, ts_pct: 0.61, usg: 31.0 },
      { board_order: 2, pick: 2, name: "Darryn Peterson", position: "G", school: "Kansas", gp: 28, pts: 21.4, reb: 4.0, ast: 4.8, ts_pct: 0.58, usg: 28.0 },
    ], provenance: { table: "silver_draft_boards + silver_prospect_stats", as_of: "2026-09-10T04:00:00Z" } },
    free_agents: { ok: true, rows: [
      { name: "Trae Young", team: "ATL", fa_type: "ufa", prior_salary: 45999600, cap_hold: 59799480 },
      { name: "Jalen Williams", team: "OKC", fa_type: "rfa", prior_salary: 6580000, cap_hold: 8554000 },
    ], provenance: { table: "silver_free_agents", as_of: "2026-09-10T05:00:00Z" } },
    cap_room: { ok: true, rows: [
      { team: "NYK", committed: 178000000, option_salary: 12000000, fa_holds: 30000000, roster_charges: 6000000, projected_room: -32000000 },
      { team: "DET", committed: 80000000, option_salary: 0, fa_holds: 9000000, roster_charges: 12000000, projected_room: 75000000 },
    ], provenance: { table: "silver_cap_room", as_of: "2026-09-10T05:10:00Z" } },
    fit: { ok: true, team: "NYK",
      gaps: [{ factor: "ball_security", label: "Ball security", value: 0.139, rank: 22, of: 30 }, { factor: "shooting", label: "Shooting", value: 0.557, rank: 18, of: 30 }],
      cap: { committed: 178000000, option_salary: 12000000, fa_holds: 30000000, projected_room: -32000000 },
      targets: [{ name: "Trae Young", team: "ATL", fa_type: "ufa", prior_salary: 45999600, cap_hold: 59799480, ppg: 25.4, rpg: 2.9, apg: 11.2, spg: 1.1, bpg: 0.1, fg3_pct: 0.354, gp: 76 }],
      errors: [],
      provenance: { table: "silver_team_ratings + silver_cap_room + silver_free_agents + silver_player_season", as_of: "2026-09-08T16:57:36Z" } },
  },
};

test("Draft view renders prospect board, free agents, cap room and fit with provenance", async () => {
  await mount(<DraftView initialTeam="NYK" />, async input => {
    const url = String(input);
    if (url.includes("/draft")) {
      assert.match(url, /team=NYK/);
      return Response.json(draftFixture);
    }
    return Response.json({ ok: true });
  }, async host => {
    assert.match(host.textContent!, /Big board · 2027-28/);
    assert.match(host.textContent!, /Big-board population · order is a talent rank, not team placement/);
    assert.equal(host.querySelector("th")!.textContent, "Rank");
    assert.match(host.textContent!, /AJ Dybantsa/);
    assert.match(host.textContent!, /BYU/);
    assert.match(host.textContent!, /61\.0%/);
    assert.match(host.textContent!, /31\.0%/);
    assert.doesNotMatch(host.textContent!, /3100\.0%/);
    assert.match(host.textContent!, /Trae Young/);
    assert.match(host.textContent!, /\$46\.0M/);
    assert.match(host.textContent!, /\$75\.0M/);
    assert.match(host.textContent!, /Ball security · #22 of 30/);
    assert.match(host.textContent!, /silver_draft_boards/);
    assert.match(host.textContent!, /silver_free_agents/);
    assert.match(host.textContent!, /silver_cap_room/);
    assert.match(host.textContent!, /silver_team_ratings/);
  });
});

test("Draft view formats prospect per-game stats to one decimal", async () => {
  const precision = { ...draftFixture, blocks: { ...draftFixture.blocks,
    board: { ...draftFixture.blocks.board, rows: [
      { board_order: 1, pick: 1, name: "Precision Prospect", position: "G", school: "Test U", gp: 10, pts: 12.34, reb: 4.06, ast: 3, ts_pct: 0.6, usg: 25.0 },
    ] },
  } };
  await mount(<DraftView initialTeam="NYK" />, async () => Response.json(precision), async host => {
    assert.match(host.textContent!, /Precision Prospect[\s\S]*12\.3[\s\S]*4\.1[\s\S]*3\.0/);
  });
});

test("Draft view labels a mock draft as team-placement picks", async () => {
  const mockFixture = { ...draftFixture, blocks: { ...draftFixture.blocks,
    board: { ...draftFixture.blocks.board, board: "mock_draft" as const, order_semantics: "pick" as const } } };
  await mount(<DraftView initialTeam="NYK" />, async () => Response.json(mockFixture), async host => {
    assert.match(host.textContent!, /Mock draft · 2027-28/);
    assert.match(host.textContent!, /Mock-draft population · order is a projected team-placement pick/);
    assert.equal(host.querySelector("th")!.textContent, "Pick");
  });
});

test("Draft view degrades per block when tables are missing", async () => {
  const degraded = { ...draftFixture, blocks: { ...draftFixture.blocks,
    board: { ok: false, rows: [], error: "silver_draft_boards not in warehouse", provenance: { table: "silver_draft_boards", as_of: null } },
    free_agents: { ok: false, rows: [], error: "silver_free_agents not in warehouse", provenance: { table: "silver_free_agents", as_of: null } },
  } };
  await mount(<DraftView initialTeam="NYK" />, async () => Response.json(degraded), async host => {
    assert.match(host.textContent!, /silver_draft_boards not in warehouse/);
    assert.match(host.textContent!, /silver_free_agents not in warehouse/);
    assert.match(host.textContent!, /Trae Young/);
    assert.match(host.textContent!, /Ball security · #22 of 30/);
  });
});

test("Draft view surfaces the backend error", async () => {
  await mount(<DraftView initialTeam="NYK" />, async () => Response.json({ ok: false, error: "warehouse unreachable" }, { status: 422 }), async host => {
    assert.match(host.textContent!, /warehouse unreachable/);
    assert.match(host.textContent!, /No sample data is substituted/);
  });
});

test("Shots queries follow asynchronously loaded and subsequently selected seasons", async () => {
  const calls: string[] = [];
  function Seasons() {
    const [season, setSeason] = React.useState("");
    return <><button onClick={() => setSeason("2022-23")}>Loaded season</button><button onClick={() => setSeason("2023-24")}>Selected season</button><ShotsExplorer season={season} initialPlayer="2544" /></>;
  }
  await mount(<Seasons />, async input => { calls.push(String(input)); return Response.json({ ok: true, data: [] }); }, async (host, dom) => {
    const input = host.querySelector<HTMLInputElement>('[aria-label="Shots season"]')!;
    assert.equal(input.value, "");
    assert.equal([...host.querySelectorAll("button")].find(button => button.textContent === "Load shots")!.disabled, true);
    for (const [label, season] of [["Loaded season", "2022-23"], ["Selected season", "2023-24"]]) {
      await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent === label)!.click());
      assert.equal(input.value, season);
      await act(async () => host.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
      assert.ok(calls.slice(-2).every(url => new URL(url).searchParams.get("season") === season));
    }
  });
});

test("Warehouse passes loaded seasons and table filter changes to Shots", async () => {
  clearEnvelopeCache();
  let resolveDetail!: (response: Response) => void;
  let first = true;
  const detail = { ok: true, columns: [], rows: [], seasons: ["2022-23", "2021-22"], count: 0 };
  await mount(<WarehouseView />, async input => {
    const url = String(input);
    if (url.includes("freshness")) return Response.json({ ok: true, rows: [{ table: "silver_shots", rows: 0, last_fetch: null }] });
    if (url.includes("/warehouse/tables/")) {
      if (first) { first = false; return new Promise<Response>(resolve => { resolveDetail = resolve; }); }
      return Response.json(detail);
    }
    return Response.json({});
  }, async (host, dom) => {
    const input = () => host.querySelector<HTMLInputElement>('[aria-label="Shots season"]')!;
    assert.equal(input().value, "");
    await act(async () => resolveDetail(Response.json(detail)));
    assert.equal(input().value, "2022-23");
    await act(async () => {
      const filter = host.querySelector<HTMLSelectElement>('[aria-label="Table season"]')!;
      filter.value = "2021-22";
      filter.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    assert.equal(input().value, "2021-22");
  });
});
