"""Tests for loading and cleaning the input tables."""

import pandas as pd
import pytest

from src import generate_sample_data as gen
from src.load_data import load_google_reviews, load_survey_responses

SURVEY_HEADER = (
    "response_id,submitted_at,rating_overall,rating_food,rating_service,"
    "rating_ambience,rating_value,would_recommend,positives,complaints,suggestions"
)


def _write_survey(tmp_path, *rows):
    path = tmp_path / "survey.csv"
    path.write_text("\n".join([SURVEY_HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def test_sample_survey_loads_without_duplicates():
    survey, report = load_survey_responses()
    assert report.rows_read == gen.N_SURVEY_ROWS
    assert report.duplicates_removed == gen.N_SURVEY_DUPLICATES
    assert len(survey) == report.rows_kept
    assert survey["response_id"].is_unique
    assert report.invalid_ratings == 0
    assert report.texts_cleaned > 0


def test_sample_reviews_load_with_expected_types():
    reviews, report = load_google_reviews()
    assert len(reviews) == gen.N_GOOGLE_REVIEWS
    assert report.duplicates_removed == 0
    assert reviews["owner_replied"].dtype == bool
    assert pd.api.types.is_datetime64_any_dtype(reviews["review_date"])
    assert reviews["rating"].between(1, 5).all()


def test_text_is_trimmed_and_recased(tmp_path):
    path = _write_survey(
        tmp_path,
        "SR-1,2026-04-01 12:00:00,4,4,4,4,4,8,  MUY  BUENA COMIDA ,el plato llegó frío,   ",
    )
    survey, report = load_survey_responses(path)
    assert survey.loc[0, "positives"] == "Muy buena comida"
    assert survey.loc[0, "complaints"] == "El plato llegó frío"
    assert pd.isna(survey.loc[0, "suggestions"])
    assert report.texts_cleaned == 3


def test_out_of_range_ratings_become_missing(tmp_path):
    path = _write_survey(
        tmp_path,
        "SR-1,2026-04-01 12:00:00,7,4,abc,4,4,11,,,",
        "SR-2,2026-04-02 12:00:00,5,4,3,4,4,10,,,",
    )
    survey, report = load_survey_responses(path)
    assert report.invalid_ratings == 3
    assert pd.isna(survey.loc[0, "rating_overall"])
    assert pd.isna(survey.loc[0, "rating_service"])
    assert pd.isna(survey.loc[0, "would_recommend"])
    assert survey.loc[1, "rating_overall"] == 5


def test_missing_column_raises(tmp_path):
    path = tmp_path / "survey.csv"
    path.write_text("response_id,submitted_at\nSR-1,2026-04-01\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rating_overall"):
        load_survey_responses(path)
