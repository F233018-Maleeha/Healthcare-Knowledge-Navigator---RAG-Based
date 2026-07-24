from datetime import date

from app.core.config import Settings
from app.generation.confidence import compute_confidence
from app.models.schemas import AuthorityTier, Chunk, Claim, RetrievedChunk

settings = Settings()


def _chunk(chunk_id, doc_id, tier, pub_date):
    return Chunk(
        chunk_id=chunk_id, doc_id=doc_id, text="some clinical text",
        title="t", source="s", authority_tier=tier, publication_date=pub_date,
    )


def test_no_sources_yields_zero_low_confidence():
    result = compute_confidence([], [], settings)
    assert result.label == "low"
    assert result.score == 0


def test_retrieved_sources_but_no_claims_yields_low_confidence():
    """Regression test: previously, an empty claims list (the model
    correctly saying 'sources don't cover this') defaulted self_rating
    to a neutral 0.5, letting high-quality-looking retrieved sources
    alone push the score up to 'high' even though nothing was actually
    answered. A gaps-only response must never outscore a real one."""
    retrieved = [
        RetrievedChunk(chunk=_chunk("c1", "d1", AuthorityTier.GUIDELINE_OR_META_ANALYSIS, date(2024, 1, 1))),
        RetrievedChunk(chunk=_chunk("c2", "d2", AuthorityTier.GUIDELINE_OR_META_ANALYSIS, date(2024, 1, 1))),
        RetrievedChunk(chunk=_chunk("c3", "d3", AuthorityTier.GUIDELINE_OR_META_ANALYSIS, date(2024, 1, 1))),
    ]
    result = compute_confidence(retrieved, [], settings)
    assert result.label == "low"
    assert result.score == 0


def test_multiple_recent_high_tier_sources_yield_high_confidence():
    retrieved = [
        RetrievedChunk(chunk=_chunk("c1", "d1", AuthorityTier.GUIDELINE_OR_META_ANALYSIS, date(2024, 1, 1))),
        RetrievedChunk(chunk=_chunk("c2", "d2", AuthorityTier.GUIDELINE_OR_META_ANALYSIS, date(2024, 1, 1))),
        RetrievedChunk(chunk=_chunk("c3", "d3", AuthorityTier.GUIDELINE_OR_META_ANALYSIS, date(2024, 1, 1))),
    ]
    claims = [Claim(text="x", citation_ids=["c1"], confidence="high")]
    result = compute_confidence(retrieved, claims, settings)
    assert result.label == "high"
    assert result.breakdown.retrieval_agreement == 100


def test_single_old_low_tier_source_yields_low_confidence():
    retrieved = [RetrievedChunk(chunk=_chunk("c1", "d1", AuthorityTier.CASE_REPORT_OR_EXPERT_OPINION, date(2010, 1, 1)))]
    claims = [Claim(text="x", citation_ids=["c1"], confidence="low")]
    result = compute_confidence(retrieved, claims, settings)
    assert result.label == "low"


def test_breakdown_fields_present_for_transparency():
    retrieved = [RetrievedChunk(chunk=_chunk("c1", "d1", AuthorityTier.SYSTEMATIC_REVIEW, date(2022, 1, 1)))]
    result = compute_confidence(retrieved, [], settings)
    b = result.breakdown
    assert all(hasattr(b, f) for f in ["retrieval_agreement", "source_authority", "recency", "self_rating"])
