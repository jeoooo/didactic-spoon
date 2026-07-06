import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be parsed or contains no extractable text."""


def extract_text_from_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise PDFExtractionError("Could not read PDF file") from exc

    if reader.is_encrypted:
        raise PDFExtractionError("PDF is encrypted and cannot be read")

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception as exc:
            raise PDFExtractionError("Could not extract text from PDF") from exc

    text = "\n".join(pages_text).strip()
    if not text:
        raise PDFExtractionError("PDF contains no extractable text")

    return text
