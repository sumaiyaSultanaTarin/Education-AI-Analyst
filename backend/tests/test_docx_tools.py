from tools.docx_tools import extract_docx_content


def test_extract_docx_content(sample_docs_dir):
    result = extract_docx_content(str(sample_docs_dir / "department_report.docx"))

    assert any("Department" in p for p in result["paragraphs"])
    assert len(result["tables"]) == 1
    header_row = result["tables"][0][0]
    assert header_row == ["Program", "Enrolled Students"]
