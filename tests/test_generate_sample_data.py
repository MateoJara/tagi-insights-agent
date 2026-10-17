"""Tests for the synthetic sample data generator."""

import numpy as np
import pandas as pd
import pytest

from src import generate_sample_data as gen
from src.schema import GOOGLE_REVIEWS, column_names


@pytest.fixture(scope="module")
def reviews():
    return gen.generate_google_reviews(np.random.default_rng(gen.SEED))


@pytest.fixture(scope="module")
def generated():
    return gen.generate_all(gen.SEED)


def test_reviews_match_schema(reviews):
    assert list(reviews.columns) == column_names(GOOGLE_REVIEWS)
    for column in GOOGLE_REVIEWS:
        if column.required:
            assert reviews[column.name].notna().all(), column.name
    assert reviews["rating"].between(1, 5).all()
    assert len(reviews) == gen.N_GOOGLE_REVIEWS
    assert reviews["review_id"].is_unique


def test_dates_within_range(reviews):
    assert reviews["review_date"].between(gen.REVIEWS_START, gen.END).all()


def test_owner_reply_dates_are_consistent(reviews):
    replied = reviews["owner_replied"]
    assert reviews.loc[~replied, "owner_reply_date"].isna().all()
    assert (reviews.loc[replied, "owner_reply_date"] > reviews.loc[replied, "review_date"]).all()


def test_planted_story_in_the_stars(reviews):
    after = reviews["review_date"] >= gen.SERVICE_DECLINE_START
    assert reviews.loc[~after, "rating"].mean() - reviews.loc[after, "rating"].mean() > 0.5
    stopped = reviews["review_date"] >= gen.OWNER_STOPS_REPLYING
    assert reviews.loc[stopped, "owner_replied"].mean() < 0.1 < reviews.loc[~stopped, "owner_replied"].mean()


def test_comments_are_varied(reviews):
    assert reviews["text"].notna().mean() > 0.4
    assert reviews["text"].dropna().nunique() > 150


def test_answer_key_covers_every_comment(generated):
    reviews, key = generated
    assert len(key) == reviews["text"].notna().sum()
    assert key["id"].is_unique
    assert set(key["id"]) == set(reviews.loc[reviews["text"].notna(), "review_id"])


def test_planted_comment_stories(generated):
    reviews, key = generated
    topics = key.assign(topic=key["topics"].str.split("|")).explode("topic")
    assert (topics["topic"] == "detail_cookie").sum() >= 10

    dates = reviews.set_index("review_id")["review_date"]
    after = topics["id"].map(dates) >= gen.SERVICE_DECLINE_START
    service_complaints = topics["topic"].isin(["service_wait", "service_attitude", "service_order_error"])
    top_recent_complaint = topics.loc[after & service_complaints, "topic"].value_counts().index[0]
    assert top_recent_complaint == "service_wait"
    wait = topics["topic"] == "service_wait"
    assert wait[after].mean() > wait[~after].mean()


def test_changing_text_seed_keeps_the_numbers():
    first = gen.generate_google_reviews(np.random.default_rng(gen.SEED), np.random.default_rng(1))
    second = gen.generate_google_reviews(np.random.default_rng(gen.SEED), np.random.default_rng(2))
    numeric = ["review_date", "rating", "owner_replied", "owner_reply_date"]
    pd.testing.assert_frame_equal(first[numeric], second[numeric])
    assert not first["text"].equals(second["text"])


def test_same_seed_writes_identical_files(tmp_path):
    first = gen.write_sample_data(tmp_path / "a", answer_key_path=tmp_path / "a" / "key.csv")
    second = gen.write_sample_data(tmp_path / "b", answer_key_path=tmp_path / "b" / "key.csv")
    assert first.read_bytes() == second.read_bytes()
    assert (tmp_path / "a" / "key.csv").read_bytes() == (tmp_path / "b" / "key.csv").read_bytes()


def test_different_seed_writes_different_files(tmp_path):
    first = gen.write_sample_data(tmp_path / "a", seed=1)
    second = gen.write_sample_data(tmp_path / "b", seed=2)
    assert first.read_bytes() != second.read_bytes()
