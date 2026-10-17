"""Tests for the report charts."""

from src import generate_sample_data as gen
from src.charts import main, write_charts
from src.load_data import load_google_reviews

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_write_charts_creates_png_files(tmp_path):
    reviews, _ = load_google_reviews()
    paths = write_charts(reviews, tmp_path)
    assert [path.name for path in paths] == ["rating_distribution.png", "monthly_rating.png", "monthly_volume.png"]
    for path in paths:
        assert path.read_bytes().startswith(PNG_SIGNATURE)


def test_main_writes_charts_for_given_file(tmp_path):
    path = gen.write_sample_data(tmp_path / "data", seed=7)
    main(["--reviews", str(path), "--output-dir", str(tmp_path / "charts")])
    assert len(list((tmp_path / "charts").glob("*.png"))) == 3
