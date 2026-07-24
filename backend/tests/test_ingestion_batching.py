from unittest.mock import AsyncMock

import pytest

from app.ingestion.pipeline import _embed_in_batches


class _RecordingEmbedder:
    """Records the size of every batch it was called with, so tests
    can assert the batching logic actually splits large inputs."""

    def __init__(self):
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[0.0] for _ in texts]


@pytest.mark.asyncio
async def test_embed_in_batches_splits_large_input_into_configured_batch_size():
    embedder = _RecordingEmbedder()
    texts = [f"text {i}" for i in range(45)]

    result = await _embed_in_batches(embedder, texts, batch_size=20)

    assert len(result) == 45
    assert [len(c) for c in embedder.calls] == [20, 20, 5]  # 45 split into 20/20/5, not one call of 45


@pytest.mark.asyncio
async def test_embed_in_batches_single_call_when_under_batch_size():
    embedder = _RecordingEmbedder()
    texts = [f"text {i}" for i in range(5)]

    result = await _embed_in_batches(embedder, texts, batch_size=20)

    assert len(result) == 5
    assert len(embedder.calls) == 1


@pytest.mark.asyncio
async def test_embed_in_batches_handles_empty_input():
    embedder = _RecordingEmbedder()
    result = await _embed_in_batches(embedder, [], batch_size=20)
    assert result == []
    assert embedder.calls == []
