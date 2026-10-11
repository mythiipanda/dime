import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import net from "node:net";

async function freePort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.unref();
    probe.on("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const addr = probe.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      probe.close(() => resolve(port));
    });
  });
}

const PORT = await freePort();
const URL = `http://127.0.0.1:${PORT}`;
const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const STREAM_URL = `${BACKEND_ORIGIN}/api/v2/chat/stream`;

const customData = {
  tables: [
    {
      output_id: "fixture-metric",
      display_name: "Fixture metric",
      subject_display_name: "QA Fixture A",
      value: 12.3,
      unit: "points",
      provenance: {
        capability: "fixture_capability",
        origin: "live",
        warehouse_id: null,
        season: "fixture-season",
        as_of: "2026-01-01",
        live_sources: ["nba_api", "espn", "https://fixture.invalid/citation", "javascript:alert(1)"]
      }
    }
  ],
  artifacts: [
    {
      kind: "chart",
      title: "QA Fixture provenance chart",
      series: [{ name: "QA Fixture A", values: [12.3] }],
      provenance: {
        capability: "fixture_capability",
        origin: "live",
        warehouse_id: null,
        season: "fixture-season",
        as_of: "2026-01-01",
        live_sources: ["nba_api", "espn", "https://fixture.invalid/citation", "javascript:alert(1)"]
      }
    }
  ]
};

const finalAnswer = {
  text: "QA Fixture A scored 12.3 points in the fixture slate.",
  carry: {
    run_id: "run-734",
    verification: "partial",
    verified_claims: 0,
    gaps: [{ kind: "execution_failure", blocks: [] }]
  }
};

const failureFrame = { kind: "quota", message: "quota exhausted" };

const sseBody =
  `event: custom_data\n` +
  `data: ${JSON.stringify(customData)}\n\n` +
  `event: final_answer\n` +
  `data: ${JSON.stringify(finalAnswer)}\n\n` +
  `event: failure\n` +
  `data: ${JSON.stringify(failureFrame)}\n\n`;

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Max-Age": "600"
};

function startServer() {
  const frontendDir = path.dirname(fileURLToPath(import.meta.url));
  const nextBin = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
  const server = spawn(process.execPath, [nextBin, "start", "-p", String(PORT)], {
    cwd: frontendDir,
    stdio: "pipe"
  });
  server.stderr?.on("data", (d) => process.stderr.write(`[next:stderr] ${d}`));
  server.stdout?.on("data", (d) => process.stdout.write(`[next:stdout] ${d}`));
  server.on("error", (err) => console.log(`FAIL: server spawn error - ${err && err.message ? err.message : String(err)}`));
  server.on("exit", (code, signal) => console.log(`server exit code=${code} signal=${signal ?? "none"}`));
  return server;
}

function waitForServer(url, timeoutMs = 60000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = async () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error(`server did not start at ${url}`));
        return;
      }
      try {
        const res = await fetch(url);
        if (res.ok) {
          resolve();
          return;
        }
      } catch {
      }
      setTimeout(tick, 500);
    };
    tick();
  });
}

let failures = 0;

function check(name, ok, detail = "") {
  if (ok) {
    console.log(`PASS: ${name}`);
  } else {
    failures += 1;
    console.log(`FAIL: ${name}${detail ? ` - ${detail}` : ""}`);
  }
}

let server = null;
let browser = null;

try {
  server = startServer();
  await waitForServer(URL, 90000);
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.route(STREAM_URL, async (route) => {
    const req = route.request();
    if (req.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: { ...corsHeaders },
        body: ""
      });
      return;
    }
    await route.fulfill({
      status: 200,
      headers: {
        ...corsHeaders,
        "Content-Type": "text/event-stream"
      },
      body: sseBody
    });
  });
  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  const composer = page.getByPlaceholder(/Ask about any team/);
  await composer.waitFor({ state: "visible", timeout: 60000 });
  await composer.fill("QA Fixture A points in the fixture slate?");
  const send = page.getByRole("button", { name: "Send" });
  await send.waitFor({ state: "visible", timeout: 30000 });
  await send.click();
  try {
    await page.getByText("QA Fixture A scored 12.3 points in the fixture slate.").waitFor({ state: "visible", timeout: 60000 });
  } catch {}
  try {
    const sourcesControl = page.getByText(/Sources & provenance/i).first();
    await sourcesControl.waitFor({ state: "visible", timeout: 15000 });
    await sourcesControl.click();
    await page.waitForTimeout(1000);
  } catch {}
  const bodyText = await page.locator("body").innerText();
  const bodyLower = bodyText.toLowerCase();
  const html = await page.content();
  const anchors = page.locator("a");
  const anchorCount = await anchors.count();
  let badBareHref = false;
  for (let i = 0; i < anchorCount; i++) {
    const href = await anchors.nth(i).getAttribute("href");
    if (href === "nba_api" || href === "espn") {
      badBareHref = true;
      break;
    }
  }
  let answerVisible = false;
  try {
    answerVisible = await page.getByText("QA Fixture A scored 12.3 points in the fixture slate.").isVisible();
  } catch {
    answerVisible = false;
  }
  check("fixture answer text is visible", answerVisible, "answer text not visible");
  let chartVisible = false;
  let chartValueBound = false;
  try {
    const artifactTitle = page.getByText("QA Fixture provenance chart", { exact: true });
    chartVisible = await artifactTitle.isVisible();
    const card = artifactTitle.locator("xpath=../..");
    const circle = card.locator('svg[aria-label="Scoring trend chart"] circle').first();
    const cy = Number(await circle.getAttribute("cy"));
    const expectedCy = 10 + (1 - (12.3 - 10) / 5) * (180 - 20);
    chartValueBound = Number.isFinite(cy) && Math.abs(cy - expectedCy) < 0.1;
  } catch {
    chartVisible = false;
  }
  check("chart artifact rendered", chartVisible, "chart title not visible");
  check("chart binds the fixture value", chartValueBound, "chart point geometry does not match value 12.3");
  const hasNba = bodyText.includes("nba_api");
  const hasEspn = bodyText.includes("espn");
  check("live sources rendered without bare hrefs", hasNba && hasEspn && !badBareHref, `nba_api=${hasNba} espn=${hasEspn} bareHref=${badBareHref}`);
  let exactCitationCount = 0;
  try {
    for (let i = 0; i < anchorCount; i++) {
      const href = await anchors.nth(i).getAttribute("href");
      if (href === "https://fixture.invalid/citation") exactCitationCount += 1;
    }
  } catch {
    exactCitationCount = 0;
  }
  check("citation link rendered with exact href", exactCitationCount >= 1, `exact citation anchors=${exactCitationCount}`);
  let jsCount = 0;
  try {
    jsCount = await page.locator('a[href^="javascript:"]').count();
  } catch {
    jsCount = 0;
  }
  const jsAbsent = !html.includes("javascript:alert(1)") && jsCount === 0;
  check("dangerous source not rendered", jsAbsent, "javascript:alert(1) found");
  const mentionsPartial = bodyLower.includes("partial");
  const hasBadVerification = bodyLower.includes("verified answer") || bodyLower.includes("all claims verified") || bodyLower.includes("fully checked");
  let verificationBound = false;
  try {
    const verificationStatus = page.getByText("Verification status: partial", { exact: true });
    const disclosure = await verificationStatus.locator("xpath=..").innerText();
    verificationBound = disclosure.includes("Verification status: partial") &&
      disclosure.includes("0 verified claims. 1 gap reported.");
  } catch {
    verificationBound = false;
  }
  check("verification disclosure", mentionsPartial && !hasBadVerification, `partial=${mentionsPartial} clean=${!hasBadVerification}`);
  check("verification bound to claim count", verificationBound, "verification status and claim count not bound in one element");
  let quotaVisible = false;
  try {
    quotaVisible = await page.getByText("Dime's model hit its usage limit. Your question is fine — try again in a little while.", { exact: true }).isVisible();
  } catch {
    quotaVisible = false;
  }
  const noLostConn = !bodyLower.includes("connection was lost");
  check("quota failure copy", quotaVisible && noLostConn, `quota=${quotaVisible} clean=${noLostConn}`);
} catch (e) {
  failures += 1;
  console.log(`FAIL: fixture setup - ${e && e.message ? e.message : String(e)}`);
} finally {
  if (browser) {
    await browser.close().catch(() => {});
  }
  if (server) {
    await new Promise((resolve) => {
      try {
        server.kill();
      } catch {}
      setTimeout(resolve, 2000);
    });
  }
}

process.exit(failures === 0 ? 0 : 1);
