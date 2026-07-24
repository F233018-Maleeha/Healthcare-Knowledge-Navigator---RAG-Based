"""
Central configuration for the Healthcare Knowledge Navigator backend.

Every external dependency (LLM provider, embedding provider, vector store,
Postgres) is driven off environment variables so the same codebase runs
in local dev (docker-compose), CI, and production without code changes.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True
    )

    # --- App ---
    app_name: str = "Healthcare Knowledge Navigator"
    environment: Literal["development", "staging", "production"] = "production"
    log_level: str = "INFO"

    # --- Auth ---
    jwt_secret: str = Field(default="dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- Postgres (metadata, audit log, feedback) ---
    postgres_dsn: str = "postgresql+asyncpg://hkn:hkn@localhost:5432/hkn"

    # --- Vector store ---
    vector_backend: Literal["qdrant", "memory"] = "qdrant"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "hkn_chunks"

    # --- Embeddings ---
    embedding_provider: Literal["openai", "voyage", "cohere", "gemini", "local_stub","local_semantic"] = "local_semantic"
    embedding_model: str = "text-embedding-3-large"
    embedding_api_key: str | None = None
    embedding_dim: int = 768
    embedding_batch_size: int = 50

    # --- Generation (LLM) ---
    llm_provider: Literal["anthropic", "gemini", "groq"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    llm_max_tokens: int = 1024

    # --- Retrieval tuning ---
    retrieval_dense_top_k: int = 15
    retrieval_sparse_top_k: int = 15
    retrieval_final_top_k: int = 5
    rerank_enabled: bool = True
    reranker_provider: Literal["llm", "lexical"] = "llm"

    # --- Confidence scoring weights (must sum to 1.0) ---
    weight_retrieval_agreement: float = 0.30
    weight_source_authority: float = 0.25
    weight_recency: float = 0.15
    weight_self_rating: float = 0.30

    # --- Free-tier rate limiting (Gemini free tier: e.g. 15 RPM on flash models) ---
    gemini_requests_per_minute: int = 12 
    llm_max_retries: int = 2

    embedding_requests_per_minute: int = 6
    embedding_max_retries: int = 5

    # --- Redis (rate limiting / caching / queue) ---
    redis_url: str = "redis://localhost:6379/0"

    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]
    auto_seed_sample_corpus: bool = True
    sample_corpus_path: str = "data/sample_corpus/cardiology_demo_corpus.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()