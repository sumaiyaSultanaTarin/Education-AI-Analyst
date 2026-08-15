from tools.pdf_tools import extract_pdf_content


def test_extract_pdf_content(sample_docs_dir):
    result = extract_pdf_content(str(sample_docs_dir / "course_syllabus.pdf"))

    assert len(result["pages"]) >= 1
    full_text = " ".join(page["text"] for page in result["pages"])
    assert "Data Structures" in full_text

    tables = [t for page in result["pages"] for t in page["tables"]]
    assert len(tables) >= 1
