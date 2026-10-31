"use client";

import React from "react";
import type { BioactivityRecord } from "@/lib/types";
import styles from "./BioactivityTable.module.css";

interface Props {
  bioactivities: BioactivityRecord[];
}

export default function BioactivityTable({ bioactivities }: Props) {
  if (!bioactivities || bioactivities.length === 0) {
    return null;
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.title}>
          <span>Measured Bioactivity Assays (ChEMBL Curated)</span>
          <span className={styles.countBadge}>{bioactivities.length} Assays</span>
        </div>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Biological Target</th>
              <th>Parameter</th>
              <th>Value</th>
              <th>Assay Context</th>
              <th>Record ID</th>
            </tr>
          </thead>
          <tbody>
            {bioactivities.map((act, idx) => {
              const displayVal = act.value_nm !== null && act.value_nm !== undefined
                ? `${act.relation || "="} ${act.value_nm} nM`
                : "Not stated";

              return (
                <tr key={idx}>
                  <td className={styles.targetCell}>
                    <div>{act.target_name}</div>
                    {act.target_organism && (
                      <span className={styles.organismText}>{act.target_organism}</span>
                    )}
                  </td>
                  <td>
                    <span className={styles.typeBadge}>{act.standard_type}</span>
                  </td>
                  <td className={styles.valueCell}>{displayVal}</td>
                  <td>
                    <span title={act.assay_description || ""} style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      {act.assay_description
                        ? act.assay_description.length > 70
                          ? `${act.assay_description.slice(0, 70)}...`
                          : act.assay_description
                        : "In vitro binding / functional assay"}
                    </span>
                  </td>
                  <td>
                    {act.chembl_assay_id ? (
                      <a
                        href={`https://www.ebi.ac.uk/chembl/assay_report_card/${act.chembl_assay_id}/`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.assayLink}
                      >
                        {act.chembl_assay_id}
                      </a>
                    ) : act.doi ? (
                      <a
                        href={`https://doi.org/${act.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.assayLink}
                      >
                        DOI
                      </a>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>ChEMBL</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
