import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  try {
    const response = await fetch(`${process.env.BACKEND_URL || "http://localhost:8001"}/readiness`, {
      signal: AbortSignal.any([req.signal, AbortSignal.timeout(30000)]), cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ success: false, error: "Backend unavailable. Start Pharmind Local and retry." }, { status: 502 });
  }
}
