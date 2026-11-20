import assert from "node:assert/strict";
import test from "node:test";
import { memoPdfLines, memoToPdfBlob } from "./stream/memo-pdf";
import type { MemoArtifactPayload } from "./stream/types";

const memo: MemoArtifactPayload = {
  kind: "memo",
  title: "Cap & roster strategy",
  subtitle: "Owner briefing",
  sections: [
    { heading: "Cap position", body: "Orlando sits under the first apron with a locked core.", anchors: [{ ref: "src-1", row: 0, columns: ["payroll"] }] },
    { heading: "Trade options", body: "Aggregate mid-tier salary for a wing." },
  ],
  footnote: "Sources: silver_salaries",
  source: "warehouse",
};

test("memoPdfLines keeps title, subtitle, sections, citations and footnote", () => {
  const lines = memoPdfLines(memo);
  assert.equal(lines[0].text, "Cap & roster strategy");
  assert.equal(lines[0].style, "title");
  assert.deepEqual(lines.map(l => l.style).includes("subtitle"), true);
  assert.equal(lines.find(l => l.style === "heading")?.text, "Cap position");
  const citation = lines.find(l => l.text.startsWith("Cited rows:"));
  assert.equal(citation?.text, "Cited rows: src-1 row 0");
  assert.equal(lines.at(-1)?.text, "Source: warehouse");
});

test("memoToPdfBlob produces a PDF with page content", () => {
  const blob = memoToPdfBlob(memo);
  assert.equal(blob.type, "application/pdf");
  assert.ok(blob.size > 1000);
});
