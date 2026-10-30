# Pharmind Local development guide

This guide describes the current implementation. The app is local-first; it can run without external network access after its models and local evidence database have been prepared.

## Architecture

```text
Next.js UI → local FastAPI API → RDKit identity → local ChromaDB retrieval
                                      ↓                   ↓
                           Ollama chat/model ← local FastEmbed + FlashRank
```

Monographs retrieve passages by topic (mechanism, ADME, adverse effects, indications, toxicology, interactions, and history) and rerank within each topic. When online mode is enabled, each monograph also runs live PubMed searches, while a broader PubChem/DailyMed/PubMed/ClinicalTrials.gov source refresh runs at most every 12 hours per compound in the current process. Follow-up chat searches PubMed for the user's question and combines those results with local evidence. This uses abstracts and database records, not full PubMed article text; evidence coverage remains bounded by source availability and retrieval. The default Ollama provider keeps prompts and retrieved evidence on this machine.

The application returns no sample monograph when the local index is empty. Fields without supporting evidence are marked unavailable. Citations resolve to indexed source metadata and the retrieved passage.

## Installation and model preparation

Use Python 3.10 or newer and Node.js. Install Python packages from `backend/requirements.txt`; this file includes RDKit, FastEmbed, FlashRank, ChromaDB, PDF parsing, and the API dependencies. Choose a cloud LLM provider in `backend/.env`, or install Ollama and pull a local model.

Prepare the FastEmbed and FlashRank model cache explicitly while online. From `backend/`, run:

```bash
python scripts/prepare_local_models.py
```

For full monograph queries, prepare a local ChromaDB database using the ingestion command below. Custom PDF ingestion and RDKit structure processing run locally.

## Network and privacy behavior

| Operation | Network use |
|---|---|
| Ollama inference | Local Ollama endpoint; prompts stay on this machine when Ollama is local |
| OpenAI, Anthropic, Gemini inference | Sends prompts, conversation history, and retrieved evidence to the selected provider |
| PubChem/DailyMed/PubMed/ClinicalTrials search and ingestion | Contacts those source services |
| FastEmbed/FlashRank/Ollama first-time model setup | Downloads model files |
| Query against a prepared index, PDF ingestion, RDKit | Local processing |

Online source access is off by default and controlled separately from the model provider in connection settings. Cloud providers receive prompts, conversation history, and retrieved passages even when online literature sources are off. With Ollama, cached document models, and online sources off, research runs locally. NCBI's key is optional for online searches. Fonts are served locally.

## Data ingestion and sources

From `backend/`, run `python -m ingest.run_ingest` with `ONLINE_SOURCES=true` in `backend/.env` while online. The script fetches the benchmark set from PubChem, up to three useful DailyMed labels per drug, topic-focused PubMed abstracts deduplicated by PMID, and up to 15 ClinicalTrials.gov study records per drug. It chunks label and trial text, stores bibliographic/study identifiers, embeds locally, and writes to ChromaDB. It does not download PubMed full text. The `--quickstart` option builds a smaller Aspirin-only demo. Ingestion volume is intentionally bounded by the search limits in `backend/ingest/run_ingest.py`.

The current gold-standard evaluation set contains five drug profiles. Add independently reviewed source-backed reference facts before expanding benchmark claims. Source terms and local copies remain subject to the source provider's license, copyright, and terms. Do not treat API availability as permission to redistribute source text. For custom or novel compounds, associate uploaded PDFs with the exact compound name used in the query; retrieval filters those passages by that name when no indexed CID is available.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Common settings:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `anthropic`, or `gemini` |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Any model already installed in Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama endpoint (Docker uses the host gateway) |
| `PHARMER_MODEL_CACHE` | `./.cache` | FlashRank model cache directory |
| `CHROMA_PATH` | discovered local path | Persistent local vector index |
| `NCBI_API_KEY` | unset | Optional higher PubMed request limit |

The Docker Compose project is `pharmind-local`, with separate `research-data` and `model-cache` volumes. Host ports are `3001` for the workspace and `8001` for the API; internal ports stay `3000` and `8000`. The Windows `start-pharmind-local.bat` launcher prepares the local document-model cache without ingesting demo literature. `stop-pharmind-local.bat` stops only this project and preserves its volumes. Local frontend development also uses port `3001` and defaults to the API on port `8001`.

## Evaluation

From `backend/`, run `python -m scripts.evaluate`. This compares generated content with keyword lists in `data/gold_standard.json`, reports field coverage across the output schema, citation evidence presence, and a retrieved-text keyword recall proxy. The proxy is exact keyword matching, not semantic recall. Use `--llm-eval` for a model-assisted correctness and unsupported-claim audit using the configured provider; with a cloud provider, this sends evaluation prompts and gold/reference content to that service. The default run is local with Ollama.

The current five-drug benchmark is too small to establish research-grade factual completeness. The model-assisted judge is also an estimate, not independent expert adjudication. Use domain-reviewed test cases, source-attributed expected facts, and human audit before making quality claims.

## Main code paths

- `backend/main.py`: health, monograph, chat, PDF, and debug API endpoints.
- `backend/rag/pipeline.py`: monograph retrieval, topic balancing, citations, and validation.
- `backend/rag/chat.py`: conversation assembly, active-drug filtering, and chat citations.
- `backend/rag/llm.py`: provider adapters.
- `backend/rag/config.py`: `.env` loading and online source policy.
- `backend/ingest/`: source adapters and local PDF indexing.
- `backend/scripts/evaluate.py`: benchmark metrics and report output.
