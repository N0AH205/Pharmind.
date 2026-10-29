import { redirect } from "next/navigation";

export default async function ChatPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; mode?: string }>;
}) {
  const { q, mode } = await searchParams;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (mode) params.set("mode", mode);
  const query = params.toString();
  redirect(query ? `/?${query}` : "/");
}
