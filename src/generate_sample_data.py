"""Generate the synthetic sample dataset: Google reviews of a fictional restaurant.

Writes data/sample/google_reviews.csv, plus tests/fixtures/comment_answer_key.csv
with the topics behind every comment.
Run with: python -m src.generate_sample_data
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src import sample_comments as comments
from src.schema import GOOGLE_REVIEWS, column_names

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "sample"
# Kept apart from the data so the analysis never reads the answers.
ANSWER_KEY_PATH = ROOT / "tests" / "fixtures" / "comment_answer_key.csv"

# Fixed date range so the output does not depend on the day it is run.
REVIEWS_START = pd.Timestamp("2024-10-01")
END = pd.Timestamp("2026-09-30")

# Planted story: from July 2026 the stars drop and complaints shift to waiting
# times, while food and value keep being praised. The owner had already stopped
# replying a year before the end. Diners keep praising a small detail: the cookie.
SERVICE_DECLINE_START = pd.Timestamp("2026-07-01")
OWNER_STOPS_REPLYING = pd.Timestamp("2025-10-01")

N_GOOGLE_REVIEWS = 600
REVIEW_TEXT_RATE = 0.5

ASPECTS = ("food", "service", "ambience", "value")

# Star probabilities (1 to 5), before and after the decline.
REVIEW_RATING_PROBS = [0.02, 0.02, 0.10, 0.30, 0.56]
REVIEW_RATING_PROBS_DECLINE = [0.20, 0.10, 0.15, 0.25, 0.30]


def text_rng_for(seed):
    """Texts draw from their own stream, so editing phrases never shifts the numbers."""
    return np.random.default_rng([seed, 1])


def _random_days(rng, start, end, n):
    n_days = (end - start).days + 1
    return start + pd.to_timedelta(rng.integers(0, n_days, n), unit="D")


def _review_topics(rating, in_decline, text_rng):
    """Topics and joiner for a review, given its stars."""
    if rating >= 4:
        return comments.pick_praise_topics(str(text_rng.choice(ASPECTS)), text_rng), None
    in_service = in_decline and text_rng.random() < 0.8
    complaint_aspect = "service" if in_service else str(text_rng.choice(ASPECTS))
    # A one-word "Pésimo" only fits a 1 or 2 star review.
    complaint = comments.pick_complaint_topics(
        complaint_aspect, in_decline, text_rng, allow_generic=rating <= 2
    )
    if rating == 3:
        # Praise a different aspect so the review does not contradict itself.
        other = str(text_rng.choice([aspect for aspect in ASPECTS if aspect != complaint_aspect]))
        praise = str(text_rng.choice(comments.topics_for(other, "praise")))
        return [praise, *complaint], ", pero "
    return complaint, None


def _generate_reviews(rng, text_rng):
    n = N_GOOGLE_REVIEWS
    review_dates = _random_days(rng, REVIEWS_START, END, n).sort_values()

    rows, answer_key = [], []
    for i, review_date in enumerate(review_dates, start=1):
        review_id = f"GR-{i:04d}"
        in_decline = review_date >= SERVICE_DECLINE_START
        probs = REVIEW_RATING_PROBS_DECLINE if in_decline else REVIEW_RATING_PROBS
        rating = int(rng.choice([1, 2, 3, 4, 5], p=probs))
        reply_rate = 0.6 if review_date < OWNER_STOPS_REPLYING else 0.05
        owner_replied = bool(rng.random() < reply_rate)
        reply_date = pd.NaT
        if owner_replied:
            reply_date = review_date + pd.Timedelta(days=int(rng.integers(1, 11)))
        # Many Google ratings come without any text.
        text = None
        if text_rng.random() < REVIEW_TEXT_RATE:
            topics, joiner = _review_topics(rating, in_decline, text_rng)
            text = comments.compose(topics, text_rng, joiner)
            answer_key.append((review_id, "|".join(topics)))
        rows.append((review_id, review_date, rating, text, owner_replied, reply_date))

    reviews = pd.DataFrame(rows, columns=column_names(GOOGLE_REVIEWS))
    return reviews, pd.DataFrame(answer_key, columns=["id", "topics"])


def generate_google_reviews(rng, text_rng=None):
    return _generate_reviews(rng, text_rng or text_rng_for(SEED))[0]


def generate_all(seed=SEED):
    """The reviews and the answer key (id, topics) for their comments."""
    return _generate_reviews(np.random.default_rng(seed), text_rng_for(seed))


def write_sample_data(output_dir=OUTPUT_DIR, seed=SEED, answer_key_path=None):
    reviews, answer_key = generate_all(seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reviews_path = output_dir / "google_reviews.csv"
    reviews.to_csv(reviews_path, index=False, lineterminator="\n", encoding="utf-8", date_format="%Y-%m-%d")
    if answer_key_path:
        Path(answer_key_path).parent.mkdir(parents=True, exist_ok=True)
        answer_key.to_csv(answer_key_path, index=False, lineterminator="\n", encoding="utf-8")
    return reviews_path


if __name__ == "__main__":
    path = write_sample_data(answer_key_path=ANSWER_KEY_PATH)
    print(f"{path} ({len(pd.read_csv(path))} rows)")
    print(f"{ANSWER_KEY_PATH} ({len(pd.read_csv(ANSWER_KEY_PATH))} comments)")
