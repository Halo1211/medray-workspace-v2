export type ProviderLocation = "local" | "online";
export type ProviderCapability = "vision" | "chat" | "report";

export interface AIProviderPreset {
  id: string;
  name: string;
  location: ProviderLocation;
  backend: "ollama" | "openai-compatible";
  baseUrl: string;
  docsUrl?: string;
  capabilities: ProviderCapability[];
  note: string;
  noteId: string;
}

export const aiProviderPresets: AIProviderPreset[] = [
  { id: "ollama", name: "Ollama", location: "local", backend: "ollama", baseUrl: "http://127.0.0.1:11434", docsUrl: "https://ollama.com/download", capabilities: ["vision", "chat", "report"], note: "Native Ollama API; image review requires a vision-capable model.", noteId: "API Ollama native; tinjauan gambar memerlukan model yang mendukung visi." },
  { id: "lm-studio", name: "LM Studio", location: "local", backend: "openai-compatible", baseUrl: "http://127.0.0.1:1234/v1", docsUrl: "https://lmstudio.ai/docs/developer/rest", capabilities: ["vision", "chat", "report"], note: "Start the local server and load a model in LM Studio first.", noteId: "Jalankan server lokal dan muat model di LM Studio terlebih dahulu." },
  { id: "llama-cpp", name: "llama.cpp", location: "local", backend: "openai-compatible", baseUrl: "http://127.0.0.1:8080/v1", docsUrl: "https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md", capabilities: ["vision", "chat", "report"], note: "Multimodal input depends on the loaded model and mmproj configuration.", noteId: "Masukan multimodal bergantung pada model yang dimuat dan konfigurasi mmproj." },
  { id: "vllm", name: "vLLM", location: "local", backend: "openai-compatible", baseUrl: "http://127.0.0.1:8000/v1", docsUrl: "https://docs.vllm.ai/en/latest/serving/openai_compatible_server/", capabilities: ["vision", "chat", "report"], note: "Use an image-capable model for vision; protect externally exposed servers with a reverse proxy.", noteId: "Gunakan model yang mendukung gambar untuk visi; lindungi server yang dibuka ke jaringan dengan reverse proxy." },
  { id: "localai", name: "LocalAI", location: "local", backend: "openai-compatible", baseUrl: "http://127.0.0.1:8080/v1", docsUrl: "https://localai.io/basics/getting_started/", capabilities: ["vision", "chat", "report"], note: "OpenAI-compatible local runtime with model-specific multimodal support.", noteId: "Runtime lokal kompatibel OpenAI dengan dukungan multimodal yang bergantung pada model." },
  { id: "jan", name: "Jan", location: "local", backend: "openai-compatible", baseUrl: "http://127.0.0.1:1337/v1", docsUrl: "https://jan.ai/docs/api-server", capabilities: ["vision", "chat", "report"], note: "Enable Jan's local API server and load a compatible model.", noteId: "Aktifkan server API lokal Jan dan muat model yang kompatibel." },
  { id: "tgi", name: "Hugging Face TGI", location: "local", backend: "openai-compatible", baseUrl: "http://127.0.0.1:8080/v1", docsUrl: "https://huggingface.co/docs/text-generation-inference/en/messages_api", capabilities: ["chat", "report"], note: "Chat and report support depends on the model's chat template; use another runtime for VLM unless image input is exposed.", noteId: "Dukungan percakapan dan laporan bergantung pada templat chat model; gunakan runtime lain untuk VLM kecuali masukan gambar tersedia." },
  { id: "litellm", name: "LiteLLM", location: "local", backend: "openai-compatible", baseUrl: "http://127.0.0.1:4000/v1", docsUrl: "https://docs.litellm.ai/docs/proxy/quick_start", capabilities: ["vision", "chat", "report"], note: "Gateway for many upstream providers; actual capabilities and privacy follow the selected upstream model.", noteId: "Gerbang untuk banyak penyedia upstream; kemampuan dan privasi mengikuti model upstream yang dipilih." },
  { id: "custom-local", name: "Other compatible / VLM server", location: "local", backend: "openai-compatible", baseUrl: "", capabilities: ["vision", "chat", "report"], note: "Any server exposing OpenAI-compatible /models and /chat/completions endpoints can be tested.", noteId: "Server apa pun yang menyediakan endpoint /models dan /chat/completions kompatibel OpenAI dapat diuji." },
  { id: "openai", name: "OpenAI", location: "online", backend: "openai-compatible", baseUrl: "https://api.openai.com/v1", docsUrl: "https://platform.openai.com/docs/api-reference", capabilities: ["vision", "chat", "report"], note: "Capabilities depend on the model selected from the provider account.", noteId: "Kemampuan bergantung pada model yang dipilih dari akun penyedia." },
  { id: "openrouter", name: "OpenRouter", location: "online", backend: "openai-compatible", baseUrl: "https://openrouter.ai/api/v1", docsUrl: "https://openrouter.ai/docs/quickstart", capabilities: ["vision", "chat", "report"], note: "Gateway to many hosted models; review the chosen upstream provider's privacy and data policy.", noteId: "Gerbang ke banyak model daring; periksa kebijakan privasi dan data penyedia upstream yang dipilih." },
  { id: "groq", name: "Groq", location: "online", backend: "openai-compatible", baseUrl: "https://api.groq.com/openai/v1", docsUrl: "https://console.groq.com/docs/openai", capabilities: ["vision", "chat", "report"], note: "OpenAI-compatible hosted inference; supported inputs vary by model.", noteId: "Inferensi daring kompatibel OpenAI; jenis masukan yang didukung berbeda menurut model." },
  { id: "together", name: "Together AI", location: "online", backend: "openai-compatible", baseUrl: "https://api.together.ai/v1", docsUrl: "https://docs.together.ai/docs/inference/openai-compatibility", capabilities: ["vision", "chat", "report"], note: "Use the provider/model identifier shown by Together; vision support is model-specific.", noteId: "Gunakan pengenal penyedia/model dari Together; dukungan visi bergantung pada model." },
  { id: "custom-online", name: "Other OpenAI-compatible provider", location: "online", backend: "openai-compatible", baseUrl: "", capabilities: ["vision", "chat", "report"], note: "Remote endpoints must use HTTPS. Review the provider's privacy policy before sending case data.", noteId: "Endpoint jarak jauh wajib memakai HTTPS. Periksa kebijakan privasi penyedia sebelum mengirim data kasus." },
];

export function providersForLocation(location: ProviderLocation) {
  return aiProviderPresets.filter(provider => provider.location === location);
}

export function providerById(id: string) {
  return aiProviderPresets.find(provider => provider.id === id)
    || aiProviderPresets.find(provider => provider.id === "custom-local")!;
}
