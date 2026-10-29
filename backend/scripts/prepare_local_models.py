"""Explicit one-time download; research requests only use cached models."""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastembed import TextEmbedding
from flashrank import Ranker

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
cache = Path(os.getenv("PHARMER_MODEL_CACHE", "./.cache"))
TextEmbedding(model_name="BAAI/bge-small-en-v1.5", cache_dir=str(cache / "embeddings"))
Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir=str(cache))
print("Embedding and reranking models cached. Local research is ready.")
