import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Pharmind",
    template: "%s · Pharmind",
  },
  icons: { icon: "/icon.svg" },
  description:
    "Your personal pharmacology workspace. Run AI locally with Ollama or bring your own provider key.",
  keywords: ["Pharmind", "drug information", "pharmacology", "RAG", "SMILES", "pharmaceutical research"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body><a href="#main-content" className="skip-link">Skip to content</a>{children}</body>
    </html>
  );
}
