"""
NCBI Bookshelf / StatPearls Client — Clinical Drug Monographs.

Fetches peer-reviewed clinical drug monographs from StatPearls on NCBI Bookshelf:
  - Mechanism of Action (cellular & receptor level)
  - FDA-approved & off-label Indications
  - Absolute & relative Contraindications
  - Adverse Effects & Black Box Warnings
  - Clinical Toxicity, Overdose & Antidotes
  - Patient Monitoring & Organ-specific dose adjustments

Zero Wikipedia. 100% Peer-reviewed NIH/NLM clinical literature.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import httpx
from rag.config import require_network_allowed

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "statpearls"


def _get_cache(key: str) -> list[dict] | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _set_cache(key: str, data: list[dict]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{key}.json"
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to cache StatPearls data for %s: %s", key, exc)


async def search_statpearls_pmids(drug_name: str, max_results: int = 3, strict: bool = False) -> list[str]:
    """Search for StatPearls monograph PMIDs in PubMed."""
    require_network_allowed("StatPearls monograph search")
    clean = drug_name.strip()
    if not clean:
        return []

    failures = []
    async with httpx.AsyncClient(timeout=15) as client:
        # Try Title match first for highest specificity
        query = f'"{clean}"[Title] AND "StatPearls"[Book]'
        try:
            resp = await client.get(
                f"{EUTILS_BASE}/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results},
            )
            if resp.status_code == 200:
                idlist = resp.json().get("esearchresult", {}).get("idlist", [])
                if idlist:
                    return idlist
            else:
                resp.raise_for_status()
        except Exception as exc:
            failures.append(exc)
            logger.warning("StatPearls title search failed for %s: %s", drug_name, exc)

        # Fallback to Title/Abstract
        query_fallback = f'("{clean}"[Title/Abstract]) AND ("StatPearls"[Book])'
        try:
            resp = await client.get(
                f"{EUTILS_BASE}/esearch.fcgi",
                params={"db": "pubmed", "term": query_fallback, "retmode": "json", "retmax": max_results},
            )
            if resp.status_code == 200:
                return resp.json().get("esearchresult", {}).get("idlist", [])
            resp.raise_for_status()
        except Exception as exc:
            failures.append(exc)
            logger.warning("StatPearls fallback search failed for %s: %s", drug_name, exc)

    if strict and failures:
        raise RuntimeError(f"StatPearls search failed for {drug_name}: {failures[-1]}")
    return []


async def fetch_statpearls_passages(
    drug_name: str,
    canonical_name: str | None = None,
    cid_str: str | None = None,
    strict: bool = False,
) -> list[dict]:
    """
    Fetch and chunk peer-reviewed StatPearls clinical monograph sections.
    Returns passages tagged by pharmacological section (moa, indications, contraindications, adverse_effects, toxicology).
    """
    c_name = canonical_name or drug_name
    cache_key = re.sub(r"[^\w\-]", "_", c_name.lower())
    cached = _get_cache(cache_key)
    if cached or (cached is not None and not strict):
        return cached

    pmids = await search_statpearls_pmids(c_name, strict=strict)
    if not pmids and c_name.lower() != drug_name.lower():
        pmids = await search_statpearls_pmids(drug_name, strict=strict)

    if not pmids:
        _set_cache(cache_key, [])
        return []

    passages: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(
                f"{EUTILS_BASE}/efetch.fcgi",
                params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
            )
            if resp.status_code != 200:
                if strict:
                    resp.raise_for_status()
                return []

            root = ET.fromstring(resp.text)
            articles = root.findall(".//PubmedBookArticle") + root.findall(".//PubmedArticle")
            for article in articles:
                pmid_elem = article.find(".//PMID")
                pmid = pmid_elem.text.strip() if pmid_elem is not None and pmid_elem.text else ""
                title_elem = article.find(".//ArticleTitle") or article.find(".//BookTitle")
                title = title_elem.text.strip() if title_elem is not None and title_elem.text else f"{c_name} Clinical Monograph"

                # Extract accession / book ID if present
                book_id_elem = article.find(".//BookDocument/Book/BookId") or article.find(".//ArticleId[@IdType='bookaccession']")
                nbk_id = book_id_elem.text.strip() if book_id_elem is not None and book_id_elem.text else ""
                url = f"https://www.ncbi.nlm.nih.gov/books/{nbk_id}/" if nbk_id else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                # Check structured abstract sections
                abstract_elem = article.find(".//Abstract")
                if abstract_elem is None:
                    continue

                abstract_texts = abstract_elem.findall(".//AbstractText")
                if abstract_texts:
                    for sec in abstract_texts:
                        sec_label = (sec.get("Label") or "").strip().lower()
                        sec_text = "".join(sec.itertext()).strip()
                        if not sec_text:
                            continue

                        field = "clinical_pharmacology"
                        if "indication" in sec_label:
                            field = "indications"
                        elif "mechanism" in sec_label or "moa" in sec_label or "action" in sec_label:
                            field = "moa"
                        elif "contraindication" in sec_label:
                            field = "contraindications"
                        elif "adverse" in sec_label or "effect" in sec_label or "warning" in sec_label:
                            field = "adverse_effects"
                        elif "toxic" in sec_label or "overdose" in sec_label:
                            field = "toxicology"
                        elif "pharmacokinetic" in sec_label or "adme" in sec_label or "absorption" in sec_label:
                            field = "adme"
                        elif "monitor" in sec_label or "administration" in sec_label or "dosage" in sec_label:
                            field = "dosage"

                        label_prefix = f" [{sec_label.upper()}]" if sec_label else ""
                        passages.append({
                            "text": f"StatPearls Clinical Review{label_prefix}: {sec_text}",
                            "source": f"NCBI StatPearls — {c_name} ({title})",
                            "url": url,
                            "drug": c_name,
                            "pubchem_cid": cid_str or "",
                            "field": field,
                            "retrieval_group": field,
                            "pmid": pmid,
                            "document_id": nbk_id or pmid,
                        })
                else:
                    full_text = "".join(abstract_elem.itertext()).strip()
                    if full_text:
                        passages.append({
                            "text": f"StatPearls Peer-Reviewed Clinical Monograph: {full_text}",
                            "source": f"NCBI StatPearls — {c_name}: {title}",
                            "url": url,
                            "drug": c_name,
                            "pubchem_cid": cid_str or "",
                            "field": "indications",
                            "retrieval_group": "moa",
                            "pmid": pmid,
                            "document_id": nbk_id or pmid,
                        })


        except Exception as exc:
            logger.warning("Failed to fetch/parse StatPearls XML for %s: %s", c_name, exc)
            if strict:
                raise

    _set_cache(cache_key, passages)
    return passages
