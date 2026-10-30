import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy route for uploading research PDFs to the Python FastAPI backend (/upload-pdf).
 */
export async function POST(req: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";
    const url = new URL(req.url);
    const drugName = url.searchParams.get("drug_name") || "";

    if (Number(req.headers.get("content-length")) > 21 * 1024 * 1024) return NextResponse.json({ success: false, error: "PDFs must be 20 MB or smaller." }, { status: 413 });
    const replacement = url.searchParams.get("replace_document_id");
    const formData = await req.formData();
    const file = formData.get("file");
    if (!(file instanceof File) || file.size > 20 * 1024 * 1024) return NextResponse.json({ success: false, error: "Choose a PDF of 20 MB or smaller." }, { status: 400 });

    const res = await fetch(
      `${backendUrl}/upload-pdf?drug_name=${encodeURIComponent(drugName)}${replacement ? `&replace_document_id=${encodeURIComponent(replacement)}` : ""}`,
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
