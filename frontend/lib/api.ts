import { readEvents } from "./events";
import { connectionHeaders } from "./connection";
import type { ChatMode, QueryRequest, QueryResponse } from "./types";

const API_BASE = "/api";

async function responseError(response: Response) {
  const body = await response.json().catch(() => null);
  return typeof body?.error === "string" ? body.error : typeof body?.detail === "string" ? body.detail : `Request failed (HTTP ${response.status}).`;
}

export async function queryDrug(smiles: string): Promise<QueryResponse> {
  const body: QueryRequest = { smiles };

  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...connectionHeaders() },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    return { success: false, error: await responseError(res) };
  }

  return res.json();
}

export interface StreamCallbacks {
  onStatus?: (status: { stage: string; message: string }) => void;
  onToken?: (token: string) => void;
  onResult?: (data: any) => void;
  onError?: (error: string) => void;
}

export async function queryDrugStream(smiles: string, callbacks: StreamCallbacks, signal?: AbortSignal) {
  try {
    const res = await fetch(`${API_BASE}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...connectionHeaders() },
      body: JSON.stringify({ smiles }),
      signal: AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout(15 * 60 * 1000)]),
    });

    if (!res.ok || !res.body) {
      callbacks.onError?.(await responseError(res));
      return;
    }

    let finished = false;
    await readEvents(res.body, event => {
      if (event.type === "status") callbacks.onStatus?.({ stage: event.stage, message: event.message });
      else if (event.type === "token") callbacks.onToken?.(event.content);
      else if (event.type === "result") { finished = true; callbacks.onResult?.(event.data); }
      else if (event.type === "error") { finished = true; callbacks.onError?.(event.message); }
    });
    if (!finished) callbacks.onError?.("The response ended before a complete profile arrived. Please retry.");
  } catch (err: any) {
    callbacks.onError?.(signal?.aborted ? "Request stopped." : err.name === "TimeoutError" ? "The model took too long. Try a smaller model or a shorter question." : err.message || "Network connection error");
  }
}

export async function sendChatMessage(
  question: string,
  history: { role: "user" | "assistant"; content: string }[] = [],
  activeDrug: { name: string; cid?: string } = { name: "" },
  mode: ChatMode = "structure_science",
  options: { documentId?: string; signal?: AbortSignal } = {},
) {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...connectionHeaders() },
      body: JSON.stringify({ question, history, active_drug: { name: activeDrug.name, cid: activeDrug.cid ?? null }, mode, document_id: options.documentId }),
      signal: AbortSignal.any([...(options.signal ? [options.signal] : []), AbortSignal.timeout(5 * 60 * 1000)]),
    });
    if (!res.ok) {
      return { success: false, error: await responseError(res) };
    }
    return res.json();
  } catch {
    if (options.signal?.aborted) return { success: false, error: "Request stopped." };
    return { success: false, error: "Request failed or timed out. Could not reach the local backend. Start it and try again." };
  }
}

export async function uploadPDF(file: File, drugName: string = "", replaceDocumentId?: string) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload-pdf?drug_name=${encodeURIComponent(drugName)}${replaceDocumentId ? `&replace_document_id=${encodeURIComponent(replaceDocumentId)}` : ""}`, {
    method: "POST",
    body: formData,
    headers: connectionHeaders(),
  });

  if (!res.ok) {
    return { success: false, error: await responseError(res) };
  }

  return res.json();
}

export async function getUploadedPDFs() {
  const res = await fetch(`${API_BASE}/uploaded-pdfs`);
  if (!res.ok) {
    return { success: false, error: await responseError(res) };
  }
  return res.json();
}

export async function deleteUploadedPDF(documentId: string) {
  const res = await fetch(`${API_BASE}/uploaded-pdfs/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    return { success: false, error: await responseError(res) };
  }
  return res.json();
}
