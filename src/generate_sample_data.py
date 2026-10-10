"""Generate the synthetic sample dataset for a fictional restaurant.

Writes data/sample/survey_responses.csv and data/sample/google_reviews.csv, plus
tests/fixtures/comment_answer_key.csv with the topics behind every comment.
Run with: python -m src.generate_sample_data
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src import sample_comments as comments
from src.survey_schema import GOOGLE_REVIEWS, SURVEY_RESPONSES, column_names

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "sample"
# Kept apart from the data so the analysis never reads the answers.
ANSWER_KEY_PATH = ROOT / "tests" / "fixtures" / "comment_answer_key.csv"

# Fixed date ranges so the output does not depend on the day it is run.
SURVEY_START = pd.Timestamp("2026-04-01")
REVIEWS_START = pd.Timestamp("2024-10-01")
END = pd.Timestamp("2026-09-30")

# Planted story: service gets worse from this date on (mostly waiting times), food
# and value hold, and the owner had already stopped replying to reviews a year
# before the end. Diners also keep praising a small detail: the free cookie.
SERVICE_DECLINE_START = pd.Timestamp("2026-07-01")
OWNER_STOPS_REPLYING = pd.Timestamp("2025-10-01")

N_SURVEY_ROWS = 300
N_SURVEY_DUPLICATES = 6
N_GOOGLE_REVIEWS = 200
MISSING_RATING_RATE = 0.03
REVIEW_TEXT_RATE = 0.4

ASPECTS = ("food", "service", "ambience", "value")
ASPECT_OFFSET = {"food": 0.2, "service": 0.0, "ambience": 0.0, "value": 0.3}
SERVICE_DECLINE_OFFSET = -1.4

# Star probabilities (1 to 5) for Google reviews, before and after the decline.
REVIEW_RATING_PROBS = [0.02, 0.02, 0.10, 0.30, 0.56]
REVIEW_RATING_PROBS_DECLINE = [0.20, 0.10, 0.15, 0.25, 0.30]


def text_rng_for(seed):
    """Texts draw from their own stream, so editing phrases never shifts the numbers."""
    return np.random.default_rng([seed, 1])


def _random_days(rng, start, end, n):
    n_days = (end - start).days + 1
    return start + pd.to_timedelta(rng.integers(0, n_days, n), unit="D")


def _pick_aspect(ratings, rng, best):
    target = max(ratings.values()) if best else min(ratings.values())
    return str(rng.choice([aspect for aspect, value in ratings.items() if value == target]))


def _survey_texts(ratings, overall, in_decline, text_rng):
    """Return {column: (text, topics)} for the open questions this diner answered."""
    answers = {}
    if text_rng.random() < (0.40 if overall >= 4 else 0.10):
        topics = comments.pick_praise_topics(_pick_aspect(ratings, text_rng, best=True), text_rng)
        answers["positives"] = (comments.compose(topics, text_rng), topics)
    if text_rng.random() < (0.60 if min(ratings.values()) <= 2 else 0.06):
        aspect = _pick_aspect(ratings, text_rng, best=False)
        topics = comments.pick_complaint_topics(aspect, in_decline, text_rng)
        answers["complaints"] = (comments.compose(topics, text_rng), topics)
    if text_rng.random() < 0.15:
        answers["suggestions"] = (comments.compose(["suggestion"], text_rng), ["suggestion"])
    return answers


def _generate_survey(rng, text_rng):
    n = N_SURVEY_ROWS - N_SURVEY_DUPLICATES
    days = _random_days(rng, SURVEY_START, END, n)
    hours = rng.choice([12, 13, 14, 19, 20, 21], n)
    minutes = rng.integers(0, 60, n)
    submitted_at = (
        days + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")
    ).sort_values()
    in_decline = np.asarray(submitted_at >= SERVICE_DECLINE_START)

    # One hidden satisfaction level per diner keeps the ratings correlated.
    satisfaction = rng.normal(4.1, 0.7, n)
    raw = {
        aspect: satisfaction + ASPECT_OFFSET[aspect] + rng.normal(0, 0.5, n)
        for aspect in ASPECTS
    }
    raw["service"] = raw["service"] + np.where(in_decline, SERVICE_DECLINE_OFFSET, 0.0)
    overall_raw = np.mean([raw[aspect] for aspect in ASPECTS], axis=0)
    overall_raw = overall_raw + rng.normal(0, 0.3, n)
    recommend_raw = (overall_raw - 1) / 4 * 10 + rng.normal(0, 1, n)

    df = pd.DataFrame(
        {
            "response_id": [f"SR-{i:04d}" for i in range(1, n + 1)],
            "submitted_at": submitted_at,
            "rating_overall": np.clip(np.rint(overall_raw), 1, 5).astype(int),
            "would_recommend": np.clip(np.rint(recommend_raw), 0, 10).astype(int),
        }
    )
    for aspect in ASPECTS:
        df[f"rating_{aspect}"] = np.clip(np.rint(raw[aspect]), 1, 5).astype(int)

    text_columns = {"positives": [None] * n, "complaints": [None] * n, "suggestions": [None] * n}
    answer_key = []
    for position in range(n):
        ratings = {aspect: int(df.at[position, f"rating_{aspect}"]) for aspect in ASPECTS}
        overall = int(df.at[position, "rating_overall"])
        answers = _survey_texts(ratings, overall, in_decline[position], text_rng)
        for column, (text, topics) in answers.items():
            text_columns[column][position] = text
            answer_key.append(("survey_responses", df.at[position, "response_id"], column, "|".join(topics)))
    for column, values in text_columns.items():
        df[column] = values

    # Some diners skip questions.
    for column in SURVEY_RESPONSES:
        if column.kind == "rating":
            skipped = rng.random(n) < MISSING_RATING_RATE
            df[column.name] = df[column.name].astype("Int64").mask(skipped)

    # A few diners submit the form twice.
    duplicated = df.iloc[rng.choice(n, N_SURVEY_DUPLICATES, replace=False)]
    df = pd.concat([df, duplicated]).sort_values("submitted_at", kind="stable")
    return df[column_names(SURVEY_RESPONSES)].reset_index(drop=True), answer_key


def _review_topics(rating, in_decline, text_rng):
    """Topics and joiner for a Google review, given its stars."""
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
        # Most Google ratings come without any text.
        text = None
        if text_rng.random() < REVIEW_TEXT_RATE:
            topics, joiner = _review_topics(rating, in_decline, text_rng)
            text = comments.compose(topics, text_rng, joiner)
            answer_key.append(("google_reviews", review_id, "text", "|".join(topics)))
        rows.append((review_id, review_date, rating, text, owner_replied, reply_date))

    return pd.DataFrame(rows, columns=column_names(GOOGLE_REVIEWS)), answer_key


def generate_survey_responses(rng, text_rng=None):
    return _generate_survey(rng, text_rng or text_rng_for(SEED))[0]


def generate_google_reviews(rng, text_rng=None):
    return _generate_reviews(rng, text_rng or text_rng_for(SEED))[0]


def generate_all(seed=SEED):
    """Both tables and the answer key (table, id, column, topics) for their comments."""
    rng, text_rng = np.random.default_rng(seed), text_rng_for(seed)
    survey, survey_key = _generate_survey(rng, text_rng)
    reviews, reviews_key = _generate_reviews(rng, text_rng)
    answer_key = pd.DataFrame(survey_key + reviews_key, columns=["table", "id", "column", "topics"])
    return survey, reviews, answer_key


def write_sample_data(output_dir=OUTPUT_DIR, seed=SEED, answer_key_path=None):
    survey, reviews, answer_key = generate_all(seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    survey_path = output_dir / "survey_responses.csv"
    reviews_path = output_dir / "google_reviews.csv"
    survey.to_csv(survey_path, index=False, lineterminator="\n", encoding="utf-8")
    reviews.to_csv(
        reviews_path, index=False, lineterminator="\n", encoding="utf-8", date_format="%Y-%m-%d"
    )
    if answer_key_path:
        Path(answer_key_path).parent.mkdir(parents=True, exist_ok=True)
        answer_key.to_csv(answer_key_path, index=False, lineterminator="\n", encoding="utf-8")
    return survey_path, reviews_path


if __name__ == "__main__":
    for path in write_sample_data(answer_key_path=ANSWER_KEY_PATH):
        print(f"{path} ({len(pd.read_csv(path))} rows)")
    print(f"{ANSWER_KEY_PATH} ({len(pd.read_csv(ANSWER_KEY_PATH))} comments)")
