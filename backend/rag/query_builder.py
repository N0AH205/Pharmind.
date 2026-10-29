"""
Retrieval query builder — Phase 2.5.

Constructs an optimised semantic query string from a drug's known names
(common name > IUPAC name > synonyms) combined with a field-specific suffix.

This module is the extensibility hook for field-specific retrieval (Phase 4).
Today every call passes field=None. Later, pipeline.py can call:

    build_retrieval_query(structure_data, field="adme")

to retrieve pharmacokinetics-focused chunks separately from mechanism chunks.
"""

from __future__ import annotations

# Semantic suffixes per retrieval field.
# None = general / default (used for the single-pass Phase 3 retrieval).
FIELD_SUFFIXES: dict[str | None, str] = {
    None:              "pharmacology mechanism clinical",
    "moa":             "mechanism of action inhibitor receptor target",
    "physiologic_effect": "pharmacodynamics physiological effects clinical response serotonin reuptake",
    "binding_affinity": "binding affinity Ki Kd dissociation constant cyclooxygenase COX-1 COX-2 enzyme assay",
    "potency":          "potency IC50 EC50 ED50 concentration dose response COX-1 COX-2 assay",
    "efficacy":         "maximum efficacy Emax pharmacodynamic dose response inhibition prostaglandin",
    "selectivity":      "selectivity COX-1 COX-2 ratio inhibition concentration assay",
    "molecular_targets": "molecular target binding affinity Kd Ki IC50 EC50 Emax receptor enzyme",
    "cytotoxicity":     "cytotoxicity cell viability cell line IC50 EC50 assay",
    "genetic_toxicology": "mutagenicity genotoxicity carcinogenicity reproductive toxicity Ames assay",
    "hazard_classifications": "GHS hazard classification hazard statements pictograms carcinogen classification",
    "indications":     "indications therapeutic use treatment approved off-label",
    "contraindications": "contraindications warnings precautions",
    "adverse_effects": "adverse effects side effects toxicity frequency",
    "drug_interactions": "drug interactions clinical pharmacology label-reported study-reported",
    "interactions":    "drug interactions contraindications clinical pharmacology",
    "adme":            "absorption distribution metabolism excretion pharmacokinetics bioavailability clearance half-life",
    "toxicology":      "toxicology acute toxicity ld50 cytotoxicity hazard nonclinical",
    "acute_toxicity":  "acute toxicity overdose LD50 lethal dose animal route",
    "history":         "history discovery development origin clinical trials",
    "clinical_trials": "clinical trial phase study design outcomes enrollment results primary endpoint",
    "research_review": "systematic review meta-analysis evidence efficacy safety pharmacology",
    "safety":          "warnings precautions contraindications adverse reactions interactions boxed warning",
    "dosage":          "dosage administration dose formulation strength clinical use adjustments renal hepatic",
    "boxed_warning":   "boxed warning black box warning severe warnings contraindications",
    "special_populations": "renal impairment hepatic impairment pregnancy lactation pediatric geriatric dosing",
    "pharmacogenomics": "pharmacogenomics pharmacogenetics CPIC PharmGKB gene allele variant metabolism",
    "regulatory":      "FDA approval status BPOM Indonesia registration authorization label",
    "bpom":            "BPOM Indonesia registrasi obat izin edar sediaan indikasi",
    "physicochemical": "LogP LogD pKa solubility partition coefficient physicochemical properties",
    "cyp_profile":     "cytochrome P450 CYP3A4 CYP2D6 CYP2C9 CYP2C19 substrate inhibitor inducer metabolism",
}


def build_retrieval_query(
    structure_data: dict,
    field: str | None = None,
) -> str:
    """
    Build a semantic query string for ChromaDB retrieval.

    Name priority:
        1. common_name  (e.g. "Aspirin")        ← most likely to match documents
        2. iupac_name   (e.g. "2-acetoxybenzoic acid")
        3. up to 2 additional synonyms

    Args:
        structure_data: dict returned by ingest.pubchem.enrich_structure()
        field:          Optional field key from FIELD_SUFFIXES.
                        None → general pharmacology query (Phase 3 default).

    Returns:
        A space-separated query string such as:
            "Aspirin acetylsalicylic acid pharmacology mechanism clinical"
    """
    name_parts: list[str] = []

    common = structure_data.get("common_name")
    iupac = structure_data.get("iupac_name")
    synonyms: list[str] = structure_data.get("synonyms", [])

    # Build ordered name list: common first, then IUPAC, then fill from synonyms
    if common:
        name_parts.append(common)

    if iupac and iupac.lower() not in {n.lower() for n in name_parts}:
        name_parts.append(iupac)

    for syn in synonyms:
        if len(name_parts) >= 3:
            break
        if syn.lower() not in {n.lower() for n in name_parts}:
            name_parts.append(syn)

    # Fallback: if we got nothing from PubChem, use the raw SMILES
    if not name_parts:
        smiles = structure_data.get("smiles", "")
        name_parts.append(smiles)

    suffix = FIELD_SUFFIXES.get(field, FIELD_SUFFIXES[None])
    query = " ".join(name_parts[:3])
    return f"{query} {suffix}".strip()
