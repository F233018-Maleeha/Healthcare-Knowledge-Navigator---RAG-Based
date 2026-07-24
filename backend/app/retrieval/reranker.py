"""
Reranking (roadmap Section 4.5).

The dense+sparse fusion stage is good at *finding* plausible candidates
but not at judging fine-grained relevance to the specific question -
this is what reranking is for. The previous implementation was a
lexical token-overlap proxy, which testing showed is actively
unreliable: an irrelevant query scored HIGHER than a genuinely
relevant one (see tests/test_reranker.py for the exact case). This
replaces it with real semantic scoring.

LLMReranker uses whatever LLM provider is already configured for
generation (get_llm_client) via the shared complete_json() primitive
(see generation/llm_client.py) - no separate API key, no new service
to set up. One batched call scores every candidate at once, so cost
and latency stay comparable to a single generation call rather than
scaling per-candidate.

IMPORTANT: scores are matched back to candidates by chunk_id (a
stable, unique string we already control), NOT by positional index.
An earlier version asked the model to echo back a 0-based integer
index alongside each score - this was fragile because LLMs commonly
default to 1-based indexing out of habit even when shown 0-based
examples, silently shifting every score onto the WRONG neighboring
candidate. That bug was invisible in aggregate testing (the reranker
still "worked" on average) but showed up exactly as reported: a
genuinely relevant document ranking below irrelevant ones on some
queries, because its score had actually been assigned to a
neighboring candidate. Keying by chunk_id removes the entire class of
off-by-one/indexing-convention bugs, since there is no integer
translation involved at all.
"""
import logging
from abc import ABC, abstractmethod

from app.core.config import Settings
from app.generation.llm_client import LLMGenerationError, get_llm_client
from app.models.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

RERANK_SYSTEM_PROMPT = """You are a relevance-scoring assistant for a clinical evidence retrieval \
system. Given a clinician's question and a list of candidate source excerpts (each labeled with a \
unique id in brackets), score how relevant each excerpt is to actually answering that SPECIFIC \
question - not just whether it's generally in the same topic area. A source about a \
related-but-different condition, or the wrong sub-topic within the same specialty, should score low \
even though it may share vocabulary with the question.

Score each excerpt from 0.0 (irrelevant) to 1.0 (directly and specifically relevant).

Respond with ONLY a raw JSON object, no markdown fences, no preamble, matching exactly this schema:
{"scores": [{"chunk_id": "<the exact id shown in brackets>", "relevance": 0.0}, ...]}
Copy each chunk_id EXACTLY as shown in its bracket label - do not renumber, reorder, or invent your \
own ids. Include one entry per candidate; the order of entries in your response does not matter."""


class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        ...


class LexicalOverlapReranker(Reranker):
    """Zero-network, zero-cost fallback only. NOT a reliable relevance
    signal on its own - see the calibration test in
    tests/test_reranker.py, where a genuinely irrelevant query scored
    higher than a relevant one. Used as: (a) the offline/dev option
    when reranker_provider=lexical, and (b) an automatic fallback if
    the LLM reranker call fails for any reason, so a reranking hiccup
    never breaks retrieval entirely.
    """

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        q_tokens = set(query.lower().split())

        def overlap_score(rc: RetrievedChunk) -> float:
            t_tokens = set(rc.chunk.text.lower().split())
            if not t_tokens:
                return 0.0
            return len(q_tokens & t_tokens) / len(q_tokens | t_tokens)

        for rc in candidates:
            rc.rerank_score = overlap_score(rc)
        candidates.sort(key=lambda r: r.rerank_score or 0.0, reverse=True)
        return candidates[:top_k]


class LLMReranker(Reranker):
    """Real semantic reranking via the already-configured LLM provider."""

    def __init__(self, settings: Settings, max_candidates: int = 24):
        self.settings = settings
        self.max_candidates = max_candidates
        self._fallback = LexicalOverlapReranker()

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []

        effective_cap = max(self.max_candidates, top_k)
        scoring_set = candidates[:effective_cap]

        try:
            scores_by_id = await self._score(query, scoring_set)
        except Exception as e:
            logger.warning(
                "LLM reranker failed (%s) - falling back to lexical overlap for this query.", e
            )
            return await self._fallback.rerank(query, candidates, top_k)

        default_score = 0.2
        for rc in scoring_set:
            rc.rerank_score = scores_by_id.get(rc.chunk.chunk_id, default_score)

        scoring_set.sort(key=lambda r: r.rerank_score or 0.0, reverse=True)
        return scoring_set[:top_k]

    async def _score(self, query: str, candidates: list[RetrievedChunk]) -> dict[str, float]:
        """Returns a dict of {chunk_id: relevance_score}. Keying by the
        candidate's own chunk_id (rather than a positional index the
        model has to echo back correctly) is what makes this immune to
        the off-by-one/indexing-convention bug described in the module
        docstring - see there for the full explanation."""
        # Truncate each candidate's text for the scoring prompt - we
        # only need enough to judge relevance, not the full excerpt
        # (which the generation step gets in full separately).
        listing = "\n".join(
            f"[{rc.chunk.chunk_id}] {rc.chunk.text[:400]}" for rc in candidates
        )
        user_message = f"Clinician question: {query}\n\nCandidate excerpts:\n{listing}"

        llm = get_llm_client(self.settings)
        parsed = await llm.complete_json(RERANK_SYSTEM_PROMPT, user_message)
        raw_scores = parsed.get("scores")

        if not isinstance(raw_scores, list) or not raw_scores:
            raise LLMGenerationError(f"Reranker returned no usable scores: {parsed}")

        valid_ids = {rc.chunk.chunk_id for rc in candidates}
        by_id: dict[str, float] = {}
        for entry in raw_scores:
            if not isinstance(entry, dict):
                continue
            chunk_id = entry.get("chunk_id")
            relevance = entry.get("relevance")
            if (
                isinstance(chunk_id, str)
                and chunk_id in valid_ids  # ignore any id the model invented that we didn't send
                and isinstance(relevance, (int, float))
            ):
                by_id[chunk_id] = float(relevance)

        if not by_id:
            raise LLMGenerationError(
                f"Reranker response had no valid chunk_id/relevance entries matching our "
                f"candidates: {parsed}"
            )

        return by_id


def get_reranker(settings: Settings) -> Reranker:
    if settings.reranker_provider == "llm":
        return LLMReranker(settings)
    if settings.reranker_provider == "lexical":
        return LexicalOverlapReranker()
    raise ValueError(f"Unsupported reranker_provider: {settings.reranker_provider}")