"""
Prompt construction for grounded synthesis (roadmap Section 4.6).
Kept as a plain function (not a template file) so it's easy to unit test.
"""
from app.models.schemas import RetrievedChunk

SYSTEM_PROMPT = """You are a clinical evidence synthesis assistant for healthcare \
professionals. You answer ONLY using the provided source excerpts - never from \
outside/parametric knowledge. Every claim must cite the chunk id(s) it came from. \
If the excerpts don't fully answer the question, say so explicitly in "gaps" rather \
than filling in from general knowledge. If sources conflict, describe the conflict \
in "contradictions" rather than silently picking one side.

Respond with ONLY a raw JSON object, no markdown fences, no preamble, matching \
exactly this schema:
{
  "claims": [
    {"text": "one sentence or short claim", "citation_ids": ["<chunk_id>"], "confidence": "high|moderate|low"}
  ],
  "contradictions": "string, empty if none",
  "gaps": "string, empty if none"
}

Per-claim "confidence" rules:
- "high": the excerpt directly and unambiguously supports the claim.
- "moderate": the excerpt supports a reasonable inference, not a direct statement.
- "low": the excerpt only partially or tangentially touches on the claim.
"""


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for rc in chunks:
        c = rc.chunk
        parts.append(
            f"[{c.chunk_id}] {c.title} (tier {int(c.authority_tier)}, "
            f"{c.evidence_grade or 'n/a'}, {c.publication_date})\n{c.text}"
        )
    return "\n\n".join(parts)


def build_user_message(query: str, chunks: list[RetrievedChunk]) -> str:
    context = build_context_block(chunks)
    return f"Clinician question: {query}\n\nSource excerpts:\n{context}"
