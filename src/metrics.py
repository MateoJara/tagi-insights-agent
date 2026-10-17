"""Metrics for the insights dashboard, computed from the cleaned reviews.

Run with: python -m src.metrics
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from src.load_data import SAMPLE_DIR, load_google_reviews

SATISFIED_MIN_RATING = 4
RECENT_MONTHS = 3
# Below these, the figures are only indicative and the dashboard says so.
MIN_REVIEWS = 50
MIN_RECENT_REVIEWS = 10
MIN_PREVIOUS_REVIEWS = 10
MIN_COMMENTS = 20


def recent_mask(dates, months=RECENT_MONTHS):
    """Rows in the last `months` months of the data (relative to its latest date, not today)."""
    return dates > dates.max() - pd.DateOffset(months=months)


def _mean(values):
    values = values.dropna()
    return float(values.mean()) if len(values) else None


def _share(flags):
    return float(flags.mean()) if len(flags) else None


def satisfied_share(ratings):
    """Share of ratings that are 4 or 5 stars."""
    ratings = ratings.dropna()
    return float((ratings >= SATISFIED_MIN_RATING).mean()) if len(ratings) else None


def rating_distribution(reviews):
    """Number of reviews per star rating, 5 down to 1, including ratings nobody gave."""
    counts = reviews["rating"].value_counts()
    return counts.reindex([5, 4, 3, 2, 1], fill_value=0).astype(int)


def monthly_reviews(reviews):
    """Reviews, mean stars and reply rate per calendar month, months without reviews included."""
    months = reviews["review_date"].dt.to_period("M").rename("month")
    table = reviews.groupby(months).agg(
        n_reviews=("rating", "size"),
        mean_rating=("rating", "mean"),
        reply_rate=("owner_replied", "mean"),
    )
    every_month = pd.period_range(table.index.min(), table.index.max(), freq="M", name="month")
    table = table.reindex(every_month)
    table["n_reviews"] = table["n_reviews"].fillna(0).astype(int)
    return table


def review_summary(reviews, months=RECENT_MONTHS):
    recent = recent_mask(reviews["review_date"], months)
    # "previous" excludes the recent period, so it is the right side of a
    # before/now comparison; the overall figures include both.
    previous = ~recent
    last_reply = reviews["owner_reply_date"].max()
    has_text = reviews["text"].notna()
    return {
        "n_reviews": len(reviews),
        "first_date": reviews["review_date"].min().date(),
        "last_date": reviews["review_date"].max().date(),
        "mean_rating": _mean(reviews["rating"]),
        "distribution": {int(stars): int(n) for stars, n in rating_distribution(reviews).items()},
        "satisfied_share": satisfied_share(reviews["rating"]),
        "text_share": _share(has_text),
        "recent_months": months,
        "recent_n": int(recent.sum()),
        "previous_n": int(previous.sum()),
        "recent_text_n": int((recent & has_text).sum()),
        "previous_text_n": int((previous & has_text).sum()),
        "recent_mean_rating": _mean(reviews.loc[recent, "rating"]),
        "previous_mean_rating": _mean(reviews.loc[previous, "rating"]),
        "recent_satisfied_share": satisfied_share(reviews.loc[recent, "rating"]),
        "previous_satisfied_share": satisfied_share(reviews.loc[previous, "rating"]),
        "reply_rate": _share(reviews["owner_replied"]),
        "recent_reply_rate": _share(reviews.loc[recent, "owner_replied"]),
        "previous_reply_rate": _share(reviews.loc[previous, "owner_replied"]),
        "last_owner_reply": None if pd.isna(last_reply) else last_reply.date(),
    }


def data_warnings(summary):
    """Codes for the figures that rest on too few reviews, from a review_summary."""
    warnings = []
    if summary["n_reviews"] < MIN_REVIEWS:
        warnings.append("few_reviews")
    if summary["previous_n"] == 0:
        warnings.append("no_previous_reviews")
    else:
        if summary["previous_n"] < MIN_PREVIOUS_REVIEWS:
            warnings.append("few_previous_reviews")
        if summary["recent_n"] < MIN_RECENT_REVIEWS:
            warnings.append("few_recent_reviews")
    if summary["recent_text_n"] + summary["previous_text_n"] < MIN_COMMENTS:
        warnings.append("few_comments")
    return warnings


def build_metrics(reviews_path, months=RECENT_MONTHS):
    """Load the reviews and return every figure the dashboard needs as plain data."""
    reviews, cleaning = load_google_reviews(reviews_path)
    monthly = monthly_reviews(reviews)
    summary = review_summary(reviews, months)
    return {
        "reviews_cleaning": {**vars(cleaning), "rows_kept": cleaning.rows_kept},
        "reviews": summary,
        "data_warnings": data_warnings(summary),
        "reviews_monthly": {
            str(month): {
                "n_reviews": int(row["n_reviews"]),
                "mean_rating": None if pd.isna(row["mean_rating"]) else float(row["mean_rating"]),
                "reply_rate": None if pd.isna(row["reply_rate"]) else float(row["reply_rate"]),
            }
            for month, row in monthly.iterrows()
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compute the dashboard metrics as JSON.")
    parser.add_argument("--reviews", default=SAMPLE_DIR / "google_reviews.csv")
    parser.add_argument("--output", help="write the JSON to this file instead of printing it")
    args = parser.parse_args(argv)

    text = json.dumps(build_metrics(args.reviews), indent=2, default=str)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
