"""
Wires embeddings + vector store + BM25 + fusion + reranking into a
single retrieve() call used by the API layer.
"""
import asyncio

from app.core.config import Settings
from app.models.schemas import RetrievedChunk
from app.retrieval.bm25_index import BM25Index
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.hybrid import apply_source_diversity_filter, reciprocal_rank_fusion
from app.retrieval.reranker import Reranker, get_reranker
from app.retrieval.vector_store import VectorStore


class RetrievalPipeline:
    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        reranker: Reranker | None = None,
    ):
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.reranker = reranker or get_reranker(settings)

    async def _dense_search(self, query: str, specialty_filter: list[str] | None) -> list[RetrievedChunk]:
        [query_vec] = await self.embedder.embed([query])
        return await self.vector_store.search(
            query_vec, top_k=self.settings.retrieval_dense_top_k, specialty_filter=specialty_filter
        )

    async def retrieve(
        self, query: str, specialty_filter: list[str] | None = None, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        final_k = top_k or self.settings.retrieval_final_top_k

        dense, sparse = await asyncio.gather(
            self._dense_search(query, specialty_filter),
            asyncio.to_thread(
                self.bm25_index.search, query, self.settings.retrieval_sparse_top_k, specialty_filter
            ),
        )

        fused = reciprocal_rank_fusion(dense, sparse)

        if self.settings.rerank_enabled:
            fused = await self.reranker.rerank(query, fused, top_k=final_k * 3)

        return apply_source_diversity_filter(fused, top_k=final_k)
