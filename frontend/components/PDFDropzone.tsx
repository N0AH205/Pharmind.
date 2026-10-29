"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { uploadPDF, getUploadedPDFs, deleteUploadedPDF } from "@/lib/api";
import styles from "./PDFDropzone.module.css";

interface UploadedDoc {
  doc_name: string;
  chunks: number;
  total_pages: number;
  upload_date?: string;
  associated_drug?: string;
}

interface PDFDropzoneProps {
  onSuccess?: (doc: {
    filename: string;
    pages: number;
    chunks_stored: number;
    associated_drug: string;
  }) => void;
}

export default function PDFDropzone({ onSuccess }: PDFDropzoneProps) {
  const [activeTab, setActiveTab] = useState<"upload" | "library">("upload");
  const [drugName, setDrugName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const [papers, setPapers] = useState<UploadedDoc[]>([]);
  const [loadingPapers, setLoadingPapers] = useState(false);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPapers = useCallback(async () => {
    setLoadingPapers(true);
    try {
      const res = await getUploadedPDFs();
      const list = Array.isArray(res?.documents)
        ? res.documents
        : Array.isArray(res?.data)
        ? res.data
        : [];
      if (res?.success) {
        setPapers(list);
      } else {
        setStatus("The document library is unavailable. Start your local backend and try again.");
        setIsError(true);
      }
    } catch (e) {
      setStatus("Could not reach your local document library.");
      setIsError(true);
    } finally {
      setLoadingPapers(false);
    }
  }, []);

  useEffect(() => {
    fetchPapers();
  }, [fetchPapers]);

  async function handleFileSelect(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("Only PDF files are supported.");
      setIsError(true);
      return;
    }

    setUploading(true);
    setStatus(`Indexing '${file.name}' in your local library…`);
    setIsError(false);

    try {
      const res = await uploadPDF(file, drugName);
      if (res.success) {
        setStatus(
          `Successfully indexed ${res.data.chunks_stored} passages across ${res.data.pages} page(s).`
        );
        setIsError(false);
        fetchPapers();
        if (onSuccess) {
          onSuccess({
            filename: file.name,
            pages: res.data.pages,
            chunks_stored: res.data.chunks_stored,
            associated_drug: drugName,
          });
        }
      } else {
        setStatus(res.error || "Failed to index PDF.");
        setIsError(true);
      }
    } catch (e: any) {
      setStatus(e.message || "Failed to upload file.");
      setIsError(true);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(filename: string) {
    if (!confirm(`Remove "${filename}" from your local document library?`)) {
      return;
    }
    setDeletingFile(filename);
    try {
      const res = await deleteUploadedPDF(filename);
      if (res.success) {
        setPapers((prev) => prev.filter((p) => p.doc_name !== filename));
        setStatus(`Removed "${filename}" (${res.deleted_chunks} chunks deleted).`);
        setIsError(false);
      } else {
        setStatus(res.error || "Failed to delete file.");
        setIsError(true);
      }
    } catch (e: any) {
      setStatus(e.message || "Failed to delete file.");
      setIsError(true);
    } finally {
      setDeletingFile(null);
    }
  }

  return (
    <div className={styles.wrapper}>
      {/* Navigation Tabs */}
      <div className={styles.tabBar} role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "upload"}
          className={`${styles.tabBtn} ${activeTab === "upload" ? styles.tabBtnActive : ""}`}
          onClick={() => setActiveTab("upload")}
        >
          Upload Paper
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "library"}
          className={`${styles.tabBtn} ${activeTab === "library" ? styles.tabBtnActive : ""}`}
          onClick={() => {
            setActiveTab("library");
            fetchPapers();
          }}
        >
          Indexed Papers ({papers.length})
        </button>
      </div>

      {activeTab === "upload" ? (
        <>
          <div
            className={styles.dropzone}
            role="button"
            tabIndex={uploading ? -1 : 0}
            aria-label="Choose a PDF for your local library"
            aria-disabled={uploading}
            onKeyDown={event => {
              if (!uploading && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (e.dataTransfer.files?.[0]) {
                handleFileSelect(e.dataTransfer.files[0]);
              }
            }}
          >
            <input
              type="file"
              accept=".pdf"
              disabled={uploading}
              ref={fileInputRef}
              style={{ display: "none" }}
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  handleFileSelect(e.target.files[0]);
                }
              }}
            />
            <div className={styles.icon}>PDF</div>
            <div className={styles.textGroup}>
              <span className={styles.title}>Add a research paper</span>
              <span className={styles.sub}>
                Drop lab reports, clinical trials, or preprints into your local library
              </span>
            </div>
          </div>

          <label className={styles.sub}>
            Associate with compound name (optional)
            <input
              value={drugName}
              onChange={(event) => setDrugName(event.target.value)}
              onClick={(event) => event.stopPropagation()}
              placeholder="e.g. Humira, Semaglutide, or Metformin"
              className={styles.drugNameInput}
              aria-label="Compound name for uploaded literature"
            />
          </label>
        </>
      ) : (
        /* Paper Library Tab */
        <div className={styles.paperList}>
          {loadingPapers && papers.length === 0 ? (
            <div className={styles.emptyList}>Loading indexed documents…</div>
          ) : papers.length === 0 ? (
            <div className={styles.emptyList}>
              No uploaded literature indexed yet. Switch to "Upload Paper" to add research PDFs.
            </div>
          ) : (
            papers.map((p) => (
              <div key={p.doc_name} className={styles.paperItem}>
                <div className={styles.paperInfo}>
                  <span className={styles.paperName} title={p.doc_name}>
                    PDF {p.doc_name}
                  </span>
                  <div className={styles.paperMeta}>
                    <span>{p.chunks} chunks</span>
                    <span>•</span>
                    <span>{p.total_pages} {p.total_pages === 1 ? "page" : "pages"}</span>
                    {p.associated_drug && (
                      <>
                        <span>•</span>
                        <span style={{ color: "var(--slate)" }}>Tag: {p.associated_drug}</span>
                      </>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  className={styles.deleteBtn}
                  onClick={() => handleDelete(p.doc_name)}
                  disabled={deletingFile === p.doc_name}
                  title="Remove from vector database"
                  aria-label={`Delete ${p.doc_name}`}
                >
                  {deletingFile === p.doc_name ? "..." : "🗑️"}
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {status && (
        <div
          className={`${styles.status} ${
            isError ? styles.statusError : styles.statusSuccess
          }`}
        >
          {uploading && (
            <span
              className="spinner"
              style={{ width: 12, height: 12, marginRight: 6 }}
            />
          )}
          {status}
        </div>
      )}
    </div>
  );
}
