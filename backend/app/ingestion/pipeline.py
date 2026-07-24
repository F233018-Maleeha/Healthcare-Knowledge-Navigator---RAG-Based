"""
End-to-end ingestion: SourceDocument -> chunks -> embeddings -> vector
store + BM25 index. This is what the /ingest endpoint and offline
batch-loading scripts (scripts/ingest_*.py) both call.
"""
import asyncio

from app.ingestion.chunking import chunk_document
from app.models.schemas import Chunk, SourceDocument
from app.retrieval.bm25_index import BM25Index
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.vector_store import VectorStore


async def _embed_in_batches(
    embedder: EmbeddingProvider, texts: list[str], batch_size: int
) -> list[list[float]]:
    """Embed in fixed-size batches rather than one call for everything -
    a large ingest (many documents at once) can easily produce more
    texts than a provider's free-tier batch-size or per-request token
    limit allows in a single call. Sequential, not concurrent: most
    providers rate-limit per-minute regardless of concurrency, so
    parallel batches would just queue behind the same limiter anyway
    (see core/rate_limit.py) while adding no real speed benefit.
    """
    all_embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        all_embeddings.extend(await embedder.embed(batch))
    return all_embeddings


async def ingest_documents(
    docs: list[SourceDocument],
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    bm25_index: BM25Index,
    batch_size: int = 20,
) -> int:
    all_chunks: list[Chunk] = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))

    if not all_chunks:
        return 0

    texts = [c.text for c in all_chunks]
    embeddings = await _embed_in_batches(embedder, texts, batch_size)
    for chunk, emb in zip(all_chunks, embeddings):
        chunk.embedding = emb

    await asyncio.gather(
        vector_store.upsert_chunks(all_chunks),
        asyncio.to_thread(bm25_index.add, all_chunks),
    )
    return len(all_chunks)