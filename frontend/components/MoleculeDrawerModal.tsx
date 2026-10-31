"use client";

import { useState, useEffect, useRef } from "react";
import styles from "./MoleculeDrawerModal.module.css";

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
  const [smilesDraft, setSmilesDraft] = useState(initialSmiles);
  const [editorReady, setEditorReady] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (isOpen) dialogRef.current?.showModal(); }, [isOpen]);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Listen for SMILES updates from JSME iframe
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin === window.location.origin && event.source === iframeRef.current?.contentWindow && event.data?.type === "JSME_SMILES") {
        setCurrentSmiles(event.data.smiles || "");
        setSmilesDraft(event.data.smiles || "");
      } else if (event.origin === window.location.origin && event.source === iframeRef.current?.contentWindow && event.data?.type === "JSME_READY") {
        setEditorReady(true);
        iframeRef.current?.contentWindow?.postMessage({ type: "SET_SMILES", smiles: initialSmiles }, window.location.origin);
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [initialSmiles]);

  // Update JSME when initialSmiles or preset changes
  const loadSmilesIntoEditor = (smiles: string) => {
    setSmilesDraft(smiles);
    if (iframeRef.current && iframeRef.current.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        { type: "SET_SMILES", smiles },
        window.location.origin
      );
    }
  };

  if (!isOpen) return null;

  return (
    <dialog ref={dialogRef} className={styles.backdrop} onCancel={onClose} onClick={onClose} aria-labelledby="structure-editor-title">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerTitleWrap}>
            <div>
              <h3 id="structure-editor-title" className={styles.title}>Structure editor</h3>
              <p className={styles.subtitle}>Draw a molecule, start from a template, or load a SMILES string.</p>
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
            <span className={styles.presetsLabel}>Start from a template</span>
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className={styles.presetBtn}
                disabled={!editorReady}
                onClick={() => loadSmilesIntoEditor(p.smiles)}
              >
                {p.label}
              </button>
            ))}
            <button
              type="button"
              className={styles.presetBtn}
              onClick={() => loadSmilesIntoEditor("")}
              disabled={!editorReady}
            >
              Clear canvas
            </button>
          </div>

          <div className={styles.canvasHeading}>
            <span>Drawing canvas</span>
            <span role="status">{editorReady ? "Ready to draw" : "Loading editor…"}</span>
          </div>
          <div className={styles.editorContainer}>
            <iframe
              ref={iframeRef}
              src="/editor.html"
              className={styles.iframe}
              title="JSME Chemical Structure Editor"
            />
          </div>

          <form className={styles.previewSection} onSubmit={event => { event.preventDefault(); loadSmilesIntoEditor(smilesDraft); }}>
            <label className={styles.previewLabel} htmlFor="local-smiles">Molecular SMILES</label>
            <div className={styles.smilesInputRow}>
              <input id="local-smiles" className="input-base" value={smilesDraft} onChange={event => setSmilesDraft(event.target.value)} placeholder="Paste a SMILES string to load a structure" spellCheck={false} />
              <button type="submit" className={styles.cancelBtn} disabled={!editorReady || !smilesDraft.trim()}>Load structure</button>
            </div>
            <p className={styles.hint}>Choose a bond or atom, then click the canvas. Right-click for more drawing tools.</p>
          </form>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button type="button" className={styles.cancelBtn} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={styles.applyBtn}
            disabled={!editorReady || !currentSmiles.trim() || smilesDraft !== currentSmiles}
            onClick={() => {
              onApply(currentSmiles.trim());
              onClose();
            }}
          >
            Use structure
          </button>
        </div>
      </div>
    </dialog>
  );
}
