import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errs = [];
page.on("console", (m) => m.type() === "error" && errs.push(m.text()));
page.on("pageerror", (e) => errs.push(`pageerror: ${e.message}`));
await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

const body = () => page.locator("body").innerText();
const check = (name, pass, detail = "") =>
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

let t = await body();
check("initial tab shows the sample", /Sample analysis/.test(t));
check("initial tab has no raw table names", !/silver_/.test(t), (t.match(/silver_\w+/g) ?? []).join(","));

const railMarkCenter = async () =>
  page.evaluate(() => {
    const aside = document.querySelector("aside");
    const rail = aside.getBoundingClientRect();
    const btn = aside.querySelector('[aria-label="Expand sidebar"]');
    if (!btn) return null;
    const r = btn.getBoundingClientRect();
    return {
      railCx: Math.round(rail.x + rail.width / 2),
      btnCx: Math.round(r.x + r.width / 2),
      railW: Math.round(rail.width),
      btnW: Math.round(r.width),
    };
  });

await page.locator('[aria-label="Collapse sidebar"]').click();
await page.waitForTimeout(700);
const geom = await railMarkCenter();
check(
  "collapsed mark is centered",
  geom && Math.abs(geom.railCx - geom.btnCx) <= 1,
  JSON.stringify(geom),
);
const dupExpand = await page.locator('[aria-label="Expand sidebar"]').count();
check("exactly one expand control", dupExpand === 1, `count=${dupExpand}`);
const dupCollapse = await page.locator('[aria-label="Collapse sidebar"]').count();
check("collapse control absent while collapsed", dupCollapse === 0, `count=${dupCollapse}`);
await page.screenshot({ path: "/tmp/v-collapsed.png" });

await page.locator('[aria-label="Expand sidebar"]').click();
await page.waitForTimeout(700);

await page.locator('[aria-label="New tab"]').click();
await page.waitForTimeout(400);
t = await body();
check("new tab is empty", !/Sample analysis/.test(t) && !/League scoring/.test(t));

await page.locator('button:has-text("New analysis")').first().click();
await page.waitForTimeout(400);
t = await body();
check("New analysis gives empty chat", !/Sample analysis/.test(t));

await page.locator("textarea").first().fill("How many assists per game did Trae Young average in the 2023-24 season?");
await page.locator("textarea").first().press("Enter");
let answered = false;
for (let i = 0; i < 45; i += 1) {
  t = await body();
  if (/10\.8|Trae Young averaged/i.test(t)) { answered = true; break; }
  await page.waitForTimeout(3000);
}
check("live chat answers in the browser", answered);
check("no raw table names after live answer", !/silver_/.test(t), (t.match(/silver_\w+/g) ?? []).join(","));
await page.screenshot({ path: "/tmp/v-answered.png" });

const tiny = await page.evaluate(() => {
  const bad = [];
  for (const el of document.querySelectorAll("button,a")) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.width < 24 || r.height < 24))
      bad.push(`${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 24)} ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  return bad;
});
check("no sub-24px hit targets", tiny.length === 0, tiny.join(" | "));
check("no console errors", errs.length === 0, errs.slice(0, 3).join(" | "));

await browser.close();