"""
Core data contracts. These mirror the metadata schema specified in the
roadmap (Section 3) and are the single source of truth every layer
(ingestion, retrieval, generation, API) imports from.
"""
from datetime import date
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field


class AuthorityTier(IntEnum):
    """1 = systematic review / clinical guideline, 4 = single case report."""
    GUIDELINE_OR_META_ANALYSIS = 1
    SYSTEMATIC_REVIEW = 2
    PRIMARY_STUDY = 3
    CASE_REPORT_OR_EXPERT_OPINION = 4


class SourceDocument(BaseModel):
    """A single ingested document (guideline, paper, protocol) before chunking."""
    doc_id: str
    title: str
    source: str  # e.g. "PubMed", "NICE", "WHO", "CDC", "UpToDate"
    specialty: list[str] = Field(default_factory=list)
    authority_tier: AuthorityTier
    evidence_grade: str | None = None  # e.g. "GRADE A", "Level B"
    publication_date: date
    last_reviewed_date: date | None = None
    url_or_doi: str | None = None
    license: Literal["open", "restricted"] = "open"
    retracted: bool = False
    full_text: str


class Chunk(BaseModel):
    """A retrievable unit derived from a SourceDocument."""
    chunk_id: str
    doc_id: str
    section_type: Literal[
        "recommendation", "background", "dosing", "contraindication",
        "evidence", "other"
    ] = "other"
    text: str
    title: str
    source: str
    authority_tier: AuthorityTier
    evidence_grade: str | None = None
    publication_date: date
    specialty: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None


class RetrievedChunk(BaseModel):
    chunk: Chunk
    dense_score: float | None = None
    sparse_score: float | None = None
    fused_score: float | None = None
    rerank_score: float | None = None


class ClaimConfidence(str):
    pass


class Claim(BaseModel):
    text: str
    citation_ids: list[str]
    confidence: Literal["high", "moderate", "low"]


class ConfidenceBreakdown(BaseModel):
    retrieval_agreement: float
    source_authority: float
    recency: float
    self_rating: float


class ConfidenceResult(BaseModel):
    label: Literal["high", "moderate", "low"]
    score: int  # 0-100
    breakdown: ConfidenceBreakdown


class GeneratedAnswer(BaseModel):
    claims: list[Claim]
    contradictions: str = ""
    gaps: str = ""


class QueryRequest(BaseModel):
    query: str
    specialty_filter: list[str] | None = None
    top_k: int | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "How long should DAPT continue after PCI?",
                    "specialty_filter": None,
                    "top_k": None,
                }
            ]
        }
    }


class QueryResponse(BaseModel):
    query: str
    answer: GeneratedAnswer
    confidence: ConfidenceResult
    retrieved_chunks: list[RetrievedChunk]
    request_id: str


class FeedbackRequest(BaseModel):
    request_id: str
    rating: Literal["helpful", "not_helpful", "incorrect"]
    comment: str | None = None
