import { NextRequest } from "next/server";
import { proxyResearchStream } from "@/lib/researchProxy";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body?.question || typeof body.question !== "string") return Response.json({ success: false, error: "Enter a research question." }, { status: 400 });
  return proxyResearchStream(req, "/chat/stream", body);
}
