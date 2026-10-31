import { NextRequest } from "next/server";
import { proxyResearchStream } from "@/lib/researchProxy";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body?.smiles || typeof body.smiles !== "string") return Response.json({ error: "Missing a compound query." }, { status: 400 });
  return proxyResearchStream(req, "/query/stream", { smiles: body.smiles });
}
