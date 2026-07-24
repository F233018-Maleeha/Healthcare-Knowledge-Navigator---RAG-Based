from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.generation.llm_client import LLMGenerationError
from app.models.schemas import Chunk, RetrievedChunk
from app.retrieval.reranker import LLMReranker, LexicalOverlapReranker, get_reranker


def _rc(chunk_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(chunk=Chunk(chunk_id=chunk_id, text=text))


class TestLLMRerankerChunkIdScoring:
    """Regression tests for the chunk_id-keyed scoring fix. The
    previous version matched scores back to candidates by a positional
    0-based index the model had to echo back correctly - this failed
    whenever a model used 1-based indexing (a common LLM habit),
    silently shifting every score onto the wrong neighboring
    candidate. See reranker.py's module docstring for the full
    explanation, and the diagnostic simulation in
    tests/test_reranker_fix_verification.py that reproduced the exact
    reported symptom against the old logic.
    """

    @pytest.mark.asyncio
    async def test_relevant_document_ranks_first_by_chunk_id(self):
        """The exact real-world scenario that was reported broken:
        a DAPT/PCI question with the genuinely relevant document mixed
        among several plausible-but-irrelevant cardiology candidates."""
        settings = Settings(llm_provider="anthropic", anthropic_api_key="test-key")
        reranker = LLMReranker(settings)

        candidates = [
            _rc("doc-05::c1", "STEMI reperfusion timing and door-to-balloon benchmarks"),
            _rc("doc-07::c1", "Dual antiplatelet therapy duration after PCI stent placement"),
            _rc("doc-02::c1", "ASCVD risk and statin therapy for primary prevention"),
            _rc("doc-10::c1", "Cardiac rehabilitation referral after myocardial infarction"),
        ]
        mock_response = {"scores": [
            {"chunk_id": "doc-05::c1", "relevance": 0.1},
            {"chunk_id": "doc-07::c1", "relevance": 0.95},
            {"chunk_id": "doc-02::c1", "relevance": 0.05},
            {"chunk_id": "doc-10::c1", "relevance": 0.1},
        ]}

        with patch("app.retrieval.reranker.get_llm_client") as mock_get_client:
            mock_get_client.return_value.complete_json = AsyncMock(return_value=mock_response)
            result = await reranker.rerank(
                "How long should dual antiplatelet therapy continue after PCI?",
                candidates, top_k=4,
            )

        assert result[0].chunk.chunk_id == "doc-07::c1"
        assert result[0].rerank_score == 0.95

    @pytest.mark.asyncio
    async def test_scores_immune_to_response_order_being_shuffled(self):
        """Since matching is by chunk_id, not position, the model
        returning entries in a different order than the candidates
        were presented in must not affect correctness at all."""
        settings = Settings(llm_provider="anthropic", anthropic_api_key="test-key")
        reranker = LLMReranker(settings)
        candidates = [_rc("a", "text a"), _rc("b", "text b"), _rc("c", "text c")]

        # Deliberately out of order relative to `candidates` above.
        mock_response = {"scores": [
            {"chunk_id": "c", "relevance": 0.9},
            {"chunk_id": "a", "relevance": 0.1},
            {"chunk_id": "b", "relevance": 0.5},
        ]}
        with patch("app.retrieval.reranker.get_llm_client") as mock_get_client:
            mock_get_client.return_value.complete_json = AsyncMock(return_value=mock_response)
            result = await reranker.rerank("query", candidates, top_k=3)

        assert [rc.chunk.chunk_id for rc in result] == ["c", "b", "a"]

    @pytest.mark.asyncio
    async def test_ignores_invented_chunk_ids_not_in_the_original_candidates(self):
        """If the model hallucinates a chunk_id we never sent, that
        entry must be silently ignored rather than corrupting results."""
        settings = Settings(llm_provider="anthropic", anthropic_api_key="test-key")
        reranker = LLMReranker(settings)
        candidates = [_rc("real-1", "text")]

        mock_response = {"scores": [
            {"chunk_id": "real-1", "relevance": 0.8},
            {"chunk_id": "hallucinated-id-not-sent", "relevance": 0.99},
        ]}
        with patch("app.retrieval.reranker.get_llm_client") as mock_get_client:
            mock_get_client.return_value.complete_json = AsyncMock(return_value=mock_response)
            result = await reranker.rerank("query", candidates, top_k=1)

        assert len(result) == 1
        assert result[0].rerank_score == 0.8

    @pytest.mark.asyncio
    async def test_missing_chunk_id_gets_conservative_default_not_zero(self):
        settings = Settings(llm_provider="anthropic", anthropic_api_key="test-key")
        reranker = LLMReranker(settings)
        candidates = [_rc("scored", "text"), _rc("unscored", "text")]

        mock_response = {"scores": [{"chunk_id": "scored", "relevance": 0.7}]}
        with patch("app.retrieval.reranker.get_llm_client") as mock_get_client:
            mock_get_client.return_value.complete_json = AsyncMock(return_value=mock_response)
            result = await reranker.rerank("query", candidates, top_k=2)

        unscored = next(rc for rc in result if rc.chunk.chunk_id == "unscored")
        assert unscored.rerank_score == 0.2

    @pytest.mark.asyncio
    async def test_falls_back_to_lexical_on_total_failure(self):
        settings = Settings(llm_provider="anthropic", anthropic_api_key="test-key")
        reranker = LLMReranker(settings)
        candidates = [_rc("a", "dual antiplatelet therapy"), _rc("b", "unrelated text")]

        with patch("app.retrieval.reranker.get_llm_client") as mock_get_client:
            mock_get_client.return_value.complete_json = AsyncMock(
                side_effect=RuntimeError("network error")
            )
            result = await reranker.rerank("dual antiplatelet therapy", candidates, top_k=2)

        assert len(result) == 2  # degraded gracefully, didn't crash


def test_get_reranker_factory_selects_by_config():
    llm_settings = Settings(reranker_provider="llm", llm_provider="anthropic", anthropic_api_key="x")
    assert isinstance(get_reranker(llm_settings), LLMReranker)

    lexical_settings = Settings(reranker_provider="lexical")
    assert isinstance(get_reranker(lexical_settings), LexicalOverlapReranker)