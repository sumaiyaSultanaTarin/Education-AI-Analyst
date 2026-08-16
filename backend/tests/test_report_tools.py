from docx import Document

from tools.report_tools import build_report_docx


def test_build_report_docx_writes_a_readable_file(tmp_path):
    output_path = tmp_path / "session" / "report.docx"

    build_report_docx(
        str(output_path),
        goal="Summarize Spring 2025 performance",
        documents=[{"filename": "results.xlsx", "type": "xlsx"}],
        data_analysis={"doc-1": {"Term1": {"score": {"mean": 70, "min": 30, "max": 100, "pass_rate": 80, "count": 5}}}},
        rag_citations=[{"filename": "results.xlsx", "text": "excerpt text"}],
    )

    assert output_path.exists()

    doc = Document(str(output_path))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Summarize Spring 2025 performance" in full_text
    assert "results.xlsx" in full_text
    assert "excerpt text" in full_text


def test_build_report_docx_omits_empty_sections(tmp_path):
    output_path = tmp_path / "report.docx"

    build_report_docx(
        str(output_path), goal="g", documents=[], data_analysis={}, rag_citations=[]
    )

    doc = Document(str(output_path))
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert "Data Analysis" not in headings
    assert "Supporting Excerpts" not in headings
