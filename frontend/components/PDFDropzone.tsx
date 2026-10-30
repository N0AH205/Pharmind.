"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { uploadPDF, getUploadedPDFs, deleteUploadedPDF } from "@/lib/api";
import type { ResearchDocument } from "@/lib/types";
import styles from "./PDFDropzone.module.css";

interface Props {
  onSuccess?: (doc: ResearchDocument) => void;
  onSelect?: (doc: ResearchDocument) => void;
  onDeleted?: (documentId: string) => void;
}

export default function PDFDropzone({ onSuccess, onSelect, onDeleted }: Props) {
  const [papers, setPapers] = useState<ResearchDocument[]>([]);
  const [drugName, setDrugName] = useState("");
  const [replacement, setReplacement] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const fetchPapers = useCallback(() => getUploadedPDFs().then(result => {
    if (!result.success) throw new Error("Start the local backend to use your document library.");
    setPapers(result.documents || result.data || []);
  }).catch(error => {
    setStatus(error instanceof Error ? error.message : "Could not load your library.");
  }).finally(() => setLoading(false)), []);
  useEffect(() => { void fetchPapers(); }, [fetchPapers]);

  async function upload(file?: File) {
    if (!file || busy) return;
    if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 20 * 1024 * 1024) {
      setStatus("Choose a PDF of 20 MB or less (up to 500 pages)."); return;
    }
    setBusy(true); setStatus("Indexing your paper locally. Larger papers can take a few minutes…");
    try {
      const result = await uploadPDF(file, drugName, replacement || undefined);
      if (!result.success) throw new Error(result.error || "Could not index this paper.");
      const doc = { ...result.data, chunks: result.data.chunks_stored } as ResearchDocument;
      setStatus(`Indexed ${doc.chunks} passages. The original PDF is saved locally.`);
      setReplacement("");
      await fetchPapers();
      onSuccess?.(doc);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function remove(doc: ResearchDocument) {
    if (!confirm(`Delete “${doc.filename}” and its indexed passages from this library?`)) return;
    setBusy(true); setStatus("");
    try {
      const result = await deleteUploadedPDF(doc.document_id);
      if (!result.success) throw new Error(result.error || "Could not delete this paper.");
      onDeleted?.(doc.document_id);
      if (replacement === doc.document_id) setReplacement("");
      await fetchPapers();
    } catch (error) { setStatus(error instanceof Error ? error.message : "Deletion failed."); }
    finally { setBusy(false); }
  }

  return <div className={styles.wrapper}>
    <button type="button" className={styles.dropzone} disabled={busy} onClick={() => inputRef.current?.click()}
      onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); void upload(event.dataTransfer.files[0]); }}>
      <span className={styles.title}>{busy ? "Indexing paper…" : "Choose or drop a PDF"}</span>
      <span className={styles.sub}>20 MB maximum · 500 pages · text-based PDFs</span>
    </button>
    <input ref={inputRef} type="file" accept="application/pdf,.pdf" hidden disabled={busy} onChange={event => void upload(event.target.files?.[0])} />
    <label className={styles.sub}>Compound name (optional)<input className={styles.drugNameInput} value={drugName} disabled={busy} onChange={event => setDrugName(event.target.value)} /></label>
    <label className={styles.sub}>Upload action<select className={styles.drugNameInput} value={replacement} disabled={busy} onChange={event => setReplacement(event.target.value)}>
      <option value="">Add a new paper</option>
      {papers.filter(doc => /^[a-f0-9]{64}$/.test(doc.document_id)).map(doc => <option key={doc.document_id} value={doc.document_id}>Replace: {doc.filename} ({doc.associated_drug || "untagged"})</option>)}
    </select></label>
    <p className={styles.sub}>Scanned papers need OCR before upload. Use “Replace” to update an existing paper without keeping its old passages.</p>
    {status && <p role="status" className={styles.sub}>{status}</p>}
    <h4>Saved papers</h4>
    {loading && <p role="status">Loading library…</p>}
    {!loading && !papers.length && <p className={styles.sub}>No papers indexed yet.</p>}
    {papers.map(doc => <div key={doc.document_id} className={styles.paperItem}>
      <div className={styles.paperInfo}><strong>{doc.filename}</strong><span className={styles.paperMeta}>{doc.pages} pages · {doc.chunks} passages · {doc.associated_drug}</span>
        {doc.original_available && <a href={`/api/documents/${encodeURIComponent(doc.document_id)}/file`} target="_blank" rel="noreferrer">View PDF ↗</a>}
      </div>
      <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => onSelect?.(doc)}>Use paper</button>
      <button type="button" className={styles.deleteBtn} disabled={busy} onClick={() => void remove(doc)} aria-label={`Delete ${doc.filename}`}>Delete</button>
    </div>)}
  </div>;
}
