
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  modelSlug,
  modelEngine,
  modelDisplayName,
  providerDisplayName,
} from "./modelNames";

test("modelSlug strips the engine prefix and :free suffix", () => {
  assert.equal(
    modelSlug("openrouter:nvidia/nemotron-3-super-120b-a12b:free"),
    "nvidia/nemotron-3-super-120b-a12b"
  );
  assert.equal(modelSlug("nvidia:z-ai/glm-5.3-flash"), "z-ai/glm-5.3-flash");
  assert.equal(modelSlug("bare-id"), "bare-id");
});

test("modelEngine returns the engine prefix", () => {
  assert.equal(modelEngine("nvidia:z-ai/glm-5.3-flash"), "nvidia");
  assert.equal(modelEngine("bare-id"), "");
});

test("modelDisplayName maps known catalog slugs to friendly names", () => {
  const cases: Array<[string, string]> = [
    ["gemini:gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite"],
    ["gemini:gemini-3.5-flash", "Gemini 3.5 Flash"],
    ["nvidia:z-ai/glm-5.3-flash", "GLM 5.3 Flash"],
    ["nvidia:deepseek-ai/deepseek-v4.1-flash", "DeepSeek V4.1 Flash"],
    [
      "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
      "Nemotron 3 Super 120B",
    ],
    [
      "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free",
      "Nemotron 3 Ultra 550B",
    ],
    ["nvidia:deepseek-ai/deepseek-v4.1-flash", "DeepSeek V4.1 Flash"],
    ["nvidia:deepseek-ai/deepseek-r1", "DeepSeek R1"],
    ["openrouter:openrouter/free", "Auto"],
    ["mistral:ministral-8b-2512", "Ministral 8B"],
    ["groq:openai/gpt-oss-20b", "GPT-OSS 20B"],
    ["inception:mercury-2.5", "Mercury 2.5"],
  ];
  for (const [id, expected] of cases) {
    assert.equal(modelDisplayName(id), expected, `id=${id}`);
  }
});

test("modelDisplayName prettifies unknown slugs instead of echoing them", () => {
  assert.equal(
    modelDisplayName("nvidia:moonshotai/kimi-k2-thinking"),
    "Kimi K2 Thinking"
  );
  assert.ok(!/[:/]/.test(modelDisplayName("openrouter:some-org/future-model-2")));
});

test("providerDisplayName maps known engines and capitalizes unknown ones", () => {
  assert.equal(providerDisplayName("gemini"), "Gemini");
  assert.equal(providerDisplayName("nvidia"), "NVIDIA");
  assert.equal(providerDisplayName("openrouter"), "OpenRouter");
  assert.equal(providerDisplayName("mistral"), "Mistral");
  assert.equal(providerDisplayName("groq"), "Groq");
  assert.equal(providerDisplayName("inception"), "Inception");
  assert.equal(providerDisplayName("newengine"), "Newengine");
  assert.equal(providerDisplayName(""), "");
});
