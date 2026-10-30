import { useEffect, useRef } from "react";
import { useBrowserReady } from "@/lib/useBrowserReady";
import { createPortal } from "react-dom";
import styles from "./CitationModal.module.css";
import type { Citation } from "@/lib/types";

interface Props {
  citation: Citation | null;
  onClose: () => void;
}

export default function CitationModal({ citation, onClose }: Props) {
  const mounted = useBrowserReady();
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (citation && mounted) dialogRef.current?.showModal(); }, [citation, mounted]);

  if (!citation || !mounted) return null;

  return createPortal(
    <dialog ref={dialogRef} className={styles.overlay} onCancel={onClose} onClick={onClose} aria-labelledby="citation-title">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.titleGroup}>
            <span className={styles.icon}>📜</span>
            <div>
              <h3 id="citation-title" className={styles.title}>{citation.source}</h3>
              {citation.url && (
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.urlLink}
                >
                  {citation.url} ↗
                </a>
              )}
            </div>
          </div>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        <div className={styles.body}>
          {(citation.authors || citation.journal || citation.publication_date || citation.doi || citation.pmid || citation.document_id) && (
            <div className={styles.metadata}>
              {[citation.authors, citation.journal, citation.publication_date, citation.pmid && `PMID ${citation.pmid}`, citation.doi && `DOI ${citation.doi}`, citation.document_id && `Record ${citation.document_id}`]
                .filter(Boolean)
                .join(" · ")}
            </div>
          )}
          <h4 className={styles.subTitle}>Retrieved Source Passage</h4>
          <div className={styles.passageContainer}>
            {citation.text ? (
              <p className={styles.passageText}>{citation.text}</p>
            ) : (
              <p className={styles.noText}>Full text preview unavailable for this external source label.</p>
            )}
          </div>
        </div>

        <div className={styles.footer}>
          <button type="button" className={styles.actionBtn} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </dialog>,
    document.body
  );
}
