"""
Faithfulness checking (roadmap Section 4.7): verify that each generated
claim is actually supported by the chunk(s) it cites, rather than
trusting the model's citation at face value.

Production version: replace `_entails` with a real NLI model call
(e.g. roberta-large-mnli, or an attribution-scoring model). The
lexical-overlap proxy here keeps the pipeline runnable offline and
gives a meaningful signal even before that model is wired in.
"""
from dataclasses import dataclass

from app.models.schemas import Claim, RetrievedChunk

OVERLAP_SUPPORT_THRESHOLD = 0.15


@dataclass
class FaithfulnessResult:
    claim: Claim
    supported: bool
    max_overlap: float
    missing_citations: list[str]


def _tokens(text: str) -> set[str]:
    return set(w for w in text.lower().split() if len(w) > 2)


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta)


def check_claim(claim: Claim, retrieved_by_id: dict[str, RetrievedChunk]) -> FaithfulnessResult:
    missing = [cid for cid in claim.citation_ids if cid not in retrieved_by_id]
    best_overlap = 0.0
    for cid in claim.citation_ids:
        rc = retrieved_by_id.get(cid)
        if rc is None:
            continue
        best_overlap = max(best_overlap, _overlap(claim.text, rc.chunk.text))
    supported = best_overlap >= OVERLAP_SUPPORT_THRESHOLD and not missing
    return FaithfulnessResult(claim=claim, supported=supported, max_overlap=best_overlap, missing_citations=missing)


def check_all(claims: list[Claim], retrieved: list[RetrievedChunk]) -> list[FaithfulnessResult]:
    retrieved_by_id = {rc.chunk.chunk_id: rc for rc in retrieved}
    return [check_claim(c, retrieved_by_id) for c in claims]
