# main.py
import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api import routes_feedback, routes_ingest, routes_query
from app.core.config import get_settings
from app.core.dependencies import get_bm25_index, get_retrieval_pipeline, get_vector_store
from app.core.redis import close_redis_pool, get_redis_pool
from app.db.session import init_db
from app.ingestion.pipeline import ingest_documents
from app.models.schemas import SourceDocument

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_query.router)
app.include_router(routes_ingest.router)
app.include_router(routes_feedback.router)


async def _auto_seed_sample_corpus() -> None:
    if not settings.auto_seed_sample_corpus:
        return
    try:
        vector_store = get_vector_store()
        existing = await vector_store.count()
        if existing > 0:
            logger.info("Vector store already has %d chunks - skipping auto-seed.", existing)
            return

        corpus_path = Path(settings.sample_corpus_path)
        if not corpus_path.exists():
            logger.warning("Sample corpus not found at %s - skipping auto-seed.", corpus_path)
            return

        docs = [SourceDocument(**d) for d in json.loads(corpus_path.read_text())]
        pipeline = get_retrieval_pipeline()
        bm25_index = get_bm25_index()
        count = await ingest_documents(
            docs, pipeline.embedder, vector_store, bm25_index,
            batch_size=settings.embedding_batch_size,
        )
        logger.info("Auto-seeded sample corpus: %d documents, %d chunks.", len(docs), count)
    except Exception:
        logger.exception(
            "Auto-seed of sample corpus failed - the app will still start, but /query will find no sources until you ingest data manually."
        )


@app.on_event("startup")
async def _on_startup() -> None:
    try:
        await init_db()
    except Exception:
        logger.exception("init_db() failed at startup.")

    await _auto_seed_sample_corpus()


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    await close_redis_pool()


@app.get("/health")
async def health() -> dict:
    redis_status = "healthy"
    try:
        client = Redis(connection_pool=get_redis_pool())
        await client.ping()
        await client.aclose()
    except Exception:
        redis_status = "unreachable"

    return {
        "status": "ok",
        "environment": settings.environment,
        "redis": redis_status,
    }