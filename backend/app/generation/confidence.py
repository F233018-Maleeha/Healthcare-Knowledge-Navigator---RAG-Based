"""
Composite confidence scoring (roadmap Section 4.7).

Deliberately NOT a single opaque number: we compute four independent
sub-scores and combine them with configurable weights, and always
surface the breakdown to the caller so a clinician can see *why* the
system is or isn't confident.
"""
from datetime import date

from app.core.config import Settings
from app.models.schemas import Claim, ConfidenceBreakdown, ConfidenceResult, RetrievedChunk

_CLAIM_CONF_TO_NUM = {"high": 1.0, "moderate": 0.6, "low": 0.25}


def _recency_score(pub_date: date, today: date | None = None) -> float:
    today = today or date.today()
    age_years = (today - pub_date).days / 365.25
    if age_years <= 2:
        return 1.0
    if age_years <= 4:
        return 0.7
    if age_years <= 6:
        return 0.45
    return 0.2


def _authority_score(tier: int) -> float:
    """tier 1 (guideline/meta-analysis) -> 1.0, tier 4 (case report) -> 0.25."""
    return (5 - tier) / 4


def compute_confidence(
    retrieved: list[RetrievedChunk],
    claims: list[Claim],
    settings: Settings,
    today: date | None = None,
) -> ConfidenceResult:
    if not retrieved:
        return ConfidenceResult(
            label="low",
            score=0,
            breakdown=ConfidenceBreakdown(retrieval_agreement=0, source_authority=0, recency=0, self_rating=0),
        )

    if not claims:
        return ConfidenceResult(
            label="low",
            score=0,
            breakdown=ConfidenceBreakdown(retrieval_agreement=0, source_authority=0, recency=0, self_rating=0),
        )

    distinct_docs = {rc.chunk.doc_id for rc in retrieved}
    agreement = min(1.0, len(distinct_docs) / 3)  # 3+ independent sources = full credit

    authority = sum(_authority_score(int(rc.chunk.authority_tier)) for rc in retrieved) / len(retrieved)
    recency = sum(_recency_score(rc.chunk.publication_date, today) for rc in retrieved) / len(retrieved)

    self_rating = sum(_CLAIM_CONF_TO_NUM[c.confidence] for c in claims) / len(claims)

    composite = (
        settings.weight_retrieval_agreement * agreement
        + settings.weight_source_authority * authority
        + settings.weight_recency * recency
        + settings.weight_self_rating * self_rating
    )

    label = "high" if composite >= 0.72 else "moderate" if composite >= 0.45 else "low"

    return ConfidenceResult(
        label=label,
        score=round(composite * 100),
        breakdown=ConfidenceBreakdown(
            retrieval_agreement=round(agreement * 100),
            source_authority=round(authority * 100),
            recency=round(recency * 100),
            self_rating=round(self_rating * 100),
        ),
    )
