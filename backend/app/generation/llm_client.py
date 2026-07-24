"""
LLM client wrappers. Each provider implements ONE primitive -
complete_json(system_prompt, user_message) -> dict - which handles the
HTTP call, rate limiting, retries, and JSON parsing for that provider.

generate_answer() (RAG synthesis) and the LLM-based reranker
(retrieval/reranker.py) both build on top of this same primitive with
their own system prompts, rather than each provider needing separate
HTTP/retry code for every use case. This is the single switch point
for "which provider is active" - see get_llm_client() at the bottom.
"""
import json
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings
from app.core.rate_limit import RateLimiter, is_permanent_zero_quota, retry_with_backoff
from app.generation.prompts import SYSTEM_PROMPT, build_user_message
from app.models.schemas import GeneratedAnswer, RetrievedChunk


class LLMGenerationError(RuntimeError):
    pass


class _MalformedJSONError(LLMGenerationError):
    """Distinct from network/timeout failures - only this is worth a
    fresh retry (re-asking the model), since a timeout retrying the
    exact same slow call is pointless and just wastes the user's time."""


class _RateLimitError(RuntimeError):
    """Internal marker so retry_with_backoff can distinguish a 429 from
    any other failure, while still carrying the raw error body."""


_gemini_limiter: RateLimiter | None = None


def _get_gemini_limiter(rpm: int) -> RateLimiter:
    global _gemini_limiter
    if _gemini_limiter is None:
        _gemini_limiter = RateLimiter(max_per_minute=rpm)
    return _gemini_limiter


def _parse_json_dict(raw_text: str, error_cls: type[LLMGenerationError] = LLMGenerationError) -> dict:
    cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise error_cls(f"Model did not return valid JSON: {e}\nRaw: {raw_text[:500]}") from e


class LLMClient(ABC):
    @abstractmethod
    async def complete_json(self, system_prompt: str, user_message: str) -> dict:
        """Call the provider with the given prompts, return the parsed
        JSON response body as a plain dict. Raises LLMGenerationError
        (or a subclass) on any unrecoverable failure."""
        ...

    async def generate_answer(self, query: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        """Grounded RAG synthesis - built on complete_json() with the
        fixed SYSTEM_PROMPT/schema every provider shares."""
        user_message = build_user_message(query, chunks)
        parsed = await self.complete_json(SYSTEM_PROMPT, user_message)
        return GeneratedAnswer(**parsed)


class AnthropicClient(LLMClient):
    def __init__(self, settings: Settings):
        if not settings.anthropic_api_key:
            raise LLMGenerationError("ANTHROPIC_API_KEY is not configured")
        self.api_key = settings.anthropic_api_key
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    async def complete_json(self, system_prompt: str, user_message: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
        if resp.status_code != 200:
            raise LLMGenerationError(f"Anthropic API error {resp.status_code}: {resp.text}")

        data = resp.json()
        raw_text = "".join(block.get("text", "") for block in data.get("content", []))
        return _parse_json_dict(raw_text)


class GeminiClient(LLMClient):
    """Google's free-tier generation model. Requires network access to
    generativelanguage.googleapis.com and GEMINI_API_KEY (from aistudio.google.com).
    Set LLM_MODEL to a Gemini model name, e.g. gemini-2.0-flash.

    Free tier is strictly rate-limited (e.g. 15 RPM on flash models), so
    every call goes through a sliding-window RateLimiter before being
    sent. Both 429 (rate limit/quota) and 503 (transient server
    overload, "model experiencing high demand") are retried using the
    delay Google itself suggests in the error body when present,
    falling back to a default short delay otherwise - except a 429 with
    a permanent `limit: 0` quota, which fails fast instead of retrying,
    since no amount of waiting fixes that one.
    """

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise LLMGenerationError("GEMINI_API_KEY is not configured")
        self.api_key = settings.gemini_api_key
        self.model = settings.llm_model
        self.max_retries = settings.llm_max_retries
        self.max_tokens = settings.llm_max_tokens
        self._limiter = _get_gemini_limiter(settings.gemini_requests_per_minute)

    async def complete_json(self, system_prompt: str, user_message: str) -> dict:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "maxOutputTokens": self.max_tokens,
            },
        }

        async def _call():
            await self._limiter.acquire()
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.post(url, json=body)
            except httpx.TimeoutException as e:
                raise LLMGenerationError(
                    f"Gemini request timed out after 20s ({type(e).__name__}). "
                    f"This usually means Gemini's free tier is under heavy load "
                    f"right now - consider switching LLM_PROVIDER to groq, which "
                    f"is dramatically faster and more consistently available."
                ) from e
            except httpx.HTTPError as e:
                raise LLMGenerationError(
                    f"Network error calling Gemini ({type(e).__name__}): {e or 'no details provided'}"
                ) from e
            if resp.status_code == 429:
                if is_permanent_zero_quota(resp.text):
                    raise LLMGenerationError(
                        f"Gemini model '{self.model}' has zero free-tier quota on this "
                        f"project (limit: 0) - this is a project/billing configuration "
                        f"issue, not a transient rate limit. Generate a fresh key at "
                        f"https://aistudio.google.com/app/apikey, or try a different "
                        f"model name (e.g. gemini-1.5-flash). Raw error: {resp.text}"
                    )
                raise _RateLimitError(resp.text)
            if resp.status_code == 503:
                raise _RateLimitError(resp.text)
            if resp.status_code != 200:
                raise LLMGenerationError(f"Gemini API error {resp.status_code}: {resp.text}")
            return resp.json()

        async def _complete_once() -> dict:
            data = await retry_with_backoff(
                _call,
                max_attempts=self.max_retries,
                is_rate_limit_error=lambda e: isinstance(e, _RateLimitError),
                get_error_body=lambda e: str(e),
            )

            try:
                candidate = data["candidates"][0]
                raw_text = candidate["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                raise LLMGenerationError(f"Unexpected Gemini response shape: {data}") from e

            if candidate.get("finishReason") == "MAX_TOKENS":
                raise LLMGenerationError(
                    f"Gemini response was truncated (finishReason=MAX_TOKENS) before "
                    f"completing valid JSON - increase LLM_MAX_TOKENS (currently "
                    f"{self.max_tokens}) in .env. Partial output: {raw_text[:300]}"
                )

            return _parse_json_dict(raw_text, error_cls=_MalformedJSONError)

        try:
            return await _complete_once()
        except _MalformedJSONError:
            try:
                return await _complete_once()
            except Exception as retry_e:
                raise LLMGenerationError(
                    f"Gemini returned invalid JSON twice in a row: {retry_e}"
                ) from retry_e
        except LLMGenerationError:
            raise
        except Exception as e:
            raise LLMGenerationError(f"Gemini generation failed after retries: {e}") from e


class GroqClient(LLMClient):
    """Groq's free-tier fast inference (Llama/Mixtral-class open models),
    OpenAI-compatible chat completions API. Requires network access to
    api.groq.com and GROQ_API_KEY (from console.groq.com). Set LLM_MODEL
    to a Groq model name, e.g. llama-3.3-70b-versatile."""

    def __init__(self, settings: Settings):
        if not settings.groq_api_key:
            raise LLMGenerationError("GROQ_API_KEY is not configured")
        self.api_key = settings.groq_api_key
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    async def complete_json(self, system_prompt: str, user_message: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": self.max_tokens,
                },
            )
        if resp.status_code != 200:
            raise LLMGenerationError(f"Groq API error {resp.status_code}: {resp.text}")

        data = resp.json()
        try:
            raw_text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMGenerationError(f"Unexpected Groq response shape: {data}") from e
        return _parse_json_dict(raw_text)


def get_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicClient(settings)
    if settings.llm_provider == "gemini":
        return GeminiClient(settings)
    if settings.llm_provider == "groq":
        return GroqClient(settings)
    raise ValueError(f"Unsupported llm_provider: {settings.llm_provider}")
