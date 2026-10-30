import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy route for uploading research PDFs to the Python FastAPI backend (/upload-pdf).
 */
export async function POST(req: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";
    const url = new URL(req.url);
    const drugName = url.searchParams.get("drug_name") || "";

    const formData = await req.formData();

    const res = await fetch(
      `${backendUrl}/upload-pdf?drug_name=${encodeURIComponent(drugName)}`,
      {
        method: "POST",
        body: formData,
        headers: { "X-Pharmind-Connection": req.headers.get("X-Pharmind-Connection") || "" },
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        success: false,
        error: `Failed to upload PDF: ${err.message || err}`,
      },
      { status: 502 }
    );
  }
}
