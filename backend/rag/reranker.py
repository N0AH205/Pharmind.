"""
FlashRank local reranker wrapper — Phase 3.

Provides local passage reranking using FlashRank (bge-reranker-small)
with zero network overhead and fast CPU inference.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

_reranker_instance = None


def get_reranker():
    global _reranker_instance
    if _reranker_instance is None:
        try:
            from flashrank import Ranker
            model_name = "ms-marco-TinyBERT-L-2-v2"
            cache_dir = Path(os.getenv("PHARMER_MODEL_CACHE", "./.cache"))
            model_dir = cache_dir / model_name
            cached_model_ready = all((model_dir / name).exists() for name in (
                "config.json", "tokenizer.json", "flashrank-TinyBERT-L-2-v2.onnx"
            ))
            if not cached_model_ready:
                logger.warning("Local reranker is not cached; offline mode will use vector ranking.")
                _reranker_instance = False
            else:
                _reranker_instance = Ranker(model_name=model_name, cache_dir=str(cache_dir))
        except Exception as e:
            logger.warning(f"Could not load FlashRank ranker: {e}. Reranking will fallback to vector distance.")
            _reranker_instance = False
    return _reranker_instance if _reranker_instance else None


def rerank_passages(query: str, chunks: list[dict], top_k: int = 8) -> list[dict]:
    """
    Rerank a list of ChromaDB chunk dicts based on semantic relevance to query.

    Args:
        query: User or category query string
        chunks: List of chunk dicts (must contain 'text')
        top_k: Max chunks to return

    Returns:
        Top k reranked chunk dicts sorted by relevance score
    """
    if not chunks:
        return []

    ranker = get_reranker()
    if not ranker:
        # Fallback: sort by distance (lowest distance first)
        sorted_chunks = sorted(chunks, key=lambda x: x.get("distance", 1.0))
        return sorted_chunks[:top_k]

    try:
        from flashrank import RerankRequest

        passages = [
            {"id": i, "text": c.get("text", ""), "meta": c}
            for i, c in enumerate(chunks)
        ]

        rerank_req = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(rerank_req)

        reranked_chunks = []
        for res in results[:top_k]:
            chunk_dict = dict(res["meta"])
            chunk_dict["score"] = float(res.get("score", 0.0))
            reranked_chunks.append(chunk_dict)

        return reranked_chunks
    except Exception as e:
        logger.error(f"FlashRank reranking error: {e}", exc_info=True)
        sorted_chunks = sorted(chunks, key=lambda x: x.get("distance", 1.0))
        return sorted_chunks[:top_k]
