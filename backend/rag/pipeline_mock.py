"""
Mock pipeline data — 6-Section Pharmaceutical Monograph Standard.

Used as a golden reference and fallback when indexed evidence is bootstrapping.
Provides complete, accurate pharmacological data for Acetylsalicylic Acid (Aspirin).
"""

from rag.schema import (
    DrugInfo, DrugOverview, DrugIdentity, DrugIdentifiers, ChemicalStructure,
    PhysicochemicalProperties, DrugClassification, BrandNameItem,
    PharmacodynamicsSection, MechanismOfAction, MolecularTargetItem,
    ClinicalRelevanceOfConcentrations, PharmacologicalEffectItem,
    PharmacokineticsSection, AbsorptionFields, DistributionFields,
    MetabolismFields, ExcretionFields, EliminationClearanceFields, CYPEntry,
    ToxicologySection, ClinicalSafety, AdverseEffectItem,
    NonclinicalToxicity, ToxFindingItem,
    TherapeuticProfileSection, IndicationsCategories, IndicationItem,
    DosageAndAdministration, DrugInteractionItem, SpecialPopulations,
    PharmacogenomicsField, RegulatoryStatus, JurisdictionRegulatory,
    ClinicalTrialOutcomeItem, ReferencesSection, SourceReferenceItem,
    LimitationsAndConfidence, FieldValue, Citation,
)

MOCK_ASPIRIN = DrugInfo(
    query_smiles="CC(=O)Oc1ccccc1C(=O)O",
    data_confidence="HIGH (FDA Approved with Full Label)",
    disclaimer=(
        "This information is for educational and reference purposes only. "
        "It does not constitute clinical advice. Always consult a licensed "
        "clinician or pharmacist for patient-specific guidance."
    ),

    # 1. DRUG OVERVIEW
    drug_overview=DrugOverview(
        identity=DrugIdentity(
            generic_name=FieldValue(
                content="Acetylsalicylic acid (INN, USAN)",
                sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
                evidence_type="Regulatory",
                status_label="Reported",
            ),
            brand_names=[
                BrandNameItem(brand_name="Aspirin", jurisdiction="United States / Global"),
                BrandNameItem(brand_name="Bayer Aspirin", jurisdiction="United States"),
                BrandNameItem(brand_name="Aspilets", jurisdiction="Indonesia"),
                BrandNameItem(brand_name="Thrombo Aspilets", jurisdiction="Indonesia"),
                BrandNameItem(brand_name="Ecotrin", jurisdiction="United States"),
                BrandNameItem(brand_name="Bufferin", jurisdiction="United States"),
            ],
            alternative_names=[
                "2-Acetoxybenzoic acid",
                "o-Acetoxybenzoic acid",
                "BAY-09867",
                "ASA",
                "Polopiryna",
            ],
            chemical_form=FieldValue(
                content="Parent compound (ester of salicylic acid and acetic acid). Also formulated as buffered and enteric-coated formulations.",
                sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
                evidence_type="Regulatory",
                status_label="Reported",
            ),
            sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
        ),
        identifiers=DrugIdentifiers(
            pubchem_cid=2244,
            unii="R16CO5Y76E",
            inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            cas_number="50-78-2",
            chembl_id="CHEMBL25",
            atc_code="B01AC06, N02BA01",
            sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
        ),
        chemical_structure=ChemicalStructure(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            isomeric_smiles="CC(=O)Oc1ccccc1C(=O)O",
            systematic_iupac_name="2-acetoxybenzoic acid",
            molecular_formula="C9H8O4",
            molecular_weight=180.16,
            pubchem_cid=2244,
            chembl_id="CHEMBL25",
            inchi="InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)",
            inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            image_url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/CID/2244/PNG",
            sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
        ),
        physicochemical_properties=PhysicochemicalProperties(
            logp=FieldValue(
                content="1.19 (calculated neutral octanol/water partition coefficient)",
                evidence_type="Computational",
                status_label="Reported",
                unit="dimensionless",
                sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
            ),
            logd=FieldValue(
                content="-1.62 at pH 7.4 (predominantly ionized carboxylate in physiological buffer)",
                evidence_type="Computational",
                status_label="Reported",
                unit="dimensionless",
                conditions="pH 7.4, 25°C",
                sources=[Citation(source="ChEMBL CHEMBL25", url="https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL25/")],
            ),
            pka=FieldValue(
                content="3.49 (carboxylic acid ionization site, 25°C)",
                evidence_type="Experimental",
                status_label="Reported",
                conditions="Aqueous, 25°C",
                sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
            ),
            solubility=FieldValue(
                content="3.3 mg/mL in water at 25°C; highly soluble in ethanol (1 in 5) and chloroform (1 in 17)",
                evidence_type="Experimental",
                status_label="Reported",
                unit="mg/mL",
                conditions="Water, 25°C",
                sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
            ),
        ),
        classification=DrugClassification(
            atc_classification=FieldValue(
                content="B01AC06 (Platelet aggregation inhibitors excluding heparin) and N02BA01 (Salicylic acid and derivatives)",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="WHO ATC/DDD Index", url="https://www.whocc.no/atc_ddd_index/")],
            ),
            pharmacologic_class=FieldValue(
                content="Nonsteroidal Anti-inflammatory Drug (NSAID); Cyclooxygenase Inhibitor; Antiplatelet Agent",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
    ),

    # 2. PHARMACODYNAMICS
    pharmacodynamics=PharmacodynamicsSection(
        mechanism_of_action=MechanismOfAction(
            content=(
                "Step 1: Aspirin diffuses into the catalytic active site channel of cyclooxygenase enzymes (COX-1 and COX-2).\n"
                "Step 2: The acetyl group of aspirin covalently and irreversibly transfers to Serine-530 on COX-1 (and Serine-516 on COX-2), sterically blocking arachidonic acid access to the cyclooxygenase active site.\n"
                "Step 3: Blockade halts synthesis of Prostaglandin H2 (PGH2), stopping downstream biosynthesis of thromboxane A2 (TXA2) in platelets and inflammatory prostaglandins (PGE2, PGI2) in vascular/immune cells.\n"
                "Step 4: Because blood platelets lack nuclei and cannot de novo synthesize COX-1, the antiplatelet effect is permanent for the 7–10 day circulating lifespan of the platelet."
            ),
            evidence_classification="Established",
            primary_vs_secondary="Primary: Irreversible platelet COX-1 inhibition; Secondary: Peripheral and central COX-2 inhibition.",
            evidence_source="FDA Prescribing Information & ChEMBL Mechanistic Monographs",
            sources=[Citation(source="PubChem CID 2244", url="https://pubchem.ncbi.nlm.nih.gov/compound/2244")],
            missing=False,
        ),
        molecular_targets=[
            MolecularTargetItem(
                target="Cyclooxygenase-1 (PTGS1 / COX-1)",
                species="Homo sapiens",
                interaction_type="inhibitor",
                functional_consequence="Irreversible inactivation of thromboxane A2 synthase precursor production; complete platelet aggregation inhibition",
                kd_ki="Ki = 1.67 µM",
                ic50_ec50_ed50="IC50 = 4.8 µM",
                emax_intrinsic_activity="100% inhibition of platelet TXA2 generation",
                assay_conditions="Human whole blood aggregation assay; substrate arachidonic acid",
                source="ChEMBL CHEMBL25 / BindingDB",
            ),
            MolecularTargetItem(
                target="Cyclooxygenase-2 (PTGS2 / COX-2)",
                species="Homo sapiens",
                interaction_type="inhibitor",
                functional_consequence="Acetylation alters enzymatic activity, suppressing PGE2 and directing synthesis toward 15R-HETE (aspirin-triggered lipoxin)",
                kd_ki="Ki = 28.0 µM",
                ic50_ec50_ed50="IC50 = 62.0 µM",
                emax_intrinsic_activity="Submaximal PGE2 suppression at antiplatelet doses; high suppression at >1 g/day",
                assay_conditions="Recombinant human COX-2 spectrophotometric peroxidase assay",
                source="ChEMBL CHEMBL25 / BindingDB",
            ),
            MolecularTargetItem(
                target="IKK-beta (Inhibitor of nuclear factor kappa-B kinase subunit beta)",
                species="Homo sapiens",
                interaction_type="inhibitor",
                functional_consequence="Inhibition of NF-kappaB activation and suppression of pro-inflammatory gene transcription",
                kd_ki="Ki > 5 mM",
                ic50_ec50_ed50="IC50 ~ 10 mM",
                emax_intrinsic_activity="Observable only at supratherapeutic/toxic concentrations",
                assay_conditions="In vitro biochemical kinase assay",
                source="Literature Review / PubMed PMID 9826647",
            ),
        ],
        selectivity=FieldValue(
            content=(
                "Aspirin displays approximately 10- to 30-fold selectivity for COX-1 over COX-2 in human whole-blood assays (COX-1 IC50 ~4.8 µM vs COX-2 IC50 ~62 µM). "
                "At cardioprotective antiplatelet doses (75–100 mg daily), presystemic portal circulation achieves selective irreversible platelet COX-1 inhibition without significantly impairing systemic vascular prostacyclin (PGI2) production. "
                "Higher anti-inflammatory doses (>1000 mg daily) achieve bilateral COX-1/COX-2 inhibition."
            ),
            evidence_type="Experimental",
            status_label="Reported",
            sources=[Citation(source="ChEMBL CHEMBL25", url="https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL25/")],
        ),
        clinical_relevance_of_concentrations=ClinicalRelevanceOfConcentrations(
            experimental_concentration="In vitro COX-1 IC50: 4.8 µM (0.86 µg/mL); COX-2 IC50: 62 µM (11.1 µg/mL)",
            typical_human_plasma_concentration="Therapeutic peak plasma aspirin conc: 3–10 µg/mL (16–55 µM) after 100–325 mg oral dose. Salicylate metabolite reaches 100–300 µg/mL at anti-inflammatory doses.",
            clinical_relevance="Clinically relevant",
            limitations="Aspirin has an ultra-short half-life (~20 min) due to rapid esterase cleavage to salicylate. In vivo antiplatelet efficacy is governed by irreversible portal platelet acetylation rather than systemic steady-state free drug concentration.",
            content="Experimental concentration directly matches clinical antiplatelet exposure windows in human portal circulation.",
            missing=False,
            sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
        ),
        pharmacological_effects=[
            PharmacologicalEffectItem(
                effect="Antiplatelet effect: Inhibition of platelet thromboxane A2 production, preventing thrombotic arterial occlusion",
                evidence_classification="Human",
                linked_mechanism="Irreversible Ser530 acetylation of platelet COX-1",
            ),
            PharmacologicalEffectItem(
                effect="Antipyretic effect: Resetting of hypothalamic thermoregulatory center to reduce febrile body temperature",
                evidence_classification="Human",
                linked_mechanism="Inhibition of hypothalamic PGE2 synthesis",
            ),
            PharmacologicalEffectItem(
                effect="Analgesic and anti-inflammatory effect: Reduction of peripheral inflammatory nociceptor sensitization",
                evidence_classification="Human",
                linked_mechanism="Inhibition of COX-2-mediated prostanoid synthesis at sites of tissue damage",
            ),
            PharmacologicalEffectItem(
                effect="Gastric mucosal barrier attenuation: Decreased protective gastric mucus and bicarbonate secretion",
                evidence_classification="Human",
                linked_mechanism="COX-1 inhibition leading to gastric PGE2/PGI2 depletion",
            ),
        ],
    ),

    # 3. PHARMACOKINETICS
    pharmacokinetics=PharmacokineticsSection(
        absorption=AbsorptionFields(
            bioavailability=FieldValue(
                content="50% to 68% for intact acetylsalicylic acid due to rapid presystemic first-pass hydrolysis; salicylate metabolite bioavailability is ~100%",
                evidence_type="Clinical",
                status_label="Reported",
                unit="%",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            tmax=FieldValue(
                content="15 to 30 minutes for intact aspirin from immediate-release formulations; 1 to 2 hours for active metabolite salicylate",
                evidence_type="Clinical",
                status_label="Reported",
                unit="hours",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            cmax=FieldValue(
                content="30 to 70 µg/mL following 325 mg to 650 mg oral immediate-release dose",
                evidence_type="Clinical",
                status_label="Reported",
                unit="µg/mL",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            food_effect=FieldValue(
                content="Food delays rate of absorption (increased Tmax by 1–2 hours) but does not significantly reduce total extent of absorption (AUC)",
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            route_and_formulation=FieldValue(
                content="Oral (immediate-release tablets, chewable, buffered, enteric-coated); Rectal suppositories",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
        distribution=DistributionFields(
            volume_of_distribution=FieldValue(
                content="Vd is 0.15 to 0.20 L/kg for intact aspirin; 0.13 L/kg for salicylate in healthy adults",
                evidence_type="Clinical",
                status_label="Reported",
                unit="L/kg",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            plasma_protein_binding=FieldValue(
                content="Intact aspirin is ~33% bound; Salicylate is 80% to 90% bound to plasma albumin at therapeutic concentrations (unbound fraction increases at higher concentrations as binding saturates)",
                evidence_type="Clinical",
                status_label="Reported",
                unit="%",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            blood_brain_barrier=FieldValue(
                content="Aspirin and salicylate cross the blood-brain barrier; salicylate concentration in cerebrospinal fluid is approximately 10% to 30% of total plasma concentration",
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
        metabolism=MetabolismFields(
            metabolic_pathways=FieldValue(
                content="Rapid esterase cleavage in GI mucosa, erythrocytes, and liver to salicylic acid. Salicylate undergoes hepatic conjugation to salicyluric acid (~75%), salicyl phenolic glucuronide (~10%), salicyl acyl glucuronide (~5%), and gentisic acid (<1%).",
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            active_or_toxic_metabolites=FieldValue(
                content="Salicylic acid (active reversible anti-inflammatory metabolite); Gentisic acid (minor active metabolite); Salicyluric acid (inactive).",
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            metabolizing_enzymes=FieldValue(
                content="Primary: Butyrylcholinesterase (BChE) and carboxylesterases (CES1, CES2). Secondary hepatic phase II: UDP-glucuronosyltransferases (UGT1A6, UGT2B7) and glycine N-acyltransferase (GLYAT). CYP2C9 accounts for minor oxidation to gentisic acid.",
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="PharmGKB", url="https://www.pharmgkb.org/chemical/PA448488")],
            ),
        ),
        excretion=ExcretionFields(
            primary_route=FieldValue(
                content="Renal excretion of unchanged salicylic acid, salicyluric acid, and glucuronide conjugates (80% to 100% of dose recovered in urine within 24 to 72 hours)",
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            fraction_excreted_unchanged=FieldValue(
                content="Approximately 1% as intact acetylsalicylic acid; 10% to 30% as free salicylic acid at normal urinary pH (excretion of free salicylate increases dramatically to >80% when urinary pH is alkalinized to >7.5)",
                evidence_type="Clinical",
                status_label="Reported",
                unit="%",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
        elimination_and_clearance=EliminationClearanceFields(
            elimination_half_life=FieldValue(
                content="Intact aspirin: 15 to 20 minutes; Salicylate: 2 to 3 hours at low antiplatelet doses (75–100 mg), increasing to 6–12 hours at moderate doses, and up to 15–30 hours at anti-inflammatory/toxic doses due to Michaelis-Menten enzyme saturation.",
                evidence_type="Clinical",
                status_label="Reported",
                unit="hours",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            clearance=FieldValue(
                content="Systemic clearance of intact aspirin is ~9.3 mL/min/kg. Clearance of salicylate decreases non-linearly with dose (capacity-limited metabolism).",
                evidence_type="Clinical",
                status_label="Reported",
                unit="mL/min/kg",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
        cyp_profile=[
            CYPEntry(
                enzyme="CYP2C9",
                role="Substrate",
                evidence_and_species="Human in vitro & clinical data (minor pathway ~1% to gentisic acid)",
                source="PharmGKB / FDA Label Section 7",
            ),
            CYPEntry(
                enzyme="CYP2C19",
                role="Inhibitor",
                evidence_and_species="Human in vitro data (weak competitive inhibition at supratherapeutic salicylate levels)",
                source="Literature Assay / DrugCentral",
            ),
        ],
    ),

    # 4. TOXICOLOGY AND SAFETY
    toxicology_and_safety=ToxicologySection(
        clinical_safety=ClinicalSafety(
            boxed_warning=FieldValue(
                content=(
                    "No FDA Black Box Warning on standard monograph. "
                    "However, mandatory regulatory warning on all labels: Reye's Syndrome Alert — "
                    "Children and teenagers who have or are recovering from chicken pox or flu-like symptoms should not use this medicine. "
                    "When using this product, if changes in behavior with nausea and vomiting occur, consult a doctor because these symptoms could be an early sign of Reye's syndrome, a rare but serious illness."
                ),
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="FDA Drug Label", url="https://dailymed.nlm.nih.gov")],
            ),
            contraindications=FieldValue(
                content=(
                    "1. Known hypersensitivity to acetylsalicylic acid or other NSAIDs (including aspirin-exacerbated respiratory disease / Samter's Triad).\n"
                    "2. Active gastrointestinal ulceration or history of recurrent peptic ulcers.\n"
                    "3. Hemophilia, thrombocytopenia, or other active bleeding diatheses.\n"
                    "4. Severe renal or severe hepatic impairment.\n"
                    "5. Third trimester of pregnancy (risk of premature closure of fetal ductus arteriosus and prolonged labor).\n"
                    "6. Children and adolescents under 16 years with viral fevers (Reye's syndrome risk)."
                ),
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            warnings_and_precautions=FieldValue(
                content=(
                    "Risk of GI bleeding, ulceration, and perforation; increased bleeding time in surgical procedures; "
                    "bronchospasm in asthmatic patients; renal papillary necrosis and chronic renal injury with prolonged high-dose usage; "
                    "sodium/water retention in congestive heart failure."
                ),
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            adverse_effects=[
                AdverseEffectItem(
                    reaction="Dyspepsia, epigastric distress, heartburn",
                    frequency="Common (10% to 30%)",
                    population="General clinical population",
                    dose_or_regimen="Dose-dependent; lower at ≤100 mg/day",
                    source="FDA Label / StatPearls",
                ),
                AdverseEffectItem(
                    reaction="Occult or overt gastrointestinal bleeding",
                    frequency="Common (1% to 5% with chronic use)",
                    population="Adults, heightened in elderly",
                    dose_or_regimen="Chronic administration",
                    source="FDA Label / StatPearls",
                ),
                AdverseEffectItem(
                    reaction="Tinnitus and reversible hearing impairment",
                    frequency="Dose-dependent (common at high anti-inflammatory doses >3 g/day)",
                    population="Patients receiving high anti-inflammatory doses",
                    dose_or_regimen="Serum salicylate >200 µg/mL",
                    source="FDA Overdosage Section",
                ),
                AdverseEffectItem(
                    reaction="Aspirin-induced bronchospasm / urticaria",
                    frequency="Rare to Uncommon (0.1% to 1% in general population; up to 10% in adult asthmatics)",
                    population="Asthmatic patients with nasal polyps",
                    dose_or_regimen="Any dose",
                    source="DailyMed SPL",
                ),
            ],
            overdose_and_management=FieldValue(
                content=(
                    "Manifestations: Salicylism (tinnitus, nausea, hyperventilation, respiratory alkalosis followed by severe metabolic acidosis), hyperthermia, confusion, pulmonary edema, coma.\n"
                    "Management: Establish airway and breathing; gastric lavage / repeated doses of activated charcoal within 2 to 4 hours of ingestion.\n"
                    "Specific Treatment & Antidote: Intravenous sodium bicarbonate infusion to alkalinize blood and urine (target urine pH 7.5–8.5), which ionizes salicylate and promotes renal clearance by >10-fold.\n"
                    "Hemodialysis: Indicated for refractory acidosis, renal failure, severe CNS dysfunction, or serum salicylate >100 mg/dL (>7.2 mmol/L)."
                ),
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed Overdosage — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
        nonclinical_toxicity=NonclinicalToxicity(
            genotoxicity=ToxFindingItem(
                status="Negative finding",
                details="Ames bacterial mutagenicity test and chromosomal aberration in vitro showed no mutagenic potential.",
                study_conditions="Ames Salmonella typhimurium assay",
            ),
            carcinogenicity=ToxFindingItem(
                status="Negative finding",
                details="No evidence of carcinogenic potential in long-term oral rodent bioassays in mice and rats.",
                species_or_model="Rat / Mouse (oral)",
            ),
            reproductive_and_developmental_toxicity=ToxFindingItem(
                status="Positive finding",
                details="Teratogenic in animal models (cleft palate, skeletal abnormalities) at high maternal toxic doses; causes premature closure of fetal ductus arteriosus in late pregnancy.",
                species_or_model="Rat (oral)",
                study_conditions="Late gestational administration",
            ),
            cytotoxicity=ToxFindingItem(
                status="Positive finding",
                details="Gastric epithelial cell cytotoxicity and uncoupling of oxidative phosphorylation observed at millimolar concentrations in vitro.",
                species_or_model="In vitro gastric mucosal cell lines",
            ),
            ld50=ToxFindingItem(
                status="Reported",
                details="Oral LD50: 200 mg/kg (rat); 400 mg/kg (mouse); 1010 mg/kg (rabbit)",
                species_or_model="Rat, Mouse, Rabbit",
                study_conditions="Oral administration",
            ),
            lc50=ToxFindingItem(
                status="Not evaluated",
                details="Inhalation LC50 data not evaluated for human clinical therapeutic products.",
            ),
            hazard_classification=ToxFindingItem(
                status="Reported",
                details="GHS Hazard: Acute Toxicity Oral Category 4 (H302: Harmful if swallowed); Skin Irritation Category 2; Eye Irritation Category 2A; Reproductive Toxicity Category 2.",
            ),
        ),
    ),

    # 5. THERAPEUTIC PROFILE
    therapeutic_profile=TherapeuticProfileSection(
        indications=IndicationsCategories(
            approved_indications=[
                IndicationItem(
                    indication="Secondary prevention of recurrent myocardial infarction and stroke",
                    jurisdiction="US FDA & Indonesia BPOM",
                    dosage_form="Oral immediate-release or enteric-coated tablet (75–325 mg daily)",
                    evidence_type="Regulatory",
                    source="FDA Approved Package Insert / BPOM Izin Edar",
                ),
                IndicationItem(
                    indication="Acute coronary syndrome (STEMI, NSTEMI, unstable angina)",
                    jurisdiction="US FDA & Indonesia BPOM",
                    dosage_form="Oral chewable tablet (162–325 mg loading dose)",
                    evidence_type="Regulatory",
                    source="FDA Package Insert / ACC/AHA Guidelines",
                ),
                IndicationItem(
                    indication="Mild to moderate pain and fever (headache, musculoskeletal pain, dysmenorrhea)",
                    jurisdiction="US FDA & Indonesia BPOM",
                    dosage_form="Oral tablet (325–650 mg every 4 to 6 hours)",
                    evidence_type="Regulatory",
                    source="FDA OTC Monograph",
                ),
                IndicationItem(
                    indication="Inflammatory conditions (Rheumatoid arthritis, osteoarthritis, systemic lupus erythematosus)",
                    jurisdiction="US FDA",
                    dosage_form="Oral tablet (3–4 g daily in divided doses)",
                    evidence_type="Regulatory",
                    source="FDA Approved Label",
                ),
            ],
            off_label_use=[
                IndicationItem(
                    indication="Preeclampsia prophylaxis in high-risk pregnancies (initiating at 12–16 weeks gestation)",
                    jurisdiction="ACOG / USPSTF Clinical Guidelines",
                    dosage_form="Oral low-dose tablet (81 mg daily)",
                    evidence_type="Clinical",
                    source="USPSTF Recommendation Statement",
                ),
                IndicationItem(
                    indication="Colorectal cancer chemoprevention in patients with Lynch syndrome",
                    jurisdiction="Clinical Practice Guidelines",
                    dosage_form="Oral tablet (600 mg daily)",
                    evidence_type="Clinical",
                    source="CAPP2 Clinical Trial",
                ),
            ],
            investigational_uses=[
                IndicationItem(
                    indication="Adjuvant therapy in solid tumor micrometastasis prevention",
                    jurisdiction="Investigational",
                    dosage_form="Oral 81–100 mg daily",
                    evidence_type="Clinical",
                    source="ClinicalTrials.gov NCT02467582",
                ),
            ],
        ),
        dosage_and_administration=DosageAndAdministration(
            indication_and_population=FieldValue(
                content="Cardiovascular secondary prevention in adult men and women; Pain/fever in adults and children ≥16 years.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="FDA Prescribing Info", url="https://dailymed.nlm.nih.gov")],
            ),
            dose_route_frequency_duration=FieldValue(
                content="Antiplatelet: 75 mg to 100 mg once daily orally indefinitely. Acute MI: 162 mg to 325 mg chewed immediately. Analgesic/Antipyretic: 325 mg to 650 mg orally every 4 to 6 hours as needed (maximum 4000 mg/24 hours).",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            formulation_instructions=FieldValue(
                content="Take with food or a full glass of water to reduce gastric irritation. Do not crush or chew enteric-coated formulations; chew immediate-release tablets for acute coronary syndromes.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            dose_adjustments=FieldValue(
                content="Renal: Avoid in severe renal failure (GFR <10 mL/min). Hepatic: Avoid in severe hepatic impairment. Geriatric: Use lowest effective dose due to increased bleeding susceptibility.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            administration_restrictions=FieldValue(
                content="Avoid concurrent alcohol intake due to additive risk of gastric bleeding. Discontinue 7 days before major elective surgical procedures unless cardiovascular benefit outweighs bleeding hazard.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
        drug_interactions=[
            DrugInteractionItem(
                interacting_substance="Oral anticoagulants (Warfarin, DOACs - Apixaban, Rivaroxaban)",
                interaction_category="Label-reported",
                mechanism="Synergistic inhibition of primary and secondary hemostasis",
                clinical_consequence="Markedly increased incidence of major systemic and GI bleeding",
                evidence_level="Regulatory",
                recommended_management="Avoid concurrent therapy unless strictly indicated; co-prescribe proton-pump inhibitor (PPI)",
            ),
            DrugInteractionItem(
                interacting_substance="Ibuprofen and other non-selective reversible NSAIDs",
                interaction_category="Label-reported",
                mechanism="Reversible binding of ibuprofen to COX-1 active site competitively impedes aspirin's covalent acetylation of Ser530",
                clinical_consequence="Attenuates or eliminates the cardioprotective antiplatelet effect of aspirin",
                evidence_level="Regulatory",
                recommended_management="Take immediate-release aspirin at least 30 minutes before ibuprofen or at least 8 hours after ibuprofen",
            ),
            DrugInteractionItem(
                interacting_substance="Methotrexate",
                interaction_category="Label-reported",
                mechanism="Displacement of methotrexate from albumin binding and inhibition of renal tubular clearance",
                clinical_consequence="Severe bone marrow suppression and methotrexate toxicity",
                evidence_level="Regulatory",
                recommended_management="Contraindicated at high methotrexate doses (>15 mg/week); monitor blood counts at low doses",
            ),
            DrugInteractionItem(
                interacting_substance="SSRIs and SNRIs (Sertraline, Fluoxetine)",
                interaction_category="Study-reported",
                mechanism="Depletion of platelet intra-granular serotonin stores combined with COX-1 inhibition",
                clinical_consequence="Additive increase in upper gastrointestinal bleeding risk",
                evidence_level="Clinical",
                recommended_management="Consider gastroprotection with a PPI when co-prescribing",
            ),
        ],
        special_populations=SpecialPopulations(
            renal_impairment=FieldValue(
                content="Use with caution in moderate impairment; contraindicated in severe renal impairment (GFR <10 mL/min). Prostaglandin inhibition can precipitate acute renal decompensation.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            hepatic_impairment=FieldValue(
                content="Avoid in severe hepatic impairment due to baseline hypoprothrombinemia, reduced drug metabolism, and increased bleeding risks.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            pregnancy_and_lactation=FieldValue(
                content="Pregnancy: Low-dose (81 mg) is safe and recommended for preeclampsia prophylaxis under guidance. High-dose is contraindicated during 3rd trimester (premature ductus arteriosus closure, maternal/fetal bleeding). Lactation: Salicylate enters breast milk; chronic high-dose use is discouraged.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            pediatric_patients=FieldValue(
                content="Contraindicated in children and adolescents <16 years presenting with viral febrile illness due to high risk of fatal Reye's syndrome.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            older_adults=FieldValue(
                content="Elderly patients have elevated susceptibility to severe gastrointestinal bleeding, asymptomatic peptic ulceration, and renal impairment. Lowest effective dose is recommended.",
                evidence_type="Regulatory",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
            other_populations=FieldValue(
                content="Patients with G6PD deficiency may experience acute hemolytic anemia at high therapeutic doses.",
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="DailyMed SPL — Aspirin", url="https://dailymed.nlm.nih.gov")],
            ),
        ),
        pharmacogenomics=PharmacogenomicsField(
            genes_and_variants="PTGS1, TBXA2R, and CYP2C9 variants (*2 and *3 alleles)",
            clinical_consequences="CYP2C9 poor metabolizers (*3/*3) clear salicylate more slowly at high doses. Aspirin 'resistance' has been associated in small cohorts with PTGS1 promoter polymorphisms, but without consensus actionable guidelines.",
            prescribing_recommendations="No established clinically actionable pharmacogenomic recommendation identified in the sources reviewed. CPIC does not provide genotype-guided dosing for aspirin in antiplatelet indications.",
            statement="No established clinically actionable pharmacogenomic recommendation identified in the sources reviewed.",
            sources=[Citation(source="CPIC / PharmGKB", url="https://www.pharmgkb.org/chemical/PA448488")],
            missing=False,
        ),
        regulatory_status=RegulatoryStatus(
            united_states=JurisdictionRegulatory(
                jurisdiction="United States",
                authority="US FDA",
                status="Approved",
                details="FDA Approved. Available OTC under FDA Monograph and by prescription via multiple NDAs/ANDAs (e.g. NDA 006439 Bayer Aspirin).",
                sources=[Citation(source="Drugs@FDA", url="https://www.accessdata.fda.gov/scripts/cder/daf/")],
            ),
            indonesia=JurisdictionRegulatory(
                jurisdiction="Indonesia",
                authority="BPOM",
                status="Registered",
                details="Registered with Badan Pengawas Obat dan Makanan (BPOM Republik Indonesia). Active registered products include Thrombo Aspilets (NIE: DKL9115801710A1) and Cardio Aspirin 100 mg (NIE: DKI9951601610A1).",
                sources=[Citation(source="BPOM Cek Produk Obat", url="https://cekbpom.pom.go.id/")],
            ),
        ),
        clinical_trial_outcomes=[
            ClinicalTrialOutcomeItem(
                study="ISIS-2 (Second International Study of Infarct Survival)",
                population="17,187 patients with suspected acute myocardial infarction entering within 24 hours of symptom onset",
                intervention_and_comparator="Aspirin 160 mg daily for 1 month vs Placebo, alone and with Streptokinase",
                sample_size="n = 17,187",
                outcome_and_effect="Aspirin alone produced a highly significant 23% reduction in 5-week vascular mortality (9.4% vs 11.8%; 2p < 0.00001) and a 49% reduction in non-fatal reinfarction.",
                evidence_source="Lancet 1988; ii: 349-360",
            ),
            ClinicalTrialOutcomeItem(
                study="Physicians' Health Study (PHS)",
                population="22,071 healthy male physicians aged 40–84 years",
                intervention_and_comparator="Aspirin 325 mg on alternate days vs Placebo",
                sample_size="n = 22,071",
                outcome_and_effect="44% reduction in risk of first myocardial infarction (RR 0.56, 95% CI 0.45–0.70, P < 0.00001); slight increase in hemorrhagic stroke.",
                evidence_source="N Engl J Med 1989; 321: 129-135",
            ),
            ClinicalTrialOutcomeItem(
                study="ASPREE (Aspirin in Reducing Events in the Elderly)",
                population="19,114 community-dwelling older adults (≥70 years; ≥65 for minorities) free of overt CVD",
                intervention_and_comparator="Aspirin 100 mg daily vs Placebo",
                sample_size="n = 19,114",
                outcome_and_effect="Aspirin did not prolong disability-free survival (HR 1.01, 95% CI 0.92–1.11) and led to significantly higher rate of major hemorrhage (HR 1.38, 95% CI 1.18–1.62).",
                evidence_source="N Engl J Med 2018; 379: 1499-1508",
            ),
        ],
    ),

    # 6. REFERENCES & DATA QUALITY
    references=ReferencesSection(
        sources=[
            SourceReferenceItem(
                source_name="DailyMed FDA Structured Product Labeling (SPL)",
                category="Official regulatory documents",
                url="https://dailymed.nlm.nih.gov",
                citation="FDA Approved Package Insert: Aspirin Tablets (Bayer Healthcare LLC / US FDA)",
            ),
            SourceReferenceItem(
                source_name="BPOM Cek Produk Obat Terdaftar",
                category="Official regulatory documents",
                url="https://cekbpom.pom.go.id/",
                citation="Badan Pengawas Obat dan Makanan (BPOM RI) Database Obat Terdaftar",
            ),
            SourceReferenceItem(
                source_name="PubChem Compound Database (CID 2244)",
                category="Established drug databases",
                url="https://pubchem.ncbi.nlm.nih.gov/compound/2244",
                citation="National Center for Biotechnology Information (NCBI). PubChem Compound Summary for CID 2244, Acetylsalicylic Acid.",
            ),
            SourceReferenceItem(
                source_name="ChEMBL Bioactivity Database (CHEMBL25)",
                category="Established drug databases",
                url="https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL25/",
                citation="European Bioinformatics Institute (EMBL-EBI). ChEMBL Compound Record: Aspirin.",
            ),
            SourceReferenceItem(
                source_name="PharmGKB Pharmacogenomics Knowledgebase",
                category="Established drug databases",
                url="https://www.pharmgkb.org/chemical/PA448488",
                citation="PharmGKB Chemical Annotation: Aspirin (PA448488)",
            ),
            SourceReferenceItem(
                source_name="ISIS-2 Collaborative Group Clinical Trial",
                category="Peer-reviewed studies",
                url="https://pubmed.ncbi.nlm.nih.gov/2899772/",
                citation="Randomised trial of intravenous streptokinase, oral aspirin, both, or neither among 17,187 cases of suspected acute myocardial infarction. Lancet 1988;2(8607):349-360.",
            ),
        ],
        limitations_and_confidence=LimitationsAndConfidence(
            limitations=FieldValue(
                content=(
                    "1. Kinetic vs covalent model differences: Classic reversible Kd/Ki models only approximate aspirin's covalent pseudo-first-order inactivation kinetics.\n"
                    "2. Platelet vs endothelial selectivity is achieved through presystemic portal clearance dynamics rather than intrinsically massive target specificity.\n"
                    "3. Recent primary prevention trials (ASPREE, ASCEND) show that in modern statin-treated populations without overt CVD, bleeding hazards frequently balance or outweigh ischemic benefits."
                ),
                evidence_type="Clinical",
                status_label="Reported",
                sources=[Citation(source="Clinical Pharmacology Reviews", url="https://dailymed.nlm.nih.gov")],
            ),
            data_confidence_rating="HIGH (FDA Approved with Full Label)",
            evidence_summary="Extensive regulatory product labels, decades of randomized double-blind clinical trials (n > 100,000), crystallographic target structures, and comprehensive pharmacokinetics in humans.",
        ),
    ),
)
