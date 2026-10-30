import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy route for listing indexed research PDFs from the Python FastAPI backend.
 */
export async function GET() {
  try {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";
    const res = await fetch(`${backendUrl}/uploaded-pdfs`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        success: false,
        error: `Failed to fetch uploaded PDFs: ${err.message || err}`,
      },
      { status: 502 }
    );
  }
}
