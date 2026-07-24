from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.dependencies import get_bm25_index, get_retrieval_pipeline, get_vector_store
from app.ingestion.pipeline import ingest_documents
from app.models.schemas import SourceDocument
from app.retrieval.bm25_index import BM25Index
from app.retrieval.embeddings import EmbeddingGenerationError
from app.retrieval.pipeline import RetrievalPipeline
from app.retrieval.vector_store import VectorStore

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("")
async def ingest(
    docs: list[SourceDocument],
    pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline),
    vector_store: VectorStore = Depends(get_vector_store),
    bm25_index: BM25Index = Depends(get_bm25_index),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        count = await ingest_documents(
            docs, pipeline.embedder, vector_store, bm25_index,
            batch_size=settings.embedding_batch_size,
        )
    except EmbeddingGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"documents_ingested": len(docs), "chunks_indexed": count}