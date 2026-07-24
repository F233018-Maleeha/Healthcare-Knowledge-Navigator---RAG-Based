"""
Hybrid retrieval: fuse dense + sparse result lists via Reciprocal Rank
Fusion, then apply a source-diversity filter so the final set isn't
dominated by a single document (roadmap Section 4.5).

Reranking lives in retrieval/reranker.py, not here - see that module
for the real (LLM-based) implementation.
"""
from app.models.schemas import RetrievedChunk


def reciprocal_rank_fusion(
    dense: list[RetrievedChunk], sparse: list[RetrievedChunk], k: int = 60
) -> list[RetrievedChunk]:
    """Standard RRF: score = sum(1 / (k + rank)) across the lists a chunk appears in."""
    scores: dict[str, float] = {}
    by_id: dict[str, RetrievedChunk] = {}

    for rank, rc in enumerate(dense):
        cid = rc.chunk.chunk_id
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        by_id[cid] = rc

    for rank, rc in enumerate(sparse):
        cid = rc.chunk.chunk_id
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        if cid in by_id:
            by_id[cid].sparse_score = rc.sparse_score
        else:
            by_id[cid] = rc

    fused = []
    for cid, score in scores.items():
        rc = by_id[cid]
        rc.fused_score = score
        fused.append(rc)

    fused.sort(key=lambda r: r.fused_score or 0.0, reverse=True)
    return fused


def apply_source_diversity_filter(
    candidates: list[RetrievedChunk], top_k: int, max_per_doc: int = 2
) -> list[RetrievedChunk]:
    """Don't let one document dominate the final context - cap chunks
    per source doc so the model sees a spread of independent evidence."""
    counts: dict[str, int] = {}
    result = []
    for rc in candidates:
        doc_id = rc.chunk.doc_id
        if counts.get(doc_id, 0) >= max_per_doc:
            continue
        counts[doc_id] = counts.get(doc_id, 0) + 1
        result.append(rc)
        if len(result) >= top_k:
            break
    return result
