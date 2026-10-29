"""On-demand online source refresh for compounds identified by PubChem."""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)
_REFRESH_INTERVAL_SECONDS = 12 * 60 * 60
_last_refresh: dict[str, float] = {}
_refresh_locks: dict[str, asyncio.Lock] = {}


class SearchResults(list[dict]):
    """Live passages with source failures retained for honest field statuses."""

    def __init__(self):
        super().__init__()
        self.failures: list[str] = []


async def refresh_compound_sources(structure_data: dict, collection) -> int:
    """Search supported source APIs and index results at most every 12 hours."""
    cid = str(structure_data.get("pubchem_cid") or "").strip()
    name = str(structure_data.get("common_name") or structure_data.get("iupac_name") or "").strip()
    smiles = str(structure_data.get("smiles") or "").strip()
    if not name:
        return 0

    key_id = cid if (cid and cid.isdigit()) else f"name-{name.lower()}"
    lock = _refresh_locks.setdefault(key_id, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        last_refresh = _last_refresh.get(key_id)
        if last_refresh is not None and now - last_refresh < _REFRESH_INTERVAL_SECONDS:
            return 0
        _last_refresh[key_id] = now
        try:
            from ingest.run_ingest import ingest_drug

            brand_names = structure_data.get("brand_names") or []
            dailymed_candidate = brand_names[0] if brand_names else name

            count = await ingest_drug(
                {
                    "name": name,
                    "smiles": smiles,
                    "cid": int(cid) if (cid and cid.isdigit()) else None,
                    "inchi_key": structure_data.get("inchi_key"),
                    "dailymed_query": dailymed_candidate,
                },
                collection,
            )
            logger.info("Online source refresh for %s (%s): %s chunks", name, key_id, count)
            return count
        except Exception:
            logger.exception("Online source refresh failed for %s (%s)", name, key_id)
            return 0


async def search_live_pubmed(compound: str | dict) -> list[dict]:
    """Fetch a fresh, topic-balanced PubMed and ClinicalTrials evidence set for this monograph."""
    if isinstance(compound, dict):
        name = str(compound.get("common_name") or "").strip()
        brand_names = compound.get("brand_names") or []
        if isinstance(brand_names, str):
            brand_names = [brand_names]
        raw_aliases = compound.get("synonyms") or []
        if isinstance(raw_aliases, str):
            raw_aliases = [raw_aliases]
        aliases = [name, *brand_names, *(str(alias).strip() for alias in raw_aliases), str(compound.get("iupac_name") or "").strip()]
    else:
        name = compound.strip()
        aliases = [name]
    aliases = list(dict.fromkeys(alias for alias in aliases if alias))[:4]
    if not aliases:
        return []

    passages = SearchResults()
    cid_str = str(compound.get("pubchem_cid") or "") if isinstance(compound, dict) else ""
    inchi_key = compound.get("inchi_key") if isinstance(compound, dict) else None

    search_name = name or (aliases[0] if aliases else "")
    if not search_name:
        return []

    # Run multi-source verified retrieval concurrently:
    # 1. openFDA Approved Label passages (ADME, Contraindications, Tox, Overdose)
    # 2. NCBI StatPearls Clinical Monographs (Peer-reviewed clinical indications & monitoring)
    # 3. ChEMBL Curated Targets & Quantitative Bioactivities (Ki, Kd, IC50)
    # 4. ClinicalTrials.gov (Active clinical studies)
    # 5. PubMed topic searches
    try:
        from ingest.openfda import fetch_openfda_passages
        fda_passages = await fetch_openfda_passages(search_name, canonical_name=search_name, cid_str=cid_str, strict=True)
        passages.extend(fda_passages)
    except Exception as exc:
        passages.failures.append("openFDA")
        logger.warning("Live openFDA retrieval failed for %s: %s", search_name, exc)

    try:
        from ingest.statpearls import fetch_statpearls_passages
        sp_passages = await fetch_statpearls_passages(search_name, canonical_name=search_name, cid_str=cid_str, strict=True)
        passages.extend(sp_passages)
    except Exception as exc:
        passages.failures.append("StatPearls")
        logger.warning("Live StatPearls retrieval failed for %s: %s", search_name, exc)

    # 3b. PubChem PUG-View verified pharmacology & toxicology monograph
    if cid_str and cid_str.isdigit():
        try:
            from ingest.unified_pharmacology import fetch_pubchem_pugview_data
            pv_data = await fetch_pubchem_pugview_data(cid_str, strict=True)
            group_field_map = {
                "moa": ("moa", "moa"),
                "adme": ("adme", "adme"),
                "metabolism": ("adme", "adme"),
                "half_life": ("adme", "adme"),
                "toxicology": ("toxicology", "toxicology"),
                "boxed_warning": ("boxed_warning", "boxed_warning"),
                "antidote": ("acute_toxicity", "toxicology"),
            }
            for sec_key, items in pv_data.items():
                target_field, target_group = group_field_map.get(sec_key, ("research_review", "research_review"))
                for item in items[:3]:
                    passages.append({
                        "text": item.get("text", ""),
                        "source": f"PubChem PUG-View CID {cid_str}",
                        "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid_str}",
                        "field": target_field,
                        "retrieval_group": target_group,
                        "distance": 1.0,
                        "drug": name or aliases[0],
                        "pubchem_cid": cid_str,
                        "document_id": f"pugview_{cid_str}_{sec_key}",
                    })
        except Exception as exc:
            passages.failures.append("PubChem PUG-View")
            logger.warning("PubChem PUG-View live retrieval failed: %s", exc)

    # 3c. Europe PMC open access literature
    try:
        from ingest.unified_pharmacology import fetch_europe_pmc_passages
        epmc_passages = await fetch_europe_pmc_passages(search_name, limit=3, strict=True)
        passages.extend(epmc_passages)
    except Exception as exc:
        passages.failures.append("Europe PMC")
        logger.warning("Europe PMC live search failed: %s", exc)

    # 4. On-demand ClinicalTrials.gov search for active Phase 3/4 trials
    try:
        from ingest.clinicaltrials import search_drug_trials
        trials = await search_drug_trials(search_name, limit=4, strict=True)
        for trial in trials:
            nct_id = trial.get("nct_id", "")
            passages.append({
                "text": trial.get("text", ""),
                "source": f"ClinicalTrials.gov {nct_id}",
                "url": trial.get("url", f"https://clinicaltrials.gov/study/{nct_id}"),
                "field": "clinical_trials",
                "retrieval_group": "clinical_trials",
                "distance": 1.0,
                "drug": name or aliases[0],
                "pubchem_cid": cid_str,
                "publication_date": trial.get("publication_date", ""),
                "document_id": nct_id,
            })
    except Exception as exc:
        passages.failures.append("ClinicalTrials.gov")
        logger.warning("ClinicalTrials.gov search failed: %s", exc)

    # 5. PubMed live topic search
    try:
        from ingest.pubmed import fetch_abstracts, search_pubmed

        topic_queries = [
            ("moa", "mechanism of action pharmacology molecular target"),
            ("binding_affinity", "binding affinity Ki Kd dissociation constant target assay"),
            ("potency", "potency IC50 EC50 dose response assay"),
            ("efficacy", "clinical efficacy therapeutic effect dose response"),
            ("selectivity", "selectivity comparative inhibition off-target"),
            ("adme", "pharmacokinetics absorption distribution metabolism excretion half-life"),
            ("indications", "clinical indications therapeutic use efficacy"),
            ("adverse_effects", "adverse effects safety side effects warnings"),
            ("interactions", "drug interactions contraindications interaction"),
            ("toxicology", "toxicology acute toxicity genotoxicity carcinogenicity"),
            ("acute_toxicity", "overdose poisoning acute toxicity LD50 animal"),
            ("cytotoxicity", "cytotoxicity cell viability IC50 cell line"),
            ("genetic_toxicology", "genotoxicity mutagenicity carcinogenicity reproductive toxicity"),
            ("pharmacogenomics", "pharmacogenomics gene variant genotype prescribing"),
            ("special_populations", "pregnancy lactation pediatric renal hepatic impairment"),
            ("dosage", "prescribing information dosage administration dose"),
            ("boxed_warning", "FDA boxed warning black box warning"),
            ("clinical_trials", "clinical trial randomized study outcomes results"),
            ("history", "discovery development history approval"),
        ]
        topic_pmids: dict[str, list[str]] = {}
        all_pmids: list[str] = []
        seen: set[str] = set()
        name_query = " OR ".join(f'"{alias}"[Title/Abstract]' for alias in aliases)
        semaphore = asyncio.Semaphore(3)

        async def search_topic(topic: str, suffix: str) -> tuple[str, list[str]]:
            async with semaphore:
                matches = await search_pubmed(f'({name_query}) AND ({suffix})', max_results=4, raise_errors=True)
                return topic, matches

        topic_results = await asyncio.gather(
            *(search_topic(topic, suffix) for topic, suffix in topic_queries),
            return_exceptions=True,
        )
        for result in topic_results:
            if isinstance(result, Exception):
                passages.failures.append("PubMed")
                logger.warning("Live PubMed topic search failed for %s: %s", search_name, result)
                continue
            topic, matches = result
            topic_pmids[topic] = matches
            for pmid in matches:
                if pmid not in seen:
                    seen.add(pmid)
                    all_pmids.append(pmid)

        articles = await fetch_abstracts(all_pmids, raise_errors=True)
        for topic, pmids in topic_pmids.items():
            for article in articles:
                if article.get("pmid") not in pmids:
                    continue
                pmid = article.get("pmid", "")
                passages.append({
                    "text": f"{article.get('title', '')}\n\n{article.get('abstract', '')}",
                    "source": f"PubMed PMID {pmid}",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "field": topic,
                    "retrieval_group": topic,
                    "distance": 1.0,
                    "drug": name or aliases[0],
                    "pubchem_cid": cid_str,
                    "authors": "; ".join(article.get("authors", [])),
                    "publication_date": article.get("publication_date", ""),
                    "journal": article.get("journal", ""),
                    "doi": article.get("doi", ""),
                    "pmid": pmid,
                    "document_id": pmid,
                })
    except Exception as exc:
        passages.failures.append("PubMed")
        logger.warning("Live PubMed search failed: %s", exc)

    return passages
