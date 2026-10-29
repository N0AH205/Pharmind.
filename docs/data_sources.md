# Data sources and network behavior

Pharmer stores indexed passages and their source metadata in the local ChromaDB database. Online ingestion is an explicit action; the database is not bundled with the source repository. Content use and redistribution remain subject to the original source's terms and copyright.

## Integrated and Federated Datasets

Pharmer systematically queries, links, and cross-references authoritative pharmaceutical data across 8 major domains:

### 1. Chemical Identity and Physicochemical Properties
- **PubChem PUG-REST & PUG-View**: Primary chemical resolver for 2D/3D structures, SMILES, InChIKey, IUPAC names, synonyms, and physicochemical properties (LogP, molecular formula, weight).
- **ChEBI**: Standardized ontological entity references and biological roles.
- **ChEMBL**: EMBL-EBI curated bioactivity database providing stable compound identifiers (`CHEMBL_ID`).
- **DrugCentral**: Verified drug identifiers, structures, and approved chemical forms.
- **FDA GSRS**: Unique Ingredient Identifiers (UNII) assigned through the FDA substance registration system.
- **EPA CompTox / DSSTox**: Environmental and toxicological substance identifiers and physicochemical values.

### 2. Pharmacodynamics and Molecular Targets
- **DrugCentral**: Curated binding affinities ($K_d$, $K_i$, $IC_{50}$) for human receptor, ion channel, and transporter targets.
- **ChEMBL Bioactivities**: Experimental assay measurements, target organism, and action types (agonist, antagonist, inhibitor).
- **BindingDB**: High-resolution experimental affinity records and ligand-target binding parameters.
- **IUPHAR / BPS Guide to PHARMACOLOGY**: Curated target families, pharmacodynamic classifications, and receptor mechanisms.
- **PubChem BioAssay & Binding MOAD / RCSB PDB**: Target structure binding conformations and bioassay results.

### 3. Pharmacokinetics and ADME
- **PubChem PUG-View**: Structured pharmacological monographs for absorption, distribution, metabolism, elimination half-life, and route-dependent excretion rates.
- **openFDA & DailyMed**: Official FDA Structured Product Labeling (SPL) covering bioavailability ($F\%$), volume of distribution ($V_d$), plasma protein binding, and CYP metabolic enzyme profiles.
- **PharmGKB**: Pharmacogenomic associations, metabolic pathways, and VIP gene annotations.
- **Europe PMC & PubMed**: Programmatic literature search for primary human pharmacokinetic studies reporting $AUC$, $C_{max}$, $T_{max}$, and clearance ($CL$).

### 4. Toxicology and Safety
- **openFDA**: Boxed warnings, black box alerts, contraindications, and spontaneous adverse event summaries.
- **SIDER**: Curated MedDRA adverse drug reaction profiles and frequency data.
- **PubChem HSDB & TOXNET**: Human emergency treatment protocols, acute toxicity excerpts, antidote management, and animal $LD_{50}$ values.
- **EPA ToxCast / Tox21 & ECHA**: High-throughput toxicity screening and nonclinical hazard classifications.

### 5. Clinical Trials, Indications, and Regulatory Status
- **DrugCentral & openFDA**: Curated FDA-approved indications, off-label clinical uses, and pediatric/adult patient populations.
- **ClinicalTrials.gov (API v2)**: Real-time Phase 1–4 clinical trial records, intervention arms, and posted outcome measures.
- **FDA Drugs@FDA & Orange Book**: Approval history, therapeutic equivalence, and exclusivity.
- **Badan Pengawas Obat dan Makanan (BPOM)**: Official Indonesian drug registration records, marketing authorization codes, and regulatory status.
- **WHO ATC/DDD Index**: Anatomical Therapeutic Chemical classification codes and Defined Daily Doses.

### 6. Drug Interactions and Pharmacogenomics
- **openFDA & DailyMed Section 7**: Product-specific pharmacodynamic and pharmacokinetic drug interactions.
- **PharmGKB & CPIC**: Evidence-based Clinical Pharmacogenetics Implementation Consortium guidelines and dosing recommendations.

### 7. Gene Expression & Perturbation Signatures
- **LINCS L1000 / Connectivity Map (CLUE)**, **NCBI GEO**, **DepMap**: Cellular perturbation profiles, cancer cell-line dependencies, and transcriptomic response signatures.

### 8. Scientific Literature & Supplementary Data
- **PubMed (NCBI E-Utilities)**: Peer-reviewed biomedical publications and abstracts.
- **Europe PMC REST API**: High-speed European open-access literature search, DOIs, and full-text links.
- **NCBI StatPearls**: Peer-reviewed clinical drug monographs.
- **User PDFs**: Extracts text from user-uploaded PDF scientific papers and clinical guidelines.

The current starter benchmark indexes a small, hardcoded drug set. Full ingestion retrieves up to three useful DailyMed labels per drug, several topic-focused batches of PubMed abstracts (deduplicated by PMID), and up to 15 ClinicalTrials.gov records. The quick-start Aspirin demo intentionally uses much smaller limits. These bounds make initial setup feasible, but this remains a discovery seed, not a comprehensive evidence corpus: PubMed full text is not downloaded, trial retrieval is capped, and source ranking may miss relevant records. The ingestion summary reports stored chunks by drug and field. Re-run ingestion to build or refresh the local index. Ingestion uses the local FastEmbed model; it does not require a cloud embedding API key.

## Network behavior

Online source access is always enabled; `PHARMER_OFFLINE` is ignored. PubChem, DailyMed, PubMed, and ClinicalTrials.gov are contacted for lookups and source searches. Ollama inference can remain local; cloud LLM providers send prompts and retrieved evidence to the selected provider. If the FlashRank cache is missing, retrieval falls back to vector ranking.

When `LLM_PROVIDER` is `openai`, `anthropic`, or `gemini`, user prompts, follow-up history, and retrieved passages are sent to that provider. Use Ollama with a local endpoint for local inference. The frontend has no externally hosted font dependency. Citation URLs are links; opening one in a browser is a user-initiated network action.

## Ingestion metadata

Each indexed passage carries compound identity, topic, source label, URL, and where available bibliographic metadata (authors, journal, publication date, DOI/PMID, or source record ID). The monograph citation resolver uses the trusted metadata stored in ChromaDB rather than accepting model-created URLs. Older local databases may lack the new metadata fields; rebuild the index to populate them.
