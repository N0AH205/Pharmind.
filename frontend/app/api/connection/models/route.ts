import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { base_url } = await req.json();
    const response = await fetch(`${process.env.BACKEND_URL || "http://localhost:8001"}/connection/ollama-models`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "ollama", base_url }),
      signal: AbortSignal.any([req.signal, AbortSignal.timeout(15000)]),
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ success: false, error: "Could not check local models. Start the Pharmind backend, then refresh." }, { status: 502 });
  }
}
