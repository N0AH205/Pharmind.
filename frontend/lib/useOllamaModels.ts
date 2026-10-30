"use client";

import { useEffect, useState } from "react";
import type { OllamaModel } from "./ollamaModels";

export function useOllamaModels(baseUrl: string | null) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ url: string; revision: number; models: OllamaModel[]; error: string } | null>(null);
  useEffect(() => {
    if (baseUrl === null) return;
    const controller = new AbortController();
    fetch("/api/connection/models", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base_url: baseUrl }), signal: controller.signal,
    }).then(async response => {
      const body = await response.json();
      if (!response.ok || !body.success) throw new Error(body.error || "Could not inspect local models.");
      return body.models as OllamaModel[];
    }).then(models => setResult({ url: baseUrl, revision, models, error: "" })).catch(error => {
      if (!controller.signal.aborted) setResult({ url: baseUrl, revision, models: [], error: error.message || "Could not inspect local models." });
    });
    return () => controller.abort();
  }, [baseUrl, revision]);
  const current = result?.url === baseUrl && result.revision === revision ? result : null;
  return { models: current?.models ?? [], error: current?.error ?? "", loading: baseUrl !== null && !current, refresh: () => setRevision(value => value + 1) };
}
