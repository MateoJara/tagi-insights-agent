"""Metrics for the insights report, computed from the cleaned tables.

Run with: python -m src.metrics
"""

import json

import pandas as pd

from src.load_data import load_google_reviews, load_survey_responses

ASPECT_COLUMNS = ("rating_food", "rating_service", "rating_ambience", "rating_value")
SATISFIED_MIN_RATING = 4
RECENT_MONTHS = 3


def recent_mask(dates, months=RECENT_MONTHS):
    """Rows in the last `months` months of the data (relative to its latest date, not today)."""
    return dates > dates.max() - pd.DateOffset(months=months)


def _mean(values):
    values = values.dropna()
    return float(values.mean()) if len(values) else None


def satisfied_share(ratings):
    """Share of answered ratings that are 4 or 5."""
    ratings = ratings.dropna()
    return float((ratings >= SATISFIED_MIN_RATING).mean()) if len(ratings) else None


def nps(scores):
    """Net Promoter Score: % promoters (9-10) minus % detractors (0-6), from -100 to 100."""
    scores = scores.dropna()
    if not len(scores):
        return None
    return float(((scores >= 9).mean() - (scores <= 6).mean()) * 100)


def monthly_means(survey):
    """Mean of every rating question per calendar month."""
    columns = ["rating_overall", *ASPECT_COLUMNS]
    months = survey["submitted_at"].dt.to_period("M").rename("month")
    return survey[columns].astype(float).groupby(months).mean()


def aspect_change(survey, months=RECENT_MONTHS):
    """Mean per aspect in the recent period vs everything before, worst change first."""
    recent = recent_mask(survey["submitted_at"], months)
    ratings = survey[list(ASPECT_COLUMNS)].astype(float)
    table = pd.DataFrame({"previous": ratings[~recent].mean(), "recent": ratings[recent].mean()})
    table["change"] = table["recent"] - table["previous"]
    return table.sort_values("change")


def survey_summary(survey, months=RECENT_MONTHS):
    changes = aspect_change(survey, months)
    return {
        "n_responses": len(survey),
        "first_date": survey["submitted_at"].min().date(),
        "last_date": survey["submitted_at"].max().date(),
        "mean_overall": _mean(survey["rating_overall"]),
        "mean_by_aspect": {aspect: _mean(survey[aspect]) for aspect in ASPECT_COLUMNS},
        "satisfied_share": satisfied_share(survey["rating_overall"]),
        "nps": nps(survey["would_recommend"]),
        "recent_months": months,
        "biggest_drop_aspect": changes.index[0],
        "biggest_drop_change": float(changes["change"].iloc[0]),
    }


def rating_distribution(reviews):
    """Number of reviews per star rating, 5 down to 1, including ratings nobody gave."""
    counts = reviews["rating"].value_counts()
    return counts.reindex([5, 4, 3, 2, 1], fill_value=0).astype(int)


def review_summary(reviews, months=RECENT_MONTHS):
    recent = recent_mask(reviews["review_date"], months)
    last_reply = reviews["owner_reply_date"].max()
    return {
        "n_reviews": len(reviews),
        "mean_rating": _mean(reviews["rating"]),
        "distribution": {int(stars): int(n) for stars, n in rating_distribution(reviews).items()},
        "satisfied_share": satisfied_share(reviews["rating"]),
        "text_share": float(reviews["text"].notna().mean()),
        "recent_months": months,
        "recent_n": int(recent.sum()),
        "recent_mean_rating": _mean(reviews.loc[recent, "rating"]),
        "reply_rate": float(reviews["owner_replied"].mean()),
        "recent_reply_rate": float(reviews.loc[recent, "owner_replied"].mean()),
        "last_owner_reply": None if pd.isna(last_reply) else last_reply.date(),
    }


if __name__ == "__main__":
    survey, survey_report = load_survey_responses()
    reviews, reviews_report = load_google_reviews()
    output = {
        "survey_cleaning": vars(survey_report),
        "survey": survey_summary(survey),
        "reviews_cleaning": vars(reviews_report),
        "reviews": review_summary(reviews),
    }
    print(json.dumps(output, indent=2, default=str))
