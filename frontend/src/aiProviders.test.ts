import { describe, expect, it } from "vitest";
import { providerById, providersForLocation } from "./aiProviders";

describe("AI provider catalog", () => {
  it("offers major local OpenAI-compatible runtimes in addition to Ollama", () => {
    const names = providersForLocation("local").map(provider => provider.name);
    expect(names).toEqual(expect.arrayContaining([
      "Ollama", "LM Studio", "llama.cpp", "vLLM", "LocalAI", "Jan", "Hugging Face TGI", "LiteLLM",
    ]));
    expect(providersForLocation("local").filter(provider => provider.baseUrl).every(provider => /localhost|127\.0\.0\.1/.test(provider.baseUrl))).toBe(true);
  });

  it("provides HTTPS presets for supported hosted providers", () => {
    const names = providersForLocation("online").map(provider => provider.name);
    expect(names).toEqual(expect.arrayContaining(["OpenAI", "OpenRouter", "Groq", "Together AI"]));
    expect(providersForLocation("online").filter(provider => provider.baseUrl).every(provider => provider.baseUrl.startsWith("https://"))).toBe(true);
  });

  it("returns a stable custom provider fallback", () => {
    expect(providerById("custom-local").baseUrl).toBe("");
    expect(providerById("missing").id).toBe("custom-local");
  });

  it("includes English and Indonesian guidance for every provider", () => {
    const providers = [...providersForLocation("local"), ...providersForLocation("online")];
    expect(providers.every(provider => provider.note.trim() && provider.noteId.trim())).toBe(true);
  });
});
