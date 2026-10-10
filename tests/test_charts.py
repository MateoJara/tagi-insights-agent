"""Tests for the report charts."""

from src import generate_sample_data as gen
from src.charts import main, write_charts
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


def test_main_writes_charts_for_given_files(tmp_path):
    survey_path, reviews_path = gen.write_sample_data(tmp_path / "data", seed=7)
    output_dir = tmp_path / "charts"
    main(["--survey", str(survey_path), "--reviews", str(reviews_path), "--output-dir", str(output_dir)])
    assert len(list(output_dir.glob("*.png"))) == 3
