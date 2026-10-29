import { connectionHeaders } from "./connection";
import type { ChatMode, QueryRequest, QueryResponse } from "./types";

const API_BASE = "/api";

export async function queryDrug(smiles: string): Promise<QueryResponse> {
  const body: QueryRequest = { smiles };

  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...connectionHeaders() },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    return { success: false, error: text || "Request failed" };
  }

  return res.json();
}

export interface StreamCallbacks {
  onStatus?: (status: { stage: string; message: string }) => void;
  onToken?: (token: string) => void;
  onResult?: (data: any) => void;
  onError?: (error: string) => void;
}

export async function queryDrugStream(smiles: string, callbacks: StreamCallbacks) {
  try {
    const res = await fetch(`${API_BASE}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...connectionHeaders() },
      body: JSON.stringify({ smiles }),
    });

    if (!res.ok || !res.body) {
      callbacks.onError?.(`Server returned HTTP ${res.status}`);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ")) {
          const jsonStr = trimmed.slice(6);
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "status") {
              callbacks.onStatus?.({ stage: event.stage, message: event.message });
            } else if (event.type === "token") {
              callbacks.onToken?.(event.content);
            } else if (event.type === "result") {
              callbacks.onResult?.(event.data);
            } else if (event.type === "error") {
              callbacks.onError?.(event.message);
            }
          } catch {}
        }
      }
    }
  } catch (err: any) {
    callbacks.onError?.(err.message || "Network connection error");
  }
}

export async function sendChatMessage(
  question: string,
  history: { role: "user" | "assistant"; content: string }[] = [],
  activeDrug: { name: string; cid?: string } = { name: "" },
  mode: ChatMode = "structure_science",
) {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...connectionHeaders() },
      body: JSON.stringify({ question, history, active_drug: { name: activeDrug.name, cid: activeDrug.cid ?? null }, mode }),
    });
    if (!res.ok) {
      const errText = await res.text();
      return { success: false, error: errText || `HTTP ${res.status}` };
    }
    return res.json();
  } catch {
    return { success: false, error: "Could not reach the local backend. Start it and try again." };
  }
}

export async function uploadPDF(file: File, drugName: string = "") {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload-pdf?drug_name=${encodeURIComponent(drugName)}`, {
    method: "POST",
    body: formData,
    headers: connectionHeaders(),
  });

  if (!res.ok) {
    const errText = await res.text();
    return { success: false, error: errText || `HTTP ${res.status}` };
  }

  return res.json();
}

export async function getUploadedPDFs() {
  const res = await fetch(`${API_BASE}/uploaded-pdfs`);
  if (!res.ok) {
    const errText = await res.text();
    return { success: false, error: errText || `HTTP ${res.status}` };
  }
  return res.json();
}

export async function deleteUploadedPDF(filename: string) {
  const res = await fetch(`${API_BASE}/uploaded-pdfs/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const errText = await res.text();
    return { success: false, error: errText || `HTTP ${res.status}` };
  }
  return res.json();
}
