"""
PubMed abstract fetcher — Phase 2.

Uses the NCBI E-utilities API (free, rate-limited to 3 req/s without API key,
10 req/s with NCBI_API_KEY).

API docs: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import httpx
from rag.config import require_network_allowed

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def mentions_identity(text: str, aliases: list[str]) -> bool:
    normalized = " " + re.sub(r"[^a-z0-9]+", " ", text.casefold()) + " "
    for alias in aliases:
        name = re.sub(r"[^a-z0-9]+", " ", alias.casefold()).strip()
        if len(name) >= 3 and f" {name} " in normalized:
            return True
    return False


async def search_pubmed(query: str, max_results: int = 20, raise_errors: bool = False) -> list[str]:
    require_network_allowed("PubMed search")
    """
    Search PubMed and return a list of PMIDs matching the query.

    Args:
        query:       PubMed search query string (e.g. "aspirin pharmacology mechanism").
        max_results: Maximum number of PMIDs to return.

    Returns:
        List of PMID strings (may be empty).
    """
    params: dict = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{BASE_URL}/esearch.fcgi", params=params)
            if resp.status_code != 200:
                if raise_errors:
                    resp.raise_for_status()
                return []
            return resp.json()["esearchresult"]["idlist"]
        except Exception:
            if raise_errors:
                raise
            return []


async def fetch_abstracts(pmids: list[str], raise_errors: bool = False) -> list[dict]:
    require_network_allowed("PubMed abstract download")
    """
    Fetch abstracts for a list of PMIDs via EFetch.

    Returns a list of dicts, each with keys:
        pmid     (str)
        title    (str)
        abstract (str)
        authors  (list[str])
    Only articles that have a non-empty abstract are included.
    """
    if not pmids:
        return []

    params: dict = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{BASE_URL}/efetch.fcgi", params=params)
            if resp.status_code != 200:
                if raise_errors:
                    resp.raise_for_status()
                return []
        except Exception:
            if raise_errors:
                raise
            return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        if raise_errors:
            raise
        return []

    results: list[dict] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID") or ""
        title = article.findtext(".//ArticleTitle") or ""

        # Abstract may be split across multiple AbstractText elements (structured abstract)
        abstract_parts = [
            elem.text or ""
            for elem in article.findall(".//AbstractText")
        ]
        abstract = " ".join(p.strip() for p in abstract_parts if p.strip())

        if not abstract:
            continue  # skip articles without an abstract

        # Collect author names (LastName + Initials)
        authors: list[str] = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName") or ""
            initials = author.findtext("Initials") or ""
            if last:
                authors.append(f"{last} {initials}".strip())

        journal = article.findtext(".//Journal/Title") or ""
        pub_date = article.findtext(".//JournalIssue/PubDate/Year") or article.findtext(".//JournalIssue/PubDate/MedlineDate") or ""
        doi = ""
        for locator in article.findall(".//ELocationID"):
            if locator.get("EIdType") == "doi":
                doi = (locator.text or "").strip()
                break

        results.append({
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "publication_date": pub_date,
            "doi": doi,
        })

    return results
