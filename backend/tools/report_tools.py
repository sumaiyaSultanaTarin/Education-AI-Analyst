"""DOCX report assembly, used by the Report Generator Agent."""

from pathlib import Path

from docx import Document


def build_report_docx(
    output_path: str,
    goal: str,
    documents: list[dict],
    data_analysis: dict,
    rag_citations: list[dict],
    social_summary: dict | None = None,
) -> str:
    """Compile a formatted DOCX report with citations back to source documents.

    `data_analysis` is keyed by document_id -> {sheet_name: column stats}
    (Data Analyst Agent's output shape); `rag_citations` is the Knowledge/RAG
    Agent's query hits. Returns the path written to.
    """
    doc = Document()
    doc.add_heading("Education AI Analyst — Report", level=0)
    doc.add_paragraph(f"Goal: {goal}")

    doc.add_heading("Source Documents", level=1)
    for document in documents:
        doc.add_paragraph(f"{document['filename']} ({document['type']})", style="List Bullet")

    if data_analysis:
        doc.add_heading("Data Analysis", level=1)
        for summary in data_analysis.values():
            for sheet_name, stats in summary.items():
                doc.add_heading(sheet_name, level=2)
                for column, values in stats.items():
                    doc.add_paragraph(
                        f"{column}: mean={values['mean']}, min={values['min']}, "
                        f"max={values['max']}, pass_rate={values['pass_rate']}%, "
                        f"n={values['count']}"
                    )

    if social_summary:
        doc.add_heading("Social Intelligence (Facebook)", level=1)
        doc.add_paragraph(str(social_summary))

    if rag_citations:
        doc.add_heading("Supporting Excerpts", level=1)
        for citation in rag_citations:
            doc.add_paragraph(f"[{citation['filename']}] {citation['text'][:300]}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    return output_path
