"""
Structure-aware chunking (roadmap Section 4.2).

Not naive fixed-size splitting: we first try to split on recognizable
clinical section headers, then fall back to a sliding window with
overlap for unstructured prose. Target ~300-500 tokens/chunk (approximated
here by whitespace-token count, which is close enough for chunk sizing
without pulling in a real tokenizer dependency at this stage).
"""
import re
from dataclasses import dataclass

from app.models.schemas import Chunk, SourceDocument

SECTION_PATTERNS: dict[str, str] = {
    "recommendation": r"(?im)^\s*(recommendation[s]?|guidance)\s*:?\s*$",
    "dosing": r"(?im)^\s*(dos(e|ing|age)|administration)\s*:?\s*$",
    "contraindication": r"(?im)^\s*(contraindication[s]?|warnings?|precautions?)\s*:?\s*$",
    "evidence": r"(?im)^\s*(evidence|rationale|discussion)\s*:?\s*$",
    "background": r"(?im)^\s*(background|introduction|overview)\s*:?\s*$",
}

TARGET_TOKENS = 300
OVERLAP_TOKENS = 50


@dataclass
class RawSection:
    section_type: str
    text: str


def _split_into_sections(full_text: str) -> list[RawSection]:
    """Split on recognized headers; anything before the first header (or if
    no headers are found at all) is tagged 'other'."""
    markers: list[tuple[int, int, str]] = []  # (match_start, match_end, section_type)
    for section_type, pattern in SECTION_PATTERNS.items():
        for m in re.finditer(pattern, full_text):
            markers.append((m.start(), m.end(), section_type))
    if not markers:
        return [RawSection("other", full_text)]

    markers.sort(key=lambda x: x[0])
    sections: list[RawSection] = []
    for i, (start, header_end, section_type) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(full_text)

        body = full_text[header_end:end].strip()
        if body:
            sections.append(RawSection(section_type, body))

    if markers[0][0] > 0:
        preamble = full_text[: markers[0][0]].strip()
        if preamble:
            sections.insert(0, RawSection("background", preamble))
    return sections


def _sliding_window(text: str, target_tokens: int, overlap_tokens: int) -> list[str]:
    tokens = text.split()
    if len(tokens) <= target_tokens:
        return [text]
    chunks = []
    step = target_tokens - overlap_tokens
    for start in range(0, len(tokens), step):
        window = tokens[start : start + target_tokens]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + target_tokens >= len(tokens):
            break
    return chunks


def chunk_document(doc: SourceDocument) -> list[Chunk]:
    """Produce retrievable Chunk objects from a SourceDocument."""
    sections = _split_into_sections(doc.full_text)
    chunks: list[Chunk] = []
    counter = 0
    for section in sections:
        for piece in _sliding_window(section.text, TARGET_TOKENS, OVERLAP_TOKENS):
            counter += 1
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}::c{counter}",
                    doc_id=doc.doc_id,
                    section_type=section.section_type, 
                    text=piece,
                    title=doc.title,
                    source=doc.source,
                    authority_tier=doc.authority_tier,
                    evidence_grade=doc.evidence_grade,
                    publication_date=doc.publication_date,
                    specialty=doc.specialty,
                )
            )
    return chunks
