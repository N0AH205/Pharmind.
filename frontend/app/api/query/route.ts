import { NextRequest, NextResponse } from "next/server";
import type { QueryResponse } from "@/lib/types";

/**
 * Phase 3 — Live backend query proxy route.
 * Proxies POST requests containing a SMILES string to the Python FastAPI backend.
 */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);

  if (!body?.smiles || typeof body.smiles !== "string") {
    return NextResponse.json(
      { success: false, error: "Missing or invalid 'smiles' field" } satisfies QueryResponse,
      { status: 400 }
    );
  }

  try {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    const backendRes = await fetch(`${backendUrl}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Pharmind-Connection": req.headers.get("X-Pharmind-Connection") || "" },
      body: JSON.stringify({ smiles: body.smiles }),
    });

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (error: any) {
    return NextResponse.json(
      {
        success: false,
        error: `Failed to connect to FastAPI backend: ${error.message || error}`,
      } satisfies QueryResponse,
      { status: 502 }
    );
  }
}
