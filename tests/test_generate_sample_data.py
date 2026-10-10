"""Tests for the synthetic sample data generator."""

import numpy as np
import pandas as pd
import pytest

from src import generate_sample_data as gen
from src.survey_schema import GOOGLE_REVIEWS, SURVEY_RESPONSES, column_names


@pytest.fixture(scope="module")
def survey():
    return gen.generate_survey_responses(np.random.default_rng(gen.SEED))


@pytest.fixture(scope="module")
def reviews():
    return gen.generate_google_reviews(np.random.default_rng(gen.SEED))


def _check_table(df, schema):
    assert list(df.columns) == column_names(schema)
    for column in schema:
        values = df[column.name]
        if column.required:
            assert values.notna().all(), column.name
        if column.kind == "rating":
            answered = values.dropna()
            assert answered.between(column.min_value, column.max_value).all(), column.name


def test_survey_matches_schema(survey):
    _check_table(survey, SURVEY_RESPONSES)


def test_reviews_match_schema(reviews):
    _check_table(reviews, GOOGLE_REVIEWS)


def test_row_counts(survey, reviews):
    assert len(survey) == gen.N_SURVEY_ROWS
    assert len(reviews) == gen.N_GOOGLE_REVIEWS


def test_dates_within_range(survey, reviews):
    assert survey["submitted_at"].between(gen.SURVEY_START, gen.END + pd.Timedelta(days=1)).all()
    assert reviews["review_date"].between(gen.REVIEWS_START, gen.END).all()


def test_survey_has_realistic_noise(survey):
    assert survey.duplicated().sum() == gen.N_SURVEY_DUPLICATES
    assert survey["rating_service"].isna().any()
    assert survey["complaints"].isna().mean() > 0.5


def test_owner_reply_dates_are_consistent(reviews):
    replied = reviews["owner_replied"]
    assert reviews.loc[~replied, "owner_reply_date"].isna().all()
    assert (reviews.loc[replied, "owner_reply_date"] > reviews.loc[replied, "review_date"]).all()


def test_planted_story_service_declines_food_holds(survey):
    after = survey["submitted_at"] >= gen.SERVICE_DECLINE_START
    service_drop = survey.loc[~after, "rating_service"].mean() - survey.loc[after, "rating_service"].mean()
    food_change = survey.loc[~after, "rating_food"].mean() - survey.loc[after, "rating_food"].mean()
    assert service_drop > 1.0
    assert abs(food_change) < 0.3


def test_same_seed_writes_identical_files(tmp_path):
    first = gen.write_sample_data(tmp_path / "a")
    second = gen.write_sample_data(tmp_path / "b")
    for path_a, path_b in zip(first, second):
        assert path_a.read_bytes() == path_b.read_bytes()


def test_different_seed_writes_different_files(tmp_path):
    first = gen.write_sample_data(tmp_path / "a", seed=1)
    second = gen.write_sample_data(tmp_path / "b", seed=2)
    assert first[0].read_bytes() != second[0].read_bytes()


@pytest.fixture(scope="module")
def generated():
    return gen.generate_all(gen.SEED)


def test_comments_are_varied(generated):
    survey, reviews, _ = generated
    unique_texts = pd.concat([survey["positives"], survey["complaints"], reviews["text"]]).dropna().nunique()
    assert unique_texts > 150


def test_answer_key_covers_every_comment(generated):
    survey, reviews, key = generated
    survey = survey.drop_duplicates()
    n_survey_comments = survey[["positives", "complaints", "suggestions"]].notna().sum().sum()
    assert (key["table"] == "survey_responses").sum() == n_survey_comments
    assert (key["table"] == "google_reviews").sum() == reviews["text"].notna().sum()
    assert not key.duplicated(["table", "id", "column"]).any()


def test_planted_comment_stories(generated):
    survey, _, key = generated
    topics = key.assign(topic=key["topics"].str.split("|")).explode("topic")
    assert (topics["topic"] == "detail_cookie").sum() >= 10

    complaints = topics[(topics["table"] == "survey_responses") & (topics["column"] == "complaints")]
    dates = survey.drop_duplicates().set_index("response_id")["submitted_at"]
    after = complaints["id"].map(dates) >= gen.SERVICE_DECLINE_START
    service = complaints["topic"].str.startswith("service_")
    top_after = complaints.loc[after, "topic"].value_counts().index[0]
    assert top_after == "service_wait"
    wait_share_after = (complaints.loc[after & service, "topic"] == "service_wait").mean()
    wait_share_before = (complaints.loc[~after & service, "topic"] == "service_wait").mean()
    assert wait_share_after > wait_share_before


def test_changing_text_seed_keeps_the_numbers():
    first = gen.generate_survey_responses(np.random.default_rng(gen.SEED), np.random.default_rng(1))
    second = gen.generate_survey_responses(np.random.default_rng(gen.SEED), np.random.default_rng(2))
    numeric = [c for c in first.columns if c.startswith("rating_")] + ["would_recommend", "submitted_at"]
    pd.testing.assert_frame_equal(first[numeric], second[numeric])
    assert not first["complaints"].equals(second["complaints"])
