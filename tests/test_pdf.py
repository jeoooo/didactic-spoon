from pathlib import Path

import pytest

from app.core.pdf import PDFExtractionError, extract_text_from_pdf

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_text_from_valid_pdf():
    data = (FIXTURES / "sample_resume.pdf").read_bytes()
    text = extract_text_from_pdf(data)
    assert "Jane Doe" in text
    assert "FastAPI" in text


def test_blank_pdf_raises_extraction_error():
    data = (FIXTURES / "blank.pdf").read_bytes()
    with pytest.raises(PDFExtractionError):
        extract_text_from_pdf(data)


def test_corrupt_pdf_raises_extraction_error():
    data = (FIXTURES / "corrupt.pdf").read_bytes()
    with pytest.raises(PDFExtractionError):
        extract_text_from_pdf(data)
