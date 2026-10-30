import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy route for follow-up conversational questions and pharmacology chat.
 * Forwards requests to the Python FastAPI backend (/chat).
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";

    const res = await fetch(`${backendUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Pharmind-Connection": req.headers.get("X-Pharmind-Connection") || "" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        success: false,
        error: `Failed to proxy chat to backend: ${err.message || err}`,
      },
      { status: 502 }
    );
  }
}
