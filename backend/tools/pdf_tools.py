"""PDF text/table extraction, used by the Document Ingestion Agent."""

import pdfplumber


def extract_pdf_content(path: str) -> dict:
    """Extract text and tables from a PDF, one entry per page.

    Returns {"pages": [{"page_number": int, "text": str, "tables": list[list[list[str]]]}]}.
    """
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append({
                "page_number": i,
                "text": page.extract_text() or "",
                "tables": page.extract_tables(),
            })
    return {"pages": pages}
