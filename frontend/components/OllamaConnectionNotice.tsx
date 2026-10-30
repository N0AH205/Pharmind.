"use client";

import Link from "next/link";
import type { ModelConnection } from "@/lib/connection";
import { ollamaModelWarning } from "@/lib/ollamaModels";
import { useOllamaModels } from "@/lib/useOllamaModels";
import styles from "./OllamaConnectionNotice.module.css";

export default function OllamaConnectionNotice({ connection }: { connection: ModelConnection }) {
  const local = useOllamaModels(connection.provider === "ollama" ? connection.base_url : null);
  if (connection.provider !== "ollama" || local.loading) return null;
  const warning = local.error || ollamaModelWarning(local.models, connection.model);
  if (!warning) return null;
  return <div className={styles.notice} role="status">
    <div><strong>Model setup needed</strong><p>{warning}</p></div>
    <div className={styles.actions}><Link href="/settings">Choose a model</Link><button type="button" onClick={local.refresh}>Check again</button></div>
  </div>;
}
