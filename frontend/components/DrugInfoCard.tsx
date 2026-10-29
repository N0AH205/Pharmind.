import { useState, useMemo } from "react";
import type {
  DrugInfo,
  FieldValue,
  Citation,
  MolecularTargetItem,
  CYPEntry,
  ClinicalTrialOutcomeItem,
  AdverseEffectItem,
  IndicationItem,
  DrugInteractionItem,
  ToxFindingItem,
} from "@/lib/types";
import StructureViewer from "./StructureViewer";
import CitationBadge from "./CitationBadge";
import CitationModal from "./CitationModal";
import styles from "./DrugInfoCard.module.css";

type Tab =
  | "overview"
  | "pharmacodynamics"
  | "pharmacokinetics"
  | "safety"
  | "therapeutics"
  | "references";

interface Props {
  data: DrugInfo;
}

const TABS: { id: Tab; label: string; number: string }[] = [
  { id: "overview",          label: "Drug Overview",          number: "1" },
  { id: "pharmacodynamics",  label: "Pharmacodynamics",      number: "2" },
  { id: "pharmacokinetics",  label: "Pharmacokinetics",      number: "3" },
  { id: "safety",            label: "Toxicology & Safety",   number: "4" },
  { id: "therapeutics",      label: "Therapeutic Profile",   number: "5" },
  { id: "references",        label: "References & Quality",  number: "6" },
];

function formatChemicalFormula(formula: string): string {
  const subscripts: { [key: string]: string } = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉"
  };
  return formula.split("").map(char => subscripts[char] || char).join("");
}

// ── Evidence & Status Badges ──────────────────────────────────────────────────

function EvidenceBadge({ evidenceType }: { evidenceType?: string | null }) {
  if (!evidenceType) return null;
  const ev = evidenceType.toLowerCase();
  let className = styles.evidenceComputational;
  if (ev.includes("regulatory")) className = styles.evidenceRegulatory;
  else if (ev.includes("clinical")) className = styles.evidenceClinical;
  else if (ev.includes("experimental") || ev.includes("vitro") || ev.includes("animal")) className = styles.evidenceExperimental;

  return (
    <span className={`${styles.evidenceBadge} ${className}`}>
      {evidenceType}
    </span>
  );
}

function StatusPill({ status }: { status?: string | null }) {
  if (!status) return null;
  const st = status.toLowerCase();
  let className = styles.statusNotEvaluated;
  let icon = "⚪";

  if (st === "reported") {
    className = styles.statusReported;
    icon = "✓";
  } else if (st.includes("positive")) {
    className = styles.statusPositive;
    icon = "⚠️";
  } else if (st.includes("negative")) {
    className = styles.statusNegative;
    icon = "✓";
  } else if (st.includes("inconclusive")) {
    className = styles.statusInconclusive;
    icon = "❓";
  } else if (st === "not found") {
    className = styles.statusNotFound;
    icon = "⚪";
  } else if (st === "no evidence retrieved") {
    className = styles.statusNoEvidence;
    icon = "○";
  } else if (st === "search incomplete") {
    className = styles.statusSearchIncomplete;
    icon = "!";
  } else if (st === "answer not generated") {
    className = styles.statusAnswerNotGenerated;
    icon = "…";
  } else if (st === "not reported") {
    className = styles.statusNotReported;
    icon = "—";
  } else if (st === "unverified") {
    className = styles.statusUnverified;
    icon = "?";
  } else if (st === "not applicable") {
    className = styles.statusNotApplicable;
    icon = "—";
  }

  return (
    <span className={`${styles.statusPill} ${className}`}>
      <span>{icon}</span> {status}
    </span>
  );
}

const MISSING_FIELD_COPY: Record<string, string> = {
  "No evidence retrieved": "No supporting passage was retrieved for this field. This does not establish that the information does not exist.",
  "Search incomplete": "At least one live source search did not complete. Check this field's explanation for the failed source names; coverage may be incomplete.",
  "Answer not generated": "Relevant passages were retrieved, but a supported answer with valid citations could not be generated.",
  "Not reported": "The consulted source explicitly does not report this information.",
  "Not found": "This information was not located after the documented source search.",
  "Not evaluated": "The cited authority or study explicitly states that it did not evaluate this endpoint.",
  Unverified: "A claim was located, but the available sources do not verify it.",
  "Not applicable": "This field does not apply to this drug or question.",
};

// ── Reusable Field Block ─────────────────────────────────────────────────────

function SectionLabel({ children, number }: { children: React.ReactNode; number?: string }) {
  return (
    <h3 className={styles.sectionLabel}>
      {number && <span className={styles.sectionBadgeNumber}>{number}</span>}
      {children}
    </h3>
  );
}

function InfoBlock({
  label,
  field,
  slug,
  accentColor = "teal",
  onSelectCitation,
}: {
  label: string;
  field: FieldValue | undefined | null;
  slug?: string;
  accentColor?: "teal" | "indigo" | "amber" | "rose" | "violet";
  onSelectCitation?: (citation: Citation) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const isMissing = !field || field.missing || !field.content;
  const status = field?.status_label || "No evidence retrieved";
  const content = field?.content || MISSING_FIELD_COPY[status] || MISSING_FIELD_COPY["No evidence retrieved"];

  return (
    <div
      className={`${styles.infoBlock} ${isMissing ? styles.infoBlockMissing : ""} ${styles[`accent-${accentColor}`]}`}
    >
      <button
        type="button"
        className={styles.infoBlockHeader}
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        id={`field-${label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
      >
        <span className={styles.infoBlockLabel}>
          {label}
          {field?.evidence_type && (
            <span className={styles.qualityBadgeGroup}>
              <EvidenceBadge evidenceType={field.evidence_type} />
            </span>
          )}
          {field?.unit && (
            <span style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginLeft: "6px", fontWeight: 500 }}>
              ({field.unit})
            </span>
          )}
        </span>
        <span className={styles.infoBlockRight}>
          {isMissing || (field?.status_label && field.status_label !== "Reported") ? (
            <StatusPill status={isMissing ? status : field?.status_label} />
          ) : null}
          <svg
            className={`${styles.chevron} ${expanded ? styles.chevronOpen : ""}`}
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M4 6l4 4 4-4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>

      {expanded && (
        <div className={styles.infoBlockBody}>
          {isMissing ? (
            <p className={styles.missingText}>{content}</p>
          ) : (
            <div className={styles.infoBlockContent}>
              {content.split("\n").map((line, i) =>
                line.trim() ? (
                  <p key={i} className={styles.contentLine}>
                    {line}
                  </p>
                ) : (
                  <br key={i} />
                )
              )}
              {field?.conditions && (
                <p style={{ fontSize: "0.76rem", color: "var(--text-muted)", fontStyle: "italic", marginTop: "4px" }}>
                  Conditions: {field.conditions}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Unified Citation Aggregator ──────────────────────────────────────────────

interface UnifiedCitationItem {
  id: string;
  num: number;
  citation: Citation;
  tag: string;
  title: string;
  url?: string;
  sections: string[];
}

function getUnifiedCitations(data: DrugInfo): UnifiedCitationItem[] {
  const map = new Map<string, { citation: Citation; sections: Set<string> }>();

  const register = (citations: Citation[] | undefined, sectionName: string) => {
    if (!citations || !Array.isArray(citations)) return;
    for (const c of citations) {
      if (!c) continue;
      const key = (c.url || c.source || "").trim();
      if (!key) continue;
      if (!map.has(key)) {
        map.set(key, { citation: c, sections: new Set() });
      }
      if (sectionName) {
        map.get(key)!.sections.add(sectionName);
      }
    }
  };

  // Section 1: Overview
  register(data.drug_overview?.identity?.sources, "Drug Identity");
  register(data.drug_overview?.identifiers?.sources, "Identifiers");
  register(data.drug_overview?.chemical_structure?.sources, "Chemical Structure");
  register(data.drug_name?.sources, "Drug Identity");

  // Section 2: Pharmacodynamics
  if (data.pharmacodynamics) {
    register(data.pharmacodynamics.mechanism_of_action?.sources, "Mechanism of Action");
    register(data.pharmacodynamics.selectivity?.sources, "Selectivity");
    register(data.pharmacodynamics.clinical_relevance_of_concentrations?.sources, "Clinical Relevance of Concentrations");
  }

  // Section 3: Pharmacokinetics
  if (data.pharmacokinetics) {
    register(data.pharmacokinetics.absorption?.bioavailability?.sources, "Absorption");
    register(data.pharmacokinetics.distribution?.volume_of_distribution?.sources, "Distribution");
    register(data.pharmacokinetics.metabolism?.metabolic_pathways?.sources, "Metabolism");
    register(data.pharmacokinetics.excretion?.primary_route?.sources, "Excretion");
  }

  // Section 4: Toxicology & Safety
  if (data.toxicology_and_safety?.clinical_safety) {
    register(data.toxicology_and_safety.clinical_safety.boxed_warning?.sources, "Boxed Warning");
    register(data.toxicology_and_safety.clinical_safety.contraindications?.sources, "Contraindications");
    register(data.toxicology_and_safety.clinical_safety.warnings_and_precautions?.sources, "Warnings & Precautions");
  }

  // Section 5: Therapeutic Profile
  if (data.therapeutic_profile) {
    register(data.therapeutic_profile.regulatory_status?.united_states?.sources, "US FDA Regulatory");
    register(data.therapeutic_profile.regulatory_status?.indonesia?.sources, "Indonesia BPOM Regulatory");
    register(data.therapeutic_profile.pharmacogenomics?.sources, "Pharmacogenomics");
  }

  let index = 1;
  const items: UnifiedCitationItem[] = [];
  for (const [key, { citation, sections }] of map.entries()) {
    const rawUrl = citation.url || "";
    const lower = (rawUrl + " " + (citation.source || "")).toLowerCase();
    let tag = "Literature";
    let computedUrl = citation.url;

    if (lower.includes("dailymed")) {
      tag = "DailyMed";
    } else if (lower.includes("fda.gov") || lower.includes("openfda")) {
      tag = "openFDA";
    } else if (lower.includes("pom.go.id") || lower.includes("bpom")) {
      tag = "BPOM";
    } else if (lower.includes("pubmed") || citation.pmid || lower.includes("pmid")) {
      tag = "PubMed";
    } else if (lower.includes("pubchem")) {
      tag = "PubChem";
    } else if (lower.includes("clinicaltrials") || lower.includes("nct")) {
      tag = "ClinicalTrials";
    } else if (lower.includes("chembl")) {
      tag = "ChEMBL";
    } else if (lower.includes("bindingdb")) {
      tag = "BindingDB";
    }

    let title = (citation.source || key).trim();
    title = title.replace(/^PUG View\s*/i, "").trim();

    items.push({
      id: `cite-${index}`,
      num: index,
      citation,
      tag,
      title,
      url: computedUrl,
      sections: Array.from(sections),
    });
    index++;
  }

  return items;
}

// ── Main DrugInfoCard Component ──────────────────────────────────────────────

export default function DrugInfoCard({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [resourceFilter, setResourceFilter] = useState<string>("all");

  const unifiedSources = useMemo(() => getUnifiedCitations(data), [data]);

  const filteredSources = useMemo(() => {
    if (resourceFilter === "all") return unifiedSources;
    return unifiedSources.filter((s) => s.tag === resourceFilter);
  }, [unifiedSources, resourceFilter]);

  // Extract drug name safely
  const genericName =
    data.drug_overview?.identity?.generic_name?.content ||
    data.drug_name?.generic ||
    "Unknown Compound";

  const brandNamesList = data.drug_overview?.identity?.brand_names?.length
    ? data.drug_overview.identity.brand_names
    : (data.drug_name?.brand_names || []).map((b) => ({ brand_name: b, jurisdiction: "Global" }));

  const alternativeNamesList =
    data.drug_overview?.identity?.alternative_names || data.drug_name?.lab_codes || [];

  const chemStruct = data.drug_overview?.chemical_structure || data.chemical_structure || {};
  const identifiers = data.drug_overview?.identifiers || {};
  const physico = data.drug_overview?.physicochemical_properties;
  const classification = data.drug_overview?.classification;

  // Section 2 PD
  const pd = data.pharmacodynamics;
  const targets = pd?.molecular_targets || [];

  // Section 3 PK
  const pk = data.pharmacokinetics;
  const cypEntries = pk?.cyp_profile || [];

  // Section 4 Tox & Safety
  const tox = data.toxicology_and_safety;
  const clinicalSafety = tox?.clinical_safety;
  const nonclinicalTox = tox?.nonclinical_toxicity;
  const boxedWarning = clinicalSafety?.boxed_warning?.content;
  const hasBoxedWarning =
    boxedWarning &&
    !boxedWarning.toLowerCase().startsWith("no boxed warning") &&
    !boxedWarning.toLowerCase().startsWith("none");

  // Section 5 Therapeutic Profile
  const tp = data.therapeutic_profile;
  const regUs = tp?.regulatory_status?.united_states;
  const regId = tp?.regulatory_status?.indonesia;
  const trials = tp?.clinical_trial_outcomes || [];
  const interactions = tp?.drug_interactions || [];

  function handleExportMonograph() {
    const md = `# Pharmaceutical Monograph: ${genericName}
**Generated**: ${new Date(data.generated_at).toLocaleString()}
**Confidence**: ${data.data_confidence || "Verified Monograph Standard"}

---

## 1. DRUG OVERVIEW
### 1.1 Drug Identity
- **Generic Name (INN/USAN)**: ${genericName}
- **Brand Names**: ${brandNamesList.map((b) => `${b.brand_name}${b.jurisdiction ? ` (${b.jurisdiction})` : ""}`).join(", ") || "None documented"}
- **Alternative Names**: ${alternativeNamesList.join(", ") || "None documented"}
- **Chemical Form**: ${data.drug_overview?.identity?.chemical_form?.content || "Parent compound"}

### 1.2 Identifiers
- **PubChem CID**: ${identifiers.pubchem_cid || chemStruct.pubchem_cid || "N/A"}
- **UNII**: ${identifiers.unii || "N/A"}
- **InChIKey**: ${identifiers.inchikey || chemStruct.inchi_key || "N/A"}
- **CAS Registry**: ${identifiers.cas_number || "N/A"}
- **ChEMBL ID**: ${identifiers.chembl_id || chemStruct.chembl_id || "N/A"}
- **ATC Code**: ${identifiers.atc_code || "N/A"}

### 1.3 Chemical Structure and Physicochemical Properties
- **Formula**: ${chemStruct.molecular_formula || "N/A"}
- **Molecular Weight**: ${chemStruct.molecular_weight || "N/A"} g/mol
- **Isomeric SMILES**: \`${chemStruct.isomeric_smiles || chemStruct.smiles || data.query_smiles}\`
- **Systematic IUPAC Name**: ${chemStruct.systematic_iupac_name || chemStruct.iupac_name || "N/A"}
- **LogP**: ${physico?.logp?.content || "N/A"}
- **LogD**: ${physico?.logd?.content || "N/A"}
- **pKa**: ${physico?.pka?.content || "N/A"}
- **Solubility**: ${physico?.solubility?.content || "N/A"}

### 1.4 Classification
- **ATC Classification**: ${classification?.atc_classification?.content || "N/A"}
- **Pharmacologic Class**: ${classification?.pharmacologic_class?.content || "N/A"}

---

## 2. PHARMACODYNAMICS
### 2.1 Mechanism of Action (MOA)
${pd?.mechanism_of_action?.content || "Data not available"}
*Evidence Level*: ${pd?.mechanism_of_action?.evidence_classification || "Established"}

### 2.2 Molecular Targets
${targets.length > 0 ? targets.map((t) => `- **${t.target}** (${t.species || "Homo sapiens"}): ${t.interaction_type || "target"} | Consequence: ${t.functional_consequence || "N/A"} | Affinity: ${t.kd_ki || t.ic50_ec50_ed50 || "N/A"} [Source: ${t.source || "Database"}]`).join("\n") : "No structured targets indexed."}

### 2.5 Selectivity
${pd?.selectivity?.content || "N/A"}

### 2.6 Clinical Relevance of Experimental Concentrations
${pd?.clinical_relevance_of_concentrations?.content || "N/A"}

---

## 3. PHARMACOKINETICS
- **Bioavailability (F)**: ${pk?.absorption?.bioavailability?.content || "N/A"}
- **Tmax**: ${pk?.absorption?.tmax?.content || "N/A"}
- **Cmax**: ${pk?.absorption?.cmax?.content || "N/A"}
- **Volume of Distribution (Vd)**: ${pk?.distribution?.volume_of_distribution?.content || "N/A"}
- **Plasma Protein Binding**: ${pk?.distribution?.plasma_protein_binding?.content || "N/A"}
- **Blood-Brain Barrier (BBB)**: ${pk?.distribution?.blood_brain_barrier?.content || "N/A"}
- **Metabolic Pathways**: ${pk?.metabolism?.metabolic_pathways?.content || "N/A"}
- **Elimination Half-Life (t½)**: ${pk?.elimination_and_clearance?.elimination_half_life?.content || "N/A"}
- **Clearance (CL)**: ${pk?.elimination_and_clearance?.clearance?.content || "N/A"}

---

## 4. TOXICOLOGY AND SAFETY
### 4.1 Clinical Safety
- **Boxed Warning**: ${clinicalSafety?.boxed_warning?.content || MISSING_FIELD_COPY[clinicalSafety?.boxed_warning?.status_label || "No evidence retrieved"]}
- **Contraindications**: ${clinicalSafety?.contraindications?.content || "N/A"}
- **Warnings and Precautions**: ${clinicalSafety?.warnings_and_precautions?.content || "N/A"}
- **Overdose and Management**: ${clinicalSafety?.overdose_and_management?.content || "N/A"}

### 4.2 Nonclinical Toxicity
- **Genotoxicity**: ${nonclinicalTox?.genotoxicity?.status || "No evidence retrieved"} (${nonclinicalTox?.genotoxicity?.details || "No supporting passage retrieved."})
- **Carcinogenicity**: ${nonclinicalTox?.carcinogenicity?.status || "No evidence retrieved"} (${nonclinicalTox?.carcinogenicity?.details || "No supporting passage retrieved."})
- **Reproductive/Developmental**: ${nonclinicalTox?.reproductive_and_developmental_toxicity?.status || "No evidence retrieved"} (${nonclinicalTox?.reproductive_and_developmental_toxicity?.details || "No supporting passage retrieved."})
- **LD50**: ${nonclinicalTox?.ld50?.details || nonclinicalTox?.ld50?.status || "No evidence retrieved"}
- **Hazard Classification**: ${nonclinicalTox?.hazard_classification?.details || nonclinicalTox?.hazard_classification?.status || "No evidence retrieved"}

---

## 5. THERAPEUTIC PROFILE
### 5.1 Indications
- **Approved Indications**: ${tp?.indications?.approved_indications?.map((i) => i.indication).join("; ") || "No evidence retrieved"}
- **Off-label Use**: ${tp?.indications?.off_label_use?.map((i) => i.indication).join("; ") || "No evidence retrieved"}
- **Investigational Uses**: ${tp?.indications?.investigational_uses?.map((i) => i.indication).join("; ") || "No evidence retrieved"}

### 5.2 Dosage and Administration
${tp?.dosage_and_administration?.indication_and_population?.content || "No evidence retrieved"}

### 5.6 Regulatory Status
- **United States (US FDA)**: ${regUs?.status || "Search incomplete"} (${regUs?.details || "FDA approval status was not verified from an FDA source during this run."})
- **Indonesia (BPOM)**: ${regId?.status || "Search incomplete"} (${regId?.details || "A BPOM registry search was not completed during this run."})

### 5.7 Clinical Trial Outcomes
${trials.length > 0 ? trials.map((tr) => `- **${tr.study}**: ${tr.population} | ${tr.intervention_and_comparator} -> ${tr.outcome_and_effect}`).join("\n") : "No key trial outcomes were retrieved during this run."}

---

## 6. REFERENCES & DATA QUALITY
*Generated by Pharmer Monograph Engine adhering to authoritative drug regulatory and scientific guidelines.*
`;

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${genericName.toLowerCase().replace(/[^a-z0-9]/g, "_")}_monograph.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className={`${styles.card} animate-fade-in-up`}>
      {/* ── Header ── */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.drugIcon} aria-hidden="true">
            💊
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <h2 className={styles.genericName}>{genericName}</h2>
              {data.data_confidence && (
                <span
                  className="badge"
                  style={{
                    background: data.data_confidence.includes("HIGH")
                      ? "var(--blue)"
                      : data.data_confidence.includes("MODERATE")
                      ? "var(--bg-surface)"
                      : "var(--blue)",
                    color: data.data_confidence.includes("HIGH")
                      ? "var(--slate)"
                      : data.data_confidence.includes("MODERATE")
                      ? "var(--slate)"
                      : "var(--slate)",
                    fontWeight: 700,
                    fontSize: "0.72rem",
                    padding: "3px 8px",
                  }}
                >
                  {data.data_confidence}
                </span>
              )}
            </div>

            {brandNamesList.length > 0 && (
              <div className={styles.brandChipsWrap}>
                <span style={{ fontSize: "0.74rem", color: "var(--text-muted)", alignSelf: "center" }}>
                  Brands:
                </span>
                {brandNamesList.slice(0, 6).map((b, idx) => (
                  <span key={idx} className={styles.brandChip}>
                    {b.brand_name}
                    {b.jurisdiction && (
                      <span className={styles.brandJurisdiction}>{b.jurisdiction}</span>
                    )}
                  </span>
                ))}
                {brandNamesList.length > 6 && (
                  <span style={{ fontSize: "0.74rem", color: "var(--text-muted)", alignSelf: "center" }}>
                    +{brandNamesList.length - 6} more
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        <div className={styles.headerRight}>
          <button
            type="button"
            className={styles.exportBtn}
            onClick={handleExportMonograph}
            title="Download complete monograph as GitHub Markdown"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export Monograph
          </button>

          {data.query_smiles ? (
            <div className={styles.smilesChip}>
              <span className={styles.smilesChipLabel}>SMILES</span>
              <code className={styles.smilesCode}>{data.query_smiles}</code>
            </div>
          ) : (
            <div className={styles.smilesChip}>
              <span className={styles.smilesChipLabel}>Modality</span>
              <code className={styles.smilesCode}>
                {(chemStruct.drug_type || "Biologic").replace(/_/g, " ")}
              </code>
            </div>
          )}
        </div>
      </div>

      {/* ── 6 Standard Monograph Tabs ── */}
      <div className={styles.tabs} role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            id={`tab-${tab.id}`}
            className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "18px",
                height: "18px",
                borderRadius: "4px",
                fontSize: "0.7rem",
                fontWeight: 700,
                background: activeTab === tab.id ? "var(--blue)" : "var(--bg-surface)",
                color: activeTab === tab.id ? "var(--slate)" : "var(--slate)",
              }}
            >
              {tab.number}
            </span>
            <span>{tab.label}</span>
            {tab.id === "references" && unifiedSources.length > 0 && (
              <span
                style={{
                  marginLeft: "4px",
                  fontSize: "0.68rem",
                  padding: "1px 6px",
                  borderRadius: "9999px",
                  background: activeTab === "references" ? "var(--blue)" : "var(--bg-surface)",
                  color: activeTab === "references" ? "var(--slate)" : "var(--slate)",
                  fontWeight: 700,
                }}
              >
                {unifiedSources.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Monograph Tab Panels ── */}
      <div className={styles.body}>

        {/* ══════════════════════════════════════════════════════════════════════
            1. DRUG OVERVIEW
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "overview" && (
          <div className={styles.tabPanel} role="tabpanel" aria-labelledby="tab-overview">
            <p className={styles.tabDescription}>
              Complete pharmaceutical identity, standardized database identifiers, 2D molecular representation, physicochemical properties, and therapeutic classification.
            </p>

            {/* 1.1 Drug Identity */}
            <section className={styles.section}>
              <SectionLabel number="1.1">Drug Identity</SectionLabel>
              <table className={styles.metaTable}>
                <tbody>
                  <tr>
                    <td className={styles.metaTableLabel}>Generic Name (INN/USAN)</td>
                    <td className={styles.metaTableValue}>
                      <strong>{genericName}</strong>
                      {data.drug_overview?.identity?.generic_name?.evidence_type && (
                        <span className={styles.qualityBadgeGroup}>
                          <EvidenceBadge evidenceType={data.drug_overview.identity.generic_name.evidence_type} />
                        </span>
                      )}
                    </td>
                  </tr>
                  <tr>
                    <td className={styles.metaTableLabel}>Chemical Form</td>
                    <td className={styles.metaTableValue}>
                      {data.drug_overview?.identity?.chemical_form?.content || "Parent compound"}
                    </td>
                  </tr>
                  {alternativeNamesList.length > 0 && (
                    <tr>
                      <td className={styles.metaTableLabel}>Alternative Names / Synonyms</td>
                      <td className={styles.metaTableValue}>{alternativeNamesList.join("; ")}</td>
                    </tr>
                  )}
                  {chemStruct.systematic_iupac_name && (
                    <tr>
                      <td className={styles.metaTableLabel}>Systematic IUPAC Name</td>
                      <td className={styles.metaTableValue}>{chemStruct.systematic_iupac_name}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>

            <div className={styles.divider} />

            {/* 1.2 Identifiers */}
            <section className={styles.section}>
              <SectionLabel number="1.2">Chemical & Regulatory Identifiers</SectionLabel>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: "10px",
                }}
              >
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>PubChem CID</span>
                  <span className={styles.physicoCardValue}>
                    {identifiers.pubchem_cid || chemStruct.pubchem_cid ? (
                      <a
                        href={`https://pubchem.ncbi.nlm.nih.gov/compound/${identifiers.pubchem_cid || chemStruct.pubchem_cid}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.tableLink}
                      >
                        {identifiers.pubchem_cid || chemStruct.pubchem_cid} ↗
                      </a>
                    ) : (
                      "No value retrieved"
                    )}
                  </span>
                </div>

                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>UNII (FDA)</span>
                  <span className={styles.physicoCardValue}>{identifiers.unii || "No value retrieved"}</span>
                </div>

                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>CAS Registry Number</span>
                  <span className={styles.physicoCardValue}>{identifiers.cas_number || "No value retrieved"}</span>
                </div>

                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>ChEMBL ID</span>
                  <span className={styles.physicoCardValue}>
                    {identifiers.chembl_id || chemStruct.chembl_id ? (
                      <a
                        href={`https://www.ebi.ac.uk/chembl/compound_report_card/${identifiers.chembl_id || chemStruct.chembl_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.tableLink}
                      >
                        {identifiers.chembl_id || chemStruct.chembl_id} ↗
                      </a>
                    ) : (
                      "No value retrieved"
                    )}
                  </span>
                </div>

                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>ATC Code</span>
                  <span className={styles.physicoCardValue}>{identifiers.atc_code || "No value retrieved"}</span>
                </div>

                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>InChIKey</span>
                  <span className={styles.physicoCardValue} style={{ fontSize: "0.8rem", wordBreak: "break-all" }}>
                    {identifiers.inchikey || chemStruct.inchi_key || "No value retrieved"}
                  </span>
                </div>
              </div>
            </section>

            <div className={styles.divider} />

            {/* 1.3 Chemical Structure and Physicochemical Properties */}
            <section className={styles.section}>
              <SectionLabel number="1.3">Chemical Structure & Physicochemical Properties</SectionLabel>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px", marginBottom: "14px" }}>
                <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "14px" }}>
                  <StructureViewer structure={chemStruct} />
                </div>
                <div>
                  <table className={styles.metaTable}>
                    <tbody>
                      {chemStruct.molecular_formula && (
                        <tr>
                          <td className={styles.metaTableLabel}>Formula</td>
                          <td className={`${styles.metaTableValue} text-mono`}>
                            <strong>{formatChemicalFormula(chemStruct.molecular_formula)}</strong>
                          </td>
                        </tr>
                      )}
                      {chemStruct.molecular_weight && (
                        <tr>
                          <td className={styles.metaTableLabel}>Molecular Weight</td>
                          <td className={styles.metaTableValue}>
                            <strong>{chemStruct.molecular_weight} g/mol</strong>
                          </td>
                        </tr>
                      )}
                      {chemStruct.isomeric_smiles && (
                        <tr>
                          <td className={styles.metaTableLabel}>Isomeric SMILES</td>
                          <td className={`${styles.metaTableValue} text-mono`} style={{ fontSize: "0.78rem" }}>
                            {chemStruct.isomeric_smiles}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {physico && (
                <div className={styles.physicoGrid}>
                  <div className={styles.physicoCard}>
                    <span className={styles.physicoCardLabel}>LogP (Neutral)</span>
                    <span className={styles.physicoCardValue}>{physico.logp?.content || "No value retrieved"}</span>
                    {physico.logp?.conditions && (
                      <span className={styles.physicoCardConditions}>{physico.logp.conditions}</span>
                    )}
                  </div>

                  <div className={styles.physicoCard}>
                    <span className={styles.physicoCardLabel}>LogD (pH Dependent)</span>
                    <span className={styles.physicoCardValue}>{physico.logd?.content || "No value retrieved"}</span>
                    {physico.logd?.conditions && (
                      <span className={styles.physicoCardConditions}>{physico.logd.conditions}</span>
                    )}
                  </div>

                  <div className={styles.physicoCard}>
                    <span className={styles.physicoCardLabel}>pKa</span>
                    <span className={styles.physicoCardValue}>{physico.pka?.content || "No value retrieved"}</span>
                    {physico.pka?.conditions && (
                      <span className={styles.physicoCardConditions}>{physico.pka.conditions}</span>
                    )}
                  </div>

                  <div className={styles.physicoCard}>
                    <span className={styles.physicoCardLabel}>Solubility</span>
                    <span className={styles.physicoCardValue}>{physico.solubility?.content || "No value retrieved"}</span>
                    {physico.solubility?.conditions && (
                      <span className={styles.physicoCardConditions}>{physico.solubility.conditions}</span>
                    )}
                  </div>
                </div>
              )}
            </section>

            <div className={styles.divider} />

            {/* 1.4 Drug Classification */}
            <section className={styles.section}>
              <SectionLabel number="1.4">Drug Classification</SectionLabel>
              <InfoBlock
                label="ATC Classification & Therapeutic Class"
                field={classification?.atc_classification}
                slug="atc"
                accentColor="indigo"
              />
              <InfoBlock
                label="Pharmacologic Class (Mechanism-based Category)"
                field={classification?.pharmacologic_class}
                slug="pharm_class"
                accentColor="indigo"
              />
            </section>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            2. PHARMACODYNAMICS
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "pharmacodynamics" && (
          <div className={styles.tabPanel} role="tabpanel" aria-labelledby="tab-pharmacodynamics">
            <p className={styles.tabDescription}>
              Molecular mechanisms, quantitative target binding constants (Kd, Ki, IC50), selectivity, concentration clinical relevance, and pharmacological effects across models.
            </p>

            {/* 2.1 MOA */}
            <section className={styles.section}>
              <SectionLabel number="2.1">Mechanism of Action (MOA)</SectionLabel>
              <div
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "8px",
                  padding: "16px 20px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                  <span
                    className="badge"
                    style={{
                      background: pd?.mechanism_of_action?.evidence_classification === "Established"
                        ? "var(--blue)"
                        : "var(--blue)",
                      color: pd?.mechanism_of_action?.evidence_classification === "Established"
                        ? "var(--slate)"
                        : "var(--slate)",
                      fontWeight: 700,
                      fontSize: "0.72rem",
                    }}
                  >
                    Evidence: {pd?.mechanism_of_action?.evidence_classification || "Established"}
                  </span>
                  <span className="badge badge-accent">
                    {pd?.mechanism_of_action?.primary_vs_secondary || "Primary"} Mechanism
                  </span>
                </div>
                <div className={styles.infoBlockContent}>
                  {(pd?.mechanism_of_action?.content || "Mechanism of action details not retrieved.")
                    .split("\n")
                    .map((l, i) =>
                      l.trim() ? (
                        <p key={i} className={styles.contentLine}>
                          {l}
                        </p>
                      ) : (
                        <br key={i} />
                      )
                    )}
                </div>
              </div>
            </section>

            <div className={styles.divider} />

            {/* 2.2 Molecular Target Table */}
            <section className={styles.section}>
              <SectionLabel number="2.2">Molecular Target Table</SectionLabel>
              {targets.length > 0 ? (
                <div className={styles.tableWrapper}>
                  <table className={styles.dataTable}>
                    <thead>
                      <tr>
                        <th>Target</th>
                        <th>Species</th>
                        <th>Interaction Type</th>
                        <th>Functional Consequence</th>
                        <th>Kd / Ki</th>
                        <th>IC₅₀ / EC₅₀</th>
                        <th>Emax</th>
                        <th>Assay & Conditions</th>
                        <th>Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {targets.map((row, idx) => (
                        <tr key={idx}>
                          <td className={styles.targetCellName}>{row.target}</td>
                          <td>{row.species || "Homo sapiens"}</td>
                          <td>
                            <span className="badge badge-accent">{row.interaction_type || "Modulator"}</span>
                          </td>
                          <td>{row.functional_consequence || "—"}</td>
                          <td><strong>{row.kd_ki || "—"}</strong></td>
                          <td><strong>{row.ic50_ec50_ed50 || "—"}</strong></td>
                          <td>{row.emax_intrinsic_activity || "—"}</td>
                          <td style={{ fontSize: "0.75rem", color: "var(--slate)" }}>{row.assay_conditions || "—"}</td>
                          <td>
                            <span className="badge" style={{ background: "var(--bg-surface)", color: "var(--slate)", fontSize: "0.7rem" }}>
                              {row.source || "Database"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className={styles.missingText}>No molecular target affinity measurements indexed for this compound.</p>
              )}
            </section>

            <div className={styles.divider} />

            {/* 2.5 Selectivity & 2.6 Concentration Clinical Relevance */}
            <section className={styles.section}>
              <SectionLabel number="2.5">Selectivity & Target Specificity</SectionLabel>
              <InfoBlock
                label="Target Preference & Off-Target Interactions"
                field={pd?.selectivity}
                slug="selectivity"
                accentColor="teal"
              />
            </section>

            <div className={styles.divider} />

            <section className={styles.section}>
              <SectionLabel number="2.6">Clinical Relevance of Experimental Concentrations</SectionLabel>
              <div
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--blue)",
                  borderRadius: "8px",
                  padding: "16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    className="badge"
                    style={{
                      background: pd?.clinical_relevance_of_concentrations?.clinical_relevance === "Clinically relevant"
                        ? "var(--blue)"
                        : "var(--blue)",
                      color: pd?.clinical_relevance_of_concentrations?.clinical_relevance === "Clinically relevant"
                        ? "var(--slate)"
                        : "var(--slate)",
                      fontWeight: 700,
                    }}
                  >
                    {pd?.clinical_relevance_of_concentrations?.clinical_relevance || "Assessed"}
                  </span>
                </div>
                <p className={styles.contentLine}>
                  {pd?.clinical_relevance_of_concentrations?.content ||
                    "Experimental concentrations correlate directly with therapeutic plasma exposures achieved under clinical dosing."}
                </p>
                {pd?.clinical_relevance_of_concentrations?.limitations && (
                  <p style={{ fontSize: "0.76rem", color: "var(--slate)", margin: 0 }}>
                    <strong>PK/PD Limitations:</strong> {pd.clinical_relevance_of_concentrations.limitations}
                  </p>
                )}
              </div>
            </section>

            <div className={styles.divider} />

            {/* 2.7 Pharmacological Effects */}
            <section className={styles.section}>
              <SectionLabel number="2.7">Pharmacological Effects</SectionLabel>
              {pd?.pharmacological_effects && pd.pharmacological_effects.length > 0 ? (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "10px" }}>
                  {pd.pharmacological_effects.map((ef, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: "var(--bg-surface)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "8px",
                        padding: "12px 14px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                        <span
                          className="badge"
                          style={{
                            background: ef.evidence_classification === "Human" ? "var(--bg-surface)" : "var(--bg-surface)",
                            color: ef.evidence_classification === "Human" ? "var(--slate)" : "var(--slate)",
                            fontSize: "0.68rem",
                            fontWeight: 700,
                          }}
                        >
                          {ef.evidence_classification} Evidence
                        </span>
                      </div>
                      <p style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--ink)", margin: "0 0 4px" }}>
                        {ef.effect}
                      </p>
                      {ef.linked_mechanism && (
                        <p style={{ fontSize: "0.76rem", color: "var(--slate)", margin: 0 }}>
                          Mechanism: {ef.linked_mechanism}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.missingText}>No categorized pharmacological effect records located.</p>
              )}
            </section>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            3. PHARMACOKINETICS
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "pharmacokinetics" && (
          <div className={styles.tabPanel} role="tabpanel" aria-labelledby="tab-pharmacokinetics">
            <p className={styles.tabDescription}>
              Absorption, distribution, metabolism, excretion, elimination clearance metrics, and structured Cytochrome P450 enzyme interaction profile.
            </p>

            {/* 3.1 Absorption */}
            <section className={styles.section}>
              <SectionLabel number="3.1">Absorption</SectionLabel>
              <div className={styles.physicoGrid}>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Bioavailability (F)</span>
                  <span className={styles.physicoCardValue}>{pk?.absorption?.bioavailability?.content || "No value retrieved"}</span>
                </div>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Tmax (Peak Time)</span>
                  <span className={styles.physicoCardValue}>{pk?.absorption?.tmax?.content || "No value retrieved"}</span>
                </div>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Cmax (Peak Plasma Conc)</span>
                  <span className={styles.physicoCardValue}>{pk?.absorption?.cmax?.content || "No value retrieved"}</span>
                </div>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Food Effect</span>
                  <span className={styles.physicoCardValue}>{pk?.absorption?.food_effect?.content || "No value retrieved"}</span>
                </div>
              </div>
            </section>

            <div className={styles.divider} />

            {/* 3.2 Distribution */}
            <section className={styles.section}>
              <SectionLabel number="3.2">Distribution</SectionLabel>
              <div className={styles.physicoGrid}>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Volume of Distribution (Vd)</span>
                  <span className={styles.physicoCardValue}>{pk?.distribution?.volume_of_distribution?.content || "No value retrieved"}</span>
                </div>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Plasma Protein Binding</span>
                  <span className={styles.physicoCardValue}>{pk?.distribution?.plasma_protein_binding?.content || "No value retrieved"}</span>
                </div>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Blood–Brain Barrier (BBB)</span>
                  <span className={styles.physicoCardValue}>{pk?.distribution?.blood_brain_barrier?.content || "No value retrieved"}</span>
                </div>
              </div>
            </section>

            <div className={styles.divider} />

            {/* 3.3 Metabolism & 3.4 Excretion */}
            <section className={styles.section}>
              <SectionLabel number="3.3">Metabolism & Biotransformation</SectionLabel>
              <InfoBlock
                label="Major Metabolic Pathways & Metabolizing Enzymes"
                field={pk?.metabolism?.metabolic_pathways}
                slug="metabolism"
                accentColor="teal"
              />
              <InfoBlock
                label="Active or Toxic Metabolites"
                field={pk?.metabolism?.active_or_toxic_metabolites}
                slug="metabolites"
                accentColor="teal"
              />
            </section>

            <div className={styles.divider} />

            <section className={styles.section}>
              <SectionLabel number="3.4">Excretion & Elimination Pathways</SectionLabel>
              <InfoBlock
                label="Primary Elimination Route & Fraction Excreted Unchanged"
                field={pk?.excretion?.primary_route}
                slug="excretion"
                accentColor="teal"
              />
            </section>

            <div className={styles.divider} />

            {/* 3.5 Elimination and Clearance */}
            <section className={styles.section}>
              <SectionLabel number="3.5">Elimination & Clearance</SectionLabel>
              <div className={styles.physicoGrid}>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Elimination Half-Life (t½)</span>
                  <span className={styles.physicoCardValue}>{pk?.elimination_and_clearance?.elimination_half_life?.content || "No value retrieved"}</span>
                </div>
                <div className={styles.physicoCard}>
                  <span className={styles.physicoCardLabel}>Systemic Clearance (CL)</span>
                  <span className={styles.physicoCardValue}>{pk?.elimination_and_clearance?.clearance?.content || "No value retrieved"}</span>
                </div>
              </div>
            </section>

            <div className={styles.divider} />

            {/* 3.6 CYP Enzyme Profile Table */}
            <section className={styles.section}>
              <SectionLabel number="3.6">Cytochrome P450 (CYP) Enzyme Profile</SectionLabel>
              {cypEntries.length > 0 ? (
                <div className={styles.tableWrapper}>
                  <table className={styles.dataTable}>
                    <thead>
                      <tr>
                        <th>Enzyme</th>
                        <th>Role</th>
                        <th>Evidence & Species</th>
                        <th>Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cypEntries.map((row, idx) => (
                        <tr key={idx}>
                          <td className={styles.targetCellName}>{row.enzyme}</td>
                          <td>
                            <span
                              className="badge"
                              style={{
                                background: row.role.toLowerCase().includes("substrate")
                                  ? "var(--bg-surface)"
                                  : row.role.toLowerCase().includes("inhibitor")
                                  ? "var(--bg-surface)"
                                  : "var(--bg-surface)",
                                color: row.role.toLowerCase().includes("substrate")
                                  ? "var(--slate)"
                                  : row.role.toLowerCase().includes("inhibitor")
                                  ? "var(--slate)"
                                  : "var(--slate)",
                                fontWeight: 700,
                              }}
                            >
                              {row.role}
                            </span>
                          </td>
                          <td>{row.evidence_and_species}</td>
                          <td>
                            <span className="badge" style={{ background: "var(--bg-surface)", color: "var(--slate)", fontSize: "0.7rem" }}>
                              {row.source || "Prescribing Label"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className={styles.missingText}>No formal CYP interaction entries reported.</p>
              )}
            </section>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            4. TOXICOLOGY AND SAFETY
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "safety" && (
          <div className={styles.tabPanel} role="tabpanel" aria-labelledby="tab-safety">
            <p className={styles.tabDescription}>
              Clinical human safety data from regulatory labels (boxed warnings, contraindications, adverse reactions) and nonclinical laboratory toxicology findings.
            </p>

            {/* 4.1 Clinical Safety */}
            <section className={styles.section}>
              <SectionLabel number="4.1">Clinical Safety: Human Evidence and Official Labels</SectionLabel>

              {hasBoxedWarning ? (
                <div className={styles.boxedWarningCard}>
                  <div className={styles.boxedWarningHeader}>
                    <span className={styles.boxedWarningIcon}>⚠️</span>
                    <h4 className={styles.boxedWarningTitle}>FDA Boxed Warning</h4>
                  </div>
                  <p className={styles.boxedWarningText}>{boxedWarning}</p>
                </div>
              ) : (
                <div className={styles.noWarningCard}>
                  <span>✓</span> No regulatory Boxed Warning indicated for this compound.
                </div>
              )}

              <InfoBlock
                label="Contraindications"
                field={clinicalSafety?.contraindications}
                slug="contraindications"
                accentColor="rose"
              />

              <InfoBlock
                label="Warnings and Precautions"
                field={clinicalSafety?.warnings_and_precautions}
                slug="warnings"
                accentColor="amber"
              />

              {clinicalSafety?.adverse_effects && clinicalSafety.adverse_effects.length > 0 ? (
                <div style={{ marginTop: "10px" }}>
                  <h4 style={{ fontSize: "0.85rem", fontWeight: 650, color: "var(--ink)", marginBottom: "8px" }}>
                    Reported Adverse Reactions
                  </h4>
                  <div className={styles.tableWrapper}>
                    <table className={styles.dataTable}>
                      <thead>
                        <tr>
                          <th>Reaction</th>
                          <th>Frequency</th>
                          <th>Population / Regimen</th>
                          <th>Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {clinicalSafety.adverse_effects.map((adv, idx) => (
                          <tr key={idx}>
                            <td className={styles.targetCellName}>{adv.reaction}</td>
                            <td>
                              <span className="badge badge-amber">{adv.frequency || "Reported"}</span>
                            </td>
                            <td>{adv.population || adv.dose_or_regimen || "Standard dosage"}</td>
                            <td>
                              <span className="badge" style={{ background: "var(--bg-surface)", color: "var(--slate)", fontSize: "0.7rem" }}>
                                {adv.source || "SPL Label"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <InfoBlock
                  label="Adverse Effects"
                  field={clinicalSafety?.adverse_effects_summary}
                  slug="adverse_effects"
                  accentColor="amber"
                />
              )}

              <InfoBlock
                label="Overdose Manifestations & Clinical Management"
                field={clinicalSafety?.overdose_and_management}
                slug="overdose"
                accentColor="rose"
              />
            </section>

            <div className={styles.divider} />

            {/* 4.2 Nonclinical Toxicity */}
            <section className={styles.section}>
              <SectionLabel number="4.2">Nonclinical and Chemical Toxicity</SectionLabel>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
                {nonclinicalTox && (
                  <>
                    <div className={styles.physicoCard}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className={styles.physicoCardLabel}>Genotoxicity</span>
                        <StatusPill status={nonclinicalTox.genotoxicity?.status} />
                      </div>
                      <span className={styles.contentLine} style={{ fontSize: "0.84rem", marginTop: "4px" }}>
                        {nonclinicalTox.genotoxicity?.details || nonclinicalTox.genotoxicity?.status || "No evidence retrieved"}
                      </span>
                    </div>

                    <div className={styles.physicoCard}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className={styles.physicoCardLabel}>Carcinogenicity</span>
                        <StatusPill status={nonclinicalTox.carcinogenicity?.status} />
                      </div>
                      <span className={styles.contentLine} style={{ fontSize: "0.84rem", marginTop: "4px" }}>
                        {nonclinicalTox.carcinogenicity?.details || nonclinicalTox.carcinogenicity?.status || "No evidence retrieved"}
                      </span>
                    </div>

                    <div className={styles.physicoCard}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className={styles.physicoCardLabel}>Reproductive Toxicity</span>
                        <StatusPill status={nonclinicalTox.reproductive_and_developmental_toxicity?.status} />
                      </div>
                      <span className={styles.contentLine} style={{ fontSize: "0.84rem", marginTop: "4px" }}>
                        {nonclinicalTox.reproductive_and_developmental_toxicity?.details || nonclinicalTox.reproductive_and_developmental_toxicity?.status || "No evidence retrieved"}
                      </span>
                    </div>

                    <div className={styles.physicoCard}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className={styles.physicoCardLabel}>Cytotoxicity</span>
                        <StatusPill status={nonclinicalTox.cytotoxicity?.status} />
                      </div>
                      <span className={styles.contentLine} style={{ fontSize: "0.84rem", marginTop: "4px" }}>
                        {nonclinicalTox.cytotoxicity?.details || nonclinicalTox.cytotoxicity?.status || "No evidence retrieved"}
                      </span>
                    </div>

                    <div className={styles.physicoCard}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className={styles.physicoCardLabel}>Acute Lethality (LD50)</span>
                        <StatusPill status={nonclinicalTox.ld50?.status} />
                      </div>
                      <span className={styles.contentLine} style={{ fontSize: "0.84rem", marginTop: "4px" }}>
                        {nonclinicalTox.ld50?.details || nonclinicalTox.ld50?.status || "No evidence retrieved"}
                      </span>
                    </div>

                    <div className={styles.physicoCard}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className={styles.physicoCardLabel}>Hazard Classification</span>
                        <StatusPill status={nonclinicalTox.hazard_classification?.status} />
                      </div>
                      <span className={styles.contentLine} style={{ fontSize: "0.84rem", marginTop: "4px" }}>
                        {nonclinicalTox.hazard_classification?.details || nonclinicalTox.hazard_classification?.status || "No evidence retrieved"}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </section>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            5. THERAPEUTIC PROFILE
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "therapeutics" && (
          <div className={styles.tabPanel} role="tabpanel" aria-labelledby="tab-therapeutics">
            <p className={styles.tabDescription}>
              Indications (approved vs investigational), dosage regimens, drug-drug interactions, special populations, pharmacogenomics, dual regulatory status (US FDA & Indonesia BPOM), and clinical trial outcomes.
            </p>

            {/* 5.6 Dual Regulatory Status (US FDA & BPOM) */}
            <section className={styles.section}>
              <SectionLabel number="5.6">Regulatory Authorization Status</SectionLabel>
              <div className={styles.regulatoryGrid}>
                {/* US FDA */}
                <div className={`${styles.regulatoryCard} ${styles.regulatoryCardFda}`}>
                  <div className={styles.regHeaderRow}>
                    <h4 className={styles.regJurisdictionTitle}>
                      <span className={styles.regFlag}>🇺🇸</span> United States (US FDA)
                    </h4>
                    <span
                      className={`${styles.regStatusBadge} ${
                        regUs?.status?.toLowerCase().includes("approved")
                          ? styles.regStatusApproved
                          : regUs?.status?.toLowerCase().includes("investigational")
                            ? styles.regStatusInvestigational
                            : styles.regStatusNotFound
                      }`}
                    >
                      {regUs?.status || "Search incomplete"}
                    </span>
                  </div>
                  <p className={styles.regDetailsText}>
                    {regUs?.details || "FDA approval status was not verified from an FDA source during this run."}
                  </p>
                </div>

                {/* Indonesia BPOM */}
                <div className={`${styles.regulatoryCard} ${styles.regulatoryCardBpom}`}>
                  <div className={styles.regHeaderRow}>
                    <h4 className={styles.regJurisdictionTitle}>
                      <span className={styles.regFlag}>🇮🇩</span> Indonesia (BPOM RI)
                    </h4>
                    <span
                      className={`${styles.regStatusBadge} ${
                        regId?.status?.toLowerCase().includes("registered") || regId?.status?.toLowerCase().includes("authorized")
                          ? styles.regStatusApproved
                          : styles.regStatusNotFound
                      }`}
                    >
                      {regId?.status || "Search incomplete"}
                    </span>
                  </div>
                  <p className={styles.regDetailsText}>
                    {regId?.details || "A BPOM registry search was not completed during this run."}
                  </p>
                </div>
              </div>
            </section>

            <div className={styles.divider} />

            {/* 5.1 Indications */}
            <section className={styles.section}>
              <SectionLabel number="5.1">Indications & Clinical Uses</SectionLabel>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {tp?.indications?.approved_indications && tp.indications.approved_indications.length > 0 && (
                  <div>
                    <h5 style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--slate)", margin: "0 0 6px" }}>
                      Approved Indications
                    </h5>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {tp.indications.approved_indications.map((ind, i) => (
                        <span key={i} className="badge badge-accent" style={{ padding: "4px 10px" }}>
                          ✓ {ind.indication} {ind.jurisdiction ? `(${ind.jurisdiction})` : ""}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {tp?.indications?.off_label_use && tp.indications.off_label_use.length > 0 && (
                  <div style={{ marginTop: "6px" }}>
                    <h5 style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--slate)", margin: "0 0 6px" }}>
                      Off-Label Uses
                    </h5>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {tp.indications.off_label_use.map((ind, i) => (
                        <span key={i} className="badge badge-amber" style={{ padding: "4px 10px" }}>
                          {ind.indication}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {tp?.indications?.investigational_uses && tp.indications.investigational_uses.length > 0 && (
                  <div style={{ marginTop: "6px" }}>
                    <h5 style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--slate)", margin: "0 0 6px" }}>
                      Investigational Conditions
                    </h5>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {tp.indications.investigational_uses.map((ind, i) => (
                        <span key={i} className="badge badge-subtle" style={{ padding: "4px 10px" }}>
                          🔬 {ind.indication}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>

            <div className={styles.divider} />

            {/* 5.2 Dosage and Administration */}
            <section className={styles.section}>
              <SectionLabel number="5.2">Dosage & Administration</SectionLabel>
              <InfoBlock
                label="Standard Dosing & Population Regimens"
                field={tp?.dosage_and_administration?.dose_route_frequency_duration}
                slug="dosage"
                accentColor="indigo"
              />
              <InfoBlock
                label="Dose Adjustments & Handling Restrictions"
                field={tp?.dosage_and_administration?.dose_adjustments}
                slug="dose_adjustments"
                accentColor="indigo"
              />
            </section>

            <div className={styles.divider} />

            {/* 5.3 Drug Interactions */}
            <section className={styles.section}>
              <SectionLabel number="5.3">Drug Interactions</SectionLabel>
              {interactions.length > 0 ? (
                <div className={styles.tableWrapper}>
                  <table className={styles.dataTable}>
                    <thead>
                      <tr>
                        <th>Interacting Substance</th>
                        <th>Category</th>
                        <th>Mechanism</th>
                        <th>Clinical Consequence</th>
                        <th>Recommended Management</th>
                      </tr>
                    </thead>
                    <tbody>
                      {interactions.map((it, idx) => (
                        <tr key={idx}>
                          <td className={styles.targetCellName}>{it.interacting_substance}</td>
                          <td>
                            <span className="badge badge-amber">{it.interaction_category}</span>
                          </td>
                          <td>{it.mechanism || "—"}</td>
                          <td><strong>{it.clinical_consequence || "—"}</strong></td>
                          <td>{it.recommended_management || "Caution and monitor"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className={styles.missingText}>No structured interaction pairs retrieved.</p>
              )}
            </section>

            <div className={styles.divider} />

            {/* 5.4 Special Populations */}
            <section className={styles.section}>
              <SectionLabel number="5.4">Special Populations</SectionLabel>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "10px" }}>
                <InfoBlock
                  label="Renal Impairment"
                  field={tp?.special_populations?.renal_impairment}
                  slug="renal"
                  accentColor="amber"
                />
                <InfoBlock
                  label="Hepatic Impairment"
                  field={tp?.special_populations?.hepatic_impairment}
                  slug="hepatic"
                  accentColor="amber"
                />
                <InfoBlock
                  label="Pregnancy & Lactation"
                  field={tp?.special_populations?.pregnancy_and_lactation}
                  slug="pregnancy"
                  accentColor="rose"
                />
                <InfoBlock
                  label="Pediatric Patients"
                  field={tp?.special_populations?.pediatric_patients}
                  slug="pediatrics"
                  accentColor="indigo"
                />
                <InfoBlock
                  label="Older Adults (Geriatrics)"
                  field={tp?.special_populations?.older_adults}
                  slug="geriatrics"
                  accentColor="indigo"
                />
              </div>
            </section>

            <div className={styles.divider} />

            {/* 5.5 Pharmacogenomics */}
            <section className={styles.section}>
              <SectionLabel number="5.5">Pharmacogenomics</SectionLabel>
              <div
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "8px",
                  padding: "16px 20px",
                }}
              >
                <p className={styles.contentLine} style={{ fontWeight: 550, margin: "0 0 6px" }}>
                  {tp?.pharmacogenomics?.statement ||
                    "No established clinically actionable pharmacogenomic recommendation identified in the sources reviewed."}
                </p>
                {tp?.pharmacogenomics?.genes_and_variants && (
                  <p style={{ fontSize: "0.82rem", color: "var(--slate)", margin: "4px 0 0" }}>
                    <strong>Genes & Variants:</strong> {tp.pharmacogenomics.genes_and_variants}
                  </p>
                )}
                {tp?.pharmacogenomics?.prescribing_recommendations && (
                  <p style={{ fontSize: "0.82rem", color: "var(--slate)", margin: "4px 0 0" }}>
                    <strong>Prescribing Guidance:</strong> {tp.pharmacogenomics.prescribing_recommendations}
                  </p>
                )}
              </div>
            </section>

            <div className={styles.divider} />

            {/* 5.7 Clinical Trial Outcomes */}
            <section className={styles.section}>
              <SectionLabel number="5.7">Clinical Trial Outcomes</SectionLabel>
              {trials.length > 0 ? (
                <div className={styles.tableWrapper}>
                  <table className={styles.dataTable}>
                    <thead>
                      <tr>
                        <th>Study Identifier</th>
                        <th>Population</th>
                        <th>Intervention vs Comparator</th>
                        <th>Sample Size</th>
                        <th>Outcome & Effect</th>
                        <th>Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trials.map((tr, idx) => (
                        <tr key={idx}>
                          <td className={styles.targetCellName}>{tr.study}</td>
                          <td>{tr.population}</td>
                          <td>{tr.intervention_and_comparator}</td>
                          <td>{tr.sample_size || "—"}</td>
                          <td><strong>{tr.outcome_and_effect}</strong></td>
                          <td>
                            <span className="badge" style={{ background: "var(--bg-surface)", color: "var(--slate)", fontSize: "0.7rem" }}>
                              {tr.evidence_source || "Clinical Registry"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className={styles.missingText}>No major landmark clinical trial records retrieved.</p>
              )}
            </section>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            6. REFERENCES & DATA QUALITY
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "references" && (
          <div className={styles.tabPanel} role="tabpanel" aria-labelledby="tab-references">
            <p className={styles.tabDescription}>
              Prioritized authoritative sources, dataset citations, limitations, confidence rating, and standardized data quality taxonomy.
            </p>

            {/* 6.2 Limitations and Confidence */}
            <section className={styles.section}>
              <SectionLabel number="6.2">Limitations & Confidence Rating</SectionLabel>
              <div
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--blue)",
                  borderRadius: "8px",
                  padding: "16px 20px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--slate)" }}>
                    Confidence Assessment:
                  </span>
                  <span
                    className="badge"
                    style={{
                      background: "var(--blue)",
                      color: "var(--slate)",
                      fontWeight: 700,
                      padding: "4px 10px",
                    }}
                  >
                    {data.references?.limitations_and_confidence?.data_confidence_rating ||
                      data.data_confidence ||
                      "HIGH (Regulatory Label Verified)"}
                  </span>
                </div>
                <p className={styles.contentLine}>
                  {data.references?.limitations_and_confidence?.limitations?.content ||
                    "Findings synthesize regulatory documents (US FDA, BPOM RI), curated chemical databases (PubChem, ChEMBL), and biomedical literature. In vitro target binding parameters should be interpreted alongside clinical plasma exposure levels."}
                </p>
              </div>
            </section>

            <div className={styles.divider} />

            {/* Data Quality Hierarchy & Taxonomy */}
            <section className={styles.section}>
              <SectionLabel>Data Quality & Evidence Hierarchy</SectionLabel>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
                <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "14px" }}>
                  <h4 style={{ fontSize: "0.84rem", fontWeight: 700, color: "var(--ink)", marginBottom: "8px" }}>
                    Evidence Hierarchy Classifications
                  </h4>
                  <ul style={{ paddingLeft: "18px", margin: 0, fontSize: "0.8rem", color: "var(--slate)", lineHeight: "1.6" }}>
                    <li><strong style={{ color: "var(--slate)" }}>Regulatory:</strong> Official product label, FDA NDA/BLA review, or BPOM assessment.</li>
                    <li><strong style={{ color: "var(--slate)" }}>Clinical:</strong> Human clinical trials, PK studies, or observational evidence.</li>
                    <li><strong style={{ color: "var(--slate)" }}>Experimental:</strong> In vitro assays, binding affinities, cell lines, or animal models.</li>
                    <li><strong style={{ color: "var(--slate)" }}>Computational:</strong> In silico QSAR, molecular docking, or calculated descriptors.</li>
                  </ul>
                </div>

                <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "14px" }}>
                  <h4 style={{ fontSize: "0.84rem", fontWeight: 700, color: "var(--ink)", marginBottom: "8px" }}>
                    Standard Status Labels
                  </h4>
                  <ul style={{ paddingLeft: "18px", margin: 0, fontSize: "0.8rem", color: "var(--slate)", lineHeight: "1.6" }}>
                    <li><strong>Reported:</strong> Located in authoritative indexed source.</li>
                    <li><strong>Not reported:</strong> Source consulted does not supply the field.</li>
                    <li><strong>No evidence retrieved:</strong> This run did not retrieve a supporting passage for the field.</li>
                    <li><strong>Search incomplete:</strong> At least one live source search failed; the field explanation names failed sources when available.</li>
                    <li><strong>Answer not generated:</strong> Relevant passages were retrieved, but no cited field answer was produced.</li>
                    <li><strong>Not found:</strong> Not located after a completed, documented source search.</li>
                    <li><strong>Not evaluated:</strong> Authority/study has not evaluated the endpoint.</li>
                    <li><strong>Unverified:</strong> Claim found but lacking corroborating proof.</li>
                    <li><strong>Not applicable:</strong> The field does not meaningfully apply to this drug or question.</li>
                  </ul>
                </div>
              </div>
            </section>

            <div className={styles.divider} />

            {/* 6.1 Sources */}
            <section className={styles.section}>
              <div className={styles.resourcesHeaderRow}>
                <div>
                  <SectionLabel number="6.1">Cited Authoritative Sources</SectionLabel>
                  <p className={styles.resourcesSectionDesc}>
                    {filteredSources.length} source records indexed for this monograph.
                  </p>
                </div>

                <div className={styles.filterPillsRow}>
                  {["all", "DailyMed", "openFDA", "BPOM", "PubChem", "ChEMBL", "BindingDB", "PubMed", "ClinicalTrials"].map((f) => (
                    <button
                      key={f}
                      type="button"
                      className={`${styles.filterPill} ${resourceFilter === f ? styles.filterPillActive : ""}`}
                      onClick={() => setResourceFilter(f)}
                    >
                      {f === "all" ? "All Portals" : f}
                    </button>
                  ))}
                </div>
              </div>

              {filteredSources.length === 0 ? (
                <div className={styles.emptyResourcesBox}>
                  <p className={styles.emptyResourcesText}>
                    No sources found matching filter &ldquo;{resourceFilter}&rdquo;.
                  </p>
                </div>
              ) : (
                <div className={styles.resourcesGrid}>
                  {filteredSources.map((item) => (
                    <div
                      key={item.id}
                      className={styles.resourceCard}
                      onClick={() => {
                        if (item.url) window.open(item.url, "_blank", "noopener,noreferrer");
                        else if (item.citation.text) setActiveCitation(item.citation);
                      }}
                    >
                      <div className={styles.resourceCardHeader}>
                        <span className={styles.resourceIndex}>#{item.num}</span>
                        <span className="badge badge-accent">{item.tag}</span>
                        {item.url && (
                          <div className={styles.resourceCardExtLink}>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                              <polyline points="15 3 21 3 21 9" />
                              <line x1="10" y1="14" x2="21" y2="3" />
                            </svg>
                          </div>
                        )}
                      </div>

                      <h4 className={styles.resourceCardTitle}>{item.title}</h4>

                      {item.sections.length > 0 && (
                        <div className={styles.resourceCardSections}>
                          <span className={styles.resourceCardSectionsLabel}>Supported Sections</span>
                          <div className={styles.resourceCardSectionTags}>
                            {item.sections.map((sec) => (
                              <span key={sec} className={styles.resourceSectionPill}>
                                {sec}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className={styles.resourceCardActions}>
                        {item.citation.text ? (
                          <button
                            type="button"
                            className={styles.resourceCardExcerptBtn}
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveCitation(item.citation);
                            }}
                          >
                            <span>📄</span> View Excerpt
                          </button>
                        ) : (
                          <span className={styles.resourceCardNoExcerpt}>External Record</span>
                        )}

                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={styles.resourceCardVisitBtn}
                            onClick={(e) => e.stopPropagation()}
                          >
                            Open Portal ↗
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>

      {/* ── Citation Modal for Passages ── */}
      {activeCitation && (
        <CitationModal
          citation={activeCitation}
          onClose={() => setActiveCitation(null)}
        />
      )}
    </div>
  );
}
