/**
 * DrugInfo schema — TypeScript types matching the Python Pydantic backend schema (6-Section Standard).
 * Standard Sections:
 * 1. DRUG OVERVIEW (Identity, Identifiers, Chemical Structure & Physicochemical Properties, Classification)
 * 2. PHARMACODYNAMICS (Mechanism of Action, Molecular Target Table, Selectivity, Concentration Relevance, Pharmacological Effects)
 * 3. PHARMACOKINETICS (Absorption, Distribution, Metabolism, Excretion, Elimination/Clearance, CYP Enzyme Profile)
 * 4. TOXICOLOGY AND SAFETY (Clinical Safety, Nonclinical & Chemical Toxicity)
 * 5. THERAPEUTIC PROFILE (Indications, Dosage & Administration, Drug Interactions, Special Populations, Pharmacogenomics, Regulatory Status [US FDA & Indonesia BPOM], Clinical Trial Outcomes)
 * 6. REFERENCES & DATA QUALITY (Prioritized Sources Hierarchy, Limitations & Confidence Rating)
 */

export type EvidenceType = "Regulatory" | "Clinical" | "Experimental" | "Computational";

export type StatusLabel =
  | "Reported"
  | "Not reported"
  | "No evidence retrieved"
  | "Search incomplete"
  | "Answer not generated"
  | "Not found"
  | "Not evaluated"
  | "Unverified"
  | "Not applicable";

export interface Citation {
  source: string;       // e.g. "PubChem CID 2244", "DailyMed SPL 2023-04"
  url?: string;
  accessed_at?: string;
  text?: string;        // Full passage text retrieved from ChromaDB
  publication_date?: string;
  authors?: string;
  journal?: string;
  doi?: string;
  pmid?: string;
  document_id?: string;
}

export interface FieldValue {
  content: string | null;
  sources: Citation[];
  missing: boolean;
  evidence_type?: EvidenceType | string;
  status_label?: StatusLabel | string;
  unit?: string;
  conditions?: string;
}

// ── 1. DRUG OVERVIEW ──────────────────────────────────────────────────────────

export interface BrandNameItem {
  brand_name: string;
  jurisdiction?: string; // e.g., "United States", "Indonesia", "European Union"
}

export interface DrugIdentity {
  generic_name: FieldValue;
  brand_names: BrandNameItem[];
  alternative_names: string[];
  chemical_form: FieldValue;
  sources?: Citation[];
}

export interface DrugIdentifiers {
  pubchem_cid?: number | null;
  unii?: string | null;
  inchikey?: string | null;
  cas_number?: string | null;
  chembl_id?: string | null;
  atc_code?: string | null;
  sources?: Citation[];
}

export interface PhysicochemicalProperties {
  logp: FieldValue;
  logd: FieldValue;
  pka: FieldValue;
  solubility: FieldValue;
}

export interface DrugClassification {
  atc_classification: FieldValue;
  pharmacologic_class: FieldValue;
}

export interface ChemicalStructure {
  smiles?: string;
  isomeric_smiles?: string;
  systematic_iupac_name?: string;
  molecular_formula?: string;
  molecular_weight?: number;
  drug_type?: string;
  biologic_class?: string;
  target?: string;
  chembl_id?: string;
  inchi?: string;
  inchi_key?: string;
  iupac_name?: string; // legacy alias
  pubchem_cid?: number;
  image_url?: string;
  sources: Citation[];
}

export interface DrugOverview {
  identity: DrugIdentity;
  identifiers: DrugIdentifiers;
  chemical_structure: ChemicalStructure;
  physicochemical_properties: PhysicochemicalProperties;
  classification: DrugClassification;
}

// ── 2. PHARMACODYNAMICS ───────────────────────────────────────────────────────

export interface MolecularTargetItem {
  target: string;
  species?: string;
  interaction_type?: string;
  functional_consequence?: string;
  kd_ki?: string;
  ic50_ec50_ed50?: string;
  emax_intrinsic_activity?: string;
  assay_conditions?: string;
  source?: string;
}

export interface MechanismOfAction {
  content?: string | null;
  evidence_classification?: "Established" | "Proposed" | "Observed only at high concentrations" | string;
  primary_vs_secondary?: string;
  evidence_source?: string;
  sources: Citation[];
  missing: boolean;
}

export interface ClinicalRelevanceOfConcentrations {
  experimental_concentration?: string;
  typical_human_plasma_concentration?: string;
  clinical_relevance?: "Clinically relevant" | "Substantially higher" | "Uncertain" | string;
  limitations?: string;
  content?: string | null;
  sources: Citation[];
  missing: boolean;
}

export interface PharmacologicalEffectItem {
  effect: string;
  evidence_classification: "Human" | "Animal" | "In vitro" | string;
  linked_mechanism?: string;
}

export interface BioactivityRecord {
  target_name: string;
  target_organism?: string;
  action_type?: string;
  standard_type: string;
  value_nm?: number | null;
  relation?: string;
  pchembl_value?: number | null;
  assay_description?: string;
  chembl_assay_id?: string;
  doi?: string;
}

export interface PharmacodynamicsSection {
  mechanism_of_action: MechanismOfAction;
  molecular_targets: MolecularTargetItem[];
  selectivity: FieldValue;
  clinical_relevance_of_concentrations: ClinicalRelevanceOfConcentrations;
  pharmacological_effects: PharmacologicalEffectItem[];

  // Legacy fields
  physiologic_effect?: FieldValue;
  binding_affinity?: FieldValue;
  potency?: FieldValue;
  efficacy?: FieldValue;
  bioactivities?: BioactivityRecord[];
}

// ── 3. PHARMACOKINETICS ───────────────────────────────────────────────────────

export interface AbsorptionFields {
  bioavailability: FieldValue;
  tmax: FieldValue;
  cmax: FieldValue;
  food_effect: FieldValue;
  route_and_formulation: FieldValue;
}

export interface DistributionFields {
  volume_of_distribution: FieldValue;
  plasma_protein_binding: FieldValue;
  blood_brain_barrier: FieldValue;
}

export interface MetabolismFields {
  metabolic_pathways: FieldValue;
  active_or_toxic_metabolites: FieldValue;
  metabolizing_enzymes: FieldValue;
}

export interface ExcretionFields {
  primary_route: FieldValue;
  fraction_excreted_unchanged: FieldValue;
}

export interface EliminationClearanceFields {
  elimination_half_life: FieldValue;
  clearance: FieldValue;
}

export interface CYPEntry {
  enzyme: string;
  role: string;
  evidence_and_species: string;
  source?: string;
}

export interface CYPProfile {
  substrates: string[];
  inhibitors: string[];
  inducers: string[];
  evidence_source?: string;
}

export interface PharmacokineticsSection {
  absorption: AbsorptionFields;
  distribution: DistributionFields;
  metabolism: MetabolismFields;
  excretion: ExcretionFields;
  elimination_and_clearance: EliminationClearanceFields;
  cyp_profile: CYPEntry[];
  cyp_summary?: CYPProfile;
}

// ── 4. TOXICOLOGY AND SAFETY ──────────────────────────────────────────────────

export interface AdverseEffectItem {
  reaction: string;
  frequency?: string;
  population?: string;
  dose_or_regimen?: string;
  source?: string;
}

export interface ClinicalSafety {
  boxed_warning: FieldValue;
  contraindications: FieldValue;
  warnings_and_precautions: FieldValue;
  adverse_effects: AdverseEffectItem[];
  adverse_effects_summary?: FieldValue;
  overdose_and_management: FieldValue;
}

export type ToxStatus =
  | "Positive finding"
  | "Negative finding"
  | "Not evaluated"
  | "Not found"
  | "No evidence retrieved"
  | "Search incomplete"
  | "Answer not generated"
  | "Inconclusive";

export interface ToxFindingItem {
  status: ToxStatus | string;
  details?: string;
  species_or_model?: string;
  study_conditions?: string;
}

export interface NonclinicalToxicity {
  genotoxicity: ToxFindingItem;
  carcinogenicity: ToxFindingItem;
  reproductive_and_developmental_toxicity: ToxFindingItem;
  cytotoxicity: ToxFindingItem;
  ld50: ToxFindingItem;
  lc50: ToxFindingItem;
  hazard_classification: ToxFindingItem;
}

export interface ToxicologySection {
  clinical_safety: ClinicalSafety;
  nonclinical_toxicity: NonclinicalToxicity;

  // Legacy fields
  acute_toxicity?: FieldValue;
  cytotoxicity?: FieldValue;
  genetic_toxicology?: FieldValue;
  hazard_classifications?: FieldValue;
}

// ── 5. THERAPEUTIC PROFILE ────────────────────────────────────────────────────

export interface IndicationItem {
  indication: string;
  jurisdiction?: string;
  dosage_form?: string;
  evidence_type?: string;
  source?: string;
}

export interface IndicationsCategories {
  approved_indications: IndicationItem[];
  off_label_use: IndicationItem[];
  investigational_uses: IndicationItem[];
  summary?: FieldValue;
}

export interface DosageAndAdministration {
  indication_and_population: FieldValue;
  dose_route_frequency_duration: FieldValue;
  formulation_instructions: FieldValue;
  dose_adjustments: FieldValue;
  administration_restrictions: FieldValue;
}

export interface DrugInteractionItem {
  interacting_substance: string;
  interaction_category: string;
  mechanism?: string;
  clinical_consequence?: string;
  evidence_level?: string;
  recommended_management?: string;
}

export interface SpecialPopulations {
  renal_impairment: FieldValue;
  hepatic_impairment: FieldValue;
  pregnancy_and_lactation: FieldValue;
  pediatric_patients: FieldValue;
  older_adults: FieldValue;
  other_populations: FieldValue;
}

export interface PharmacogenomicsField {
  genes_and_variants?: string;
  clinical_consequences?: string;
  prescribing_recommendations?: string;
  statement: string;
  sources: Citation[];
  missing: boolean;
}

export interface JurisdictionRegulatory {
  jurisdiction: string;
  authority: string;
  status: string;
  details?: string;
  sources: Citation[];
}

export interface RegulatoryStatus {
  united_states: JurisdictionRegulatory;
  indonesia: JurisdictionRegulatory;
}

export interface ClinicalTrialOutcomeItem {
  study: string;
  population: string;
  intervention_and_comparator: string;
  sample_size?: string;
  outcome_and_effect: string;
  evidence_source?: string;
}

export interface TherapeuticProfileSection {
  indications: IndicationsCategories;
  dosage_and_administration: DosageAndAdministration;
  drug_interactions: DrugInteractionItem[];
  special_populations: SpecialPopulations;
  pharmacogenomics: PharmacogenomicsField;
  regulatory_status: RegulatoryStatus;
  clinical_trial_outcomes: ClinicalTrialOutcomeItem[];

  // Legacy fields
  contraindications?: FieldValue;
  adverse_effects?: FieldValue;
}

// ── 6. REFERENCES & DATA QUALITY ──────────────────────────────────────────────

export interface SourceReferenceItem {
  source_name: string;
  category: string;
  url?: string;
  citation?: string;
}

export interface LimitationsAndConfidence {
  limitations: FieldValue;
  data_confidence_rating: string;
  evidence_summary?: string;
}

export interface ReferencesSection {
  sources: SourceReferenceItem[];
  limitations_and_confidence: LimitationsAndConfidence;
}

// ── Legacy Root Types (for backward compatibility) ───────────────────────────

export interface LegacyDrugName {
  generic: string;
  brand_names: string[];
  lab_codes: string[];
  sources: Citation[];
}

export interface LegacyADMEFields {
  absorption: FieldValue;
  distribution: FieldValue;
  metabolism: FieldValue;
  excretion: FieldValue;
  cyp_profile?: CYPProfile;
}

export interface LegacyToxicologyFields {
  acute_toxicity: FieldValue;
  cytotoxicity: FieldValue;
  genetic_toxicology: FieldValue;
  hazard_classifications: FieldValue;
}

export interface LegacyTherapeuticProfile {
  indications: FieldValue;
  contraindications: FieldValue;
  adverse_effects: FieldValue;
  drug_interactions: FieldValue;
}

export interface HistoryFields {
  background: FieldValue;
  discovery: FieldValue;
  development: FieldValue;
  clinical_trials: FieldValue;
}

// ── Root DrugInfo ─────────────────────────────────────────────────────────────

export interface DrugInfo {
  query_smiles: string;
  generated_at: string;
  data_confidence?: string;
  disclaimer: string;

  // 6 Standard Sections
  drug_overview: DrugOverview;
  pharmacodynamics: PharmacodynamicsSection;
  pharmacokinetics: PharmacokineticsSection;
  toxicology_and_safety: ToxicologySection;
  therapeutic_profile: TherapeuticProfileSection;
  references?: ReferencesSection;

  // Legacy fields populated for backward compatibility
  drug_name: LegacyDrugName;
  therapeutic_classes?: FieldValue;
  chemical_structure: ChemicalStructure;
  adme: LegacyADMEFields;
  toxicology: LegacyToxicologyFields;
  history?: HistoryFields;
}

export interface QueryRequest {
  smiles: string;
}

export interface QueryResponse {
  success: boolean;
  data?: DrugInfo;
  error?: string;
}

export interface ResearchDocument {
  document_id: string;
  filename: string;
  pages: number;
  chunks: number;
  associated_drug?: string;
  original_available?: boolean;
}

export interface ChatSource {
  document_id?: string;
  page?: number;
  cited?: boolean;
  id: string;
  num: number;
  name: string;
  url: string;
  title?: string;
  text?: string;
  field?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  smiles?: string;
  text?: string;
  sources?: ChatSource[];
  drugInfo?: DrugInfo;
  error?: string;
  timestamp: Date | string;
}

export type ChatMode = "paper_learning" | "structure_science" | "molecule_theory";

export interface ChatSession {
  activeDocument?: ResearchDocument;
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
  mode?: ChatMode;
}
