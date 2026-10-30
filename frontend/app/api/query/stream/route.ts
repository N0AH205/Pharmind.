import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);

  if (!body?.smiles || typeof body.smiles !== "string") {
    return new Response(JSON.stringify({ error: "Missing 'smiles' parameter" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";

  try {
    const backendRes = await fetch(`${backendUrl}/query/stream`, {
      method: "POST",
      signal: AbortSignal.any([req.signal, AbortSignal.timeout(15 * 60 * 1000)]),
      headers: { "Content-Type": "application/json", "X-Pharmind-Connection": req.headers.get("X-Pharmind-Connection") || "" },
      body: JSON.stringify({ smiles: body.smiles }),
    });

    if (!backendRes.ok || !backendRes.body) {
      return new Response(JSON.stringify({ error: `Backend returned ${backendRes.status}` }), {
        status: backendRes.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(backendRes.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  } catch (error: any) {
    return new Response(JSON.stringify({ error: `Connection error: ${error.message}` }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }
}
