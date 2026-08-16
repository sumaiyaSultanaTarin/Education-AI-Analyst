"""Local lexicon-based sentiment scoring for social comments.

Uses VADER rather than an LLM call — a post can have many comments, and
free-tier OpenRouter rate limits are an explicit risk in docs/architecture.md
(gap #3). VADER is tuned for short, informal text (social media), which
fits Facebook comments well.
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

_POSITIVE_THRESHOLD = 0.05
_NEGATIVE_THRESHOLD = -0.05


def analyze_sentiment(text: str) -> dict:
    """Score a comment's sentiment.

    Returns {"score": float in [-1, 1], "label": "positive"|"neutral"|"negative"}.
    """
    compound = _analyzer.polarity_scores(text)["compound"]

    if compound >= _POSITIVE_THRESHOLD:
        label = "positive"
    elif compound <= _NEGATIVE_THRESHOLD:
        label = "negative"
    else:
        label = "neutral"

    return {"score": compound, "label": label}
