"""
PharmaRAG — FastAPI backend entry point.

Phase 3: Full RAG pipeline (ChromaDB retrieval + LLM structured output).

Endpoints:
  GET  /health               → status + retriever chunk count
  POST /query                → run_pipeline(smiles) → DrugInfo JSON
  GET  /debug/retrieval      → raw ChromaDB results for a SMILES (no LLM)
  GET  /debug/query-builder  → show what query would be built for a SMILES
"""

from typing import Literal

from fastapi import FastAPI, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from pydantic import BaseModel, Field
from rag.schema import DrugInfo, QueryRequest
from rag.pipeline import run_pipeline
from rag.retriever import get_retriever
from rag.query_builder import build_retrieval_query
from ingest.local_chem import enrich_structure_local as enrich_structure
from rag.connection_api import router as connection_router, model_connection_context, connection_validation_error

app = FastAPI(
    title="Pharmer API",
    description="Structured drug-information RAG system — Phase 3",
    version="0.3.0",
)
app.include_router(connection_router)
app.middleware("http")(model_connection_context)
app.add_exception_handler(RequestValidationError, connection_validation_error)

# The browser UI is served locally; the Next.js backend proxy calls FastAPI server-to-server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Production endpoints ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — reports retriever readiness and chunk count."""
    retriever = get_retriever()
    return {
        "status": "ok",
        "phase": 3,
        "retriever_ready": retriever.is_ready(),
        "chunk_count": retriever.chunk_count(),
    }


@app.post("/query", response_model=None)
async def query_drug(req: QueryRequest):
    """
    Accept a SMILES string and return a structured DrugInfo object.

    Flow: SMILES → Local RDKit → ChromaDB → Qwen (Ollama) → Pydantic → JSON
    Falls back to mock data if ChromaDB is empty.
    """
    from rag.safety import ClinicalAdviceRefusal
    try:
        result: DrugInfo = await run_pipeline(req.smiles, debug=False)
        return {"success": True, "data": result.model_dump()}
    except ClinicalAdviceRefusal as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )


class ChatRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = Field(default_factory=list)
    active_drug: dict[str, str | None] = Field(default_factory=dict)
    mode: Literal["paper_learning", "structure_science", "molecule_theory"] = "structure_science"

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Conversational Q&A endpoint for follow-up questions and pharmacology discussion.
    """
    from rag.chat import answer_chat_question
    from rag.safety import check_query_safety
    is_safe, refusal = await check_query_safety(req.question)
    if not is_safe:
        return {
            "success": True,
            "answer": refusal or "Pharmind is designed for educational and reference purposes only. We cannot provide patient-specific clinical advice, diagnosis, or personal dosage instructions. Always consult a licensed clinician for medical guidance."
        }

    try:
        reply_answer, reply_sources = await answer_chat_question(
            req.question,
            history=req.history,
            active_drug=req.active_drug,
            mode=req.mode,
        )
        return {
            "success": True,
            "answer": reply_answer,
            "sources": reply_sources,
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})


@app.post("/upload-pdf")
async def upload_pdf_endpoint(
    file: UploadFile = File(...),
    drug_cid: str = Query("custom"),
    drug_name: str = Query(""),
):
    """
    Ingest custom lab report or research paper PDF directly into local ChromaDB.
    """
    from ingest.pdf_ingest import ingest_pdf_bytes
    try:
        content = await file.read()
        res = await ingest_pdf_bytes(
            content,
            filename=file.filename or "uploaded.pdf",
            drug_cid=drug_cid,
            drug_name=drug_name,
        )
        return {"success": True, "data": res}
    except Exception as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})


@app.get("/uploaded-pdfs")
async def list_uploaded_pdfs():
    """
    List all user-uploaded research PDFs currently indexed in local ChromaDB.
    """
    from ingest.pdf_ingest import get_uploaded_pdfs
    try:
        docs = await get_uploaded_pdfs()
        return {"success": True, "data": docs, "documents": docs}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})


@app.delete("/uploaded-pdfs/{filename}")
async def delete_uploaded_pdf_endpoint(filename: str):
    """
    Remove an uploaded PDF from the local vector database by filename.
    """
    from ingest.pdf_ingest import delete_uploaded_pdf
    try:
        res = await delete_uploaded_pdf(filename)
        return res
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})



@app.post("/query/stream")
async def query_drug_stream(req: QueryRequest):
    """
    Server-Sent Events (SSE) endpoint: streams status stages, tokens, and final DrugInfo JSON.
    """
    from fastapi.responses import StreamingResponse
    import json

    async def event_generator():
        from rag.pipeline import run_pipeline_stream
        async for event in run_pipeline_stream(req.smiles):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Debug endpoints (not part of the public API contract) ─────────────────────

@app.get("/debug/retrieval")
async def debug_retrieval(
    smiles: str = Query(..., description="SMILES string to resolve and retrieve for"),
    n: int = Query(8, ge=1, le=20, description="Number of chunks to retrieve"),
):
    """
    Run the full retrieval pipeline (PubChem → QueryBuilder → ChromaDB) and
    return the raw retrieved chunks with distance scores.

    No LLM is called. Use this to verify retrieval quality before connecting Qwen.

    Example:
        GET /debug/retrieval?smiles=CC(=O)Oc1ccccc1C(=O)O
    """
    try:
        structure_data = await enrich_structure(smiles)
        query = build_retrieval_query(structure_data)
        retriever = get_retriever()
        cid = str(structure_data.get("pubchem_cid") or "") or None
        chunks = await retriever.retrieve(query, n_results=n, pubchem_cid=cid)

        # Summarise field and source coverage
        field_counts: dict[str, int] = {}
        for chunk in chunks:
            f = chunk.get("field", "unknown")
            field_counts[f] = field_counts.get(f, 0) + 1

        return {
            "smiles": smiles,
            "resolved_name": structure_data.get("common_name") or structure_data.get("iupac_name"),
            "pubchem_cid": structure_data.get("pubchem_cid"),
            "query": query,
            "chunk_count_in_db": retriever.chunk_count(),
            "chunks_returned": len(chunks),
            "field_coverage": field_counts,
            "chunks": [
                {
                    "rank": i + 1,
                    "distance": round(chunk["distance"], 4),
                    "field": chunk.get("field"),
                    "source": chunk.get("source"),
                    "url": chunk.get("url"),
                    "drug": chunk.get("drug"),
                    "preview": chunk.get("text", "")[:300],
                }
                for i, chunk in enumerate(chunks)
            ],
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )


@app.get("/debug/query-builder")
async def debug_query_builder(
    smiles: str = Query(..., description="SMILES string"),
    field: str | None = Query(None, description="Optional field context: moa|adme|indications|…"),
):
    """
    Show what retrieval query would be built for a given SMILES + field.
    Useful for diagnosing why ChromaDB might return irrelevant chunks.
    """
    try:
        structure_data = await enrich_structure(smiles)
        query = build_retrieval_query(structure_data, field=field)
        return {
            "smiles": smiles,
            "field": field,
            "query": query,
            "common_name": structure_data.get("common_name"),
            "iupac_name": structure_data.get("iupac_name"),
            "synonyms": structure_data.get("synonyms", [])[:5],
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/debug/pipeline")
async def debug_pipeline(req: QueryRequest):
    """
    Run the full pipeline with debug=True.
    Returns the DrugInfo result PLUS retrieved chunks and source_map keys.

    NOT for production use — exposes internal retrieval data.
    """
    from rag.safety import ClinicalAdviceRefusal
    try:
        result = await run_pipeline(req.smiles, debug=True)
        return {"success": True, **result}
    except ClinicalAdviceRefusal as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )
