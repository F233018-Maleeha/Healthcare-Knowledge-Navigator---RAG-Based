"""
Application-wide singletons (embedder, vector store, BM25 index,
retrieval pipeline). Built once at startup and shared across requests
via FastAPI dependency injection.
"""
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.retrieval.bm25_index import BM25Index
from app.retrieval.embeddings import get_embedder
from app.retrieval.pipeline import RetrievalPipeline
from app.retrieval.vector_store import VectorStore


@lru_cache
def get_bm25_index() -> BM25Index:
    return BM25Index()


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore(get_settings())


@lru_cache
def get_retrieval_pipeline() -> RetrievalPipeline:
    settings = get_settings()
    return RetrievalPipeline(
        settings=settings,
        embedder=get_embedder(settings),
        vector_store=get_vector_store(),
        bm25_index=get_bm25_index(),
    )
