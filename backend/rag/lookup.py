"""A bounded compound overview; full monograph generation is not a prerequisite for a lookup."""
import asyncio
import difflib
import hashlib
import re

from starlette.concurrency import run_in_threadpool

from ingest.local_chem import COMMON_DRUGS_DB
from ingest.pubmed import mentions_identity
from rag.citation_resolver import resolve_citations
from rag.config import sources_enabled
from rag.context_builder import build_context
from rag.pipeline import build_fallback_drug_info, resolve_query_structure, has_verified_identity
from rag.retriever import get_retriever
from rag.schema import DrugInfo, FieldValue, SourceReferenceItem


def identity_suggestions(query: str) -> list[dict]:
    names = [name for name in COMMON_DRUGS_DB if re.fullmatch(r"[a-z][a-z -]{2,}", name)]
    suggestions = {}
    for match in difflib.get_close_matches(query.casefold(), names, n=3, cutoff=.8):
        canonical = COMMON_DRUGS_DB[match]["common_name"]
        suggestions[canonical] = {"query": canonical, "label": f"{canonical} ({match})" if match != canonical.casefold() else canonical}
    return list(suggestions.values())


async def fetch_overview_evidence(structure: dict) -> list[dict]:
    from ingest.dailymed import search_drug_labels, get_label_sections
    from ingest.pubmed import search_pubmed, fetch_abstracts
    name = structure["common_name"]
    cid = str(structure.get("pubchem_cid") or "")
    aliases = list(dict.fromkeys([name, *structure.get("brand_names", []), *structure.get("synonyms", [])]))[:8]

    async def labels():
        records = await search_drug_labels(name, pagesize=3)
        label = next((record for record in records if mentions_identity(record.get("title", ""), aliases)), None)
        if label is None:
            return []
        sections = await get_label_sections(label["setid"])
        priority = ["indications", "mechanism_of_action", "boxed_warning", "contraindications", "adverse_effects", "drug_interactions", "warnings"]
        selected = [(field, sections[field]) for field in priority if sections.get(field)]
        pk = sections.get("pharmacokinetics") or sections.get("clinical_pharmacology", "")
        for field, pattern in [("absorption", r"absorp|bioavailability|peak plasma"), ("metabolism", r"metaboli|CYP3A"), ("half_life", r"half.life")]:
            sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", pk)
            matching = [sentence for sentence in sentences if re.search(pattern, sentence, re.I)]
            if matching:
                selected.append((field, " ".join(matching)[:1100]))
        return [{"text": text[:1100], "source": f"DailyMed: {label['title']} ({field})", "url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={label['setid']}", "field": field, "document_id": label["setid"], "drug": name.casefold(), "pubchem_cid": cid, "identity_verified": True} for field, text in selected]

    async def papers():
        pmids = await search_pubmed(f'"{name}"[Title/Abstract] AND (pharmacology OR pharmacokinetics OR review)', max_results=4)
        articles = await fetch_abstracts(pmids)
        return [{"text": f"{article['title']}\n{article['abstract']}"[:1100], "source": f"PubMed PMID {article['pmid']}", "url": f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/", "field": "research_review", "pmid": article["pmid"], "drug": name.casefold(), "pubchem_cid": cid, "identity_verified": True} for article in articles if mentions_identity(f"{article['title']} {article['abstract']}", aliases)]

    tasks = [asyncio.create_task(labels()), asyncio.create_task(papers())]
    try:
        done, _ = await asyncio.wait(tasks, timeout=15)
        return [chunk for task in tasks if task in done and not task.cancelled() and task.exception() is None for chunk in task.result()]
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def cache_evidence(retriever, chunks: list[dict]):
    from rag.embeddings import embed_batch_local
    ids = ["overview_" + hashlib.sha256(f"{chunk['pubchem_cid']}:{chunk['url']}:{chunk['field']}:{chunk['text']}".encode()).hexdigest() for chunk in chunks]
    metadatas = [{key: value for key, value in chunk.items() if key != "text" and isinstance(value, (str, int, float, bool))} for chunk in chunks]
    retriever.collection.upsert(ids=ids, documents=[chunk["text"] for chunk in chunks], embeddings=embed_batch_local([chunk["text"] for chunk in chunks]), metadatas=metadatas)


def build_overview(query: str, structure: dict, source_map: dict) -> DrugInfo:
    data = build_fallback_drug_info(query, structure, structure["common_name"]).model_dump()

    def unevaluated(node):
        if isinstance(node, dict):
            if "content" in node and node.get("missing"):
                node.update(content="Not evaluated in this overview. Ask a focused follow-up question.", missing=True, status_label="Not evaluated", sources=[])
            for child in node.values():
                unevaluated(child)
        elif isinstance(node, list):
            for child in node:
                unevaluated(child)
    unevaluated(data)
    profile = DrugInfo(**data)
    profile.drug_overview.identity.generic_name = FieldValue(content=structure["common_name"], missing=False, status_label="Reported", sources=structure.get("sources", []))
    profile.drug_name.generic = structure["common_name"]
    profile.drug_name.brand_names = structure.get("brand_names", [])
    profile.query_smiles = structure.get("smiles") or query
    profile.drug_overview.identity.brand_names = [item for item in profile.drug_overview.identity.brand_names if item.brand_name.casefold() != structure["common_name"].casefold()]
    profile.data_confidence = "UNASSESSED (Brief source-based overview)"
    for jurisdiction in (profile.therapeutic_profile.regulatory_status.united_states, profile.therapeutic_profile.regulatory_status.indonesia):
        jurisdiction.status = "Not evaluated"
        jurisdiction.details = "Regulatory approval was not checked in this overview."
    profile.therapeutic_profile.pharmacogenomics.statement = "Not evaluated in this overview."
    profile.therapeutic_profile.pharmacogenomics.missing = True

    def excerpt(*fields):
        for sid, chunk in source_map.items():
            if chunk.get("field") in fields and chunk.get("source", "").startswith("DailyMed:"):
                return FieldValue(content=chunk["text"], missing=False, status_label="Source excerpt", sources=resolve_citations([sid], source_map))
        return FieldValue(content="No matching label passage was retrieved. Ask a focused question to search the available papers.", missing=True, status_label="No evidence retrieved")

    profile.pharmacodynamics.mechanism_of_action = profile.pharmacodynamics.mechanism_of_action.model_copy(update=excerpt("mechanism_of_action").model_dump())
    profile.pharmacodynamics.mechanism_of_action.evidence_classification = "Not evaluated" if profile.pharmacodynamics.mechanism_of_action.missing else "Source excerpt"
    profile.pharmacodynamics.mechanism_of_action.primary_vs_secondary = None
    profile.therapeutic_profile.indications.summary = excerpt("indications")
    profile.pharmacokinetics.absorption.bioavailability = excerpt("absorption")
    profile.pharmacokinetics.metabolism.metabolic_pathways = excerpt("metabolism")
    profile.pharmacokinetics.elimination_and_clearance.elimination_half_life = excerpt("half_life")
    profile.toxicology_and_safety.clinical_safety.boxed_warning = excerpt("boxed_warning")
    profile.toxicology_and_safety.clinical_safety.adverse_effects_summary = excerpt("adverse_effects")
    profile.toxicology_and_safety.clinical_safety.contraindications = excerpt("contraindications")
    profile.therapeutic_profile.interaction_summary = excerpt("drug_interactions")
    profile.references.sources = [SourceReferenceItem(source_name=chunk["source"], category="Retrieved source", url=chunk.get("url")) for chunk in source_map.values()]
    profile.references.limitations_and_confidence.limitations = FieldValue(content="Direct excerpts from matched drug labels, not an AI-generated monograph. Passages may be shortened and are not a complete safety review. Advanced assays, dosing, populations and regulatory approval were not evaluated. Ask focused follow-up questions for more detail.", missing=False, status_label="Reported")
    profile.references.limitations_and_confidence.data_confidence_rating = profile.data_confidence
    return DrugInfo(**profile.model_dump(exclude={"adme", "toxicology", "therapeutic_classes"}))


async def lookup_stream(query: str):
    from rag.safety import looks_like_clinical_advice
    if looks_like_clinical_advice(query):
        yield {"type": "clarification", "message": "Compound lookup provides research references. Patient-specific treatment and dosing questions require a clinician.", "suggestions": []}
        return
    yield {"type": "status", "stage": "identity", "message": "Verifying the compound name..."}
    try:
        structure = await asyncio.wait_for(resolve_query_structure(query), timeout=12)
    except TimeoutError:
        structure = {}
    if not has_verified_identity(structure):
        suggestions = identity_suggestions(query)
        message = f"I couldn't verify '{query}' as a single compound."
        if suggestions:
            message += " Did you mean one of these? Confirm the compound before I search its medical evidence."
        else:
            message += " Enter the active ingredient, exact brand with country, a PubChem CID, or valid SMILES. No model generation was started."
        yield {"type": "clarification", "message": message, "suggestions": suggestions}
        return
    name = structure["common_name"]
    yield {"type": "status", "stage": "retrieving", "message": f"Finding evidence for {name}..."}
    retriever = await run_in_threadpool(get_retriever)
    cid = str(structure.get("pubchem_cid") or "")
    try:
        chunks = await retriever.retrieve(f"{name} mechanism uses pharmacokinetics safety", n_results=12, pubchem_cid=cid or None, drug_name=name, include_custom_pdf=True)
    except RuntimeError:
        if not sources_enabled():
            yield {"type": "clarification", "message": "Local retrieval is not ready. Prepare the document models in Model & connection before searching offline.", "suggestions": []}
            return
        chunks = []
    if sources_enabled():
        fresh = await fetch_overview_evidence(structure)
        chunks = (fresh + chunks)[:12]
        if fresh:
            try:
                await run_in_threadpool(cache_evidence, retriever, fresh)
            except Exception:
                yield {"type": "status", "stage": "cache_unavailable", "message": "Online evidence is available. Continuing without saving an offline copy."}
    if not chunks:
        yield {"type": "clarification", "message": f"{name} was identified, but no supporting source passages are available. Add a paper for this compound or enable online sources.", "suggestions": []}
        return
    _, source_map = build_context(chunks[:12])
    yield {"type": "result", "data": build_overview(query, structure, source_map).model_dump()}
