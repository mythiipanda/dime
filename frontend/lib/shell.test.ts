import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import * as net from "node:net";
import { createRequire } from "node:module";
import { isActiveDestination, normalizeActive } from "./shell";
import { getSeason2627Coverage, hasSeason2627, parseSeasonValue } from "./warehouse";

function read(rel: string[]) {
  return readFileSync(join(process.cwd(), ...rel), "utf8");
}

test("duplicate rails are hidden with a descendant selector", () => {
  const shell = read(["components", "site", "WorkspaceShell.tsx"]);
  assert.ok(shell.includes('.workspace-content main aside[aria-label="dime navigation"]'));
  assert.ok(!shell.includes(".workspace-content > main > aside"));
  const page = read(["app", "page.tsx"]);
  assert.ok(page.includes("WorkspaceShell"));
  assert.ok(page.includes("DimeHarness"));
});

test("chat rail resolves active case-insensitively for all destinations", () => {
  assert.equal(normalizeActive("chat"), "chat");
  assert.equal(normalizeActive("Chat"), "chat");
  assert.equal(normalizeActive("Warehouse"), "warehouse");
  assert.ok(isActiveDestination("Chat", normalizeActive("chat")));
  const names = ["Today", "Chat", "Notebook", "Warehouse", "Skills", "History", "Explore", "Standings"];
  for (const name of names) {
    assert.ok(isActiveDestination(name, normalizeActive(name)));
  }
  assert.ok(isActiveDestination("Today", normalizeActive("Today")));
  assert.ok(!isActiveDestination("Chat", normalizeActive("Today")));
});

test("chat frame fits viewport without page scroll", { timeout: 90000 }, async (t) => {
  const require = createRequire(import.meta.url);
  const nextBin = require.resolve("next/dist/bin/next");
  const getPort = () =>
    new Promise<number>((resolve, reject) => {
      const s = net.createServer();
      s.on("error", reject);
      s.listen(0, "127.0.0.1", () => {
        const a = s.address();
        const p = typeof a === "object" && a ? a.port : 0;
        s.close((e?: Error) => (e ? reject(e) : resolve(p)));
      });
    });
  const port = await getPort();
  assert.ok(port > 0 && port < 65536);
  const server = spawn(process.execPath, [nextBin, "start", "-p", String(port), "-H", "127.0.0.1"], {
    cwd: process.cwd(),
    stdio: ["ignore", "pipe", "pipe"],
  });
  let spawnError: Error | null = null;
  server.on("error", (e: Error) => {
    spawnError = e;
  });
  let stderrTail = "";
  const remember = (chunk: unknown) => {
    stderrTail += String(chunk);
    if (stderrTail.length > 8000) stderrTail = stderrTail.slice(-8000);
  };
  server.stdout?.on("data", remember);
  server.stderr?.on("data", remember);
  const closed = new Promise<number | null>((resolve) => {
    server.on("close", (code: number | null) => resolve(code));
  });
  let browser: Awaited<ReturnType<typeof chromium.launch>> | null = null;
  try {
    const base = `http://127.0.0.1:${port}`;
    const deadline = Date.now() + 30000;
    let ready = false;
    while (Date.now() < deadline) {
      if (spawnError) break;
      if (server.exitCode !== null) break;
      try {
        const r = await fetch(base + "/", { signal: AbortSignal.timeout(2500) });
        if (r.ok) {
          await r.text();
          ready = true;
          break;
        }
      } catch {}
      await new Promise((r) => setTimeout(r, 250));
    }
    assert.ok(
      ready,
      `next start did not become ready spawnError=${spawnError ? String(spawnError) : "none"} exitCode=${server.exitCode} log=${stderrTail.slice(-2000)}`,
    );
    const envPath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
    let executablePath: string | undefined;
    if (envPath) {
      assert.ok(existsSync(envPath), `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH missing: ${envPath}`);
      executablePath = envPath;
    } else if (process.platform === "win32") {
      const edgeX86 = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
      const edgeX64 = "C:/Program Files/Microsoft/Edge/Application/msedge.exe";
      if (existsSync(edgeX86)) executablePath = edgeX86;
      else if (existsSync(edgeX64)) executablePath = edgeX64;
    }
    try {
      browser = await chromium.launch(executablePath ? { executablePath } : {});
    } catch (e) {
      assert.fail(`chromium.launch failed executablePath=${executablePath ?? "(installed browsers)"} err=${String(e)}`);
    }
    assert.ok(browser, "chromium.launch did not return a browser");
    for (const width of [1360, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage();
      try {
        await page.goto(base + "/", { waitUntil: "load" });
        const ta = page.locator("textarea").first();
        await ta.waitFor({ timeout: 15000 });
        await page.waitForFunction(
          () =>
            Array.from(document.querySelectorAll("aside")).filter((el) => {
              const b = el.getBoundingClientRect();
              return b.width > 0 && b.height > 0;
            }).length === 1,
          undefined,
          { timeout: 15000 },
        );
        const m = await page.evaluate(() => {
          const taEl = document.querySelector("textarea")!;
          const first = taEl.getBoundingClientRect();
          const section = taEl.closest("section");
          if (!section) throw new Error("chat section not found for textarea");
          const inScope = [section, ...Array.from(section.querySelectorAll("*"))] as HTMLElement[];
          const cands = inScope
            .filter((el) => {
              const cs = getComputedStyle(el);
              const oy = cs.overflowY;
              const h = (el as HTMLElement).clientHeight;
              return (oy === "auto" || oy === "scroll") && h > 100;
            })
            .sort((a, b) => b.clientHeight - a.clientHeight);
          const scroller = (cands[0] ?? null) as HTMLElement | null;
          const de = document.documentElement;
          const asides = Array.from(document.querySelectorAll("aside")).filter((el) => {
            const b = el.getBoundingClientRect();
            return b.width > 0 && b.height > 0;
          });
          const home = Array.from(document.querySelectorAll("a[href='/'][aria-current='page']")).filter((el) => {
            const b = (el as HTMLElement).getBoundingClientRect();
            return b.width > 0 && b.height > 0;
          });
          if (!scroller) {
            return {
              top: first.top,
              bottom: first.bottom,
              left: first.left,
              right: first.right,
              topAfter: first.top,
              bottomAfter: first.bottom,
              leftAfter: first.left,
              rightAfter: first.right,
              scrollH: de.scrollHeight,
              scrollW: de.scrollWidth,
              innerW: window.innerWidth,
              asides: asides.length,
              home: home.length,
              hasScroller: false,
              sTop0: -1,
              sTop1: -1,
              scrolled: false,
            };
          }
          const sTop0 = scroller.scrollTop;
          const filler = document.createElement("div");
          filler.setAttribute("data-probe", "hark-scroll");
          filler.style.height = "3000px";
          filler.style.width = "1px";
          scroller.appendChild(filler);
          scroller.scrollTop = scroller.scrollHeight;
          const sTop1 = scroller.scrollTop;
          const scrolled = sTop1 > sTop0;
          const second = taEl.getBoundingClientRect();
          const out = {
            top: first.top,
            bottom: first.bottom,
            left: first.left,
            right: first.right,
            topAfter: second.top,
            bottomAfter: second.bottom,
            leftAfter: second.left,
            rightAfter: second.right,
            scrollH: de.scrollHeight,
            scrollW: de.scrollWidth,
            innerW: window.innerWidth,
            asides: asides.length,
            home: home.length,
            hasScroller: true,
            sTop0,
            sTop1,
            scrolled,
          };
          filler.remove();
          return out;
        });
        t.diagnostic(`width=${width} ` + JSON.stringify(m));
        console.log(JSON.stringify({ width, height: 900, ...m }));
        assert.ok(m.top >= 0, `textarea top ${m.top} width ${width}`);
        assert.ok(m.bottom <= 900, `textarea bottom ${m.bottom} width ${width}`);
        assert.ok(m.scrollH <= 901, `scrollHeight ${m.scrollH} width ${width}`);
        assert.ok(m.scrollW <= width + 1, `scrollWidth ${m.scrollW} width ${width}`);
        assert.equal(m.asides, 1, `asides ${m.asides} width ${width}`);
        assert.equal(m.home, 1, `home ${m.home} width ${width}`);
        assert.ok(m.hasScroller, `no chat scroller width ${width}`);
        assert.ok(m.scrolled, `scroller did not scroll width ${width} sTop0=${m.sTop0} sTop1=${m.sTop1}`);
        assert.ok(
          Math.abs(m.topAfter - m.top) <= 2 && Math.abs(m.bottomAfter - m.bottom) <= 2,
          `composer moved top ${m.top}->${m.topAfter} bottom ${m.bottom}->${m.bottomAfter} width ${width}`,
        );
        assert.ok(m.topAfter >= 0 && m.bottomAfter <= 900, `textarea moved after scroll width ${width}`);
      } finally {
        await context.close();
      }
    }
  } finally {
    if (browser) await browser.close();
    try {
      server.kill();
    } catch {}
    await Promise.race([closed, new Promise((r) => setTimeout(r, 5000))]);
  }
});

test("empty states are honest and share one action", () => {
  const routes: Array<{ dir: string; name: string }> = [
    { dir: "today", name: "Today" },
    { dir: "explore", name: "Explore" },
    { dir: "history", name: "History" },
    { dir: "notebook", name: "Notebook" },
    { dir: "skills", name: "Skills" },
    { dir: "standings", name: "Standings" },
  ];
  const banned = [
    "Daily briefing",
    "League-wide discovery",
    "Your work",
    "Working papers",
    "Analyst toolkit",
    "League table",
    "matchups and questions",
    "follow the evidence",
    "pick up a thread",
    "lasting record",
    "research methods",
    "playoff race",
  ];
  for (const r of routes) {
    const src = read(["app", r.dir, "page.tsx"]);
    assert.ok(src.includes("Not available yet"));
    assert.ok(src.includes("Back to Chat"));
    assert.ok(src.includes(r.name + " is not available yet."));
    for (const phrase of banned) {
      assert.ok(!src.includes(phrase));
    }
  }
});

test("season 2026-27 statement derives from returned rows", () => {
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2025-26", max: "2026-27" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.deepEqual(parseSeasonValue("2025-26"), { start_year: 2025, end_year: 2026 });
  assert.deepEqual(parseSeasonValue("2025-2026"), { start_year: 2025, end_year: 2026 });
  assert.deepEqual(parseSeasonValue("2026-27"), { start_year: 2026, end_year: 2027 });
  assert.equal(parseSeasonValue("2026"), null);
  assert.equal(parseSeasonValue("22026"), null);
  assert.equal(parseSeasonValue("42026"), null);
  assert.equal(
    getSeason2627Coverage([
      { name: "silver_scoreboard", row_count: 1, column_count: 1, season_range: { min: "2026", max: "2026" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "b", row_count: 1, column_count: 1, season_range: { min: "22026", max: "22026" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "c", row_count: 1, column_count: 1, season_range: { min: "42026", max: "42026" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2025-26", max: "2025-26" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(getSeason2627Coverage([]), "unknown");
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2024-25", max: "2028-29" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2028-29", max: "2024-25" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2026", max: "2027" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: null, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 0, column_count: 1, season_range: { min: "2025-26", max: "2026-27" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2026-027", max: "2026-027" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  assert.equal(
    getSeason2627Coverage([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2020-21", max: "2025-26" }, source_badge: "nba_official", description: "x" },
    ]),
    "unknown",
  );
  const page = read(["app", "warehouse", "page.tsx"]);
  assert.ok(page.includes("getSeason2627Coverage(tables)"));
  assert.ok(page.includes("2026-27 season coverage is unknown."));
  assert.ok(page.includes("2026-27 season: data available."));
  assert.ok(page.includes("No 2026-27 season data in the warehouse yet."));
  assert.ok(!page.includes("offseason"));
  assert.ok(page.includes("No tables in the warehouse."));
  assert.ok(page.includes("data-state="));
  assert.ok(page.includes("aria-busy"));
});
