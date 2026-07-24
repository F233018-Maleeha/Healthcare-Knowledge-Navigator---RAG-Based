"""
Vector store abstraction (roadmap Section 4.4).

Uses Qdrant's AsyncQdrantClient throughout - this matters for real
concurrent load: the previous version used the synchronous client
inside an async app, which meant every vector search blocked the whole
FastAPI event loop on network I/O once talking to a real Qdrant server
(as opposed to in-memory mode, where it happened to be harmless). With
the async client, one clinician's search waiting on Qdrant no longer
blocks every other clinician's request from even starting.
"""
import asyncio

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchAny, PointStruct, VectorParams

from app.core.config import Settings
from app.models.schemas import Chunk, RetrievedChunk


class VectorStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.collection = settings.qdrant_collection
        self.dim = settings.embedding_dim
        if settings.vector_backend == "memory":
            self.client = AsyncQdrantClient(":memory:")
        else:
            self.client = AsyncQdrantClient(
                url=settings.qdrant_url, 
                api_key=settings.qdrant_api_key
            )
        self._collection_ready = False
        self._ready_lock = asyncio.Lock()

    async def _ensure_collection(self) -> None:
        if self._collection_ready:
            return
        async with self._ready_lock:
            if self._collection_ready:  # re-check after acquiring the lock
                return
            existing = [c.name for c in (await self.client.get_collections()).collections]
            if self.collection not in existing:
                await self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
                )
            self._collection_ready = True

    async def count(self) -> int:
        await self._ensure_collection()
        result = await self.client.count(collection_name=self.collection, exact=True)
        return result.count

    async def upsert_chunks(self, chunks: list[Chunk]) -> int:
        await self._ensure_collection()
        points = []
        for chunk in chunks:
            assert chunk.embedding is not None, f"chunk {chunk.chunk_id} missing embedding"
            points.append(
                PointStruct(
                    id=abs(hash(chunk.chunk_id)) % (2**63),
                    vector=chunk.embedding,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "section_type": chunk.section_type,
                        "text": chunk.text,
                        "title": chunk.title,
                        "source": chunk.source,
                        "authority_tier": int(chunk.authority_tier),
                        "evidence_grade": chunk.evidence_grade,
                        "publication_date": chunk.publication_date.isoformat(),
                        "specialty": chunk.specialty,
                    },
                )
            )
        await self.client.upsert(collection_name=self.collection, points=points)
        return len(points)

    async def search(
        self, query_vector: list[float], top_k: int, specialty_filter: list[str] | None = None
    ) -> list[RetrievedChunk]:
        await self._ensure_collection()
        query_filter = None
        if specialty_filter:
            query_filter = Filter(
                must=[FieldCondition(key="specialty", match=MatchAny(any=specialty_filter))]
            )
        result = await self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
        )

        results = []
        for hit in result.points:
            p = hit.payload
            chunk = Chunk(
                chunk_id=p["chunk_id"],
                doc_id=p["doc_id"],
                section_type=p["section_type"],
                text=p["text"],
                title=p["title"],
                source=p["source"],
                authority_tier=p["authority_tier"],
                evidence_grade=p.get("evidence_grade"),
                publication_date=p["publication_date"],
                specialty=p.get("specialty", []),
            )
            results.append(RetrievedChunk(chunk=chunk, dense_score=hit.score))
        return results
