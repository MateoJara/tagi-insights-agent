"""Tests for the report charts."""

from src.charts import write_charts
from src.load_data import load_google_reviews, load_survey_responses

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_write_charts_creates_png_files(tmp_path):
    survey, _ = load_survey_responses()
    reviews, _ = load_google_reviews()
    paths = write_charts(survey, reviews, tmp_path)
    assert [path.name for path in paths] == [
        "rating_distribution.png",
        "monthly_trend.png",
        "aspect_change.png",
    ]
    for path in paths:
        assert path.read_bytes().startswith(PNG_SIGNATURE)
