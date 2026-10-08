import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errs = [];
page.on("console", (m) => m.type() === "error" && errs.push(m.text()));
page.on("pageerror", (e) => errs.push(`pageerror: ${e.message}`));
await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

const check = (n, pass, d = "") => console.log(`${pass ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

const trigger = page.locator('button[aria-haspopup="listbox"]');
check("picker trigger exists", (await trigger.count()) === 1);
check("defaults to Auto", (await trigger.innerText()).trim() === "Auto",
  (await trigger.innerText()).trim());

await trigger.click();
await page.waitForTimeout(350);
const list = page.locator('[role="listbox"]');
check("listbox opens", (await list.count()) === 1);
await page.screenshot({ path: "/tmp/p-open.png" });

const options = await page.locator('[role="option"]').allInnerTexts();
check("lists every catalog model", options.length >= 10, `${options.length} options`);
check("groups by provider", /Cerebras/i.test(await list.innerText()) && /Gemini/i.test(await list.innerText()));
check("Automatic is the first option", options[0].trim().startsWith("Automatic"), options[0]);
check("default is marked", /default/i.test(await list.innerText()));

const cerebras = page.locator('[role="option"]', { hasText: "gpt-oss-120b" }).first();
await cerebras.click();
await page.waitForTimeout(300);
check("selecting closes the list", (await page.locator('[role="listbox"]').count()) === 0);
check("trigger shows the choice", (await trigger.innerText()).includes("gpt-oss-120b"),
  (await trigger.innerText()).trim());

await trigger.click();
await page.waitForTimeout(250);
await page.keyboard.press("Escape");
await page.waitForTimeout(250);
check("escape closes the list", (await page.locator('[role="listbox"]').count()) === 0);
check("focus returns to the trigger",
  await page.evaluate(() => document.activeElement?.getAttribute("aria-haspopup") === "listbox"));

await trigger.click();
await page.waitForTimeout(250);
await page.keyboard.press("ArrowDown");
await page.waitForTimeout(150);
const activeText = await page.evaluate(() => {
  const rows = [...document.querySelectorAll('[role="option"]')];
  return rows.find((r) => r.className.includes("bg-hover"))?.textContent?.trim() ?? "";
});
check("arrow keys move the highlight", activeText.length > 0, activeText.slice(0, 40));
await page.screenshot({ path: "/tmp/p-keyboard.png" });

await page.keyboard.press("Escape");
await page.locator('button[aria-haspopup="listbox"]').click();
await page.waitForTimeout(200);
await page.locator('[role="option"]', { hasText: "Automatic" }).first().click();
await page.waitForTimeout(250);
check("back to Automatic", (await trigger.innerText()).trim() === "Auto");

const box = await trigger.boundingBox();
check("trigger is a real hit target", box.height >= 24, `${Math.round(box.width)}x${Math.round(box.height)}`);

await trigger.click();
await page.waitForTimeout(300);
const overflow = await page.evaluate(() => {
  const el = document.querySelector('[role="listbox"]');
  if (!el) return "no listbox open";
  const r = el.getBoundingClientRect();
  return r.left < 0 || r.top < 0 || r.right > window.innerWidth + 2
      || r.bottom > window.innerHeight + 2
    ? `left=${Math.round(r.left)} top=${Math.round(r.top)} right=${Math.round(r.right)} bottom=${Math.round(r.bottom)} vp=${window.innerWidth}x${window.innerHeight}` : "";
});
check("menu stays inside the viewport", overflow === "", overflow);
await page.keyboard.press("Escape");
check("no console errors", errs.length === 0, errs.slice(0, 3).join(" | "));

await trigger.click();
await page.waitForTimeout(300);
const scroll = await page.evaluate(() => {
  const el = document.querySelector('[role="listbox"]');
  return { capped: el.scrollHeight > el.clientHeight + 2,
           h: Math.round(el.getBoundingClientRect().height) };
});
check("long catalog scrolls instead of overflowing", scroll.capped, JSON.stringify(scroll));

await page.locator('[role="option"]', { hasText: "qwen-3.8-27b" }).first().click();
await page.waitForTimeout(250);
check("selection is reflected in the trigger",
  (await trigger.innerText()).includes("qwen-3.8-27b"));

await page.locator("textarea").first()
  .fill("How many assists per game did Trae Young average in the 2023-24 season?");
await page.locator("textarea").first().press("Enter");
let answered = false;
for (let i = 0; i < 90; i += 1) {
  const body = await page.locator("body").innerText();
  if (/10\.8/.test(body) && !/could not verify/i.test(body)) { answered = true; break; }
  if (/Could not reach|timed out|could not verify a publishable/i.test(body)) {
    console.log("  stopped early:", body.split("\n").find((l) => /could not|timed out/i.test(l)));
    break;
  }
  await page.waitForTimeout(3000);
}
const finalText = await page.locator("body").innerText();
const line = finalText.split("\n").filter((l) => /Trae Young/i.test(l) && l.length > 40)[0] ?? "";
check("the chosen model answers a real question", answered, line.trim().slice(0, 70));
await page.screenshot({ path: "/tmp/p-final.png" });

await browser.close();