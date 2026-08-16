from tools.social_csv_tools import parse_social_csv

_CSV_HEADER = "fb_post_id,post_content,posted_at,fb_comment_id,author,comment_content\n"


def _write_csv(tmp_path, rows: str):
    path = tmp_path / "comments.csv"
    path.write_text(_CSV_HEADER + rows, encoding="utf-8")
    return path


def test_parse_social_csv_groups_comments_by_post(tmp_path):
    rows = (
        "post-1,Great turnout at the fair!,2025-09-01,c-1,Ayesha,Loved it!\n"
        "post-1,Great turnout at the fair!,2025-09-01,c-2,Rahim,Could be better organized\n"
        "post-2,New library hours announced,2025-09-03,c-3,Nadia,Finally!\n"
    )
    path = _write_csv(tmp_path, rows)

    result = parse_social_csv(str(path))

    assert len(result["posts"]) == 2
    post_1 = next(p for p in result["posts"] if p["fb_post_id"] == "post-1")
    assert post_1["content"] == "Great turnout at the fair!"
    assert len(post_1["comments"]) == 2
    assert post_1["comments"][0] == {
        "fb_comment_id": "c-1", "author": "Ayesha", "content": "Loved it!",
    }

    post_2 = next(p for p in result["posts"] if p["fb_post_id"] == "post-2")
    assert len(post_2["comments"]) == 1


def test_parse_social_csv_empty_file(tmp_path):
    path = _write_csv(tmp_path, "")

    result = parse_social_csv(str(path))

    assert result == {"posts": []}
