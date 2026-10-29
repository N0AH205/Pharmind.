"""
ChromaDB vector retriever — Phase 2/3.

Two-stage retrieval:
  Stage 1 — Metadata filter: constrain to chunks where pubchem_cid matches.
            This guarantees all returned chunks are about the correct drug.
  Stage 2 — Vector similarity: rank the filtered subset by semantic similarity.

This design ensures drug identity correctness (100%) before semantic scoring.
SOURCE_N labelling is done in context_builder.py, not here.

Embeddings: local FastEmbed BGE-small ONNX model. No API key required.
"""

from __future__ import annotations

import os

import chromadb
import httpx
from rag.config import OFFLINE_MODE  # Loads backend/.env before paths are resolved.

def _resolve_chroma_path() -> str:
    env_path = os.getenv("CHROMA_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    candidates = [
        "data/chroma",
        "../data/chroma",
        "/app/data/chroma",
        os.path.join(os.path.dirname(__file__), "..", "data", "chroma"),
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return env_path or "../data/chroma"

CHROMA_PATH = _resolve_chroma_path()
COLLECTION_NAME = "pharma_docs"
from rag.embeddings import embed_text_local, embed_batch_local


def _embed(text: str) -> list[float]:
    """
    Embed text locally using FastEmbed (BAAI/bge-small-en-v1.5, 384d).
    100% offline, zero API keys required.
    """
    return embed_text_local(text)



class Retriever:
    """
    Two-stage retriever: metadata filter → vector similarity.

    Use get_retriever() to get the shared singleton.
    """

    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_PATH, settings=chromadb.config.Settings(anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._ready = self.collection.count() > 0

    def is_ready(self) -> bool:
        # Keep readiness correct when PDFs or ingestion add chunks after startup.
        self._ready = self.collection.count() > 0
        return self._ready

    def chunk_count(self) -> int:
        return self.collection.count()

    def get_drug_chunk_count(self, identifier: str) -> int:
        """Return the number of chunks stored for a specific drug CID or drug name."""
        if not identifier:
            return 0
        if identifier.isdigit():
            results = self.collection.get(
                where={"pubchem_cid": identifier},
                include=[],
            )
        else:
            results = self.collection.get(
                where={"drug": identifier.strip().casefold()},
                include=[],
            )
        return len(results["ids"])

    async def retrieve(
        self,
        query: str,
        n_results: int = 8,
        pubchem_cid: str | None = None,
        drug_name: str | None = None,
        fields: list[str] | None = None,
        include_custom_pdf: bool = True,
    ) -> list[dict]:
        """
        Return the top-n most semantically relevant chunks for the query.

        Two-stage process:
          1. If pubchem_cid is provided, restrict the search to only chunks
             with that CID in their metadata (or custom uploaded PDFs if include_custom_pdf=True).
          2. Rank the filtered set by cosine similarity to the query embedding.

        Args:
            query:              Semantic query string.
            n_results:          Maximum number of chunks to return.
            pubchem_cid:        PubChem CID string (e.g. "2244" for Aspirin).
            drug_name:          Common drug name.
            fields:             List of document fields to filter by.
            include_custom_pdf: If True, allows user-uploaded PDF chunks (pubchem_cid='custom')
                                to be retrieved alongside the specific drug chunks.

        Returns list of dicts with:
            text, source, url, field, distance, drug, pubchem_cid
        """
        if not self._ready:
            return []

        query_vec = _embed(query)

        # Combine drug identity and source-field filters so a section can
        # directly search the matching DailyMed/PubMed categories.
        filters: list[dict] = []
        if pubchem_cid and pubchem_cid.isdigit():
            if include_custom_pdf:
                filters.append({"$or": [{"pubchem_cid": pubchem_cid}, {"pubchem_cid": "custom"}]})
            else:
                filters.append({"pubchem_cid": pubchem_cid})
        elif drug_name or pubchem_cid:
            name_val = (drug_name or pubchem_cid).strip().casefold()
            if include_custom_pdf:
                filters.append({"$or": [{"drug": name_val}, {"pubchem_cid": "custom"}]})
            else:
                filters.append({"drug": name_val})

        if fields:
            allowed_fields = list(fields)
            if include_custom_pdf and "research" not in allowed_fields:
                allowed_fields.append("research")
            filters.append({"field": {"$in": allowed_fields}})

        where = filters[0] if len(filters) == 1 else ({"$and": filters} if filters else None)

        if where:
            pool_size = len(self.collection.get(where=where, include=[])["ids"])
        else:
            pool_size = self.collection.count()

        if pool_size == 0:
            return []

        n = min(n_results, pool_size)

        # Build ChromaDB query kwargs
        kwargs: dict = {
            "query_embeddings": [query_vec],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        return [
            {
                "text":        doc,
                "source":      meta.get("source", ""),
                "url":         meta.get("url", ""),
                "field":       meta.get("field", ""),
                "distance":    dist,
                "drug":        meta.get("drug", ""),
                "pubchem_cid": meta.get("pubchem_cid", ""),
                "authors": meta.get("authors", ""),
                "publication_date": meta.get("publication_date", ""),
                "journal": meta.get("journal", ""),
                "doi": meta.get("doi", ""),
                "pmid": meta.get("pmid", ""),
                "document_id": meta.get("document_id", ""),
                "doc_name": meta.get("doc_name", ""),
                "page": meta.get("page", 1),
                "total_pages": meta.get("total_pages", 1),
                "doc_id": meta.get("doc_id", ""),
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    async def list_chunks_by_drug(self, pubchem_cid: str) -> list[dict]:
        """
        Return all metadata for chunks belonging to a drug.
        Useful for inspecting ingestion coverage. No embedding needed.
        """
        results = self.collection.get(
            where={"pubchem_cid": pubchem_cid},
            include=["metadatas"],
        )
        return results["metadatas"]


# ── Module-level singleton ────────────────────────────────────────────────────

_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    """Return the shared Retriever singleton (lazy-initialised)."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
