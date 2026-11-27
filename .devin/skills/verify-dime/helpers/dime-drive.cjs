#!/usr/bin/env node
"use strict";

const path = require("path");
const { execSync } = require("child_process");

function repoRoot() {
  return path.resolve(__dirname, "..", "..", "..", "..");
}

function loadPlaywright() {
  const root = repoRoot();
  try {
    return require(path.join(root, "frontend", "node_modules", "playwright"));
  } catch (err) {
    console.error("playwright not found at frontend/node_modules — run `npm ci` in frontend first");
    process.exit(2);
  }
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        args[key] = next;
        i++;
      } else {
        args[key] = true;
      }
    } else {
      args._.push(a);
    }
  }
  return args;
}

function cmdDoctor(args) {
  const backendPort = args["backend-port"] || "9910";
  const frontendPort = args["frontend-port"] || "3010";
  const report = { backend: {}, frontend: {}, ok: true };

  for (const [name, port, healthPath] of [
    ["backend", backendPort, "/api/health"],
    ["frontend", frontendPort, "/"],
  ]) {
    let pids = "";
    try {
      pids = execSync(`lsof -ti tcp:${port} 2>/dev/null || true`).toString().trim();
    } catch (_) {}
    if (!pids) {
      try {
        const ss = execSync(`ss -ltnp 2>/dev/null | grep -E ':${port} ' || true`).toString();
        const match = ss.match(/pid=(\d+)/);
        if (match) pids = match[1];
      } catch (_) {}
    }
    const entry = report[name];
    entry.port = port;
    if (!pids) {
      entry.listening = false;
      report.ok = false;
      continue;
    }
    entry.listening = true;
    const pid = pids.split("\n")[0];
    entry.pid = pid;
    try {
      entry.cwd = execSync(`readlink /proc/${pid}/cwd 2>/dev/null || echo unknown`).toString().trim();
    } catch (_) {
      entry.cwd = "unknown";
    }
    entry.expected_checkout = repoRoot();
    entry.owned_by_this_checkout =
      entry.cwd !== "unknown" && entry.cwd.startsWith(entry.expected_checkout);
  }

  const http = require("http");
  const probe = (port, p) =>
    new Promise((resolve) => {
      const req = http.get({ host: "127.0.0.1", port, path: p, timeout: 5000 }, (res) => {
        let body = "";
        res.on("data", (c) => (body += c));
        res.on("end", () => resolve({ status: res.statusCode, body: body.slice(0, 300) }));
      });
      req.on("error", (e) => resolve({ error: String(e.message || e) }));
      req.on("timeout", () => {
        req.destroy();
        resolve({ error: "timeout" });
      });
    });

  return (async () => {
    report.backend.health = await probe(backendPort, "/api/health");
    report.frontend.page = await probe(frontendPort, "/");
    if (!report.backend.health || report.backend.health.status !== 200) report.ok = false;
    if (!report.frontend.page || report.frontend.page.status !== 200) report.ok = false;
    console.log(JSON.stringify(report, null, 2));
    process.exit(report.ok ? 0 : 1);
  })();
}

async function withBrowser(args, fn) {
  const pw = loadPlaywright();
  const browser = await pw.chromium.launch({ args: ["--disable-web-security"] });
  try {
    const page = await browser.newPage({
      viewport: { width: parseInt(args.width || "1440", 10), height: parseInt(args.height || "900", 10) },
    });
    await fn(page);
  } finally {
    await browser.close();
  }
}

async function cmdShot(args) {
  if (!args.url || !args.out) {
    console.error("shot requires --url and --out");
    process.exit(2);
  }
  await withBrowser(args, async (page) => {
    await page.goto(args.url, { waitUntil: "networkidle", timeout: 30000 });
    if (args["wait-for"]) {
      await page.waitForSelector(args["wait-for"], { timeout: parseInt(args.timeout || "15000", 10) });
    }
    if (args["wait-text"]) {
      await page.waitForFunction(
        (t) => document.body.innerText.includes(t),
        args["wait-text"],
        { timeout: parseInt(args.timeout || "15000", 10) }
      );
    }
    if (args.settle) await page.waitForTimeout(parseInt(args.settle, 10));
    require("fs").mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
    await page.screenshot({ path: args.out, fullPage: !!args.full });
    console.log(`shot: ${args.out}`);
  });
}

async function cmdText(args) {
  if (!args.url) {
    console.error("text requires --url");
    process.exit(2);
  }
  await withBrowser(args, async (page) => {
    await page.goto(args.url, { waitUntil: "networkidle", timeout: 30000 });
    if (args["wait-for"]) {
      await page.waitForSelector(args["wait-for"], { timeout: parseInt(args.timeout || "15000", 10) });
    }
    const text = await page.evaluate(() => document.body.innerText);
    console.log(text);
  });
}

async function cmdInteract(args) {
  if (!args.url || !args.script) {
    console.error("interact requires --url and --script <steps.json>");
    process.exit(2);
  }
  const steps = JSON.parse(require("fs").readFileSync(args.script, "utf8"));
  await withBrowser(args, async (page) => {
    await page.goto(args.url, { waitUntil: "networkidle", timeout: 30000 });
    const transcript = [];
    for (const step of steps) {
      const timeout = parseInt(step.timeout || "15000", 10);
      if (step.click) {
        await page.click(step.click, { timeout });
        transcript.push(`click ${step.click} ok`);
      } else if (step.fill) {
        await page.fill(step.fill, step.value || "", { timeout });
        transcript.push(`fill ${step.fill} ok`);
      } else if (step.press) {
        await page.keyboard.press(step.press);
        transcript.push(`press ${step.press} ok`);
      } else if (step["wait-for"]) {
        await page.waitForSelector(step["wait-for"], { timeout });
        transcript.push(`wait-for ${step["wait-for"]} ok`);
      } else if (step["wait-text"]) {
        await page.waitForFunction((t) => document.body.innerText.includes(t), step["wait-text"], { timeout });
        transcript.push(`wait-text ${step["wait-text"]} ok`);
      } else if (step.shot) {
        require("fs").mkdirSync(path.dirname(path.resolve(step.shot)), { recursive: true });
        await page.screenshot({ path: step.shot, fullPage: !!step.full });
        transcript.push(`shot ${step.shot}`);
      } else if (step["assert-text"]) {
        const present = await page.evaluate((t) => document.body.innerText.includes(t), step["assert-text"]);
        transcript.push(`assert-text "${step["assert-text"]}" ${present ? "PASS" : "FAIL"}`);
        if (!present) {
          console.log(transcript.join("\n"));
          process.exit(1);
        }
      } else if (step["assert-absent"]) {
        const present = await page.evaluate((t) => document.body.innerText.includes(t), step["assert-absent"]);
        transcript.push(`assert-absent "${step["assert-absent"]}" ${present ? "FAIL" : "PASS"}`);
        if (present) {
          console.log(transcript.join("\n"));
          process.exit(1);
        }
      } else if (step.settle) {
        await page.waitForTimeout(parseInt(step.settle, 10));
      }
    }
    console.log(transcript.join("\n"));
  });
}

async function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  const args = parseArgs(rest);
  try {
    if (cmd === "doctor") await cmdDoctor(args);
    else if (cmd === "shot") await cmdShot(args);
    else if (cmd === "text") await cmdText(args);
    else if (cmd === "interact") await cmdInteract(args);
    else {
      console.error("usage: dime-drive.cjs <doctor|shot|text|interact> [--flags]");
      process.exit(2);
    }
  } catch (err) {
    console.error(`drive failure: ${err.message}`);
    process.exit(1);
  }
}

main();
