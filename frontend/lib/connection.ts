export type Provider = "ollama" | "openai" | "anthropic" | "gemini";
export interface ModelConnection {
  provider: Provider;
  model: string;
  api_key: string;
  base_url: string;
  online_sources: boolean;
}

export const DEFAULT_CONNECTION: ModelConnection = {
  provider: "ollama", model: "qwen2.5:3b", api_key: "",
  base_url: "http://localhost:11434", online_sources: false,
};
export const PROVIDERS = {
  ollama: { name: "Ollama", model: "qwen2.5:3b" },
  openai: { name: "OpenAI", model: "" },
  anthropic: { name: "Anthropic", model: "" },
  gemini: { name: "Google Gemini", model: "" },
};
const STORAGE_KEY = "pharmind_connection_v1";

export function getConnection(): ModelConnection {
  if (typeof window === "undefined") return DEFAULT_CONNECTION;
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    if (saved && Object.hasOwn(PROVIDERS, saved.provider) && typeof saved.model === "string") {
      return { ...DEFAULT_CONNECTION, ...saved };
    }
  } catch { /* Storage may be disabled in private browsing. */ }
  return DEFAULT_CONNECTION;
}

export function saveConnection(connection: ModelConnection) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(connection));
}

export function clearConnection() {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function connectionHeaders(connection = getConnection()): Record<string, string> {
  return { "X-Pharmind-Connection": JSON.stringify(connection) };
}
