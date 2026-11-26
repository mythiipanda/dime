import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadSkillTool } from "./dist/pi-context.js";

function fixtureSkill() {
    const dir = mkdtempSync(join(tmpdir(), "dime-skill-"));
    const filePath = join(dir, "warehouse-guide.md");
    writeFileSync(filePath, "# warehouse guide\nfull skill body");
    return { name: "warehouse-guide", filePath };
}

test("load_skill returns full content once, then an already-loaded notice", async () => {
    const skill = fixtureSkill();
    const tool = loadSkillTool([skill]);
    const first = await tool.execute("c1", { name: "warehouse-guide" });
    assert(first.structuredContent.content.includes("full skill body"));
    const second = await tool.execute("c2", { name: "warehouse-guide" });
    assert(!second.structuredContent.content.includes("full skill body"));
    assert(second.structuredContent.content.includes("already loaded"));
    assert(second.structuredContent.ok === true);
    const third = await tool.execute("c3", { name: "Warehouse-Guide" });
    assert(third.structuredContent.content.includes("full skill body"));
});

test("load_skill unknown-skill path is unaffected by the idempotence cache", async () => {
    const skill = fixtureSkill();
    const tool = loadSkillTool([skill]);
    await tool.execute("c1", { name: "warehouse-guide" });
    const miss = await tool.execute("c2", { name: "nonexistent" });
    assert(miss.structuredContent.ok === false);
    assert(miss.structuredContent.content.includes("Unknown skill"));
});
