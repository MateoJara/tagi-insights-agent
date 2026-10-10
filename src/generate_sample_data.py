"""Generate the synthetic sample dataset for a fictional restaurant.

Writes data/sample/survey_responses.csv and data/sample/google_reviews.csv.
Run with: python -m src.generate_sample_data
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.survey_schema import GOOGLE_REVIEWS, SURVEY_RESPONSES, column_names

SEED = 42
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"

# Fixed date ranges so the output does not depend on the day it is run.
SURVEY_START = pd.Timestamp("2026-04-01")
REVIEWS_START = pd.Timestamp("2024-10-01")
END = pd.Timestamp("2026-09-30")

# Planted story: service gets worse from this date on, food and value hold,
# and the owner had already stopped replying to reviews a year before the end.
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

POSITIVES = {
    "food": [
        "La comida estuvo deliciosa",
        "Muy rico el plato del día",
        "Las porciones son generosas y todo llegó caliente",
        "El postre fue lo mejor de la visita",
    ],
    "service": [
        "Nos atendieron rápido y con buena actitud",
        "El mesero fue muy amable",
        "Excelente atención de todo el equipo",
    ],
    "ambience": [
        "El lugar es acogedor y la música no molesta",
        "Buen ambiente para conversar",
        "Me gustó la decoración y lo limpio que está todo",
    ],
    "value": [
        "Buen precio para lo que sirven",
        "Muy buena relación calidad-precio",
        "Económico y llenador",
    ],
}

COMPLAINTS = {
    "food": [
        "El plato llegó frío",
        "A la sopa le faltaba sabor",
        "La porción fue más pequeña que otras veces",
    ],
    "service": [
        "Esperamos más de media hora por el pedido",
        "Nadie se acercó a la mesa en un buen rato",
        "El mesero fue cortante cuando pedimos la cuenta",
        "Se equivocaron con el pedido y no ofrecieron cambiarlo",
        "Mala atención, parecía que les molestaba atender",
    ],
    "ambience": [
        "La música estaba demasiado alta",
        "Las mesas están muy juntas",
        "Hacía mucho calor adentro",
    ],
    "value": [
        "Subieron los precios y la porción es la misma",
        "Me pareció caro para lo que sirven",
    ],
}

SUGGESTIONS = [
    "Deberían tener más opciones vegetarianas",
    "Sería bueno poder pagar con transferencia",
    "Ojalá abrieran los domingos",
    "Podrían poner más mesas afuera",
    "Sería útil tener el menú en un código QR",
    "Que haya más personal a la hora del almuerzo",
]


def _random_days(rng, start, end, n):
    n_days = (end - start).days + 1
    return start + pd.to_timedelta(rng.integers(0, n_days, n), unit="D")


def _messy(text, rng):
    """Occasionally distort casing and spacing, as free-text answers do."""
    roll = rng.random()
    if roll < 0.05:
        return text.upper()
    if roll < 0.10:
        return text.lower()
    if roll < 0.15:
        return f"  {text} "
    if roll < 0.18:
        return text.replace(" ", "  ", 1)
    return text


def _pick_aspect(ratings, rng, best):
    target = max(ratings.values()) if best else min(ratings.values())
    return rng.choice([aspect for aspect, value in ratings.items() if value == target])


def _survey_texts(ratings, overall, rng):
    positives = complaints = suggestions = None
    if rng.random() < (0.35 if overall >= 4 else 0.10):
        aspect = _pick_aspect(ratings, rng, best=True)
        positives = _messy(rng.choice(POSITIVES[aspect]), rng)
    if rng.random() < (0.55 if min(ratings.values()) <= 2 else 0.05):
        aspect = _pick_aspect(ratings, rng, best=False)
        complaints = _messy(rng.choice(COMPLAINTS[aspect]), rng)
    if rng.random() < 0.15:
        suggestions = _messy(rng.choice(SUGGESTIONS), rng)
    return positives, complaints, suggestions


def generate_survey_responses(rng):
    n = N_SURVEY_ROWS - N_SURVEY_DUPLICATES
    days = _random_days(rng, SURVEY_START, END, n)
    hours = rng.choice([12, 13, 14, 19, 20, 21], n)
    minutes = rng.integers(0, 60, n)
    submitted_at = (
        days + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")
    ).sort_values()

    # One hidden satisfaction level per diner keeps the ratings correlated.
    satisfaction = rng.normal(4.1, 0.7, n)
    raw = {
        aspect: satisfaction + ASPECT_OFFSET[aspect] + rng.normal(0, 0.5, n)
        for aspect in ASPECTS
    }
    raw["service"] = raw["service"] + np.where(
        submitted_at >= SERVICE_DECLINE_START, SERVICE_DECLINE_OFFSET, 0.0
    )
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

    texts = [
        _survey_texts(
            {aspect: row[f"rating_{aspect}"] for aspect in ASPECTS},
            row["rating_overall"],
            rng,
        )
        for _, row in df.iterrows()
    ]
    df[["positives", "complaints", "suggestions"]] = pd.DataFrame(texts, index=df.index)

    # Some diners skip questions.
    for column in SURVEY_RESPONSES:
        if column.kind == "rating":
            skipped = rng.random(n) < MISSING_RATING_RATE
            df[column.name] = df[column.name].astype("Int64").mask(skipped)

    # A few diners submit the form twice.
    duplicated = df.iloc[rng.choice(n, N_SURVEY_DUPLICATES, replace=False)]
    df = pd.concat([df, duplicated]).sort_values("submitted_at", kind="stable")
    return df[column_names(SURVEY_RESPONSES)].reset_index(drop=True)


def _review_text(rating, in_decline, rng):
    if rating >= 4:
        return rng.choice(POSITIVES[rng.choice(ASPECTS)])
    complaint_aspect = "service" if in_decline and rng.random() < 0.8 else rng.choice(ASPECTS)
    complaint = rng.choice(COMPLAINTS[complaint_aspect])
    if rating == 3:
        # Praise a different aspect so the review does not contradict itself.
        other_aspects = [aspect for aspect in ASPECTS if aspect != complaint_aspect]
        praise = rng.choice(POSITIVES[rng.choice(other_aspects)])
        return f"{praise}, pero {complaint[0].lower()}{complaint[1:]}"
    return complaint


def generate_google_reviews(rng):
    n = N_GOOGLE_REVIEWS
    review_dates = _random_days(rng, REVIEWS_START, END, n).sort_values()

    rows = []
    for i, review_date in enumerate(review_dates, start=1):
        in_decline = review_date >= SERVICE_DECLINE_START
        probs = REVIEW_RATING_PROBS_DECLINE if in_decline else REVIEW_RATING_PROBS
        rating = int(rng.choice([1, 2, 3, 4, 5], p=probs))
        # Most Google ratings come without any text.
        text = None
        if rng.random() < REVIEW_TEXT_RATE:
            text = _messy(_review_text(rating, in_decline, rng), rng)
        reply_rate = 0.6 if review_date < OWNER_STOPS_REPLYING else 0.05
        owner_replied = bool(rng.random() < reply_rate)
        reply_date = pd.NaT
        if owner_replied:
            reply_date = review_date + pd.Timedelta(days=int(rng.integers(1, 11)))
        rows.append((f"GR-{i:04d}", review_date, rating, text, owner_replied, reply_date))

    return pd.DataFrame(rows, columns=column_names(GOOGLE_REVIEWS))


def write_sample_data(output_dir=OUTPUT_DIR, seed=SEED):
    rng = np.random.default_rng(seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    survey_path = output_dir / "survey_responses.csv"
    reviews_path = output_dir / "google_reviews.csv"
    generate_survey_responses(rng).to_csv(
        survey_path, index=False, lineterminator="\n", encoding="utf-8"
    )
    generate_google_reviews(rng).to_csv(
        reviews_path, index=False, lineterminator="\n", encoding="utf-8", date_format="%Y-%m-%d"
    )
    return survey_path, reviews_path


if __name__ == "__main__":
    for path in write_sample_data():
        print(f"{path} ({len(pd.read_csv(path))} rows)")
