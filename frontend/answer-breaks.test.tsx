import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import AnswerText from "./components/AnswerText";

const FOUR_LINES = [
  "Boston leads the East at 9.4 net rating.",
  "The gap over Milwaukee is 1.8 points per 100 possessions.",
  "Live data updates every few minutes.",
  "Small samples can swing the gap.",
].join("\n");

describe("AnswerText line breaks", () => {
  it("multi-line answer preserves line breaks like streaming", () => {
    const html = renderToStaticMarkup(React.createElement(AnswerText, { text: FOUR_LINES }));
    for (const line of FOUR_LINES.split("\n")) {
      assert.ok(html.includes(line));
    }
    assert.ok(html.includes("<br") || html.includes("pre-wrap"));
  });
});
