"""
Pydantic schema for the structured drug-information output (6-Section Standard).

Standard Sections:
1. DRUG OVERVIEW (Identity, Identifiers, Chemical Structure & Physicochemical Properties, Classification)
2. PHARMACODYNAMICS (Mechanism of Action, Molecular Target Table, Selectivity, Concentration Relevance, Pharmacological Effects)
3. PHARMACOKINETICS (Absorption, Distribution, Metabolism, Excretion, Elimination/Clearance, CYP Enzyme Profile)
4. TOXICOLOGY AND SAFETY (Clinical Safety, Nonclinical & Chemical Toxicity)
5. THERAPEUTIC PROFILE (Indications, Dosage & Administration, Drug Interactions, Special Populations, Pharmacogenomics, Regulatory Status [US FDA & Indonesia BPOM], Clinical Trial Outcomes)
6. REFERENCES & DATA QUALITY (Prioritized Sources Hierarchy, Limitations & Confidence Rating)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator, field_validator


# ── Core Citation & FieldValue Models ────────────────────────────────────────

class Citation(BaseModel):
    source: str
    url: Optional[str] = None
    accessed_at: Optional[str] = None
    text: Optional[str] = None
    publication_date: Optional[str] = None
    authors: Optional[str] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    document_id: Optional[str] = None


class FieldValue(BaseModel):
    """
    A single output field with content, citations, and data quality metadata.
    """
    content: Optional[str] = None
    sources: list[Citation] = Field(default_factory=list)
    missing: bool = False
    evidence_type: Optional[str] = Field(
        default=None,
        description="Regulatory | Clinical | Experimental | Computational",
    )
    status_label: Optional[str] = Field(
        default=None,
        description="Reported | Not reported | No evidence retrieved | Search incomplete | Answer not generated | Not found | Not evaluated | Unverified | Not applicable",
    )
    unit: Optional[str] = None
    conditions: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def unpack_nested_content(cls, data: Any) -> Any:
        if isinstance(data, dict):
            c = data.get("content")
            if isinstance(c, dict):
                data["content"] = c.get("content")
                if "sources" in c and not data.get("sources"):
                    data["sources"] = c.get("sources")
            if data.get("status_label") == "Not found" and not data.get("sources"):
                data["status_label"] = "No evidence retrieved"
        return data


# ── 1. DRUG OVERVIEW ─────────────────────────────────────────────────────────

class BrandNameItem(BaseModel):
    brand_name: str
    jurisdiction: Optional[str] = None  # e.g., "United States", "Indonesia", "European Union"


class DrugIdentity(BaseModel):
    generic_name: FieldValue = Field(
        description="International Nonproprietary Name (INN) or USAN",
    )
    brand_names: list[BrandNameItem] = Field(default_factory=list)
    alternative_names: list[str] = Field(
        default_factory=list,
        description="Synonyms, lab research codes, or abbreviations",
    )
    chemical_form: FieldValue = Field(
        description="Parent compound, salt, specific enantiomer, prodrug, or combination",
    )
    sources: list[Citation] = Field(default_factory=list)


class DrugIdentifiers(BaseModel):
    pubchem_cid: Optional[int] = None
    unii: Optional[str] = None           # FDA Unique Ingredient Identifier
    inchikey: Optional[str] = None
    cas_number: Optional[str] = None     # CAS Registry Number
    chembl_id: Optional[str] = None
    atc_code: Optional[str] = None
    sources: list[Citation] = Field(default_factory=list)


class PhysicochemicalProperties(BaseModel):
    logp: FieldValue = Field(
        description="Calculated or measured partition coefficient between octanol and water for neutral compound",
    )
    logd: FieldValue = Field(
        description="Distribution coefficient at specified pH (ionized + neutral)",
    )
    pka: FieldValue = Field(
        description="Acid dissociation constant pKa with relevant ionization site",
    )
    solubility: FieldValue = Field(
        description="Solubility in specified solvent with units, temperature, and pH",
    )


class DrugClassification(BaseModel):
    atc_classification: FieldValue = Field(
        description="ATC code and corresponding therapeutic classification",
    )
    pharmacologic_class: FieldValue = Field(
        description="Pharmacological category based on mechanism or principal action",
    )


class ChemicalStructure(BaseModel):
    smiles: Optional[str] = None
    isomeric_smiles: Optional[str] = None
    systematic_iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    drug_type: Optional[str] = "small_molecule"
    biologic_class: Optional[str] = None
    target: Optional[str] = None
    chembl_id: Optional[str] = None
    inchi: Optional[str] = None
    inchi_key: Optional[str] = None
    pubchem_cid: Optional[int] = None
    image_url: Optional[str] = None
    sources: list[Citation] = Field(default_factory=list)


class DrugOverview(BaseModel):
    identity: DrugIdentity
    identifiers: DrugIdentifiers
    chemical_structure: ChemicalStructure
    physicochemical_properties: PhysicochemicalProperties
    classification: DrugClassification


# ── 2. PHARMACODYNAMICS ──────────────────────────────────────────────────────

class MolecularTargetItem(BaseModel):
    target: str
    species: Optional[str] = "Homo sapiens"
    interaction_type: Optional[str] = None   # agonist, antagonist, inhibitor, activator, modulator
    functional_consequence: Optional[str] = None
    kd_ki: Optional[str] = None              # Kd or Ki with unit (e.g., "1.2 nM")
    ic50_ec50_ed50: Optional[str] = None     # IC50 / EC50 with unit and type
    emax_intrinsic_activity: Optional[str] = None
    assay_conditions: Optional[str] = None
    source: Optional[str] = None


class MechanismOfAction(BaseModel):
    content: Optional[str] = None
    evidence_classification: Optional[str] = Field(
        default=None,
        description="Established | Proposed | Observed only at high concentrations",
    )
    primary_vs_secondary: Optional[str] = "Primary"
    evidence_source: Optional[str] = None
    sources: list[Citation] = Field(default_factory=list)
    missing: bool = False

    @model_validator(mode="before")
    @classmethod
    def unpack_nested_content(cls, data: Any) -> Any:
        if isinstance(data, dict):
            c = data.get("content")
            if isinstance(c, dict):
                data["content"] = c.get("content")
                if "sources" in c and not data.get("sources"):
                    data["sources"] = c.get("sources")
        return data


class ClinicalRelevanceOfConcentrations(BaseModel):
    experimental_concentration: Optional[str] = None
    typical_human_plasma_concentration: Optional[str] = None
    clinical_relevance: Optional[str] = Field(
        default=None,
        description="Clinically relevant | Substantially higher | Uncertain",
    )
    limitations: Optional[str] = None  # Free vs bound drug, tissue accumulation
    content: Optional[str] = None
    sources: list[Citation] = Field(default_factory=list)
    missing: bool = False

    @model_validator(mode="before")
    @classmethod
    def unpack_nested_content(cls, data: Any) -> Any:
        if isinstance(data, dict):
            c = data.get("content")
            if isinstance(c, dict):
                data["content"] = c.get("content")
                if "sources" in c and not data.get("sources"):
                    data["sources"] = c.get("sources")
        return data


class PharmacologicalEffectItem(BaseModel):
    effect: str
    evidence_classification: str       # Human | Animal | In vitro
    linked_mechanism: Optional[str] = None


class BioactivityRecord(BaseModel):
    """Retained for backward-compatibility with ChEMBL bioactivity extractors."""
    target_name: str
    target_organism: Optional[str] = "Homo sapiens"
    action_type: Optional[str] = None
    standard_type: str
    value_nm: Optional[float] = None
    relation: Optional[str] = "="
    pchembl_value: Optional[float] = None
    assay_description: Optional[str] = None
    chembl_assay_id: Optional[str] = None
    doi: Optional[str] = None


class PharmacodynamicsSection(BaseModel):
    mechanism_of_action: MechanismOfAction
    molecular_targets: list[MolecularTargetItem] = Field(default_factory=list)
    selectivity: FieldValue
    clinical_relevance_of_concentrations: ClinicalRelevanceOfConcentrations
    pharmacological_effects: list[PharmacologicalEffectItem] = Field(default_factory=list)

    # Legacy fields maintained for backward compatibility
    physiologic_effect: Optional[FieldValue] = None
    binding_affinity: Optional[FieldValue] = None
    potency: Optional[FieldValue] = None
    efficacy: Optional[FieldValue] = None
    bioactivities: list[BioactivityRecord] = Field(default_factory=list)

    @field_validator("molecular_targets", mode="before")
    @classmethod
    def normalize_targets(cls, v: Any) -> list[Any]:
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append({"target": item})
                else:
                    res.append(item)
            return res
        return []


# ── 3. PHARMACOKINETICS ──────────────────────────────────────────────────────

class AbsorptionFields(BaseModel):
    bioavailability: FieldValue     # F% fraction reaching systemic circulation
    tmax: FieldValue                # Time to Cmax
    cmax: FieldValue                # Peak concentration after specified dose
    food_effect: FieldValue         # Impact of meal intake
    route_and_formulation: FieldValue  # Oral, IV, transdermal, etc.


class DistributionFields(BaseModel):
    volume_of_distribution: FieldValue  # Vd (L or L/kg)
    plasma_protein_binding: FieldValue  # % bound and unbound fraction
    blood_brain_barrier: FieldValue     # CNS penetration & limitations


class MetabolismFields(BaseModel):
    metabolic_pathways: FieldValue
    active_or_toxic_metabolites: FieldValue
    metabolizing_enzymes: FieldValue


class ExcretionFields(BaseModel):
    primary_route: FieldValue               # Renal, fecal, biliary
    fraction_excreted_unchanged: FieldValue # % excreted intact


class EliminationClearanceFields(BaseModel):
    elimination_half_life: FieldValue  # t1/2
    clearance: FieldValue              # CL apparent clearance per unit time


class CYPEntry(BaseModel):
    enzyme: str                        # e.g., CYP3A4, CYP2D6
    role: str                          # Substrate | Inhibitor | Inducer
    evidence_and_species: str          # Human clinical data | Human in vitro data | Animal data
    source: Optional[str] = None


class CYPProfile(BaseModel):
    """Legacy CYPProfile model for backward compatibility."""
    substrates: list[str] = Field(default_factory=list)
    inhibitors: list[str] = Field(default_factory=list)
    inducers: list[str] = Field(default_factory=list)
    evidence_source: Optional[str] = None


class PharmacokineticsSection(BaseModel):
    absorption: AbsorptionFields
    distribution: DistributionFields
    metabolism: MetabolismFields
    excretion: ExcretionFields
    elimination_and_clearance: EliminationClearanceFields
    cyp_profile: list[CYPEntry] = Field(default_factory=list)

    # Legacy field
    cyp_summary: Optional[CYPProfile] = None


# ── 4. TOXICOLOGY AND SAFETY ────────────────────────────────────────────────

class AdverseEffectItem(BaseModel):
    reaction: str
    frequency: Optional[str] = None      # Common (>10%), Rare (<0.1%), etc.
    population: Optional[str] = None
    dose_or_regimen: Optional[str] = None
    source: Optional[str] = None


class ClinicalSafety(BaseModel):
    boxed_warning: FieldValue            # Regulatory boxed warning text or "None"
    contraindications: FieldValue        # Absolute and relative
    warnings_and_precautions: FieldValue
    adverse_effects: list[AdverseEffectItem] = Field(default_factory=list)
    adverse_effects_summary: Optional[FieldValue] = None
    overdose_and_management: FieldValue  # Manifestations, supportive care, antidotes

    @field_validator("adverse_effects", mode="before")
    @classmethod
    def normalize_adverse_effects(cls, v: Any) -> list[Any]:
        if isinstance(v, str):
            return [{"reaction": v}]
        if isinstance(v, dict):
            content = v.get("content")
            if content:
                return [{"reaction": content}]
            return []
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append({"reaction": item})
                else:
                    res.append(item)
            return res
        return []


_MISSING_TOX_STATUSES = {
    "No evidence retrieved",
    "Search incomplete",
    "Answer not generated",
    "Not found",
    "Not evaluated",
}


class ToxFindingItem(BaseModel):
    status: str = "No evidence retrieved"
    details: Optional[str] = None
    species_or_model: Optional[str] = None
    study_conditions: Optional[str] = None


class NonclinicalToxicity(BaseModel):
    genotoxicity: ToxFindingItem
    carcinogenicity: ToxFindingItem
    reproductive_and_developmental_toxicity: ToxFindingItem
    cytotoxicity: ToxFindingItem
    ld50: ToxFindingItem                 # Species, route, conditions
    lc50: ToxFindingItem
    hazard_classification: ToxFindingItem  # GHS, IARC/NTP

    @field_validator(
        "genotoxicity", "carcinogenicity", "reproductive_and_developmental_toxicity",
        "cytotoxicity", "ld50", "lc50", "hazard_classification", mode="before"
    )
    @classmethod
    def normalize_tox_findings(cls, v: Any) -> Any:
        if isinstance(v, str):
            if v == "Not found":
                return {
                    "status": "No evidence retrieved",
                    "details": "No supporting evidence was retrieved for this endpoint; this does not establish that none exists.",
                }
            return {"status": v, "details": v}
        if isinstance(v, dict) and v.get("status") == "Not found":
            return {
                **v,
                "status": "No evidence retrieved",
                "details": v.get("details") or "No supporting evidence was retrieved for this endpoint; this does not establish that none exists.",
            }
        if isinstance(v, dict) and "status" not in v and "content" in v:
            return {"status": "Reported" if v.get("content") else "No evidence retrieved", "details": v.get("content")}
        return v


class ToxicologySection(BaseModel):
    clinical_safety: ClinicalSafety
    nonclinical_toxicity: NonclinicalToxicity

    # Legacy fields
    acute_toxicity: Optional[FieldValue] = None
    cytotoxicity: Optional[FieldValue] = None
    genetic_toxicology: Optional[FieldValue] = None
    hazard_classifications: Optional[FieldValue] = None


# ── 5. THERAPEUTIC PROFILE ───────────────────────────────────────────────────

class IndicationItem(BaseModel):
    indication: str
    jurisdiction: Optional[str] = None   # US FDA, Indonesia BPOM, EMA
    dosage_form: Optional[str] = None
    evidence_type: Optional[str] = None
    source: Optional[str] = None


class IndicationsCategories(BaseModel):
    approved_indications: list[IndicationItem] = Field(default_factory=list)
    off_label_use: list[IndicationItem] = Field(default_factory=list)
    investigational_uses: list[IndicationItem] = Field(default_factory=list)
    summary: Optional[FieldValue] = None

    @field_validator("approved_indications", "off_label_use", "investigational_uses", mode="before")
    @classmethod
    def normalize_indications(cls, v: Any) -> list[Any]:
        if isinstance(v, str):
            return [{"indication": v}]
        if isinstance(v, dict):
            content = v.get("content")
            if content:
                return [{"indication": content}]
            return []
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append({"indication": item})
                elif isinstance(item, dict):
                    ind_val = item.get("indication") or item.get("condition") or item.get("name") or "Indication"
                    res.append({**item, "indication": ind_val})
                else:
                    res.append(item)
            return res
        return []


class DosageAndAdministration(BaseModel):
    indication_and_population: FieldValue
    dose_route_frequency_duration: FieldValue
    formulation_instructions: FieldValue
    dose_adjustments: FieldValue
    administration_restrictions: FieldValue


class DrugInteractionItem(BaseModel):
    interacting_substance: str
    interaction_category: str            # Label-reported | Study-reported
    mechanism: Optional[str] = None
    clinical_consequence: Optional[str] = None
    evidence_level: Optional[str] = None
    recommended_management: Optional[str] = None


class SpecialPopulations(BaseModel):
    renal_impairment: FieldValue
    hepatic_impairment: FieldValue
    pregnancy_and_lactation: FieldValue
    pediatric_patients: FieldValue
    older_adults: FieldValue
    other_populations: FieldValue


class PharmacogenomicsField(BaseModel):
    genes_and_variants: Optional[str] = None
    clinical_consequences: Optional[str] = None
    prescribing_recommendations: Optional[str] = None
    statement: str = "No pharmacogenomic evidence was retrieved for this field."
    sources: list[Citation] = Field(default_factory=list)
    missing: bool = True


class JurisdictionRegulatory(BaseModel):
    jurisdiction: str                    # "United States" or "Indonesia"
    authority: str                       # "US FDA" or "BPOM"
    status: str                          # Approved, Registered, Investigational, or an explicit retrieval state
    details: Optional[str] = None        # Registration number (NIE / NDA), active ingredient, dosage form
    sources: list[Citation] = Field(default_factory=list)

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, v: Any) -> list[Any]:
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append({"source": item})
                else:
                    res.append(item)
            return res
        return []


class RegulatoryStatus(BaseModel):
    united_states: JurisdictionRegulatory
    indonesia: JurisdictionRegulatory


class ClinicalTrialOutcomeItem(BaseModel):
    study: str                           # Trial identifier or publication
    population: str                      # Patient group & medical condition
    intervention_and_comparator: str     # Drug dose vs comparator/placebo
    sample_size: Optional[str] = None
    outcome_and_effect: str              # Measured endpoint and numerical result
    evidence_source: Optional[str] = None


class TherapeuticProfileSection(BaseModel):
    indications: IndicationsCategories
    dosage_and_administration: DosageAndAdministration
    drug_interactions: list[DrugInteractionItem] = Field(default_factory=list)
    special_populations: SpecialPopulations
    pharmacogenomics: PharmacogenomicsField
    regulatory_status: RegulatoryStatus
    clinical_trial_outcomes: list[ClinicalTrialOutcomeItem] = Field(default_factory=list)

    # Legacy fields
    contraindications: Optional[FieldValue] = None
    adverse_effects: Optional[FieldValue] = None

    @field_validator("drug_interactions", mode="before")
    @classmethod
    def normalize_drug_interactions(cls, v: Any) -> list[Any]:
        if isinstance(v, str):
            return [{"interacting_substance": "General", "interaction_category": "Label-reported", "clinical_consequence": v}]
        if isinstance(v, dict):
            content = v.get("content")
            if content:
                return [{"interacting_substance": "General", "interaction_category": "Label-reported", "clinical_consequence": content}]
            return []
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append({"interacting_substance": item, "interaction_category": "Label-reported"})
                else:
                    res.append(item)
            return res
        return []


# ── 6. REFERENCES & DATA QUALITY ─────────────────────────────────────────────

class SourceReferenceItem(BaseModel):
    source_name: str
    category: str                        # Regulatory | Established Database | Clinical Guideline | Peer-reviewed Study | Computational
    url: Optional[str] = None
    citation: Optional[str] = None


class LimitationsAndConfidence(BaseModel):
    limitations: FieldValue
    data_confidence_rating: str = "UNASSESSED (Insufficient evidence retrieved)"
    evidence_summary: Optional[str] = None


class ReferencesSection(BaseModel):
    sources: list[SourceReferenceItem] = Field(default_factory=list)
    limitations_and_confidence: LimitationsAndConfidence


# ── Legacy compatibility models ──────────────────────────────────────────────

class DrugName(BaseModel):
    generic: str
    brand_names: list[str] = Field(default_factory=list)
    lab_codes: list[str] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)


class PharmacodynamicsFields(BaseModel):
    mechanism_of_action: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    physiologic_effect: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    binding_affinity: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    selectivity: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    potency: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    efficacy: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    bioactivities: list[BioactivityRecord] = Field(default_factory=list)


class ADMEFields(BaseModel):
    absorption: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    distribution: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    metabolism: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    excretion: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    cyp_profile: Optional[CYPProfile] = None


class ToxicologyFields(BaseModel):
    acute_toxicity: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    cytotoxicity: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    genetic_toxicology: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    hazard_classifications: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))


class TherapeuticProfile(BaseModel):
    indications: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    contraindications: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    adverse_effects: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    drug_interactions: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))


class HistoryFields(BaseModel):
    background: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    discovery: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    development: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))
    clinical_trials: FieldValue = Field(default_factory=lambda: FieldValue(content=None, missing=True, status_label="No evidence retrieved"))


# ── Root Monograph Model ─────────────────────────────────────────────────────

class DrugInfo(BaseModel):
    """
    Full structured drug-information output (6-Section Standard).
    Returned by the RAG pipeline for every SMILES / drug query.
    """
    query_smiles: str
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data_confidence: Optional[str] = Field(
        default="UNASSESSED (Insufficient evidence retrieved)",
        description="Deterministic confidence rating based on regulatory approval and assay depth",
    )
    disclaimer: str = (
        "This information is for educational and reference purposes only. "
        "It does not constitute clinical advice. Always consult a licensed "
        "clinician or pharmacist for patient-specific guidance."
    )

    # Standard 6 Sections
    drug_overview: DrugOverview
    pharmacodynamics: PharmacodynamicsSection
    pharmacokinetics: PharmacokineticsSection
    toxicology_and_safety: ToxicologySection
    therapeutic_profile: TherapeuticProfileSection
    references: ReferencesSection

    # Legacy fields populated automatically for complete backward compatibility
    drug_name: Optional[DrugName] = None
    therapeutic_classes: Optional[FieldValue] = None
    chemical_structure: Optional[ChemicalStructure] = None
    adme: Optional[ADMEFields] = None
    toxicology: Optional[ToxicologyFields] = None
    history: Optional[HistoryFields] = None

    @model_validator(mode="after")
    def populate_legacy_fields(self) -> DrugInfo:
        """Populate legacy fields if absent so existing clients and tests continue to function."""
        # 1. drug_name
        if self.drug_name is None and self.drug_overview and self.drug_overview.identity:
            generic = self.drug_overview.identity.generic_name.content or "Unknown"
            brands = [b.brand_name for b in self.drug_overview.identity.brand_names]
            self.drug_name = DrugName(
                generic=generic,
                brand_names=brands,
                lab_codes=self.drug_overview.identity.alternative_names,
                sources=self.drug_overview.identity.sources,
            )

        # 2. chemical_structure
        if self.chemical_structure is None and self.drug_overview:
            self.chemical_structure = self.drug_overview.chemical_structure

        # 3. therapeutic_classes
        if self.therapeutic_classes is None and self.drug_overview and self.drug_overview.classification:
            self.therapeutic_classes = self.drug_overview.classification.pharmacologic_class

        # 4. adme
        if self.adme is None and self.pharmacokinetics:
            pk = self.pharmacokinetics
            cyp_prof = None
            if pk.cyp_profile:
                subs = [c.enzyme for c in pk.cyp_profile if "substrate" in c.role.lower()]
                inhs = [c.enzyme for c in pk.cyp_profile if "inhibit" in c.role.lower()]
                inds = [c.enzyme for c in pk.cyp_profile if "induc" in c.role.lower()]
                cyp_prof = CYPProfile(substrates=subs, inhibitors=inhs, inducers=inds)
            self.adme = ADMEFields(
                absorption=pk.absorption.bioavailability,
                distribution=pk.distribution.volume_of_distribution,
                metabolism=pk.metabolism.metabolic_pathways,
                excretion=pk.elimination_and_clearance.elimination_half_life,
                cyp_profile=cyp_prof or pk.cyp_summary,
            )

        # 5. toxicology
        if self.toxicology is None and self.toxicology_and_safety:
            tox = self.toxicology_and_safety
            self.toxicology = ToxicologyFields(
                acute_toxicity=tox.acute_toxicity or FieldValue(
                    content=f"LD50: {tox.nonclinical_toxicity.ld50.details or tox.nonclinical_toxicity.ld50.status}",
                    missing=tox.nonclinical_toxicity.ld50.status in _MISSING_TOX_STATUSES,
                ),
                cytotoxicity=tox.cytotoxicity or FieldValue(
                    content=f"Cytotoxicity: {tox.nonclinical_toxicity.cytotoxicity.details or tox.nonclinical_toxicity.cytotoxicity.status}",
                    missing=tox.nonclinical_toxicity.cytotoxicity.status in _MISSING_TOX_STATUSES,
                ),
                genetic_toxicology=tox.genetic_toxicology or FieldValue(
                    content=f"Genotoxicity: {tox.nonclinical_toxicity.genotoxicity.details or tox.nonclinical_toxicity.genotoxicity.status}; Carcinogenicity: {tox.nonclinical_toxicity.carcinogenicity.details or tox.nonclinical_toxicity.carcinogenicity.status}",
                    missing=tox.nonclinical_toxicity.genotoxicity.status in _MISSING_TOX_STATUSES,
                ),
                hazard_classifications=tox.hazard_classifications or FieldValue(
                    content=f"Hazard: {tox.nonclinical_toxicity.hazard_classification.details or tox.nonclinical_toxicity.hazard_classification.status}",
                    missing=tox.nonclinical_toxicity.hazard_classification.status in _MISSING_TOX_STATUSES,
                ),
            )

        # 6. history
        if self.history is None:
            _miss = FieldValue(content=None, missing=True)
            trials_summary = None
            if self.therapeutic_profile and self.therapeutic_profile.clinical_trial_outcomes:
                trials_summary = "; ".join(
                    f"{t.study} ({t.population}): {t.outcome_and_effect}"
                    for t in self.therapeutic_profile.clinical_trial_outcomes[:3]
                )
            self.history = HistoryFields(
                background=_miss,
                discovery=_miss,
                development=_miss,
                clinical_trials=FieldValue(content=trials_summary, missing=trials_summary is None) if trials_summary else _miss,
            )

        return self


class QueryRequest(BaseModel):
    smiles: str = Field(..., min_length=1, description="A valid SMILES string or drug query")
