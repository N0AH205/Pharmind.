"""Context-aware follow-up chat grounded in the local literature index."""

from __future__ import annotations

import re
import logging

from rag.context_builder import build_context
from rag.config import sources_enabled
from rag.llm import generate_chat_response
from rag.reranker import rerank_passages
from rag.retriever import get_retriever

logger = logging.getLogger(__name__)

CHAT_MODE_GUIDANCE = {
    "paper_learning": (
        "Mode: Paper learning. Teach from retrieved journal passages or the uploaded paper. Explain study design, "
        "methods, results, limitations, and what the authors do or do not conclude. Separate a paper's claims from "
        "established consensus, and say when only an abstract was available."
    ),
    "structure_science": (
        "Mode: Structure and scientific evidence. Focus on the compound's identity, molecular structure, measured "
        "properties, pharmacology, and sourced experimental or clinical evidence. Preserve assay conditions and "
        "distinguish measured values from predictions."
    ),
    "molecule_theory": (
        "Mode: Molecule theory. Explain mechanisms, structure–activity relationships, molecular interactions, and "
        "biochemical hypotheses at an appropriate depth. Clearly label established findings, proposed mechanisms, "
        "and hypotheses; do not imply that a docking, simulation, or calculation was performed unless the sources say so."
    ),
}

CHAT_SYSTEM_PROMPT = """You are Pharmer, an assistant for pharmacology students and researchers.
Use the reference passages below as the evidence for factual claims. Cite claims with
[SOURCE_N] markers. If the passages do not answer a point, say what is missing rather
than guessing. Treat conversation history as context for resolving references such as
'it' or 'that drug', not as a source of scientific facts. Do not give patient-specific
diagnosis, dosing, or treatment advice.

Format and Structure Guidelines:
- Structure your answer cleanly and professionally with clear topical sections.
- For section titles, use clean markdown headings (e.g. '### Pharmacodynamics') or clean bold lead-ins (e.g. '**Overview:**').
- NEVER put bullet points on section headings (avoid '•**Heading:*' or '• **Heading**').
- NEVER output raw URLs or markdown links such as '[SOURCE_1](https://...)' or '[1](https://...)'. Use ONLY plain citation brackets like '[SOURCE_1]' or '[SOURCE_1, SOURCE_2]'. Source links are rendered automatically by the UI.
- Ensure all bold text has properly matched pairs of double asterisks ('**bold**'). Avoid broken asterisks like '**text:*'.
- When writing bullet points, ensure there is a space after the bullet (e.g. '• Point' or '- Point').
- Do not enclose common medical terms in unnecessary quotation marks.

{mode_guidance}

Active compound: {drug_name}
Reference passages:
{context}
"""


def _clean_source_url(url: str | None, chunk: dict | None = None) -> str:
    if not url:
        return ""
    m = re.search(r"pug_view/data/compound/(\d+)/JSON(?:\?heading=([^&#]+))?", url, flags=re.I)
    if m:
        cid_val = m.group(1)
        heading_val = m.group(2)
        if heading_val:
            return f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid_val}#section={heading_val}"
        return f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid_val}"
    return url


def _clean_source_name(chunk: dict) -> str:
    source = (chunk.get("source") or "Literature Reference").strip()
    source = re.sub(r"\bPUG View\b", "", source, flags=re.I).strip()
    source = re.sub(r"\s+", " ", source)
    return source


def _sanitize_chat_formatting(text: str) -> str:
    """Sanitize and normalize formatting quirks (unbalanced asterisks, bullet-headers, raw URLs)."""
    # 1. Strip markdown link URLs attached to citations: [1](http...) -> empty, [SOURCE_1](http...) -> empty
    text = re.sub(r"\[\s*(?:SOURCE_)?\d+(?:\s*,\s*(?:SOURCE_)?\d+)*\s*\](?:\([^)]*\))?", "", text, flags=re.I)
    text = re.sub(r"\[\s*SOURCE_\w+\s*\](?:\([^)]*\))?", "", text, flags=re.I)

    # 2. Convert bullet-heading hybrids like •**Heading:* or • **Heading:** or **Heading:* into clean markdown headings
    def _clean_heading(m: re.Match) -> str:
        title = m.group(1).strip().rstrip(":").rstrip("*").strip()
        return f"\n\n### {title}\n\n"

    text = re.sub(
        r"(?:^|\n)\s*[•*-]?\s*\*\*+([^*\n]+?)(?:\*+:|\*+|\*\*|:\*)\s*(?=\n|$)",
        _clean_heading,
        text,
    )

    # 3. Clean trailing colons on markdown headings
    text = re.sub(r"(?:^|\n)\s*###\s+([^\n]+?):+\s*(?=\n|$)", r"\n\n### \1\n\n", text)

    # 4. Fix malformed bold headers like **Heading:* or **Heading*: -> **Heading:**
    text = re.sub(r"\*\*([^*\n]+?)\*:", r"**\1:**", text)
    text = re.sub(r"\*\*([^*\n]+?):\*", r"**\1:**", text)

    # 5. Ensure double newlines before bullets and headings for clean paragraph separation
    text = re.sub(r"([^\n])\n\s*([•*-]\s+)", r"\1\n\n\2", text)
    text = re.sub(r"([^\n])\n\s*(###\s+)", r"\1\n\n\2", text)

    # 6. Normalize bullets: ensure bullets have a following space
    text = re.sub(r"(?:^|\n)\s*[•]\s*([^\s\n•])", r"\n• \1", text)
    text = re.sub(r"(?:^|\n)\s*[-]\s+([^\s\n\-])", r"\n• \1", text)

    # 7. Fix punctuation spacing from stripped citations (e.g. "stimulant ." -> "stimulant.")
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 8. Clean trailing redundant blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def answer_chat_question(
    question: str,
    history: list[dict[str, str]] | None = None,
    active_drug: dict[str, str | None] | None = None,
    mode: str = "structure_science",
) -> tuple[str, list[dict]]:
    """Answer a follow-up, preserving both sides of history and drug identity."""
    retriever = get_retriever()
    active_drug = active_drug or {}
    drug_name = (active_drug.get("name") or "unspecified compound").strip()
    cid = (active_drug.get("cid") or "").strip() or None
    query = f"{drug_name}: {question}" if cid else question
    indexed_cid = cid if cid and retriever.get_drug_chunk_count(cid) else None
    chunks = await retriever.retrieve(
        query=query,
        n_results=16,
        pubchem_cid=indexed_cid,
        drug_name=drug_name if not indexed_cid and active_drug.get("name") else None,
    )
    online_chunks: list[dict] = []
    if sources_enabled():
        # Search live for the user's actual question; the local index may not
        # contain recent or narrowly scoped papers for this topic.
        try:
            from ingest.pubmed import fetch_abstracts, search_pubmed

            search_terms = f"{drug_name} {question}" if drug_name != "unspecified compound" else question
            pmids = await search_pubmed(search_terms, max_results=8)
            for article in await fetch_abstracts(pmids):
                if not article.get("abstract"):
                    continue
                online_chunks.append({
                    "text": f"{article.get('title', '')}\n\n{article['abstract']}",
                    "source": f"PubMed PMID {article.get('pmid', '')}",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid', '')}/",
                    "field": "live PubMed search",
                    "distance": 1.0,
                    "drug": drug_name,
                    "pubchem_cid": cid or "",
                    "authors": "; ".join(article.get("authors", [])),
                    "publication_date": article.get("publication_date", ""),
                    "journal": article.get("journal", ""),
                    "doi": article.get("doi", ""),
                    "pmid": article.get("pmid", ""),
                    "document_id": article.get("pmid", ""),
                })
        except Exception as exc:
            logger.warning("Live PubMed search failed; using local evidence only: %s", exc)

    if not chunks and not online_chunks:
        return f"No relevant evidence was found in the enabled sources for {drug_name}. Try a more specific compound name or add a source document.", []

    # Reserve room for both live results and indexed evidence. If the local
    # reranker is unavailable, vector distances from the two sources are not
    # directly comparable, so rank each pool independently.
    ranked = (
        rerank_passages(query=query, chunks=chunks, top_k=5)
        + rerank_passages(query=query, chunks=online_chunks, top_k=5)
    )
    context, source_map = build_context(ranked)
    mode_guidance = CHAT_MODE_GUIDANCE.get(mode, CHAT_MODE_GUIDANCE["structure_science"])
    prompt = CHAT_SYSTEM_PROMPT.format(
        context=context,
        drug_name=drug_name,
        mode_guidance=mode_guidance,
    )

    conversation: list[dict[str, str]] = []
    for item in (history or [])[-20:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            conversation.append({"role": role, "content": content[:6000]})
    conversation.append({"role": "user", "content": question[:6000]})

    answer = await generate_chat_response(prompt, conversation)

    # 1. Detect all SOURCE_N referenced in answer in order of appearance
    found_sids = re.findall(r"\bSOURCE_(\d+)\b", answer, flags=re.IGNORECASE)
    sid_to_num: dict[str, int] = {}
    sources: list[dict] = []

    for sid_num in found_sids:
        full_sid = f"SOURCE_{sid_num}".upper()
        if full_sid not in sid_to_num and full_sid in source_map:
            new_num = len(sid_to_num) + 1
            sid_to_num[full_sid] = new_num
            chunk = source_map[full_sid]
            raw_url = chunk.get("url") or ""
            clean_url = _clean_source_url(raw_url, chunk)
            name = _clean_source_name(chunk)
            sources.append({
                "id": full_sid,
                "num": new_num,
                "name": name,
                "url": clean_url,
                "field": chunk.get("field", ""),
                "text": chunk.get("text", "")[:350],
            })

    # Also extract any markdown links with URLs [X](https://...) from the answer
    for m in re.finditer(r"\[(?:SOURCE_)?\d*\]\((https?://[^\s)]+)\)", answer, flags=re.IGNORECASE):
        url = _clean_source_url(m.group(1))
        if url and not any(s.get("url") == url for s in sources):
            num = len(sources) + 1
            sources.append({
                "id": f"SOURCE_{num}",
                "num": num,
                "name": "Literature Reference",
                "url": url,
                "field": "",
                "text": "",
            })

    # If the model didn't explicitly cite markers, include top consulted reference chunks
    if not sources and source_map:
        for sid, chunk in list(source_map.items())[:4]:
            raw_url = chunk.get("url") or ""
            clean_url = _clean_source_url(raw_url, chunk)
            num = len(sources) + 1
            sources.append({
                "id": sid,
                "num": num,
                "name": _clean_source_name(chunk),
                "url": clean_url,
                "field": chunk.get("field", ""),
                "text": chunk.get("text", "")[:350],
            })

    # Strip any redundant plain-text trailing "Sources" dump if the model generated one
    clean_answer = re.sub(r"\n+\s*(?:Sources|References)\s*:\s*\n[\s\S]*$", "", answer, flags=re.IGNORECASE)
    clean_answer = re.sub(r"\n+\s*Sources\s*\n[\s\S]*$", "", clean_answer, flags=re.IGNORECASE)

    # Normalize structure and clean formatting
    clean_answer = _sanitize_chat_formatting(clean_answer)

    return clean_answer, sources
