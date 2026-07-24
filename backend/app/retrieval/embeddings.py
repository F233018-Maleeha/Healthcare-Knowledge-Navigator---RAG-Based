"""
Embedding provider abstraction (roadmap Section 4.3).

Swap providers purely via config/env - no other code changes needed.
`LocalStubEmbedder` is a deterministic hash-based bag-of-words embedder
used for local dev/testing where no network access to an embedding API
is available. It is NOT semantically meaningful and must be replaced
before any real evaluation - see OpenAIEmbedder / VoyageEmbedder /
LocalSemanticEmbedder for real semantic options.
"""
import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.core.config import Settings
from app.core.rate_limit import RateLimiter


class EmbeddingGenerationError(RuntimeError):
    """Raised on any unrecoverable embedding-provider failure, so callers
    (routes_ingest.py, routes_query.py) can catch this specific type and
    return a clean error response instead of a raw, opaque 500."""


class EmbeddingProvider(ABC):
    dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class LocalSemanticEmbedder(EmbeddingProvider):
    """Generates real clinical semantic embeddings locally on CPU, for
    free, with zero network dependency and zero rate limits/quotas -
    this permanently sidesteps the class of problem hit repeatedly
    with Gemini's free tier.

    `sentence-transformers` (and its dependency, torch) is imported
    lazily inside __init__, not at module level - so installing it is
    only required if you actually select this provider. Every other
    provider in this module follows the same lazy-import pattern for
    its own heavy/optional dependency (see the various `import httpx`
    calls inside each class's own methods).
    """

    def __init__(self, model_name: str = "pritamdeka/S-PubMedBert-MS-MARCO"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dim = 768  

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        embeddings = await asyncio.to_thread(
            self.model.encode, texts, batch_size=8, convert_to_numpy=True
        )
        return embeddings.tolist()


class LocalStubEmbedder(EmbeddingProvider):
    """Deterministic hashing embedder for offline dev/testing only.

    Implements a simple hashed bag-of-words -> fixed-dim vector, L2
    normalized. Captures crude lexical overlap, nothing semantic. This
    exists so the rest of the pipeline (vector store, hybrid fusion,
    reranking) can be built and tested without a network-reachable
    embedding API.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class OpenAIEmbedder(EmbeddingProvider):
    """Real production embedder. Requires network access to
    api.openai.com and OPENAI_API_KEY. Not exercised in this sandbox."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-large", dim: int = 3072):
        self.api_key = api_key
        self.model = model
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
            )
            if resp.status_code != 200:
                raise EmbeddingGenerationError(
                    f"OpenAI embeddings error {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class VoyageEmbedder(EmbeddingProvider):
    """Real production embedder alternative (voyage-3 etc). Requires
    network access to api.voyageai.com and VOYAGE_API_KEY."""

    def __init__(self, api_key: str, model: str = "voyage-3", dim: int = 1024):
        self.api_key = api_key
        self.model = model
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
            )
            if resp.status_code != 200:
                raise EmbeddingGenerationError(
                    f"Voyage embeddings error {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class CohereEmbedder(EmbeddingProvider):
    """Real production embedder alternative. Requires network access to
    api.cohere.com and COHERE_API_KEY. Free trial key: 2,000 inputs/min,
    1,000 calls/month across all Cohere endpoints (verified 2026)."""

    def __init__(self, api_key: str, model: str = "embed-english-v3.0", dim: int = 1024):
        self.api_key = api_key
        self.model = model
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.cohere.com/v1/embed",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "texts": texts, "input_type": "search_document"},
            )
            if resp.status_code != 200:
                raise EmbeddingGenerationError(f"Cohere embeddings error {resp.status_code}: {resp.text}")
            data = resp.json()
            return data["embeddings"]


class GeminiEmbedder(EmbeddingProvider):
    """Google's free-tier embedder. Requires network access to
    generativelanguage.googleapis.com and GEMINI_API_KEY (aistudio.google.com).

    Shares the same free-tier RPM quota bucket as GeminiClient generation
    calls, so it goes through a rate limiter too - see llm_client.py for
    the identical pattern.
    """

    def __init__(self, api_key: str, model: str = "text-embedding-004", dim: int = 768,
                 requests_per_minute: int = 12, max_retries: int = 3):
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.max_retries = max_retries
        self._limiter = RateLimiter(max_per_minute=requests_per_minute)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        from app.core.rate_limit import is_permanent_zero_quota, retry_with_backoff

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:batchEmbedContents?key={self.api_key}"
        )
        requests_body = [
            {"model": f"models/{self.model}", "content": {"parts": [{"text": t}]}} for t in texts
        ]

        class _RateLimitError(RuntimeError):
            pass

        async def _call():
            await self._limiter.acquire()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json={"requests": requests_body})
            if resp.status_code == 429:
                if is_permanent_zero_quota(resp.text):
                    raise EmbeddingGenerationError(
                        f"Gemini embedding model '{self.model}' has zero free-tier quota "
                        f"on this project (limit: 0) - a project/billing configuration "
                        f"issue, not a transient rate limit. Raw error: {resp.text}"
                    )
                raise _RateLimitError(resp.text)
            if resp.status_code != 200:
                raise EmbeddingGenerationError(f"Gemini embeddings error {resp.status_code}: {resp.text}")
            return resp.json()

        try:
            data = await retry_with_backoff(
                _call,
                max_attempts=self.max_retries,
                is_rate_limit_error=lambda e: isinstance(e, _RateLimitError),
                get_error_body=lambda e: str(e),
            )
        except EmbeddingGenerationError:
            raise
        except Exception as e:
            raise EmbeddingGenerationError(f"Gemini embedding failed after retries: {e}") from e

        return [e["values"] for e in data["embeddings"]]


def get_embedder(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "local_stub":
        return LocalStubEmbedder(dim=settings.embedding_dim)
    if settings.embedding_provider == "local_semantic":
        return LocalSemanticEmbedder()
    if settings.embedding_provider == "openai":
        assert settings.embedding_api_key, "embedding_api_key required for openai provider"
        return OpenAIEmbedder(api_key=settings.embedding_api_key, model=settings.embedding_model)
    if settings.embedding_provider == "voyage":
        assert settings.embedding_api_key, "embedding_api_key required for voyage provider"
        return VoyageEmbedder(api_key=settings.embedding_api_key, model=settings.embedding_model)
    if settings.embedding_provider == "cohere":
        assert settings.embedding_api_key, "embedding_api_key required for cohere provider"
        return CohereEmbedder(api_key=settings.embedding_api_key, model=settings.embedding_model)
    if settings.embedding_provider == "gemini":
        assert settings.embedding_api_key, "embedding_api_key required for gemini provider"
        return GeminiEmbedder(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            requests_per_minute=settings.embedding_requests_per_minute,
            max_retries=settings.embedding_max_retries,
        )
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")