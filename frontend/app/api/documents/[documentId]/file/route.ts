import { NextRequest } from "next/server";

export async function GET(req: NextRequest, { params }: { params: Promise<{ documentId: string }> }) {
  const { documentId } = await params;
  try {
    const response = await fetch(`${process.env.BACKEND_URL || "http://localhost:8001"}/documents/${encodeURIComponent(documentId)}/file`, { signal: req.signal, cache: "no-store" });
    if (!response.ok) return new Response("Original PDF is unavailable. Re-upload older papers to enable viewing.", { status: response.status });
    return new Response(response.body, { headers: { "Content-Type": "application/pdf", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" } });
  } catch {
    return new Response("The local document service is unavailable.", { status: 502 });
  }
}
