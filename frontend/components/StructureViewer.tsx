"use client";

import { useState } from "react";
import type { ChemicalStructure } from "@/lib/types";
import styles from "./StructureViewer.module.css";
import { getConnection } from "@/lib/connection";

interface Props {
  structure: ChemicalStructure;
}

function formatChemicalFormula(formula: string): string {
  const subscripts: { [key: string]: string } = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉"
  };
  return formula.split("").map(char => subscripts[char] || char).join("");
}

export default function StructureViewer({ structure }: Props) {
  const [imgError, setImgError] = useState(false);
  const isBiologic = structure.drug_type === "biologic" || Boolean(structure.biologic_class);

  return (
    <div className={styles.container}>
      {isBiologic ? (
        <div className={styles.biologicBanner}>
          <div className={styles.biologicIcon}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </div>
          <div className={styles.biologicInfo}>
            <div className={styles.biologicTitle}>{structure.biologic_class || "Biologic / Macromolecule"}</div>
            <div className={styles.biologicDesc}>
              {structure.target ? `Target: ${structure.target}` : "Recombinant protein / Monoclonal antibody therapeutic"}
            </div>
          </div>
        </div>
      ) : (
        <div className={styles.imageWrap}>
          {structure.image_url && !imgError && (structure.image_url.startsWith("data:image/") || getConnection().online_sources) ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={structure.image_url}
              alt={`Chemical structure of ${structure.iupac_name || structure.smiles}`}
              className={styles.image}
              onError={() => setImgError(true)}
            />
          ) : (
            <div className={styles.imageFallback}>
              <span>Structure image unavailable</span>
            </div>
          )}
        </div>
      )}

      <div className={styles.properties}>
        <table className={styles.structureTable}>
          <tbody>
            {structure.drug_type && (
              <tr>
                <td className={styles.tableLabel}>Modality</td>
                <td className={styles.tableValue}>
                  <strong style={{ textTransform: "capitalize" }}>{structure.drug_type.replace(/_/g, " ")}</strong>
                </td>
              </tr>
            )}
            {structure.biologic_class && (
              <tr>
                <td className={styles.tableLabel}>Classification</td>
                <td className={styles.tableValue}>
                  <strong>{structure.biologic_class}</strong>
                </td>
              </tr>
            )}
            {structure.target && (
              <tr>
                <td className={styles.tableLabel}>Primary Target</td>
                <td className={styles.tableValue}>
                  <strong>{structure.target}</strong>
                </td>
              </tr>
            )}
            {structure.molecular_formula && (
              <tr>
                <td className={styles.tableLabel}>Formula</td>
                <td className={`${styles.tableValue} text-mono`}>
                  <strong>{formatChemicalFormula(structure.molecular_formula)}</strong>
                </td>
              </tr>
            )}
            {structure.molecular_weight && (
              <tr>
                <td className={styles.tableLabel}>Molecular weight</td>
                <td className={styles.tableValue}>
                  <strong>{structure.molecular_weight} g/mol</strong>
                </td>
              </tr>
            )}
            {structure.iupac_name && (
              <tr>
                <td className={styles.tableLabel}>IUPAC name</td>
                <td className={styles.tableValue}>{structure.iupac_name}</td>
              </tr>
            )}
            {structure.pubchem_cid && (
              <tr>
                <td className={styles.tableLabel}>PubChem CID</td>
                <td className={styles.tableValue}>
                  <a
                    href={`https://pubchem.ncbi.nlm.nih.gov/compound/${structure.pubchem_cid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.tableLink}
                  >
                    {structure.pubchem_cid}
                  </a>
                </td>
              </tr>
            )}
            {structure.smiles && (
              <tr>
                <td className={styles.tableLabel}>SMILES</td>
                <td className={styles.tableValue}>
                  <span className={styles.smilesText}>{structure.smiles}</span>
                </td>
              </tr>
            )}
            {structure.inchi && (
              <tr>
                <td className={styles.tableLabel}>InChI</td>
                <td className={styles.tableValue}>
                  <code className={styles.codeBlockMuted}>{structure.inchi}</code>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
