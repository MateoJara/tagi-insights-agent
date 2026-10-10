"""Build the owner-facing HTML dashboard: one self-contained file, no network needed.

Figures come from src.metrics; the short texts (alert, actions, questions) come
from an insights JSON written alongside the report.

Run with: python -m src.dashboard --insights <json> --output <html>
"""

import argparse
import html
import json
from pathlib import Path

from src.load_data import SAMPLE_DIR, load_google_reviews
from src.metrics import ASPECT_COLUMNS, build_metrics

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

MAX_REVIEWS_LISTED = 40
STEADY_CHANGE = 0.5  # an aspect moving less than this between periods counts as steady

# Dashboard text is in Spanish because it is read by the business owner.
ASPECT_LABELS = {
    "rating_food": "Comida",
    "rating_service": "Servicio",
    "rating_ambience": "Ambiente",
    "rating_value": "Precio",
}
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
HORIZONS = {
    "this_week": ("Esta semana", "crit"),
    "this_month": ("Este mes", "warn"),
    "ongoing": ("Continuo", "good"),
}
INSIGHT_TEXT_FIELDS = ("business_name", "headline", "summary", "alert", "next_level", "data_note")
ACTION_FIELDS = ("horizon", "title", "text", "why")


def load_insights(path):
    """Read and validate the texts written for the dashboard."""
    insights = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [field for field in (*INSIGHT_TEXT_FIELDS, "actions", "questions") if field not in insights]
    if missing:
        raise ValueError(f"insights file is missing fields: {missing}")
    for action in insights["actions"]:
        absent = [field for field in ACTION_FIELDS if field not in action]
        if absent:
            raise ValueError(f"action {action.get('title', '?')!r} is missing fields: {absent}")
        if action["horizon"] not in HORIZONS:
            raise ValueError(f"unknown horizon {action['horizon']!r}; use one of {list(HORIZONS)}")
    return insights


def _period(first, last):
    start, end = MONTHS[first.month - 1], MONTHS[last.month - 1]
    if first.year == last.year:
        return f"{start} a {end} de {last.year}"
    return f"{start} de {first.year} a {end} de {last.year}"


def _short_date(date):
    return f"{date.day} {MONTHS[date.month - 1][:3]} {date.year}"


def _rating_status(value):
    if value is None:
        return "warn", "Sin datos"
    if value >= 4.5:
        return "good", "Excelente"
    if value >= 4.0:
        return "good", "Sólida"
    if value >= 3.5:
        return "warn", "A mejorar"
    return "crit", "Crítica"


def _share_status(value, good, warn, labels):
    if value is None:
        return "warn", "Sin datos"
    if value >= good:
        return "good", labels[0]
    if value >= warn:
        return "warn", labels[1]
    return "crit", labels[2]


def _kpis(metrics):
    survey, reviews = metrics["survey"], metrics["reviews"]
    months = reviews["recent_months"]
    answered = survey["answered"]["rating_overall"]
    recent_mean = reviews["recent_mean_rating"]
    last_reply = reviews["last_owner_reply"]

    def kpi(label, value, unit, status, detail):
        return {"label": label, "value": value, "unit": unit, "status": status[0],
                "status_label": status[1], "detail": detail}

    return [
        kpi(
            "Calificación general",
            "—" if survey["mean_overall"] is None else f"{survey['mean_overall']:.1f}",
            "/ 5",
            _rating_status(survey["mean_overall"]),
            f"Formulario · {answered} respuestas",
        ),
        kpi(
            "Clientes satisfechos",
            "—" if survey["satisfied_share"] is None else f"{survey['satisfied_share']:.0%}",
            "4–5★",
            _share_status(survey["satisfied_share"], 0.8, 0.6, ("Alto", "Medio", "Bajo")),
            f"Formulario · {answered} respuestas",
        ),
        kpi(
            f"Google, últimos {months} meses",
            "—" if recent_mean is None else f"{recent_mean:.1f}",
            "★",
            _rating_status(recent_mean),
            f"{reviews['recent_n']} reseñas · histórico {reviews['mean_rating']:.1f}",
        ),
        kpi(
            "Reseñas recientes respondidas",
            f"{reviews['recent_reply_rate']:.0%}",
            "",
            _share_status(reviews["recent_reply_rate"], 0.8, 0.3, ("Al día", "Irregular", "Sin responder")),
            "Nunca ha respondido" if last_reply is None else f"Última respuesta: {_short_date(last_reply)}",
        ),
    ]


def _aspects(metrics):
    rows = []
    for aspect, values in metrics["survey_aspect_change"].items():
        if values["change"] <= -STEADY_CHANGE:
            status = ("crit", "Empeoró")
        elif values["change"] >= STEADY_CHANGE:
            status = ("good", "Mejoró")
        elif values["recent"] >= 4.0:
            status = ("good", "Se mantiene")
        else:
            status = ("warn", "A vigilar")
        rows.append({
            "label": ASPECT_LABELS[aspect],
            "previous": f"{values['previous']:.1f}",
            "recent": f"{values['recent']:.1f}",
            # A change that rounds to zero prints as "0.0", not "-0.0".
            "change": f"{values['change']:+.1f}" if round(values["change"], 1) else "0.0",
            "recent_n": values["recent_n"],
            "status": status[0],
            "status_label": status[1],
        })
    return rows


def _reviews_listed(reviews):
    with_text = reviews[reviews["text"].notna()].sort_values("review_date", ascending=False)
    return [
        {
            "date": _short_date(row.review_date),
            "stars": int(row.rating),
            "text": row.text,
            "replied": bool(row.owner_replied),
        }
        for row in with_text.head(MAX_REVIEWS_LISTED).itertuples()
    ]


def build_dashboard_data(survey_path, reviews_path, insights):
    """Everything the template needs, with every figure already formatted."""
    metrics = build_metrics(survey_path, reviews_path)
    reviews, _ = load_google_reviews(reviews_path)
    survey, review_summary = metrics["survey"], metrics["reviews"]
    monthly = metrics["survey_monthly_means"]
    distribution = review_summary["distribution"]

    return {
        "insights": insights,
        "horizons": {key: {"label": label, "status": status} for key, (label, status) in HORIZONS.items()},
        "survey_period": _period(survey["first_date"], survey["last_date"]),
        "reviews_period": _period(review_summary["first_date"], review_summary["last_date"]),
        "n_responses": survey["n_responses"],
        "n_reviews": review_summary["n_reviews"],
        "recent_months": review_summary["recent_months"],
        "kpis": _kpis(metrics),
        # One decimal so the shares add up to 100% (same format as the PNG chart).
        "distribution": [
            {"stars": stars, "n": n, "share": f"{n / review_summary['n_reviews']:.1%}"}
            for stars, n in distribution.items()
        ],
        "rating_sum": sum(stars * n for stars, n in distribution.items()),
        "months": [f"{MONTHS[int(key[-2:]) - 1][:3]} {key[:4]}" for key in monthly],
        "responses_per_month": list(metrics["survey_responses_per_month"].values()),
        "trend": [
            {
                "label": ASPECT_LABELS[aspect],
                "values": [None if values[aspect] != values[aspect] else round(values[aspect], 1)
                           for values in monthly.values()],
            }
            for aspect in ASPECT_COLUMNS
        ],
        "aspects": _aspects(metrics),
        "reviews": _reviews_listed(reviews),
        "n_reviews_with_text": int(reviews["text"].notna().sum()),
    }


def render_dashboard(data):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Escaping "<" keeps any text from closing the script tag that holds the data.
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    title = html.escape(f"Tablero {data['insights']['business_name']}")
    return template.replace("__TITLE__", title).replace("__DATA_JSON__", payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the owner-facing HTML dashboard.")
    parser.add_argument("--survey", default=SAMPLE_DIR / "survey_responses.csv")
    parser.add_argument("--reviews", default=SAMPLE_DIR / "google_reviews.csv")
    parser.add_argument("--insights", default=EXAMPLES_DIR / "insights.json")
    parser.add_argument("--output", default=EXAMPLES_DIR / "dashboard-ejemplo.html")
    args = parser.parse_args(argv)

    data = build_dashboard_data(args.survey, args.reviews, load_insights(args.insights))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(data), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
