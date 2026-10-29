"""
PubChem data fetcher.

Uses the PubChem PUG REST API (free, no auth required).
Active in Phase 1+; expanded in Phase 2 to return common names and synonyms
so that the retrieval query builder can construct better search strings.

Key endpoints:
  - /compound/smiles/{smiles}/property/{props}/JSON  → compound properties
  - /compound/CID/{cid}/PNG                          → structure image
  - /compound/CID/{cid}/description/JSON             → pharmacology text
  - /compound/CID/{cid}/synonyms/JSON                → common names / synonyms

Docs: https://pubchemdocs.ncbi.nlm.nih.gov/pug-rest
"""

from __future__ import annotations

import re
import urllib.parse
import asyncio

import httpx
from rag.config import require_network_allowed

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUG_VIEW_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"

PROPERTY_FIELDS = ",".join([
    "IUPACName",
    "MolecularFormula",
    "MolecularWeight",
    "CanonicalSMILES",
    "InChI",
    "InChIKey",
    "XLogP",
])

# Patterns that identify non-human-readable identifiers we want to skip
_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
_INCHI_RE = re.compile(r"^InChI=")
_NUMERIC_RE = re.compile(r"^\d+$")


def _is_readable_name(name: str) -> bool:
    """Return True if a synonym looks like a human-readable name (not a CAS, InChI, etc.)."""
    if _CAS_RE.match(name):
        return False
    if _INCHI_RE.match(name):
        return False
    if _NUMERIC_RE.match(name):
        return False
    if len(name) > 80:  # excessively long strings are usually database codes
        return False
    return True


async def get_compound_by_smiles(smiles: str) -> dict | None:
    require_network_allowed("PubChem compound lookup")
    """
    Resolve a SMILES string to PubChem compound properties.
    Returns a dict with CID, IUPACName, MolecularFormula, etc., or None if not found.
    """
    encoded = urllib.parse.quote(smiles, safe="")
    url = f"{BASE_URL}/compound/smiles/{encoded}/property/{PROPERTY_FIELDS}/JSON"

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            props = data.get("PropertyTable", {}).get("Properties", [])
            return props[0] if props else None
        except Exception:
            return None


async def get_synonyms(cid: int, max_synonyms: int = 10) -> list[str]:
    require_network_allowed("PubChem synonym lookup")
    """
    Fetch human-readable synonyms for a PubChem CID.

    Returns a filtered list of common names (e.g. ["aspirin",
    "acetylsalicylic acid", ...]), excluding CAS numbers, InChI strings,
    and other non-human-readable identifiers.
    """
    url = f"{BASE_URL}/compound/CID/{cid}/synonyms/JSON"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            all_synonyms: list[str] = (
                data.get("InformationList", {})
                    .get("Information", [{}])[0]
                    .get("Synonym", [])
            )
        except Exception:
            return []

    readable = [s for s in all_synonyms if _is_readable_name(s)]
    return readable[:max_synonyms]


async def get_structure_image_url(cid: int) -> str:
    """Return the PNG structure image URL for a PubChem CID."""
    return f"{BASE_URL}/compound/CID/{cid}/PNG"


async def get_pharmacology_text(cid: int) -> str | None:
    require_network_allowed("PubChem pharmacology lookup")
    """
    Fetch the pharmacology / description text for a compound.
    Used in Phase 2 for knowledge base ingestion.
    """
    url = f"{BASE_URL}/compound/CID/{cid}/description/JSON"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            descriptions = data.get("InformationList", {}).get("Information", [])
            texts = [
                info["Description"]
                for info in descriptions
                if "Description" in info and info.get("DescriptionSourceName") != "Wikipedia"
            ]
            return "\n\n".join(texts) if texts else None
        except Exception:
            return None


_PUG_VIEW_HEADINGS = (
    "Pharmacology and Biochemistry",
    "Drug and Medication Information",
    "Safety and Hazards",
    "Toxicity",
    "Experimental Properties",
    "Biological Test Results",
)

_PUG_VIEW_FIELD_MAP = {
    "pharmacodynamics": "pharmacodynamics",
    "mechanism of action": "mechanism_of_action",
    "absorption, distribution and excretion": "adme",
    "protein binding": "adme",
    "metabolism/metabolites": "adme",
    "biological half-life": "adme",
    "drug indication": "indications",
    "drug classes": "therapeutic_classes",
    "clinical trials": "clinical_trials",
    "clinical studies": "clinical_trials",
    "drug-drug interactions": "interactions",
    "drug-food interactions": "interactions",
    "drug warnings": "adverse_effects",
    "adverse effects": "adverse_effects",
    "drug induced liver injury": "adverse_effects",
    "ghs classification": "hazard_classifications",
    "carcinogen classification": "genetic_toxicology",
    "toxicity summary": "toxicology",
    "hepatotoxicity": "toxicology",
    "acute effects": "acute_toxicity",
    "human toxicity excerpts": "toxicology",
    "non-human toxicity excerpts": "toxicology",
    "effects during pregnancy and lactation": "toxicology",
    "exposure routes": "toxicology",
    "signs and symptoms": "toxicology",
    "first approval": "history",
    "drug development summary": "history",
    "drug targets": "pharmacology",
    "bioassay results": "pharmacology",
}


def _pug_view_value_strings(value) -> list[str]:
    """Extract readable values from PUG View's nested annotation format."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [text for item in value for text in _pug_view_value_strings(item)]
    if not isinstance(value, dict):
        return []

    strings: list[str] = []
    for key in ("String", "StringValue", "Number", "NumberValue", "Integer", "Float", "Boolean"):
        if key in value:
            strings.extend(_pug_view_value_strings(value[key]))
    if strings:
        return strings
    return [text for item in value.values() for text in _pug_view_value_strings(item)]


def _flatten_pug_view_sections(sections: list[dict], cid: int, url: str) -> list[dict]:
    chunks: list[dict] = []

    def visit(items: list[dict], parents: list[str]):
        for section in items:
            heading = str(section.get("TOCHeading") or "")
            path = [*parents, heading] if heading else parents
            field = _PUG_VIEW_FIELD_MAP.get(heading.lower())
            for info in section.get("Information", []):
                value_parts = _pug_view_value_strings(info.get("Value"))
                if not value_parts:
                    continue
                details = [f"PubChem annotation section: {' > '.join(path)}"]
                description = info.get("Description")
                if description:
                    details.append(str(description))
                references = info.get("Reference") or []
                if isinstance(references, str):
                    references = [references]
                details.extend(f"Source reference: {ref}" for ref in references[:3])
                details.extend(value_parts)
                chunks.append({"field": field or "pharmacology", "text": "\n".join(details), "url": url})
            visit(section.get("Section", []), path)

    visit(sections, [])
    return chunks


async def get_pug_view_evidence(cid: int) -> list[dict]:
    """Fetch targeted PubChem annotations that complement labels and literature."""
    require_network_allowed("PubChem PUG View annotation lookup")

    async def fetch(client: httpx.AsyncClient, heading: str):
        try:
            response = await client.get(
                f"{PUG_VIEW_URL}/{cid}/JSON",
                params={"heading": heading},
            )
            if response.status_code != 200:
                return []
            sections = response.json().get("Record", {}).get("Section", [])
            url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}#section={urllib.parse.quote_plus(heading)}"
            return _flatten_pug_view_sections(sections, cid, url)
        except Exception:
            return []

    # PubChem asks clients to keep traffic below five requests per second.
    async with httpx.AsyncClient(timeout=40, limits=httpx.Limits(max_connections=4)) as client:
        results = await asyncio.gather(*(fetch(client, heading) for heading in _PUG_VIEW_HEADINGS))
    evidence = []
    for group in results:
        for item in group:
            evidence.append({
                **item,
                "source": f"PubChem PUG View CID {cid}",
                "document_id": f"pubchem-pugview-{cid}",
            })
    return evidence


async def get_compound_by_name(name: str) -> dict | None:
    require_network_allowed("PubChem name lookup")
    """
    Resolve a compound name to PubChem compound properties.
    Returns a dict with CID, IUPACName, MolecularFormula, etc., or None if not found.
    """
    encoded = urllib.parse.quote(name, safe="")
    url = f"{BASE_URL}/compound/name/{encoded}/property/{PROPERTY_FIELDS}/JSON"

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            props = data.get("PropertyTable", {}).get("Properties", [])
            return props[0] if props else None
        except Exception:
            return None


async def get_rxnorm_name_correction(name: str) -> str | None:
    """Return an unambiguous, high-confidence RxNorm correction for a drug name typo."""
    require_network_allowed("RxNorm approximate drug-name lookup")
    if not name.strip() or len(name.strip()) < 4:
        return None

    url = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params={"term": name.strip(), "maxEntries": 10})
            if response.status_code != 200:
                return None
            candidates = response.json().get("approximateGroup", {}).get("candidate", [])
    except Exception:
        return None

    # RxNorm returns multiple synonym rows for one concept. Accept only a single
    # top-ranked concept and require a strong score; PubChem is then used to
    # independently confirm the corrected name before its identity is trusted.
    top = [candidate for candidate in candidates if candidate.get("rank") == "1"]
    concepts = {candidate.get("rxcui") for candidate in top if candidate.get("rxcui")}
    if len(concepts) != 1:
        return None
    try:
        if max(float(candidate.get("score", 0)) for candidate in top) < 7.0:
            return None
    except (TypeError, ValueError):
        return None

    named_candidates = [candidate for candidate in top if candidate.get("name")]
    preferred = next(
        (candidate for candidate in named_candidates if candidate.get("source") == "RXNORM"),
        named_candidates[0] if named_candidates else None,
    )
    return str(preferred["name"]).strip() if preferred else None


async def resolve_biologic_or_non_pubchem_drug(query: str) -> dict | None:
    """
    Resolve brand names and biologics (e.g. Humira -> adalimumab) via RxNorm and DailyMed
    when PubChem small-molecule lookup returns 404 Not Found.
    """
    require_network_allowed("RxNorm/DailyMed biologic entity lookup")
    clean_query = query.strip()
    if not clean_query or len(clean_query) < 3:
        return None

    # 1. Query RxNorm approximateTerm to find RxCUI and concept name
    rx_url = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
    candidates = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(rx_url, params={"term": clean_query, "maxEntries": 10})
            if resp.status_code == 200:
                candidates = resp.json().get("approximateGroup", {}).get("candidate", [])
    except Exception as e:
        pass

    generic_name = None
    brand_name = None
    top_cui = None

    if candidates:
        top_cui = candidates[0].get("rxcui")
        cand_name = (candidates[0].get("name") or clean_query).strip()

        # Check if candidate has active ingredient (tty=IN)
        if top_cui:
            try:
                in_url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{top_cui}/related.json"
                async with httpx.AsyncClient(timeout=10) as client:
                    resp_in = await client.get(in_url, params={"tty": "IN"})
                    if resp_in.status_code == 200:
                        groups = resp_in.json().get("relatedGroup", {}).get("conceptGroup", [])
                        for g in groups:
                            if g.get("tty") == "IN":
                                props_in = g.get("conceptProperties", [])
                                if props_in and props_in[0].get("name"):
                                    generic_name = props_in[0]["name"].strip()
                                    if cand_name.lower() != generic_name.lower():
                                        brand_name = cand_name
                                    break
            except Exception:
                pass

        if not generic_name:
            generic_name = cand_name

    # 2. Fallback check DailyMed if RxNorm didn't resolve generic
    if not generic_name:
        try:
            from ingest.dailymed import search_drug_labels
            labels = await search_drug_labels(clean_query, pagesize=3)
            if labels:
                generic_name = clean_query
                brand_name = labels[0].get("title", "").split()[0]
        except Exception:
            pass

    if not generic_name:
        return None

    # 3. Determine biologic classification
    lower_gen = generic_name.lower()
    biologic_class = "Biologic / Macromolecular Drug"
    if lower_gen.endswith("mab"):
        biologic_class = "Monoclonal Antibody (mAb)"
    elif lower_gen.endswith("cept"):
        biologic_class = "Receptor Fusion Protein"
    elif lower_gen.endswith("tide"):
        biologic_class = "Peptide / Receptor Agonist"
    elif "insulin" in lower_gen:
        biologic_class = "Insulin Analog / Hormone"
    elif lower_gen.endswith("ase"):
        biologic_class = "Recombinant Enzyme"
    elif "vaccine" in lower_gen:
        biologic_class = "Vaccine / Immunobiological"

    # Known target mapping for major biologics
    target = None
    if any(k in lower_gen for k in ["adalimumab", "infliximab", "etanercept", "golimumab", "certolizumab"]):
        target = "Tumor Necrosis Factor alpha (TNF-alpha)"
    elif any(k in lower_gen for k in ["pembrolizumab", "nivolumab", "cemiplimab"]):
        target = "Programmed Cell Death Protein 1 (PD-1)"
    elif any(k in lower_gen for k in ["trastuzumab", "pertuzumab"]):
        target = "Human Epidermal Growth Factor Receptor 2 (HER2)"
    elif "rituximab" in lower_gen:
        target = "CD20 B-lymphocyte antigen"
    elif any(k in lower_gen for k in ["semaglutide", "liraglutide", "tirzepatide", "dulaglutide"]):
        target = "Glucagon-Like Peptide-1 Receptor (GLP-1R)"
    elif "dupixent" in lower_gen or "dupilumab" in lower_gen:
        target = "Interleukin-4 Receptor alpha (IL-4R-alpha)"
    elif "ustekinumab" in lower_gen:
        target = "Interleukin-12 and Interleukin-23 (IL-12 / IL-23)"

    synonyms = list(dict.fromkeys(filter(None, [generic_name, brand_name, clean_query])))

    sources = []
    if top_cui:
        sources.append({
            "source": f"RxNorm Concept {top_cui}",
            "url": f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={top_cui}",
        })
    sources.append({
        "source": "DailyMed FDA Library",
        "url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={urllib.parse.quote(generic_name)}",
    })

    return {
        "smiles": None,
        "drug_type": "biologic",
        "biologic_class": biologic_class,
        "target": target,
        "inchi": None,
        "inchi_key": None,
        "iupac_name": None,
        "common_name": generic_name,
        "brand_names": [brand_name] if brand_name else [],
        "synonyms": synonyms,
        "molecular_formula": None,
        "molecular_weight": None,
        "pubchem_cid": None,
        "image_url": None,
        "sources": sources,
    }


async def get_compound_by_cid(cid: int) -> dict | None:
    require_network_allowed("PubChem CID lookup")
    """
    Resolve a PubChem CID to compound properties.
    Returns a dict with CID, IUPACName, MolecularFormula, etc., or None if not found.
    """
    url = f"{BASE_URL}/compound/cid/{cid}/property/{PROPERTY_FIELDS}/JSON"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            props = data.get("PropertyTable", {}).get("Properties", [])
            return props[0] if props else None
        except Exception:
            return None


async def enrich_structure(query: str) -> dict:
    """
    Main helper: given a SMILES, drug name, or PubChem CID, return a dict suitable for ChemicalStructure.

    Tries resolving by:
      1. CID (if query is purely numeric)
      2. SMILES
      3. Drug Name (as a fallback)
      4. RxNorm / DailyMed for biologics and brand names (when PubChem returns 404)
    """
    query = query.strip()
    props = None

    # 1. Check if numeric CID
    if query.isdigit():
        props = await get_compound_by_cid(int(query))

    # 2. Try SMILES lookup
    if not props:
        props = await get_compound_by_smiles(query)

    # 3. Try Name lookup
    if not props:
        props = await get_compound_by_name(query)

    # Drug-name typos otherwise pass through as if they were resolved compounds
    if not props:
        corrected_name = await get_rxnorm_name_correction(query)
        if corrected_name:
            props = await get_compound_by_name(corrected_name)

    if not props:
        # Fallback to multi-tier RxNorm + DailyMed resolver for biologics and non-PubChem compounds
        biologic_entity = await resolve_biologic_or_non_pubchem_drug(query)
        if biologic_entity:
            return biologic_entity

        return {
            "smiles": query,
            "drug_type": "unknown",
            "pubchem_cid": None,
            "iupac_name": None,
            "common_name": query.capitalize(),
            "synonyms": [query],
            "image_url": None,
            "sources": [],
        }

    cid = props.get("CID")
    iupac = props.get("IUPACName")

    # Fetch synonyms to get the common/trade name
    synonyms = await get_synonyms(cid) if cid else []

    # The common name is the first synonym that differs from the IUPAC name
    iupac_lower = (iupac or "").lower()
    common_name: str | None = next(
        (s for s in synonyms if s.lower() != iupac_lower),
        None,
    )

    # Check if name lookup for common_name gives a canonical parent compound CID
    if common_name:
        clean_name = re.sub(r"^\[.*?\]-?", "", common_name).strip()
        parent_props = await get_compound_by_name(clean_name)
        if parent_props and parent_props.get("CID"):
            parent_cid = parent_props["CID"]
            # If parent CID is different (e.g. 4091 vs 152743144), adopt the parent CID & props
            if parent_cid != cid:
                props = parent_props
                cid = parent_cid
                common_name = clean_name
                iupac = props.get("IUPACName") or iupac
                parent_syns = await get_synonyms(cid)
                if parent_syns:
                    synonyms = parent_syns

    return {
        "smiles": props.get("CanonicalSMILES") or props.get("ConnectivitySMILES") or query,
        "inchi": props.get("InChI"),
        "inchi_key": props.get("InChIKey"),
        "iupac_name": iupac,
        "common_name": common_name,
        "synonyms": synonyms,
        "molecular_formula": props.get("MolecularFormula"),
        "molecular_weight": float(props["MolecularWeight"]) if props.get("MolecularWeight") else None,
        "logp": float(props["XLogP"]) if props.get("XLogP") is not None else None,
        "pubchem_cid": cid,
        "image_url": await get_structure_image_url(cid) if cid else None,
        "sources": [
            {
                "source": f"PubChem CID {cid}",
                "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
            }
        ] if cid else [],
    }
