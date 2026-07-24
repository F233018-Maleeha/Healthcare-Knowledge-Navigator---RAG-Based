import pytest

from app.core.config import Settings
from app.ingestion.pipeline import ingest_documents
from app.retrieval.bm25_index import BM25Index
from app.retrieval.embeddings import LocalStubEmbedder
from app.retrieval.pipeline import RetrievalPipeline
from app.retrieval.vector_store import VectorStore
from tests.fixtures import SAMPLE_DOCS


@pytest.mark.asyncio
async def test_ingest_then_retrieve_returns_relevant_chunk():
    settings = Settings(vector_backend="memory", embedding_dim=256, rerank_enabled=True)
    embedder = LocalStubEmbedder(dim=settings.embedding_dim)
    vector_store = VectorStore(settings)
    bm25 = BM25Index()

    n_chunks = await ingest_documents(SAMPLE_DOCS, embedder, vector_store, bm25)
    assert n_chunks > 0

    pipeline = RetrievalPipeline(settings, embedder, vector_store, bm25)
    results = await pipeline.retrieve("anticoagulation atrial fibrillation DOAC warfarin", top_k=3)

    assert len(results) > 0
    # The AFib document should be the most lexically relevant hit for this query.
    top_doc_ids = {r.chunk.doc_id for r in results}
    assert "doc-03" in top_doc_ids


@pytest.mark.asyncio
async def test_source_diversity_filter_caps_chunks_per_document():
    settings = Settings(vector_backend="memory", embedding_dim=256, retrieval_final_top_k=5)
    embedder = LocalStubEmbedder(dim=settings.embedding_dim)
    vector_store = VectorStore(settings)
    bm25 = BM25Index()
    await ingest_documents(SAMPLE_DOCS, embedder, vector_store, bm25)

    pipeline = RetrievalPipeline(settings, embedder, vector_store, bm25)
    results = await pipeline.retrieve("cardiovascular disease management", top_k=5)

    counts: dict[str, int] = {}
    for r in results:
        counts[r.chunk.doc_id] = counts.get(r.chunk.doc_id, 0) + 1
    assert all(v <= 2 for v in counts.values())
