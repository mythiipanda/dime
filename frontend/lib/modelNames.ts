








const OVERRIDES: Record<string, string> = {
  "gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
  "gemini-3.5-flash": "Gemini 3.5 Flash",
  "z-ai/glm-5.3-flash": "GLM 5.3 Flash",
  "deepseek-ai/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
  "nvidia/nemotron-3-super-120b-a12b": "Nemotron 3 Super 120B",
  "nvidia/nemotron-3-ultra-550b-a55b": "Nemotron 3 Ultra 550B",
  "deepseek-ai/deepseek-r1": "DeepSeek R1",
  "openrouter/free": "Auto",
  "ministral-8b-2512": "Ministral 8B",
  "openai/gpt-oss-20b": "GPT-OSS 20B",
  "mercury-2.5": "Mercury 2.5",
};

const PROVIDERS: Record<string, string> = {
  gemini: "Gemini",
  nvidia: "NVIDIA",
  openrouter: "OpenRouter",
  mistral: "Mistral",
  groq: "Groq",
  inception: "Inception",
};



export function modelSlug(id: string): string {
  const i = id.indexOf(":");
  const slug = i >= 0 ? id.slice(i + 1) : id;
  return slug.replace(/:free$/, "");
}



export function modelEngine(id: string): string {
  const i = id.indexOf(":");
  return i >= 0 ? id.slice(0, i) : "";
}



export function modelDisplayName(id: string): string {
  const slug = modelSlug(id);
  const hit = OVERRIDES[slug];
  if (hit) return hit;
  const base = slug.split("/").pop() || slug;
  return base
    .split("-")
    .map((tok) => {
      if (/^[0-9]/.test(tok)) return tok.toUpperCase();
      if (/^[a-z]{2,3}$/.test(tok)) return tok.toUpperCase();
      if (/[0-9]/.test(tok)) return tok.toUpperCase();
      return tok.charAt(0).toUpperCase() + tok.slice(1);
    })
    .join(" ");
}



export function providerDisplayName(engine: string): string {
  return (
    PROVIDERS[engine] ||
    (engine ? engine.charAt(0).toUpperCase() + engine.slice(1) : "")
  );
}
