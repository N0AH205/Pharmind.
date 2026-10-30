"""
Ingestion handler for user-uploaded custom PDFs / literature files.
Extracts text from PDF, chunks it with sentence-aware sliding window,
embeds via FastEmbed SIMD batching, and indexes in ChromaDB.
"""

from __future__ import annotations

import io
import logging
import hashlib
import os
import re
import threading
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from datetime import datetime, timezone
import pypdf
from rag.retriever import get_retriever, CHROMA_PATH
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


MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 500
_document_lock = threading.RLock()


def _uploads_dir() -> Path:
    path = Path(os.getenv("PHARMIND_DOCUMENT_PATH", str(Path(CHROMA_PATH).parent / "uploads")))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _document_filter(document_id: str) -> dict:
    return {"$or": [{"document_id": document_id}, {"doc_id": document_id}]}


def get_document_file(document_id: str) -> Path | None:
    results = get_retriever().collection.get(where=_document_filter(document_id), include=["metadatas"])
    for meta in results.get("metadatas", []):
        stored = meta.get("stored_file", "")
        if re.fullmatch(r"[a-f0-9]{64}_[a-f0-9]{64}\.pdf", stored):
            path = _uploads_dir() / stored
            if path.is_file():
                return path
    return None


def _ingest_pdf(file_bytes: bytes, filename: str, drug_cid: str, drug_name: str, replace_document_id: str | None) -> dict:
    if len(file_bytes) > MAX_PDF_BYTES:
        raise ValueError("PDFs must be 20 MB or smaller.")
    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("The selected file is not a PDF.")
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    if reader.is_encrypted:
        raise ValueError("Unlock this PDF before uploading it.")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("PDFs must contain 500 pages or fewer.")
    chunks = []
    for page_num, page in enumerate(reader.pages, 1):
        chunks.extend(_sliding_chunk_text(page.extract_text() or "", page_num))
    if not chunks:
        raise ValueError("No readable text was found. Run OCR on scanned PDFs before uploading.")
    name = filename.replace("\\", "/").rsplit("/", 1)[-1][:200] or "paper.pdf"
    drug = drug_name.strip().casefold() or "custom literature"
    digest = hashlib.sha256(file_bytes).hexdigest()
    identity = hashlib.sha256(f"{digest}:{drug}".encode()).hexdigest()
    collection = get_retriever().collection
    vectors = embed_batch_local([chunk["text"] for chunk in chunks])
    with _document_lock:
        document_id = identity
        if replace_document_id:
            if not re.fullmatch(r"[a-f0-9]{64}", replace_document_id):
                raise ValueError("This older document must be deleted and uploaded again to replace it.")
            if not collection.get(where=_document_filter(replace_document_id), include=[]).get("ids"):
                raise ValueError("The paper to replace no longer exists.")
            document_id = replace_document_id
        previous = collection.get(where=_document_filter(document_id), include=["metadatas"])
        stored_file = f"{document_id}_{digest}.pdf"
        path = _uploads_dir() / stored_file
        path.write_bytes(file_bytes)
        ids = [f"pdf_{document_id}_{digest}_{i}" for i in range(len(chunks))]
        uploaded_at = datetime.now(timezone.utc).isoformat()
        metadata = [{
            "drug": drug, "pubchem_cid": str(drug_cid or "custom"), "field": "research",
            "doc_id": document_id, "document_id": document_id, "doc_name": name,
            "page": chunk["page"], "total_pages": len(reader.pages),
            "source": f"Uploaded PDF: {name} (p.{chunk['page']})", "url": "",
            "upload_date": uploaded_at, "stored_file": stored_file,
        } for chunk in chunks]
        collection.upsert(ids=ids, embeddings=vectors, documents=[c["text"] for c in chunks], metadatas=metadata)
        obsolete = set(previous.get("ids", [])) - set(ids)
        if obsolete:
            collection.delete(ids=list(obsolete))
        for meta in previous.get("metadatas", []):
            old = meta.get("stored_file", "")
            if old != stored_file and re.fullmatch(r"[a-f0-9]{64}_[a-f0-9]{64}\.pdf", old):
                (_uploads_dir() / old).unlink(missing_ok=True)
    return {"document_id": document_id, "filename": name, "pages": len(reader.pages),
            "chunks_stored": len(chunks), "associated_drug": drug, "original_available": True, "status": "success"}


async def ingest_pdf_bytes(file_bytes: bytes, filename: str, drug_cid: str = "custom", drug_name: str = "", replace_document_id: str | None = None) -> dict:
    return await run_in_threadpool(_ingest_pdf, file_bytes, filename, drug_cid, drug_name, replace_document_id)


def _list_pdfs() -> list[dict]:
    results = get_retriever().collection.get(where={"field": "research"}, include=["metadatas"])
    docs = {}
    for meta in results.get("metadatas", []):
        document_id = meta.get("document_id") or meta.get("doc_id") or meta.get("doc_name")
        if not document_id:
            continue
        if document_id not in docs:
            docs[document_id] = {
                "document_id": document_id, "filename": meta.get("doc_name", "paper.pdf"),
                "doc_name": meta.get("doc_name", "paper.pdf"), "associated_drug": meta.get("drug", ""),
                "pages": meta.get("total_pages", 1), "total_pages": meta.get("total_pages", 1),
                "chunks": 0, "upload_date": meta.get("upload_date", ""),
                "original_available": bool(meta.get("stored_file") and (_uploads_dir() / Path(meta["stored_file"]).name).is_file()),
            }
        docs[document_id]["chunks"] += 1
    return sorted(docs.values(), key=lambda doc: doc["upload_date"], reverse=True)


async def get_uploaded_pdfs() -> list[dict]:
    return await run_in_threadpool(_list_pdfs)


def _delete_pdf(document_id: str) -> dict:
    with _document_lock:
        collection = get_retriever().collection
        results = collection.get(where=_document_filter(document_id), include=["metadatas"])
        if not results.get("ids"):
            return {"success": False, "error": "Paper not found. Refresh your document library."}
        collection.delete(ids=results["ids"])
        for meta in results.get("metadatas", []):
            stored = meta.get("stored_file", "")
            if re.fullmatch(r"[a-f0-9]{64}_[a-f0-9]{64}\.pdf", stored):
                (_uploads_dir() / stored).unlink(missing_ok=True)
        return {"success": True, "document_id": document_id, "deleted_chunks": len(results["ids"])}


async def delete_uploaded_pdf(document_id: str) -> dict:
    return await run_in_threadpool(_delete_pdf, document_id)
