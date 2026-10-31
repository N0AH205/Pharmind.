"""
Knowledge base ingestion script — Phase 2.

Populates ChromaDB with pharmaceutical text from PubChem, DailyMed, and PubMed
for a benchmark set of drugs.

Embeddings are generated locally with FastEmbed; downloading source literature
from PubChem, DailyMed, and PubMed requires network access.

Run once (from the backend/ directory):
    python -m ingest.run_ingest

Re-running is safe: existing entries are overwritten (upsert by ID).

Metadata stored per chunk:
    drug        : common drug name (e.g. "Aspirin")
    pubchem_cid : str(CID) — used for metadata filtering in retriever
    field       : section type (e.g. "indications", "pharmacology", "research")
    source      : human-readable source label
    url         : source URL
"""

from __future__ import annotations

import asyncio
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chromadb
import httpx
from rag.config import OFFLINE_MODE

from ingest.pubchem import get_compound_by_cid, get_compound_by_smiles, get_pharmacology_text, get_pug_view_evidence, get_synonyms
from ingest.chembl import fetch_chembl_profile, get_chembl_activity_evidence
from ingest.dailymed import search_drug_labels, get_label_sections
from ingest.pubmed import search_pubmed, fetch_abstracts, mentions_identity
from ingest.clinicaltrials import search_drug_trials

CHROMA_PATH = os.getenv("CHROMA_PATH", "../data/chroma")
COLLECTION_NAME = "pharma_docs"

# Benchmark drug set — expand for Phase 4 evaluation
# cid field is an optional override: use it when SMILES-based PubChem lookup
# returns a wrong or ambiguous compound (e.g. isotope-labelled forms).
BENCHMARK_DRUGS: list[dict] = [
    {"name": "Aspirin",      "smiles": "CC(=O)Oc1ccccc1C(=O)O", "dailymed_query": "Durlaza"},
    {"name": "Ibuprofen",    "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"},
    # Metformin: SMILES-based lookup keeps resolving to the [14C] isotope;
    # hardcode CID 4091 (canonical Metformin entry on PubChem) as override.
    {"name": "Metformin",    "smiles": "CN(C)C(=N)NC(N)=N", "cid": 4091},
    {"name": "Atorvastatin", "smiles": "CC(C)c1c(C(=O)Nc2ccccc2F)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC(O)CC(O)CC(=O)O"},
    # Caffeine: override DailyMed query to avoid the neonatal IV caffeine citrate label
    # which lacks the general pharmacology info (adenosine antagonism, CNS effects).
    {"name": "Caffeine",     "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C", "dailymed_query": "caffeine ergotamine"},
]


from rag.embeddings import embed_text_local


def _chunk_text(text: str, max_chars: int = 1800, overlap: int = 200) -> list[str]:
    """Split long source sections into overlapping, searchable passages."""
    text = " ".join(text.split())
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start + max_chars // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [chunk for chunk in chunks if chunk]


def embed_text(text: str) -> list[float]:
    """
    Embed text locally using FastEmbed (BAAI/bge-small-en-v1.5).
    100% offline.
    """
    return embed_text_local(text)



# -- PubChem CID resolution ----------------------------------------------------

async def resolve_cid(
    name: str,
    smiles: str,
    cid_override: int | None = None,
) -> tuple[int | None, str]:
    """
    Resolve a drug to its PubChem CID.

    If cid_override is provided it takes priority (use for drugs where
    SMILES-based lookup returns an ambiguous or wrong compound).

    Returns (cid, canonical_name).
    """
    if cid_override:
        syns = await get_synonyms(cid_override, max_synonyms=5)
        common = syns[0] if syns else name
        return cid_override, common

    props = await get_compound_by_smiles(smiles)
    if props:
        cid = props.get("CID")
        if cid:
            syns = await get_synonyms(cid, max_synonyms=5)
            common = syns[0] if syns else name
            return cid, common
    # SMILES lookup failed
    return None, name


# -- Per-drug ingestion --------------------------------------------------------

async def ingest_drug(drug: dict, collection, pubmed_limit: int | None = None) -> int:
    """
    Fetch data for one drug from PubChem, DailyMed, and PubMed,
    embed each chunk, and upsert into ChromaDB.

    Each chunk's metadata includes:
        - drug        : canonical drug name
        - pubchem_cid : str(CID) for metadata-filtered retrieval
        - field       : content category
        - source      : source label
        - url         : source URL

    Returns the number of chunks stored.
    """
    name: str = drug["name"]
    smiles: str = drug["smiles"]
    cid_override: int | None = drug.get("cid")
    print(f"\n-- Ingesting {name} --")
    chunks: list[dict] = []

    # 0. Resolve CID (used as stable drug identifier in metadata)
    cid, canonical_name = await resolve_cid(name, smiles, cid_override=cid_override)
    cid_str = str(cid) if cid else ""
    if cid_override and cid:
        print(f"  PubChem CID : {cid} (hardcoded override)")
    else:
        print(f"  PubChem CID : {cid or '(not resolved)'}")
    print(f"  Canonical   : {canonical_name}")

    # 1. PubChem — pharmacology description text
    if cid:
        structure_props = await get_compound_by_cid(cid)
        inchi_key = drug.get("inchi_key") or (structure_props or {}).get("InChIKey")
        pharm_text = await get_pharmacology_text(cid)
        if pharm_text:
            chunks.append({
                "text": pharm_text,
                "source": f"PubChem CID {cid}",
                "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                "drug": canonical_name,
                "pubchem_cid": cid_str,
                "field": "pharmacology",
            })
            print(f"  PubChem pharmacology: {len(pharm_text):,} chars")
        else:
            print(f"  PubChem: no pharmacology text for CID {cid}")

        # PUG View adds annotated pharmacology, pharmacokinetics, indications,
        # interaction, toxicity, and hazard evidence missing from the basic
        # compound description endpoint.
        for annotation in await get_pug_view_evidence(cid):
            for passage in _chunk_text(annotation["text"]):
                chunks.append({
                    **annotation,
                    "text": passage,
                    "drug": canonical_name,
                    "pubchem_cid": cid_str,
                })

        # ChEMBL is queried by exact InChIKey to avoid mixing a salt, isomer,
        # or similarly named molecule into quantitative assay results.
        for activity in await get_chembl_activity_evidence(inchi_key):
            chunks.append({
                **activity,
                "drug": canonical_name,
                "pubchem_cid": cid_str,
            })
    else:
        print(f"  PubChem: CID not resolved for '{name}'")

    # 2. DailyMed — FDA label sections (XML parsing)
    # Build search candidates: override_query (if exists), original name, canonical name, and top synonyms
    override_query = drug.get("dailymed_query")
    search_candidates = [override_query] if override_query else [name]

    if name not in search_candidates:
        search_candidates.append(name)
    if canonical_name and canonical_name.lower() not in [c.lower() for c in search_candidates]:
        search_candidates.append(canonical_name)
    if cid:
        syns = await get_synonyms(cid, max_synonyms=15)
        for s in syns:
            if s.lower() not in [c.lower() for c in search_candidates]:
                search_candidates.append(s)

    # Search DailyMed concurrently for all search candidates
    search_tasks = [search_drug_labels(cand, pagesize=10) for cand in search_candidates]
    search_results = await asyncio.gather(*search_tasks)

    # Flatten search results and deduplicate by setid
    seen_setids = set()
    unique_labels = []
    for labels_list in search_results:
        for l in labels_list:
            sid = l.get("setid")
            if sid and sid not in seen_setids:
                seen_setids.add(sid)
                unique_labels.append(l)

    # Keep multiple distinct labels: dosage forms and manufacturers can carry
    # materially different indications, warnings, and pharmacokinetic details.
    unique_labels = unique_labels[:20]

    if unique_labels:
        # Fetch sections for all unique labels concurrently
        tasks = [get_label_sections(l.get("setid")) for l in unique_labels if l.get("setid")]
        all_sections = await asyncio.gather(*tasks)

        ranked_labels = sorted(
            zip(unique_labels, all_sections), key=lambda pair: len(pair[1]), reverse=True
        )
        selected = [(label, sections) for label, sections in ranked_labels if sections][:3]
        print(f"  DailyMed: analyzed {len(unique_labels)} labels from {len(search_candidates)} search terms; retaining {len(selected)} useful labels")

        for selected_label, sections in selected:
            set_id = selected_label.get("setid")
            title = selected_label.get("title", "Unknown label")
            print(f"    Retained: '{title[:60]}' (setid: {set_id}, sections: {len(sections)})")
            for field_key, text in sections.items():
                if text:
                    for passage in _chunk_text(text):
                        chunks.append({
                            "text": passage,
                            "source": f"DailyMed SPL – {canonical_name}: {title}",
                            "url": f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={set_id}",
                            "drug": canonical_name,
                            "pubchem_cid": cid_str,
                            "field": field_key,
                            "document_id": str(set_id or ""),
                        })
    else:
        print(f"  DailyMed: no labels found for '{name}' (searched synonyms: {search_candidates})")

    # 3. PubMed — field-specific research abstracts
    # Fetch targeted queries for each schema section to maximise keyword coverage
    pubmed_queries = [
        (f"{name} mechanism of action pharmacology receptor target", "moa", 18),
        (f"{name} pharmacokinetics ADME absorption distribution metabolism excretion", "adme", 18),
        (f"{name} adverse effects safety side effects toxicity postmarketing", "adverse_effects", 18),
        (f"{name} clinical indications therapeutic use treatment efficacy", "indications", 18),
        (f"{name} toxicology carcinogenicity genotoxicity reproductive toxicity", "toxicology", 15),
        (f"{name} drug interactions contraindications CYP", "interactions", 15),
        (f"{name} history discovery development approval review", "history", 15),
        (f"{name} randomized controlled trial clinical outcomes", "clinical_trials", 18),
        (f"{name} systematic review meta-analysis", "research_review", 15),
        (f"{name} renal impairment hepatic impairment dose adjustment", "adme", 12),
    ]

    pm_count = 0
    seen_pmids: set[str] = set()
    for query_str, field_label, max_res in pubmed_queries:
        result_limit = min(max_res, pubmed_limit) if pubmed_limit else max_res
        pmids = await search_pubmed(query_str, max_results=result_limit)
        abstracts = await fetch_abstracts(pmids)
        for ab in abstracts:
            if ab["abstract"] and ab["pmid"] not in seen_pmids and mentions_identity(f"{ab['title']} {ab['abstract']}", [name, canonical_name]):
                seen_pmids.add(ab["pmid"])
                chunks.append({
                    "text": f"{ab['title']}\n\n{ab['abstract']}",
                    "source": f"PubMed PMID {ab['pmid']}",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{ab['pmid']}/",
                    "drug": canonical_name,
                    "pubchem_cid": cid_str,
                    "field": field_label,
                    "authors": "; ".join(ab.get("authors", [])),
                    "publication_date": ab.get("publication_date", ""),
                    "journal": ab.get("journal", ""),
                    "doi": ab.get("doi", ""),
                    "pmid": ab.get("pmid", ""),
                })
                pm_count += 1
    print(f"  PubMed: {pm_count} abstract(s) across {len(pubmed_queries)} field queries")

    # 4. ClinicalTrials.gov — registered study summaries and posted results.
    # Limit the count to keep first-run ingestion manageable; source records remain linked.
    trial_limit = 2 if pubmed_limit else 15
    trials = await search_drug_trials(name, limit=trial_limit)
    for trial in trials:
        for passage in _chunk_text(trial["text"]):
            chunks.append({
                "text": passage,
                "source": f"ClinicalTrials.gov {trial['nct_id']}: {trial['title']}",
                "url": trial["url"],
                "drug": canonical_name,
                "pubchem_cid": cid_str,
                "field": "clinical_trials",
                "publication_date": trial.get("publication_date", ""),
                "document_id": trial["nct_id"],
            })
    print(f"  ClinicalTrials.gov: {len(trials)} study record(s)")

    # 5. ChEMBL — structured bioactivities and mechanisms
    try:
        from ingest.chembl import fetch_chembl_profile
        chembl_prof = await fetch_chembl_profile(name, inchi_key=drug.get("inchi_key"))
        c_id = chembl_prof.get("chembl_id")
        if c_id:
            for m in chembl_prof.get("mechanisms", []):
                chunks.append({
                    "text": f"ChEMBL Curated Mechanism: {m.get('mechanism_of_action')} | Action: {m.get('action_type')} | Target: {m.get('target_name')} ({m.get('target_organism')})",
                    "source": f"ChEMBL Mechanism {c_id}",
                    "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{c_id}/",
                    "drug": canonical_name,
                    "pubchem_cid": cid_str,
                    "field": "moa",
                    "retrieval_group": "moa",
                    "document_id": str(c_id),
                })
            for a in chembl_prof.get("bioactivities", []):
                chunks.append({
                    "text": f"ChEMBL Experimental Bioassay: Target {a.get('target_name')} ({a.get('target_organism')}) — {a.get('standard_type')} {a.get('relation')} {a.get('value_nm')} nM. Assay: {a.get('assay_description') or ''}",
                    "source": f"ChEMBL Bioassay {a.get('chembl_assay_id') or c_id}",
                    "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{c_id}/",
                    "drug": canonical_name,
                    "pubchem_cid": cid_str,
                    "field": "binding_affinity",
                    "retrieval_group": "binding_affinity",
                    "document_id": str(a.get("chembl_assay_id") or c_id),
                })
            print(f"  ChEMBL: {len(chembl_prof.get('mechanisms', []))} mechanism(s), {len(chembl_prof.get('bioactivities', []))} assay(s)")
    except Exception as exc:
        print(f"  ChEMBL: ingestion skipped ({exc})")

    # 6. openFDA — direct FDA drug label sections (including ADME, contraindications, and toxicology)
    try:
        from ingest.openfda import fetch_openfda_passages
        fda_chunks = await fetch_openfda_passages(name, canonical_name=canonical_name, cid_str=cid_str)
        if fda_chunks:
            chunks.extend(fda_chunks)
            print(f"  openFDA: ingested {len(fda_chunks)} section chunk(s)")
    except Exception as exc:
        print(f"  openFDA: ingestion skipped ({exc})")

    # 7. NCBI StatPearls — peer-reviewed clinical monographs
    try:
        from ingest.statpearls import fetch_statpearls_passages
        sp_passages = await fetch_statpearls_passages(name, canonical_name=canonical_name, cid_str=cid_str)
        if sp_passages:
            chunks.extend(sp_passages)
            print(f"  StatPearls: ingested {len(sp_passages)} peer-reviewed clinical monograph passage(s)")
    except Exception as exc:
        print(f"  StatPearls: ingestion skipped ({exc})")

    if not chunks:
        print(f"  WARNING: No chunks collected for {name} — skipping")
        return 0

    # 4. Embed and upsert into ChromaDB
    ids, embeddings, documents, metadatas = [], [], [], []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{name.lower().replace(' ', '_')}-{i}"
        print(f"  Embedding {i + 1}/{len(chunks)}: {chunk['field']} …", end="\r", flush=True)

        vec = embed_text(chunk["text"])
        ids.append(chunk_id)
        embeddings.append(vec)
        documents.append(chunk["text"])
        # Metadata must only contain str/int/float/bool values for ChromaDB
        metadatas.append({
            "drug":        chunk["drug"].strip().casefold(),
            "pubchem_cid": str(chunk.get("pubchem_cid") or ""),
            "field":       chunk["field"],
            "source":      chunk["source"],
            "url":         chunk["url"],
            "authors": chunk.get("authors", ""),
            "publication_date": chunk.get("publication_date", ""),
            "journal": chunk.get("journal", ""),
            "doi": chunk.get("doi", ""),
            "pmid": chunk.get("pmid", ""),
            "document_id": chunk.get("document_id", ""),
        })

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    print(f"  Stored {len(chunks)} chunk(s)                    ")
    return len(chunks)


# -- Database inspection -------------------------------------------------------

def print_db_summary(collection):
    """Print a summary of what is stored in the collection."""
    count = collection.count()
    if count == 0:
        print("Collection is empty.")
        return

    # Fetch all metadata (no embeddings — faster)
    all_items = collection.get(include=["metadatas"])
    metadatas = all_items["metadatas"]

    # Group by drug + field
    from collections import defaultdict
    summary: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for meta in metadatas:
        drug = meta.get("drug", "unknown")
        field = meta.get("field", "unknown")
        summary[drug][field] += 1

    print("\n" + "-" * 58)
    print(f"{'Drug':<20} {'Field':<30} {'Chunks':>6}")
    print("-" * 58)
    for drug in sorted(summary):
        for field in sorted(summary[drug]):
            print(f"{drug:<20} {field:<30} {summary[drug][field]:>6}")
    print("-" * 58)
    print(f"Total chunks: {count}")


# -- Entry point ---------------------------------------------------------------

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build Pharmer's local literature index")
    parser.add_argument(
        "--quickstart",
        action="store_true",
        help="Index a small Aspirin demo corpus for a fast first run",
    )
    args = parser.parse_args()

    if OFFLINE_MODE:
        raise RuntimeError("Source ingestion needs internet access. Set PHARMER_OFFLINE=false for the initial data download.")

    print("=" * 60)
    print("PharmaRAG — Knowledge Base Ingestion (Local FastEmbed)")
    print(f"Embedding model : BAAI/bge-small-en-v1.5 (Local FastEmbed ONNX)")
    print(f"ChromaDB path   : {CHROMA_PATH}")
    print("=" * 60)

    # Quick connectivity/local test check
    try:
        test_vec = embed_text("test")
        print(f"\nLocal embedding OK — vector dimension: {len(test_vec)}")
    except Exception as e:
        print(f"\nERROR: Local embedding test failed: {e}")
        return

    db = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = db.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    drugs = BENCHMARK_DRUGS[:1] if args.quickstart else BENCHMARK_DRUGS
    total = 0
    for drug in drugs:
        total += await ingest_drug(drug, collection, pubmed_limit=2 if args.quickstart else None)

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    if args.quickstart:
        print("Quick-start index is limited to Aspirin. Run without --quickstart to index the full starter set.")
    print_db_summary(collection)
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
