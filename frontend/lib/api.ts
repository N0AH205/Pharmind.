import { readEvents, STREAM_TRANSPORT_TIMEOUT_MS } from "./events";
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
  onClarification?: (data: { message: string; suggestions: { query: string; label: string }[] }) => void;
  onStatus?: (status: { stage: string; message: string }) => void;
  onToken?: (token: string) => void;
  onResult?: (data: any) => void;
  onCheckpoint?: (data: any) => void;
  onWarning?: (warning: string) => void;
  onError?: (error: string) => void;
}

export async function queryDrugStream(smiles: string, callbacks: StreamCallbacks, signal?: AbortSignal) {
  const timeout = AbortSignal.timeout(STREAM_TRANSPORT_TIMEOUT_MS);
  let finished = false;
  try {
    const res = await fetch(`${API_BASE}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...connectionHeaders() },
      body: JSON.stringify({ smiles }),
      signal: AbortSignal.any([...(signal ? [signal] : []), timeout]),
    });

    if (!res.ok || !res.body) {
      callbacks.onError?.(await responseError(res));
      return;
    }

    await readEvents(res.body, event => {
      if (event.type === "status") callbacks.onStatus?.({ stage: event.stage, message: event.message });
      else if (event.type === "token") callbacks.onToken?.(event.content);
      else if (event.type === "checkpoint") callbacks.onCheckpoint?.(event.data);
      else if (event.type === "warning") callbacks.onWarning?.(event.message);
      else if (event.type === "clarification") { finished = true; callbacks.onClarification?.(event); return false; }
      else if (event.type === "result") { finished = true; callbacks.onResult?.(event.data); return false; }
      else if (event.type === "error") { finished = true; callbacks.onError?.(event.message); return false; }
    });
    if (!finished) callbacks.onError?.("The connection closed before research finished. Any saved initial profile is still available. Please retry the query.");
  } catch (error) {
    if (!finished) callbacks.onError?.(signal?.aborted ? "Request stopped." : timeout.aborted ? "Research exceeded its time limit. Try a smaller model. Any saved initial profile is still available." : error instanceof SyntaxError ? "The backend sent an incomplete research response. Any saved initial profile is still available." : "The connection to the local backend was interrupted. Check that Pharmind is still running. Any saved initial profile is still available.");
  }
}

export async function sendChatMessage(
  question: string,
  history: { role: "user" | "assistant"; content: string }[] = [],
  activeDrug: { name: string; cid?: string } = { name: "" },
  mode: ChatMode = "structure_science",
  options: { documentId?: string; signal?: AbortSignal; onStatus?: (message: string) => void } = {},
) {
  const timeout = AbortSignal.timeout(STREAM_TRANSPORT_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...connectionHeaders() },
      body: JSON.stringify({ question, history, active_drug: { name: activeDrug.name, cid: activeDrug.cid ?? null }, mode, document_id: options.documentId }),
      signal: AbortSignal.any([...(options.signal ? [options.signal] : []), timeout]),
    });
    if (!res.ok) {
      return { success: false, error: await responseError(res) };
    }
    if (!res.body) return { success: false, error: "The backend returned no answer stream." };
    let result: any = null;
    await readEvents(res.body, event => {
      if (event.type === "status") options.onStatus?.(event.message);
      if (event.type === "result") { result = event.data; return false; }
      if (event.type === "error") { result = { success: false, error: event.message }; return false; }
    });
    return result || { success: false, error: "The connection closed before the answer was complete. Please retry your question." };
  } catch {
    if (options.signal?.aborted) return { success: false, error: "Request stopped." };
    return { success: false, error: timeout.aborted ? "Research exceeded its time limit. Try a smaller model or a more focused question." : "The connection to the local backend was interrupted. Check that Pharmind is still running and retry." };
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
