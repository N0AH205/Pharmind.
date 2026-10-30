"""
Local Embedding Engine — FastEmbed (100% Offline, ONNX-accelerated).

Replaces external cloud API calls (e.g., Google Gemini embedding API) with local,
zero-latency vector embeddings.

Uses BAAI/bge-small-en-v1.5 by default (384-dimensional dense vectors), which yields
excellent performance for biomedical and general RAG text.
"""

from __future__ import annotations

import threading
import logging
import os
from pathlib import Path
from typing import Sequence

from rag.config import OFFLINE_MODE

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"

_embedding_model: TextEmbedding | None = None
_embedding_lock = threading.Lock()


def get_embedding_model() -> TextEmbedding:
    """Return lazy-initialized FastEmbed TextEmbedding singleton."""
    global _embedding_model
    with _embedding_lock:
        if _embedding_model is None:
            logger.info(f"Loading local embedding model: {EMBED_MODEL_NAME}...")
            cache_dir = Path(os.getenv("PHARMER_MODEL_CACHE", "./.cache")) / "embeddings"
            try:
                _embedding_model = TextEmbedding(model_name=EMBED_MODEL_NAME, cache_dir=str(cache_dir), local_files_only=True)
            except Exception as exc:
                raise RuntimeError("Local embedding model is not ready. Run python scripts/prepare_local_models.py from the backend directory while online, then retry.") from exc
    return _embedding_model


def embed_text_local(text: str) -> list[float]:
    """
    Generate embedding vector for a single text chunk locally.
    Returns list of floats.
    """
    model = get_embedding_model()
    # truncate excessively long texts if any
    truncated = text[:8000]
    embeddings_generator = model.embed([truncated])
    vector = list(next(embeddings_generator))
    return [float(v) for v in vector]


def embed_batch_local(texts: Sequence[str]) -> list[list[float]]:
    """
    Generate embedding vectors for a batch of text chunks locally.
    """
    model = get_embedding_model()
    truncated_texts = [t[:8000] for t in texts]
    embeddings_generator = model.embed(truncated_texts)
    return [[float(v) for v in vec] for vec in embeddings_generator]
