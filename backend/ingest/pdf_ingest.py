"""
Ingestion handler for user-uploaded custom PDFs / literature files.
Extracts text from PDF, chunks it with sentence-aware sliding window,
embeds via FastEmbed SIMD batching, and indexes in ChromaDB.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
import pypdf
from rag.retriever import get_retriever
from rag.embeddings import embed_batch_local

logger = logging.getLogger(__name__)


def _sliding_chunk_text(
    text: str,
    page_num: int,
    chunk_size: int = 950,
    overlap: int = 150,
) -> list[dict]:
    """Split page text into overlapping segments, respecting sentence/paragraph boundaries."""
    if not text or not text.strip():
        return []

    clean_text = text.strip()
    if len(clean_text) <= chunk_size:
        return [{"text": clean_text, "page": page_num}]

    chunks = []
    start = 0
    text_len = len(clean_text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len:
            split_pos = -1
            # Look for paragraph break (\n\n)
            p_break = clean_text.rfind("\n\n", start + chunk_size // 2, end)
            if p_break != -1:
                split_pos = p_break + 2
            else:
                # Look for sentence break (. followed by space or newline)
                s_break = max(
                    clean_text.rfind(". ", start + chunk_size // 2, end),
                    clean_text.rfind(".\n", start + chunk_size // 2, end),
                )
                if s_break != -1:
                    split_pos = s_break + 2
                else:
                    # Look for whitespace
                    w_break = clean_text.rfind(" ", start + chunk_size // 2, end)
                    if w_break != -1:
                        split_pos = w_break + 1

            if split_pos != -1:
                end = split_pos

        chunk_str = clean_text[start:end].strip()
        if chunk_str:
            chunks.append({"text": chunk_str, "page": page_num})

        if end >= text_len:
            break
        start = max(start + 1, end - overlap)

    return chunks


async def ingest_pdf_bytes(
    file_bytes: bytes,
    filename: str,
    drug_cid: str = "custom",
    drug_name: str = "",
) -> dict:
    """
    Extract text from a PDF byte stream, chunk with sliding window overlap,
    generate local embeddings in batch, and store in ChromaDB.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        full_text_pages = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt and txt.strip():
                full_text_pages.append((i + 1, txt.strip()))

        if not full_text_pages:
            raise ValueError(f"No extractable text found in '{filename}'. Ensure it is not a scanned image PDF.")

        # Chunk text across pages with boundary-aware sliding window
        chunks = []
        for page_num, text in full_text_pages:
            page_chunks = _sliding_chunk_text(text, page_num=page_num, chunk_size=950, overlap=150)
            chunks.extend(page_chunks)

        if not chunks:
            raise ValueError(f"Could not construct chunks from '{filename}'.")

        retriever = get_retriever()
        collection = retriever.collection

        clean_name = filename.replace(" ", "_").lower()
        associated_drug = drug_name.strip().casefold() or "custom literature"
        clean_drug = "_".join(associated_drug.split())
        upload_time = datetime.now(timezone.utc).isoformat()
        total_pages = len(reader.pages)

        # Batch embed all chunks in parallel using FastEmbed ONNX
        chunk_texts = [c["text"] for c in chunks]
        embeddings = embed_batch_local(chunk_texts)

        ids, documents, metadatas = [], [], []
        for i, c in enumerate(chunks):
            chunk_id = f"custom_pdf_{clean_drug}_{clean_name}_{i}"
            ids.append(chunk_id)
            documents.append(c["text"])
            metadatas.append({
                "drug": associated_drug,
                "pubchem_cid": str(drug_cid or "custom"),
                "field": "research",
                "doc_id": f"pdf_{clean_name}",
                "doc_name": filename,
                "page": int(c["page"]),
                "total_pages": int(total_pages),
                "source": f"Uploaded PDF: {filename} (p.{c['page']})",
                "url": "",
                "upload_date": upload_time,
            })

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info(f"Successfully indexed PDF '{filename}': {len(chunks)} chunks stored.")
        return {
            "filename": filename,
            "pages": total_pages,
            "chunks_stored": len(chunks),
            "associated_drug": associated_drug,
            "status": "success",
        }
    except Exception as e:
        logger.error(f"Failed to process uploaded PDF '{filename}': {e}", exc_info=True)
        raise e


async def get_uploaded_pdfs() -> list[dict]:
    """Retrieve metadata summary of all currently indexed PDFs in ChromaDB."""
    retriever = get_retriever()
    if not retriever.is_ready():
        return []

    try:
        results = retriever.collection.get(
            where={"field": "research"},
            include=["metadatas"]
        )
        if not results or not results.get("metadatas"):
            return []

        docs: dict[str, dict] = {}
        for meta in results["metadatas"]:
            doc_name = meta.get("doc_name") or meta.get("source", "").replace("Uploaded PDF: ", "").split(" (p.")[0]
            if not doc_name:
                continue
            if doc_name not in docs:
                docs[doc_name] = {
                    "filename": doc_name,
                    "doc_name": doc_name,
                    "drug": meta.get("drug", "custom literature"),
                    "associated_drug": meta.get("drug", "custom literature"),
                    "pubchem_cid": meta.get("pubchem_cid", "custom"),
                    "pages": meta.get("total_pages", 1),
                    "total_pages": meta.get("total_pages", 1),
                    "chunks": 0,
                    "upload_date": meta.get("upload_date", ""),
                }
            docs[doc_name]["chunks"] += 1
            if meta.get("total_pages"):
                pages_val = max(docs[doc_name]["pages"], meta["total_pages"])
                docs[doc_name]["pages"] = pages_val
                docs[doc_name]["total_pages"] = pages_val

        return list(docs.values())
    except Exception as exc:
        logger.error(f"Error fetching uploaded PDFs: {exc}")
        return []


async def delete_uploaded_pdf(filename: str) -> dict:
    """Delete all indexed chunks for a given PDF filename from ChromaDB."""
    retriever = get_retriever()
    clean_name = filename.replace(" ", "_").lower()

    res = retriever.collection.get(
        where={"doc_name": filename},
        include=["metadatas"]
    )
    target_ids = list(res["ids"]) if res and res.get("ids") else []

    if not target_ids:
        all_research = retriever.collection.get(
            where={"field": "research"},
            include=["metadatas"]
        )
        if all_research and all_research.get("ids"):
            for chunk_id, meta in zip(all_research["ids"], all_research["metadatas"]):
                if clean_name in chunk_id or filename in meta.get("source", ""):
                    target_ids.append(chunk_id)

    if target_ids:
        retriever.collection.delete(ids=target_ids)
        logger.info(f"Deleted {len(target_ids)} chunks for PDF '{filename}'.")
        return {"success": True, "filename": filename, "deleted_chunks": len(target_ids)}

    return {"success": False, "filename": filename, "message": "File not found in index."}
