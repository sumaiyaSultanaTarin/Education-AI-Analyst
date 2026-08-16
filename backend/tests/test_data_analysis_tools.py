from tools.data_analysis_tools import sheets_to_dataframes, summarize_numeric_columns


def test_sheets_to_dataframes_builds_one_frame_per_sheet():
    sheets = {"Term1": [{"name": "A", "score": 80}, {"name": "B", "score": 30}]}

    frames = sheets_to_dataframes(sheets)

    assert list(frames) == ["Term1"]
    assert list(frames["Term1"]["score"]) == [80, 30]


def test_summarize_numeric_columns_computes_pass_rate():
    frames = sheets_to_dataframes({"Term1": [{"score": 80}, {"score": 30}, {"score": 50}]})

    stats = summarize_numeric_columns(frames["Term1"], passing_mark=40)

    assert stats["score"]["count"] == 3
    assert stats["score"]["mean"] == 53.33
    assert stats["score"]["min"] == 30
    assert stats["score"]["max"] == 80
    assert stats["score"]["pass_rate"] == 66.67  # 2 of 3 >= 40


def test_summarize_numeric_columns_ignores_non_numeric_columns():
    frames = sheets_to_dataframes({"Term1": [{"name": "A", "score": 80}]})

    stats = summarize_numeric_columns(frames["Term1"])

    assert "name" not in stats
    assert "score" in stats
