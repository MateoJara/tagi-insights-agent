"""Tests for loading and cleaning the reviews table."""

import pandas as pd
import pytest

from src import generate_sample_data as gen
from src.load_data import load_google_reviews

HEADER = "review_id,review_date,rating,text,owner_replied,owner_reply_date"


def _write(tmp_path, *rows):
    path = tmp_path / "reviews.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def test_sample_reviews_load_with_expected_types():
    reviews, report = load_google_reviews()
    assert len(reviews) == report.rows_kept == gen.N_GOOGLE_REVIEWS
    assert report.duplicates_removed == 0 and report.invalid_ratings == 0
    assert report.texts_cleaned > 0
    assert reviews["owner_replied"].dtype == bool
    assert pd.api.types.is_datetime64_any_dtype(reviews["review_date"])
    assert reviews["rating"].between(1, 5).all()


def test_text_is_trimmed_and_recased(tmp_path):
    path = _write(
        tmp_path,
        "R-1,2026-04-01,4,  MUY  BUENA COMIDA ,False,",
        "R-2,2026-04-02,2,el plato llegó frío,False,",
        "R-3,2026-04-03,5,   ,False,",
    )
    reviews, report = load_google_reviews(path)
    assert reviews["text"].tolist()[:2] == ["Muy buena comida", "El plato llegó frío"]
    assert pd.isna(reviews.loc[2, "text"])
    assert report.texts_cleaned == 3


def test_exact_duplicates_are_removed(tmp_path):
    path = _write(tmp_path, "R-1,2026-04-01,4,Bien,False,", "R-1,2026-04-01,4,Bien,False,")
    reviews, report = load_google_reviews(path)
    assert len(reviews) == 1 and report.duplicates_removed == 1


def test_out_of_range_ratings_become_missing(tmp_path):
    path = _write(tmp_path, "R-1,2026-04-01,7,Raro,False,", "R-2,2026-04-02,abc,Raro,False,",
                  "R-3,2026-04-03,5,Bien,False,")
    reviews, report = load_google_reviews(path)
    assert report.invalid_ratings == 2
    assert reviews["rating"].isna().tolist() == [True, True, False]


def test_missing_column_raises(tmp_path):
    path = tmp_path / "reviews.csv"
    path.write_text("review_id,review_date\nR-1,2026-04-01\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rating"):
        load_google_reviews(path)
