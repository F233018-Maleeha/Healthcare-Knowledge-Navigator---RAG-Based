from datetime import date

from app.ingestion.chunking import chunk_document
from app.models.schemas import AuthorityTier, SourceDocument
from tests.fixtures import SAMPLE_DOCS


def test_chunking_produces_section_tags():
    chunks = chunk_document(SAMPLE_DOCS[0])
    assert len(chunks) >= 1
    section_types = {c.section_type for c in chunks}
    assert "recommendation" in section_types
    assert "background" in section_types


def test_chunk_ids_are_unique_and_traceable_to_doc():
    chunks = chunk_document(SAMPLE_DOCS[1])
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(c.doc_id == "doc-03" for c in chunks)


def test_metadata_is_denormalized_onto_chunk():
    chunks = chunk_document(SAMPLE_DOCS[2])
    for c in chunks:
        assert c.title == "STEMI Reperfusion Timing"
        assert int(c.authority_tier) == 2


def test_header_stripped_correctly_even_with_blank_line_before_it():
    """Regression test: a blank line before a section header (the
    normal case in real-world formatted text, e.g. DailyMed drug
    labels) previously broke header-stripping - the header word itself
    would leak into the chunk's text instead of being removed."""
    doc = SourceDocument(
        doc_id="blank-line-test",
        title="Blank Line Header Test",
        source="test",
        authority_tier=AuthorityTier.GUIDELINE_OR_META_ANALYSIS,
        publication_date=date(2024, 1, 1),
        full_text=(
            "Recommendation\nFirst section text.\n\n"
            "Dosing\nSecond section text.\n\n"
            "Contraindications\nThird section text."
        ),
    )
    chunks = chunk_document(doc)
    texts_by_section = {c.section_type: c.text for c in chunks}
    assert texts_by_section["dosing"] == "Second section text."
    assert texts_by_section["contraindication"] == "Third section text."
    assert "Dosing" not in texts_by_section["dosing"]
    assert "Contraindications" not in texts_by_section["contraindication"]
