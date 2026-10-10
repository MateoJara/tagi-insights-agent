"""Tests for the report metrics."""

import json

import pandas as pd
import pytest

from src import generate_sample_data as gen
from src import metrics
from src.load_data import load_google_reviews, load_survey_responses


@pytest.fixture(scope="module")
def survey():
    return load_survey_responses()[0]


@pytest.fixture(scope="module")
def reviews():
    return load_google_reviews()[0]


def test_nps_by_hand():
    # 2 promoters, 1 passive, 1 detractor, 1 unanswered -> (2 - 1) / 4 = 25
    scores = pd.Series([10, 9, 8, 3, pd.NA], dtype="Int64")
    assert metrics.nps(scores) == pytest.approx(25.0)


def test_satisfied_share_ignores_unanswered():
    ratings = pd.Series([5, 4, 3, 1, pd.NA], dtype="Int64")
    assert metrics.satisfied_share(ratings) == pytest.approx(0.5)


def test_empty_inputs_return_none():
    empty = pd.Series([], dtype="Int64")
    assert metrics.nps(empty) is None
    assert metrics.satisfied_share(empty) is None


def test_recent_mask_is_relative_to_the_data():
    dates = pd.Series(pd.to_datetime(["2020-01-10", "2020-03-20", "2020-04-10"]))
    assert metrics.recent_mask(dates, months=1).tolist() == [False, True, True]


def test_rating_distribution_includes_empty_ratings():
    reviews = pd.DataFrame({"rating": pd.Series([5, 5, 3], dtype="Int64")})
    assert metrics.rating_distribution(reviews).to_dict() == {5: 2, 4: 0, 3: 1, 2: 0, 1: 0}


def test_monthly_means_cover_the_survey_period(survey):
    monthly = metrics.monthly_means(survey)
    assert str(monthly.index[0]) == "2026-04"
    assert str(monthly.index[-1]) == "2026-09"
    assert len(monthly) == 6


def test_finds_planted_service_decline(survey):
    summary = metrics.survey_summary(survey)
    assert summary["biggest_drop_aspect"] == "rating_service"
    assert summary["biggest_drop_change"] < -1.0
    changes = metrics.aspect_change(survey)
    assert changes.drop(index="rating_service")["change"].abs().max() < 0.3


def test_main_writes_json_for_given_files(tmp_path):
    survey_path, reviews_path = gen.write_sample_data(tmp_path / "data", seed=7)
    output = tmp_path / "out" / "metrics.json"
    metrics.main(["--survey", str(survey_path), "--reviews", str(reviews_path), "--output", str(output)])
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["survey"]["n_responses"] == data["survey_cleaning"]["rows_kept"]
    assert sum(data["survey_responses_per_month"].values()) == data["survey"]["n_responses"]
    assert set(data["survey_aspect_change"]) == set(metrics.ASPECT_COLUMNS)
    assert data["reviews"]["n_reviews"] == gen.N_GOOGLE_REVIEWS


def test_finds_owner_stopped_replying(reviews):
    summary = metrics.review_summary(reviews)
    assert summary["recent_reply_rate"] < 0.1 < summary["reply_rate"]
    assert summary["recent_mean_rating"] < summary["mean_rating"] - 0.5
    assert summary["n_reviews"] == gen.N_GOOGLE_REVIEWS
    assert gen.REVIEWS_START.date() <= summary["first_date"] < summary["last_date"] <= gen.END.date()
    assert sum(summary["distribution"].values()) == gen.N_GOOGLE_REVIEWS
