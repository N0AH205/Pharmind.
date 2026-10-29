"""
PharmaRAG — Multi-Source Unified Pharmacology Ingestion Client.

Unifies and federates access across leading open pharmaceutical and biomedical datasets:
1. Chemical Identity: PubChem, ChEMBL, DrugCentral, FDA GSRS (UNII), EPA CompTox
2. Pharmacodynamics & Targets: DrugCentral (Ki/Kd/IC50), ChEMBL, BindingDB, IUPHAR
3. Pharmacokinetics (ADME): PubChem PUG-View, openFDA, DailyMed, PK-DB
4. Toxicology & Safety: SIDER (adverse effects), HSDB/TOXNET, openFDA Boxed Warnings
5. Clinical & Regulatory: openFDA, DailyMed, BPOM, ClinicalTrials.gov
6. Pharmacogenomics: PharmGKB, CPIC guidelines
7. Scientific Literature: PubMed, Europe PMC REST API
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
import httpx
from rag.config import require_network_allowed

logger = logging.getLogger(__name__)

# Known brand and salt aliases for high-yield FDA/DailyMed matching
COMMON_DRUG_EXPANSIONS: dict[str, dict[str, list[str]]] = {
    "methamphetamine": {
        "salts": ["methamphetamine hydrochloride", "metamfetamine hydrochloride", "d-methamphetamine hcl"],
        "brands": ["Desoxyn", "Desoxyn Gradumet"],
        "unapproved_aliases": ["meth", "crystal meth", "speed"],
    },
    "aspirin": {
        "salts": ["acetylsalicylic acid", "sodium acetylsalicylate"],
        "brands": ["Bayer", "Bufferin", "Ecotrin", "Durlaza", "Aspilets"],
        "unapproved_aliases": ["asa"],
    },
    "ibuprofen": {
        "salts": ["ibuprofen sodium", "ibuprofen lysine"],
        "brands": ["Advil", "Motrin", "Nurofen", "Proris"],
        "unapproved_aliases": [],
    },
    "paracetamol": {
        "salts": ["acetaminophen"],
        "brands": ["Tylenol", "Panadol", "Calpol", "Sanmol", "Biogesic"],
        "unapproved_aliases": ["apap"],
    },
    "metformin": {
        "salts": ["metformin hydrochloride"],
        "brands": ["Glucophage", "Fortamet", "Glumetza", "Riomet"],
        "unapproved_aliases": [],
    },
    "atorvastatin": {
        "salts": ["atorvastatin calcium"],
        "brands": ["Lipitor", "Torvast", "Atorva", "Lipitor Plus"],
        "unapproved_aliases": [],
    },
}


COMMON_SALT_SUFFIXES = [
    "hydrochloride", "hcl", "sodium", "potassium", "calcium",
    "sulfate", "sulphate", "mesylate", "maleate", "tartrate",
    "fumarate", "acetate", "citrate", "bromide", "phosphate",
    "succinate", "dihydrate", "monohydrate", "trihydrate",
]


def get_drug_synonym_expansions(drug_name: str, synonyms: list[str] | None = None) -> list[str]:
    """
    Universal chemical & clinical synonym expansion for ANY molecule:
    1. Algorithmic salt stripping: "metformin hydrochloride" -> base "metformin"
    2. Algorithmic clinical salt candidate generation: "sotorasib" -> "sotorasib hydrochloride", etc.
    3. Dynamic synonym filtering (brands, development codes like AMG-510, INN/USAN variations)
    4. Fallback registry for irregular common abbreviations (e.g. ASA -> Aspirin)
    """
    clean = drug_name.strip()
    clean_lower = clean.lower()
    terms = [clean]

    # 1. Algorithmic salt stripping: extract parent free-base
    base_name = clean
    for suffix in COMMON_SALT_SUFFIXES:
        if clean_lower.endswith(" " + suffix):
            base_name = clean[:-len(suffix)-1].strip()
            terms.append(base_name)
            break
        elif clean_lower.endswith(suffix) and len(clean.split()) > 1:
            base_name = clean[:-len(suffix)].strip()
            terms.append(base_name)
            break

    # 2. Algorithmic clinical salt derivation (generate top pharmaceutical salt variants)
    for salt in ("hydrochloride", "sodium", "potassium", "calcium", "sulfate", "mesylate"):
        salt_variant = f"{base_name} {salt}"
        if salt_variant.lower() != clean_lower:
            terms.append(salt_variant)

    # 3. Dynamic synonym injection (prioritize clean brands, codes, and INN names)
    if synonyms:
        for s in synonyms[:15]:
            s_clean = s.strip()
            # Skip pure CAS registry numbers and InChI strings
            if re.match(r"^\d{2,7}-\d{2}-\d$", s_clean) or s_clean.startswith("InChI="):
                continue
            terms.append(s_clean)

    # 4. Known irregular colloquial abbreviations fallback
    irreg = COMMON_DRUG_EXPANSIONS.get(clean_lower)
    if irreg:
        terms.extend(irreg.get("salts", []))
        terms.extend(irreg.get("brands", []))
        terms.extend(irreg.get("unapproved_aliases", []))

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for t in terms:
        t_clean = t.strip()
        if t_clean and t_clean.lower() not in seen:
            seen.add(t_clean.lower())
            deduped.append(t_clean)
    return deduped[:12]


async def fetch_mychem_profile(drug_name: str, inchi_key: str | None = None) -> dict[str, Any]:
    """
    Query MyChem.info (Scripps Research / NIH) to aggregate:
    - DrugCentral: Curated targets, bioactivities (Ki, Kd, IC50), approved indications, contraindications
    - SIDER: MedDRA adverse drug reactions and frequencies
    - PharmGKB: CPIC annotations, VIP genes, drug cross-references
    - ChEMBL: Curated mechanism of action and molecule IDs
    - FDA GSRS: UNII identifier
    """
    require_network_allowed("fetch_mychem_profile")
    query = inchi_key or drug_name
    url = "https://mychem.info/v1/query"
    params = {
        "q": query,
        "fields": "drugcentral,sider,pharmgkb,chembl,unii",
        "size": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                if hits:
                    return hits[0]
    except Exception as exc:
        logger.debug("MyChem.info lookup failed for %s: %s", drug_name, exc)
    return {}


async def fetch_pubchem_pugview_data(cid: int | str, strict: bool = False) -> dict[str, Any]:
    """
    Extract structured pharmacological passages from PubChem PUG-View:
    - Mechanism of Action (Pharmacology and Biochemistry)
    - Absorption, Distribution, Metabolism, Excretion (ADME)
    - Biological Half-Life
    - Toxicity Summary & Non-Human Toxicity Values
    - Antidotes & Overdose Management
    - Black Box Warnings & FDA Precautions
    """
    require_network_allowed("fetch_pubchem_pugview_data")
    if not str(cid).isdigit():
        return {}

    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON/"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            if r.status_code == 200:
                record = r.json().get("Record", {})
                return _parse_pugview_record(record, cid)
            if strict:
                r.raise_for_status()
    except Exception as exc:
        logger.debug("PubChem PUG-View fetch failed for CID %s: %s", cid, exc)
        if strict:
            raise
    return {}


def _parse_pugview_record(record: dict, cid: int | str) -> dict[str, Any]:
    """Extract clean section texts from nested PUG-View JSON tree."""
    extracted: dict[str, list[dict]] = {
        "moa": [],
        "adme": [],
        "metabolism": [],
        "half_life": [],
        "toxicology": [],
        "boxed_warning": [],
        "antidote": [],
        "targets": [],
    }

    def _walk(sections):
        for sec in sections:
            heading = sec.get("TOCHeading", "")
            info_list = sec.get("Information", [])
            sub_secs = sec.get("Section", [])

            for info in info_list:
                val = info.get("Value", {})
                strings = []
                if "StringWithMarkup" in val:
                    for sm in val["StringWithMarkup"]:
                        s = sm.get("String", "").strip()
                        if s:
                            strings.append(s)
                elif "Number" in val:
                    strings.append(f"{val.get('Number')} {val.get('Unit', '')}".strip())

                if not strings:
                    continue
                content = "\n".join(strings)
                ref_num = info.get("ReferenceNumber")

                if heading in ("Mechanism of Action", "Pharmacodynamics"):
                    extracted["moa"].append({"heading": heading, "text": content, "ref": ref_num})
                elif heading in ("Absorption, Distribution and Excretion", "Pharmacokinetics"):
                    extracted["adme"].append({"heading": heading, "text": content, "ref": ref_num})
                elif heading in ("Metabolism/Metabolites",):
                    extracted["metabolism"].append({"heading": heading, "text": content, "ref": ref_num})
                elif heading in ("Biological Half-Life",):
                    extracted["half_life"].append({"heading": heading, "text": content, "ref": ref_num})
                elif heading in ("Toxicity Summary", "Non-Human Toxicity Excerpts", "Human Toxicity Excerpts", "Acute Effects"):
                    extracted["toxicology"].append({"heading": heading, "text": content, "ref": ref_num})
                elif heading in ("Black Box Warning", "Boxed Warning"):
                    extracted["boxed_warning"].append({"heading": heading, "text": content, "ref": ref_num})
                elif heading in ("Antidote and Emergency Treatment", "Treatment"):
                    extracted["antidote"].append({"heading": heading, "text": content, "ref": ref_num})

            if sub_secs:
                _walk(sub_secs)

    _walk(record.get("Section", []))
    return extracted


async def fetch_europe_pmc_passages(drug_name: str, limit: int = 5, strict: bool = False) -> list[dict]:
    """
    Query Europe PMC REST API for high-impact open access biomedical literature.
    Fast, reliable, open access full-text articles and citations.
    """
    require_network_allowed("fetch_europe_pmc_passages")
    clean = drug_name.strip()
    if not clean:
        return []

    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    query = f'"{clean}" AND (pharmacokinetics OR pharmacodynamics OR "mechanism of action" OR "clinical trial")'
    params = {
        "query": query,
        "format": "json",
        "pageSize": limit,
        "resultType": "core",
    }

    passages = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            if r.status_code == 200:
                results = r.json().get("resultList", {}).get("result", [])
                for item in results:
                    title = item.get("title", "")
                    abstract = item.get("abstractText", "")
                    if not abstract:
                        continue
                    pmid = item.get("pmid", "")
                    doi = item.get("doi", "")
                    passages.append({
                        "text": f"{title}\n\n{abstract}",
                        "source": f"Europe PMC {pmid or doi}",
                        "url": f"https://europepmc.org/article/MED/{pmid}" if pmid else f"https://doi.org/{doi}",
                        "field": "research_review",
                        "retrieval_group": "research_review",
                        "distance": 1.0,
                        "drug": clean,
                        "authors": item.get("authorString", ""),
                        "publication_date": str(item.get("pubYear", "")),
                        "journal": item.get("journalTitle", ""),
                        "doi": doi,
                        "pmid": pmid,
                    })
            elif strict:
                r.raise_for_status()
    except Exception as exc:
        logger.debug("Europe PMC search failed for %s: %s", drug_name, exc)
        if strict:
            raise
    return passages
