import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy route for deleting an indexed PDF from the Python FastAPI backend.
 */
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  try {
    const { filename } = await params;
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";
    const res = await fetch(`${backendUrl}/uploaded-pdfs/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        success: false,
        error: `Failed to delete PDF: ${err.message || err}`,
      },
      { status: 502 }
    );
  }
}
