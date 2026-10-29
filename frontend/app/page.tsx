import type { Metadata } from "next";
import ChatWorkspace from "./chat/ChatWorkspace";

export const metadata: Metadata = {
  title: "Research workspace",
};

export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; mode?: string }>;
}) {
  const { q, mode } = await searchParams;
  const initialMode = mode === "paper_learning" || mode === "molecule_theory" ? mode : "structure_science";
  return <ChatWorkspace initialQuery={q ?? ""} initialMode={initialMode} />;
}
