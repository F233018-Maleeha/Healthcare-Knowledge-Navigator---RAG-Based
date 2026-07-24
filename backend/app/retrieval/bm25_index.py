"""
Sparse (lexical) retrieval via BM25 (roadmap Section 4.5).

Crucial complement to dense retrieval for exact drug names, dosages,
abbreviations, and ICD-style codes that embeddings can blur together.
"""
import re

from rank_bm25 import BM25Okapi

from app.models.schemas import Chunk, RetrievedChunk


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Index:
    def __init__(self):
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None

    def build(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        tokenized = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def add(self, chunks: list[Chunk]) -> None:
        self.build(self._chunks + chunks)

    def search(
        self, query: str, top_k: int, specialty_filter: list[str] | None = None
    ) -> list[RetrievedChunk]:
        if self._bm25 is None or not self._chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        pairs = zip(self._chunks, scores)

        if specialty_filter:
            wanted = set(specialty_filter)
            pairs = (
                (chunk, score) for chunk, score in pairs
                if wanted.intersection(chunk.specialty)
            )

        ranked = sorted(pairs, key=lambda x: x[1], reverse=True)
        return [
            RetrievedChunk(chunk=c, sparse_score=float(s))
            for c, s in ranked[:top_k]
            if s > 0
        ]
