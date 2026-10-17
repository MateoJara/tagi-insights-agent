"""Tests for the report metrics."""

import json

import pandas as pd
import pytest

from src import generate_sample_data as gen
from src import metrics
from src.load_data import load_google_reviews


@pytest.fixture(scope="module")
def reviews():
    return load_google_reviews()[0]


def test_satisfied_share_ignores_missing():
    ratings = pd.Series([5, 4, 3, 1, pd.NA], dtype="Int64")
    assert metrics.satisfied_share(ratings) == pytest.approx(0.5)
    assert metrics.satisfied_share(pd.Series([], dtype="Int64")) is None


def test_recent_mask_is_relative_to_the_data():
    dates = pd.Series(pd.to_datetime(["2020-01-10", "2020-03-20", "2020-04-10"]))
    assert metrics.recent_mask(dates, months=1).tolist() == [False, True, True]


def test_rating_distribution_includes_empty_ratings():
    reviews = pd.DataFrame({"rating": pd.Series([5, 5, 3], dtype="Int64")})
    assert metrics.rating_distribution(reviews).to_dict() == {5: 2, 4: 0, 3: 1, 2: 0, 1: 0}


def test_monthly_reviews_include_empty_months():
    reviews = pd.DataFrame({
        "review_date": pd.to_datetime(["2026-01-05", "2026-01-20", "2026-03-02"]),
        "rating": [5, 3, 4],
        "owner_replied": [True, False, False],
    })
    monthly = metrics.monthly_reviews(reviews)
    assert [str(m) for m in monthly.index] == ["2026-01", "2026-02", "2026-03"]
    assert monthly["n_reviews"].tolist() == [2, 0, 1]
    assert monthly.loc[pd.Period("2026-01"), "mean_rating"] == 4
    assert pd.isna(monthly.loc[pd.Period("2026-02"), "mean_rating"])


def test_monthly_reviews_cover_the_sample(reviews):
    monthly = metrics.monthly_reviews(reviews)
    assert len(monthly) == 24
    assert monthly["n_reviews"].sum() == len(reviews)


def test_finds_the_planted_story(reviews):
    summary = metrics.review_summary(reviews)
    assert summary["recent_mean_rating"] < summary["previous_mean_rating"] - 0.5
    assert summary["recent_satisfied_share"] < summary["previous_satisfied_share"]
    assert summary["recent_reply_rate"] < 0.1 < summary["previous_reply_rate"]


def test_periods_split_the_reviews(reviews):
    summary = metrics.review_summary(reviews)
    assert summary["previous_n"] + summary["recent_n"] == summary["n_reviews"] == gen.N_GOOGLE_REVIEWS
    assert summary["previous_text_n"] + summary["recent_text_n"] == reviews["text"].notna().sum()
    # The overall figures mix both periods, so they sit between "previous" and "recent".
    assert summary["recent_reply_rate"] < summary["reply_rate"] < summary["previous_reply_rate"]
    assert summary["recent_mean_rating"] < summary["mean_rating"] < summary["previous_mean_rating"]
    assert sum(summary["distribution"].values()) == summary["n_reviews"]


def test_main_writes_json_for_given_file(tmp_path):
    path = gen.write_sample_data(tmp_path / "data", seed=7)
    output = tmp_path / "out" / "metrics.json"
    metrics.main(["--reviews", str(path), "--output", str(output)])
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["reviews"]["n_reviews"] == data["reviews_cleaning"]["rows_kept"]
    assert sum(month["n_reviews"] for month in data["reviews_monthly"].values()) == data["reviews"]["n_reviews"]


def _summary(**overrides):
    summary = {"n_reviews": 600, "recent_n": 75, "previous_n": 525, "recent_text_n": 36, "previous_text_n": 268}
    return {**summary, **overrides}


def test_no_warnings_with_enough_data(reviews):
    assert metrics.data_warnings(metrics.review_summary(reviews)) == []


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"n_reviews": 49}, ["few_reviews"]),
        ({"n_reviews": 30}, ["few_reviews"]),
        ({"recent_n": 9}, ["few_recent_reviews"]),
        ({"previous_n": 5}, ["few_previous_reviews"]),
        ({"recent_text_n": 5, "previous_text_n": 14}, ["few_comments"]),
        # Without a "before", "few recent reviews" is not the problem: there is nothing to compare.
        ({"n_reviews": 3, "recent_n": 3, "previous_n": 0, "recent_text_n": 2, "previous_text_n": 0},
         ["few_reviews", "no_previous_reviews", "few_comments"]),
    ],
)
def test_data_warnings_name_each_thin_figure(overrides, expected):
    assert metrics.data_warnings(_summary(**overrides)) == expected
