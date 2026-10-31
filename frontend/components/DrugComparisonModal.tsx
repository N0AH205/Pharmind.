"use client";

import { useEffect, useRef } from "react";
import styles from "./DrugComparisonModal.module.css";
import type { DrugInfo } from "@/lib/types";

interface Props {
  leftDrug: DrugInfo | null;
  rightDrug: DrugInfo | null;
  onClose: () => void;
  candidates: DrugInfo[];
  leftIndex: number;
  rightIndex: number;
  onSelect: (side: "left" | "right", index: number) => void;
}

function getDrugName(drug: DrugInfo): string {
  return (
    drug.drug_overview?.identity?.generic_name?.content ||
    drug.drug_name?.generic ||
    "Unknown Drug"
  );
}

function getMoa(drug: DrugInfo): string {
  return (
    drug.pharmacodynamics?.mechanism_of_action?.content ||
    "Data unavailable"
  );
}

function getAbsorption(drug: DrugInfo): string {
  return (
    drug.pharmacokinetics?.absorption?.bioavailability?.content ||
    drug.adme?.absorption?.content ||
    "N/A"
  );
}

function getMetabolism(drug: DrugInfo): string {
  return (
    drug.pharmacokinetics?.metabolism?.metabolic_pathways?.content ||
    drug.adme?.metabolism?.content ||
    "N/A"
  );
}

function getExcretion(drug: DrugInfo): string {
  return (
    drug.pharmacokinetics?.excretion?.primary_route?.content ||
    drug.adme?.excretion?.content ||
    "N/A"
  );
}

function getSafety(drug: DrugInfo): string {
  const boxed = drug.toxicology_and_safety?.clinical_safety?.boxed_warning?.content;
  if (boxed && !boxed.toLowerCase().startsWith("no boxed warning") && !boxed.toLowerCase().startsWith("none")) {
    return `Boxed Warning: ${boxed}`;
  }
  return (
    drug.toxicology_and_safety?.clinical_safety?.warnings_and_precautions?.content ||
    drug.toxicology?.acute_toxicity?.content ||
    "Safety evidence unavailable in this profile"
  );
}

function getRegulatory(drug: DrugInfo): string {
  const us = drug.therapeutic_profile?.regulatory_status?.united_states?.status || "Not documented";
  const bpom = drug.therapeutic_profile?.regulatory_status?.indonesia?.status || "Not documented";
  return `US FDA: ${us} | BPOM: ${bpom}`;
}

export default function DrugComparisonModal({ leftDrug, rightDrug, onClose, candidates, leftIndex, rightIndex, onSelect }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialogRef.current?.showModal(); }, []);
  if (!leftDrug || !rightDrug) return null;

  const leftName = getDrugName(leftDrug);
  const rightName = getDrugName(rightDrug);

  return (
    <dialog ref={dialogRef} className={styles.overlay} onCancel={onClose} onClick={onClose} aria-labelledby="comparison-title">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.titleGroup}>

            <div>
              <h3 id="comparison-title" className={styles.title}>Comparative Pharmacology Analysis</h3>
              <p className={styles.subTitle}>
                Side-by-side evaluation of {leftName} vs. {rightName}
              </p>
            </div>
          </div>
          <button type="button" className={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className={styles.body}>
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginBottom: "20px" }}>
            {(["left", "right"] as const).map(side => <label key={side}>{side === "left" ? "First compound " : "Second compound "}<select value={side === "left" ? leftIndex : rightIndex} onChange={event => onSelect(side, Number(event.target.value))}>{candidates.map((drug, index) => <option key={index} value={index} disabled={index === (side === "left" ? rightIndex : leftIndex)}>{getDrugName(drug)} ({index + 1})</option>)}</select></label>)}
          </div>
          <div className={styles.grid}>
            {/* Left Column */}
            <div className={styles.col}>
              <div className={styles.colHeader}>
                <h4>{leftName}</h4>
                <code>{leftDrug.query_smiles}</code>
              </div>

              <div className={styles.section}>
                <h5>Regulatory Status</h5>
                <p style={{ fontSize: "0.82rem", fontWeight: 600 }}>{getRegulatory(leftDrug)}</p>
              </div>

              <div className={styles.section}>
                <h5>Mechanism of Action</h5>
                <p>{getMoa(leftDrug)}</p>
              </div>

              <div className={styles.section}>
                <h5>ADME Profile</h5>
                <p><strong>Absorption:</strong> {getAbsorption(leftDrug)}</p>
                <p><strong>Metabolism:</strong> {getMetabolism(leftDrug)}</p>
                <p><strong>Excretion:</strong> {getExcretion(leftDrug)}</p>
              </div>

              <div className={styles.section}>
                <h5>Safety & Toxicity</h5>
                <p>{getSafety(leftDrug)}</p>
              </div>
            </div>

            <div className={styles.divider} />

            {/* Right Column */}
            <div className={styles.col}>
              <div className={styles.colHeader}>
                <h4>{rightName}</h4>
                <code>{rightDrug.query_smiles}</code>
              </div>

              <div className={styles.section}>
                <h5>Regulatory Status</h5>
                <p style={{ fontSize: "0.82rem", fontWeight: 600 }}>{getRegulatory(rightDrug)}</p>
              </div>

              <div className={styles.section}>
                <h5>Mechanism of Action</h5>
                <p>{getMoa(rightDrug)}</p>
              </div>

              <div className={styles.section}>
                <h5>ADME Profile</h5>
                <p><strong>Absorption:</strong> {getAbsorption(rightDrug)}</p>
                <p><strong>Metabolism:</strong> {getMetabolism(rightDrug)}</p>
                <p><strong>Excretion:</strong> {getExcretion(rightDrug)}</p>
              </div>

              <div className={styles.section}>
                <h5>Safety & Toxicity</h5>
                <p>{getSafety(rightDrug)}</p>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.footer}>
          <button type="button" className={styles.actionBtn} onClick={onClose}>
            Close Analysis
          </button>
        </div>
      </div>
    </dialog>
  );
}
