from tools.xlsx_tools import extract_xlsx_content


def test_extract_xlsx_content(sample_docs_dir):
    result = extract_xlsx_content(str(sample_docs_dir / "enrollment_results.xlsx"))

    rows = result["sheets"]["Results"]
    assert len(rows) == 30
    assert set(rows[0].keys()) == {
        "enrollment_no", "student_name", "department", "course", "term", "score",
    }
    assert all(isinstance(row["score"], int) for row in rows)
