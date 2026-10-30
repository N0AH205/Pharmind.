"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useBrowserReady } from "@/lib/useBrowserReady";
import { clearConnection, DEFAULT_CONNECTION, getConnection, PROVIDERS, saveConnection, type ModelConnection, type Provider } from "@/lib/connection";
import styles from "./settings.module.css";

export default function SettingsPage() {
  const ready = useBrowserReady();
  return ready ? <ConnectionSettings /> : <main id="main-content" aria-busy="true">Opening settings…</main>;
}

function ConnectionSettings() {
  const ready = true;
  const [connection, setConnection] = useState<ModelConnection>(getConnection);
  const [testing, setTesting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [readiness, setReadiness] = useState("");
  const [checking, setChecking] = useState(false);
  const [showKey, setShowKey] = useState(false);


  async function checkReadiness() {
    setChecking(true);
    try {
      const response = await fetch("/api/readiness", { cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      setReadiness(`${result.message} ${result.chunk_count} indexed passages. ${result.reranker_cached ? "Reranker cached." : "Reranker unavailable; vector ranking will be used."}`);
    } catch (error) { setReadiness(error instanceof Error ? error.message : "Could not check local readiness."); }
    finally { setChecking(false); }
  }

  function update(patch: Partial<ModelConnection>) {
    setConnection(current => ({ ...current, ...patch }));
    setNotice(""); setError("");
  }

  function valid() {
    if (!connection.model.trim()) { setError("Enter the exact model ID from your provider or Ollama installation."); return false; }
    if (connection.provider !== "ollama" && !connection.api_key.trim()) { setError("Enter your API key for this provider."); return false; }
    if (!/^[a-zA-Z0-9._:/-]+$/.test(connection.model)) { setError("Use a model ID without spaces or special characters."); return false; }
    try {
      const url = new URL(connection.base_url);
      if (!["http:", "https:"].includes(url.protocol) || !["localhost", "127.0.0.1", "[::1]", "host.docker.internal"].includes(url.hostname) || url.username || url.password || url.search || url.hash || (url.pathname !== "/" && url.pathname !== "")) throw new Error();
    } catch { setError("Use a local Ollama address, such as http://localhost:11434."); return false; }
    return true;
  }

  async function testConnection() {
    setNotice(""); setError("");
    if (!valid()) return;
    setTesting(true);
    try {
      const response = await fetch("/api/connection", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(connection) });
      const result = await response.json();
      if (!response.ok || !result.success) setError(result.error || "Connection could not be verified.");
      else setNotice(result.message);
    } catch { setError("Could not reach the local app. Check your connection and try again."); }
    finally { setTesting(false); }
  }

  function save(event: FormEvent) {
    event.preventDefault(); setError("");
    if (!valid()) return;
    try {
      saveConnection(connection);
      setNotice("Connection saved for this browser session. You can now open your workspace.");
    } catch { setError("Browser session storage is unavailable. Enable it to save your connection."); }
  }

  function forget() {
    try {
      clearConnection(); setConnection(DEFAULT_CONNECTION); setShowKey(false); setError("");
      setNotice("Saved connection and API key removed. Local defaults restored.");
    } catch { setError("Could not clear browser session storage."); }
  }

  return <div className={styles.page}>
    <header className={styles.header}><Link href="/" className={styles.brand}>pharmind.</Link><Link href="/">Back to workspace <span aria-hidden="true">↗</span></Link></header>
    <main id="main-content" className={styles.main}>
      <div className={styles.intro}><h1>Model & connection</h1><p>Choose your model and control access to online sources.</p></div>
      <div className={styles.columns}>
        <form onSubmit={save} className={styles.form}>
          <fieldset disabled={!ready || testing}>
            <legend>Model provider</legend>
            <div className={styles.providers}>{Object.entries(PROVIDERS).map(([id, provider]) => <button type="button" key={id} aria-pressed={connection.provider === id} onClick={() => update({ provider: id as Provider, model: provider.model, api_key: "" })}><span>{provider.name}</span><small>{id === "ollama" ? "On your device" : "Your API key"}</small></button>)}</div>
            <label htmlFor="model">Model ID</label><input id="model" value={connection.model} onChange={e => update({ model: e.target.value.trim() })} placeholder={connection.provider === "ollama" ? "qwen2.5:3b" : "Enter a model ID from your provider"} required autoComplete="off" />
            <p className={styles.hint}>{connection.provider === "ollama" ? "Use the exact model name shown by ollama list." : "Use a model that your provider account can access."}</p>
            {connection.provider === "ollama" ? <><label htmlFor="endpoint">Local Ollama address</label><input id="endpoint" type="url" value={connection.base_url} onChange={e => update({ base_url: e.target.value })} required /><p className={styles.hint}>Docker installations use the configured host gateway automatically.</p></> : <><label htmlFor="api-key">Your API key</label><div className={styles.keyField}><input id="api-key" type={showKey ? "text" : "password"} value={connection.api_key} onChange={e => update({ api_key: e.target.value.trim() })} placeholder="Paste your provider key" autoComplete="off" spellCheck={false} required /><button type="button" onClick={() => setShowKey(!showKey)} aria-label={showKey ? "Hide API key" : "Show API key"}>{showKey ? "Hide" : "Show"}</button></div><p className={styles.hint}>Stored in this browser tab’s session, never in your chat history. Clear it below when you are done.</p></>}
          </fieldset>
          <fieldset disabled={!ready || testing} className={styles.sources}>
            <legend>Online sources</legend>
            <label className={styles.checkbox}><input type="checkbox" checked={connection.online_sources} onChange={e => update({ online_sources: e.target.checked })} /><span>Allow online literature sources<small>Send search terms to public research databases, including PubMed and PubChem. Off by default.</small></span></label>
            <p className={styles.modeNote}>{connection.provider === "ollama" && !connection.online_sources ? "Local mode: uses your installed model and indexed documents. No online literature lookups." : connection.provider === "ollama" ? "Local model + online sources: inference runs on your device; literature searches use the internet." : "BYOK mode: your questions and selected evidence are sent to your chosen AI provider. Provider charges may apply."}</p>
          </fieldset>
          {error && <p role="alert" className={styles.notice}>{error}</p>}
          {notice && <p role="status" className={styles.notice}>{notice}</p>}
          <div className={styles.actions}><button type="submit" className="btn btn-primary" disabled={!ready || testing}>Save connection</button><button type="button" className="btn btn-ghost" onClick={testConnection} disabled={!ready || testing}>{testing ? "Testing connection…" : "Test connection"}</button></div>
          <div className={styles.bottomLinks}><button type="button" onClick={forget} disabled={testing}>Forget saved connection</button></div>
        </form>
        <aside className={styles.guide}>
          <h2>Local setup</h2>
          <button type="button" className="btn btn-ghost" onClick={checkReadiness} disabled={checking}>{checking ? "Checking local models…" : "Check local readiness"}</button>
          {readiness && <p role="status">{readiness}</p>}
          <p>For fully local research, choose Ollama and leave online sources off. Install your model and prepare the local embedding cache while you have an internet connection.</p>
          <div className={styles.guideStep}><span>1</span><div><strong>Install a model</strong><code>ollama pull qwen2.5:3b</code></div></div>
          <div className={styles.guideStep}><span>2</span><div><strong>Prepare the document index</strong><p>Run <code>python scripts/prepare_local_models.py</code> from the backend directory, or use the Docker command in the README.</p></div></div>
          <div className={styles.guideStep}><span>3</span><div><strong>Bring your reading</strong><p>Open the workspace and add a PDF to your local library.</p></div></div>
        </aside>
      </div>
    </main>
  </div>;
}
