"use client";

import { useState, useEffect, useRef } from "react";
import styles from "./MoleculeDrawerModal.module.css";
import { getConnection } from "@/lib/connection";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onApply: (smiles: string) => void;
  initialSmiles?: string;
}

const PRESETS = [
  { label: "Benzene", smiles: "c1ccccc1" },
  { label: "Phenol", smiles: "Oc1ccccc1" },
  { label: "Pyridine", smiles: "c1cnccc1" },
  { label: "Cyclohexane", smiles: "C1CCCCC1" },
  { label: "Aspirin", smiles: "CC(=O)Oc1ccccc1C(=O)O" },
];

export default function MoleculeDrawerModal({
  isOpen,
  onClose,
  onApply,
  initialSmiles = "",
}: Props) {
  const [currentSmiles, setCurrentSmiles] = useState(initialSmiles);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Listen for SMILES updates from JSME iframe
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin === window.location.origin && event.source === iframeRef.current?.contentWindow && event.data?.type === "JSME_SMILES") {
        setCurrentSmiles(event.data.smiles || "");
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Update JSME when initialSmiles or preset changes
  const loadSmilesIntoEditor = (smiles: string) => {
    setCurrentSmiles(smiles);
    if (iframeRef.current && iframeRef.current.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        { type: "SET_SMILES", smiles },
        window.location.origin
      );
    }
  };

  // Send initial SMILES when iframe finishes loading
  const handleIframeLoad = () => {
    if (initialSmiles && iframeRef.current && iframeRef.current.contentWindow) {
      setTimeout(() => {
        iframeRef.current?.contentWindow?.postMessage(
          { type: "SET_SMILES", smiles: initialSmiles },
          window.location.origin
        );
      }, 400);
    }
  };

  if (!isOpen) return null;

  return (
    <div className={styles.backdrop} onClick={onClose} aria-modal="true" role="dialog">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerTitleWrap}>
            <div className={styles.headerIcon}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <circle cx="4" cy="6" r="2" />
                <circle cx="20" cy="6" r="2" />
                <circle cx="4" cy="18" r="2" />
                <circle cx="20" cy="18" r="2" />
                <line x1="9.5" y1="10.5" x2="6" y2="7.5" />
                <line x1="14.5" y1="10.5" x2="18" y2="7.5" />
                <line x1="9.5" y1="13.5" x2="6" y2="16.5" />
                <line x1="14.5" y1="13.5" x2="18" y2="16.5" />
              </svg>
            </div>
            <div>
              <h3 className={styles.title}>Visual Structure Editor</h3>
              <p className={styles.subtitle}>Draw chemical structures or load templates to generate SMILES</p>
            </div>
          </div>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close drawer">
            <svg width="16" height="16" viewBox="0 0 14 14" fill="none">
              <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {/* Quick Presets */}
          <div className={styles.presetsBar}>
            <span className={styles.presetsLabel}>Quick templates:</span>
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className={styles.presetBtn}
                onClick={() => loadSmilesIntoEditor(p.smiles)}
              >
                {p.label}
              </button>
            ))}
            <button
              type="button"
              className={styles.presetBtn}
              onClick={() => loadSmilesIntoEditor("")}
              style={{ marginLeft: "auto", color: "var(--color-error)" }}
            >
              Clear Canvas
            </button>
          </div>

          {/* JSME Canvas Container */}
          <div className={styles.editorContainer}>
            {getConnection().online_sources ? <iframe
              ref={iframeRef}
              src="/editor.html"
              className={styles.iframe}
              title="JSME Chemical Structure Editor"
              onLoad={handleIframeLoad}
            /> : <div style={{ padding: "30px", color: "var(--slate)" }}><p>The visual editor loads an external library and is unavailable while online sources are off. Use a template or enter SMILES below.</p><label htmlFor="local-smiles">Molecular SMILES</label><input id="local-smiles" className="input-base" value={currentSmiles} onChange={event => setCurrentSmiles(event.target.value)} /></div>}
          </div>

          {/* SMILES Preview Section */}
          <div className={styles.previewSection}>
            <span className={styles.previewLabel}>Generated SMILES</span>
            <div className={styles.previewValue}>
              {currentSmiles ? (
                currentSmiles
              ) : (
                <span className={styles.previewEmpty}>Draw a chemical structure on the canvas above...</span>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button type="button" className={styles.cancelBtn} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={styles.applyBtn}
            disabled={!currentSmiles.trim()}
            onClick={() => {
              onApply(currentSmiles.trim());
              onClose();
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3.5 8.5l3 3 6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Use Drawn SMILES
          </button>
        </div>
      </div>
    </div>
  );
}
