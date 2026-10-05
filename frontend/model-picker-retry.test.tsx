import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ModelPicker from "./components/ModelPicker";

describe("model picker retry state", () => {
  it("renders a retry button when the list fails empty", () => {
    const html = renderToStaticMarkup(
      React.createElement(ModelPicker, {
        models: [],
        value: null,
        onChange: () => {},
        status: "error",
        onRetry: () => {},
      }),
    );
    assert.ok(html.includes("Retry loading models"));
  });

  it("keeps the trigger usable when models exist despite the error", () => {
    const html = renderToStaticMarkup(
      React.createElement(ModelPicker, {
        models: [
          { id: "gemini:gemini-3.5-flash-lite", engine: "gemini", available: true },
        ],
        value: "gemini:gemini-3.5-flash-lite",
        onChange: () => {},
        status: "error",
        onRetry: () => {},
      }),
    );
    assert.ok(html.includes("Gemini 3.5 Flash Lite"));
  });

  it("shows loading copy while fetching", () => {
    const html = renderToStaticMarkup(
      React.createElement(ModelPicker, {
        models: [],
        value: null,
        onChange: () => {},
        status: "loading",
      }),
    );
    assert.ok(html.includes("Loading models"));
  });
});
