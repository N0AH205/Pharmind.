import type { NextRequest } from "next/server";
import { STREAM_TRANSPORT_TIMEOUT_MS } from "./events";

export async function proxyResearchStream(req: NextRequest, endpoint: string, body: unknown) {
  try {
    const response = await fetch(`${process.env.BACKEND_URL || "http://localhost:8001"}${endpoint}`, {
      method: "POST",
      signal: AbortSignal.any([req.signal, AbortSignal.timeout(STREAM_TRANSPORT_TIMEOUT_MS)]),
      headers: { "Content-Type": "application/json", "X-Pharmind-Connection": req.headers.get("X-Pharmind-Connection") || "" },
      body: JSON.stringify(body), cache: "no-store",
    });
    if (!response.ok || !response.body) {
      const failure = await response.json().catch(() => null);
      return Response.json({ success: false, error: failure?.error || failure?.detail || `Backend returned HTTP ${response.status}.` }, { status: response.ok ? 502 : response.status });
    }
    return new Response(response.body, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no" } });
  } catch (error) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    return Response.json({ success: false, error: req.signal.aborted ? "Request stopped." : timedOut ? "The research request exceeded its time limit. Try a smaller model." : "Could not reach the local backend. Start Pharmind Local and retry." }, { status: timedOut ? 504 : 502 });
  }
}
