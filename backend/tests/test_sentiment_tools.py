from tools.sentiment_tools import analyze_sentiment


def test_positive_comment():
    result = analyze_sentiment("This teacher is amazing and truly inspiring!")
    assert result["label"] == "positive"
    assert result["score"] > 0


def test_negative_comment():
    result = analyze_sentiment("This was a terrible and disappointing class.")
    assert result["label"] == "negative"
    assert result["score"] < 0


def test_neutral_comment():
    result = analyze_sentiment("The class starts at 10am on Tuesday.")
    assert result["label"] == "neutral"


def test_score_is_within_bounds():
    result = analyze_sentiment("Absolutely the best, most wonderful, amazing experience ever!")
    assert -1.0 <= result["score"] <= 1.0
