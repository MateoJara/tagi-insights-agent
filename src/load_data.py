"""Load and clean the two input tables according to the schema."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.survey_schema import GOOGLE_REVIEWS, SURVEY_RESPONSES, Column, column_names

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


@dataclass(frozen=True)
class CleaningReport:
    rows_read: int
    duplicates_removed: int
    invalid_ratings: int
    texts_cleaned: int

    @property
    def rows_kept(self) -> int:
        return self.rows_read - self.duplicates_removed


def _clean_text(value):
    if pd.isna(value):
        return pd.NA
    text = " ".join(str(value).split())
    if not text:
        return pd.NA
    if text.isupper():
        return text.capitalize()
    return text[0].upper() + text[1:]


def _load_table(path, schema: tuple[Column, ...]):
    df = pd.read_csv(path, dtype=str, encoding="utf-8")
    missing = [name for name in column_names(schema) if name not in df.columns]
    if missing:
        raise ValueError(f"{Path(path).name} is missing columns: {missing}")
    df = df[column_names(schema)]

    rows_read = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    invalid_ratings = 0
    texts_cleaned = 0

    for column in schema:
        raw = df[column.name]
        if column.kind in ("datetime", "date"):
            df[column.name] = pd.to_datetime(raw, errors="coerce")
        elif column.kind == "rating":
            numbers = pd.to_numeric(raw, errors="coerce")
            # Anything typed but not a whole number in range is treated as unanswered.
            valid = numbers.between(column.min_value, column.max_value) & (numbers % 1 == 0)
            invalid_ratings += int((raw.notna() & ~valid).sum())
            df[column.name] = numbers.where(valid).astype("Int64")
        elif column.kind == "text":
            cleaned = raw.map(_clean_text)
            texts_cleaned += int((raw.notna() & (cleaned.fillna("") != raw.fillna(""))).sum())
            df[column.name] = cleaned
        elif column.kind == "bool":
            df[column.name] = raw.str.strip().str.lower() == "true"

    report = CleaningReport(rows_read, rows_read - len(df), invalid_ratings, texts_cleaned)
    return df, report


def load_survey_responses(path=SAMPLE_DIR / "survey_responses.csv"):
    return _load_table(path, SURVEY_RESPONSES)


def load_google_reviews(path=SAMPLE_DIR / "google_reviews.csv"):
    return _load_table(path, GOOGLE_REVIEWS)
