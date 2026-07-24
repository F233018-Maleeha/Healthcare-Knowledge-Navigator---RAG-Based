# app/api/routes_query.py
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_retrieval_pipeline
from app.core.redis import get_redis
from app.db.models import QueryAuditLog
from app.db.session import get_db_session
from app.generation.confidence import compute_confidence
from app.generation.faithfulness import check_all
from app.generation.llm_client import LLMGenerationError, get_llm_client
from app.models.schemas import GeneratedAnswer, QueryRequest, QueryResponse
from app.retrieval.embeddings import EmbeddingGenerationError
from app.retrieval.pipeline import RetrievalPipeline

router = APIRouter(prefix="/query", tags=["query"])


def _generate_cache_key(req: QueryRequest) -> str:
    """Create a deterministic hash for identical queries and filters."""
    raw = f"{req.query.strip().lower()}:{req.specialty_filter}:{req.top_k}"
    return f"cache:query:{hashlib.sha256(raw.encode()).hexdigest()}"


async def _check_rate_limit(client_ip: str, redis: Redis, limit: int = 30, window_seconds: int = 60) -> None:
    """Sliding rate limiter using Redis keys."""
    key = f"rate_limit:{client_ip}"
    current_requests = await redis.incr(key)
    if current_requests == 1:
        await redis.expire(key, window_seconds)
    
    if current_requests > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {limit} requests per minute."
        )


async def _write_audit_log(
    session: AsyncSession, request_id: str, query_text: str,
    retrieved_chunk_ids: list[str], answer: GeneratedAnswer, confidence,
) -> None:
    try:
        row = QueryAuditLog(
            request_id=request_id,
            query_text=query_text,
            retrieved_chunk_ids=retrieved_chunk_ids,
            answer_json=answer.model_dump(),
            confidence_label=confidence.label,
            confidence_score=confidence.score,
        )
        session.add(row)
        await session.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to write audit log for request_id=%s", request_id)


@router.post("", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> QueryResponse:
    # 1. Enforce Rate Limiting
    # Replace "default_client" with actual client IP or user token if present
    await _check_rate_limit("default_client", redis, limit=30, window_seconds=60)

    # 2. Check Query Cache
    cache_key = _generate_cache_key(req)
    try:
        cached_response = await redis.get(cache_key)
        if cached_response:
            return QueryResponse.model_validate_json(cached_response)
    except Exception:
        pass  # If Redis read fails, proceed to normal retrieval

    request_id = str(uuid.uuid4())

    # 3. Retrieve Documents
    try:
        retrieved = await pipeline.retrieve(
            req.query, specialty_filter=req.specialty_filter, top_k=req.top_k
        )
    except EmbeddingGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if not retrieved:
        empty_answer = GeneratedAnswer(
            claims=[],
            gaps="No relevant sources were found in the corpus for this question.",
        )
        confidence = compute_confidence([], [], settings)
        await _write_audit_log(db, request_id, req.query, [], empty_answer, confidence)
        return QueryResponse(
            query=req.query, answer=empty_answer, confidence=confidence,
            retrieved_chunks=[], request_id=request_id,
        )

    # 4. Generate Answer via LLM
    try:
        llm = get_llm_client(settings)
        answer = await llm.generate_answer(req.query, retrieved)
    except LLMGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    faithfulness = check_all(answer.claims, retrieved)
    for result, claim in zip(faithfulness, answer.claims):
        if not result.supported:
            claim.confidence = "low"

    confidence = compute_confidence(retrieved, answer.claims, settings)

    await _write_audit_log(
        db, request_id, req.query, [rc.chunk.chunk_id for rc in retrieved], answer, confidence
    )

    response_chunks = retrieved if answer.claims else []

    response = QueryResponse(
        query=req.query,
        answer=answer,
        confidence=confidence,
        retrieved_chunks=response_chunks,
        request_id=request_id,
    )

    # 5. Save to Cache (TTL = 1 Hour / 3600 Seconds)
    try:
        await redis.setex(cache_key, 3600, response.model_dump_json())
    except Exception:
        pass

    return response