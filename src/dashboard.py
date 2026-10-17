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
from src.metrics import build_metrics

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

MAX_REVIEWS_LISTED = 40
MAX_TOPICS_LISTED = 5
SMALL_DETAIL_KINDS = {
    "praise": ("Lo elogian", "good"),
    "complaint": ("Lo echan de menos", "warn"),
    "suggestion": ("Lo sugieren", "warn"),
}
MAX_TOPICS_COMPARED = 4  # per kind, in the "before and now" table
# A topic whose share of comments moves less than this between periods counts as steady.
STEADY_SHARE_CHANGE = 0.10

# Dashboard text is in Spanish because it is read by the business owner.
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
    reviews = metrics["reviews"]
    months = reviews["recent_months"]
    recent_mean = reviews["recent_mean_rating"]
    previous_mean = reviews["previous_mean_rating"]
    recent_satisfied = reviews["recent_satisfied_share"]
    previous_satisfied = reviews["previous_satisfied_share"]
    last_reply = reviews["last_owner_reply"]

    def kpi(label, value, unit, status, detail):
        return {"label": label, "value": value, "unit": unit, "status": status[0],
                "status_label": status[1], "detail": detail}

    def rating(value):
        return "—" if value is None else f"{value:.1f}"

    def share(value):
        return "—" if value is None else f"{value:.0%}"

    return [
        kpi(
            "Calificación en Google",
            rating(reviews["mean_rating"]),
            "/ 5",
            _rating_status(reviews["mean_rating"]),
            f"{reviews['n_reviews']} reseñas en total",
        ),
        kpi(
            f"Últimos {months} meses",
            rating(recent_mean),
            "★",
            _rating_status(recent_mean),
            f"{reviews['recent_n']} reseñas · antes {rating(previous_mean)}",
        ),
        kpi(
            f"Clientes satisfechos, últimos {months} meses",
            share(recent_satisfied),
            "4–5★",
            _share_status(recent_satisfied, 0.8, 0.6, ("Alto", "Medio", "Bajo")),
            f"Antes {share(previous_satisfied)}",
        ),
        kpi(
            "Reseñas recientes respondidas",
            share(reviews["recent_reply_rate"]),
            "",
            _share_status(reviews["recent_reply_rate"], 0.8, 0.3, ("Al día", "Irregular", "Sin responder")),
            "Nunca ha respondido" if last_reply is None else f"Última respuesta: {_short_date(last_reply)}",
        ),
    ]


def _topic_changes(comment_metrics):
    """Each main complaint and praise: its share of comments before and now."""
    if comment_metrics is None:
        return []
    rows = []
    for kind, label, worse_when_up in (("complaint", "Queja", True), ("praise", "Elogio", False)):
        ranking = comment_metrics["top_complaints" if kind == "complaint" else "top_praise"]
        for entry in ranking[:MAX_TOPICS_COMPARED]:
            previous, recent = entry["previous_share"] or 0.0, entry["recent_share"] or 0.0
            # Points between the two rounded shares shown, so the row adds up for the reader.
            points = round(recent * 100) - round(previous * 100)
            if abs(recent - previous) < STEADY_SHARE_CHANGE:
                status = ("good", "Estable")
            elif (recent > previous) == worse_when_up:
                status = ("crit", "Aumentó" if worse_when_up else "Disminuyó")
            else:
                status = ("good", "Disminuyó" if worse_when_up else "Aumentó")
            rows.append({
                "topic": _topic_label(entry["topic"]),
                "kind": label,
                "previous": f"{previous:.0%}",
                "recent": f"{recent:.0%}",
                "change": f"{points:+d} pts" if points else "0 pts",
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


def _topic_label(topic):
    return topic[0].upper() + topic[1:]


def _topic_rows(entries, limit=MAX_TOPICS_LISTED):
    return [
        {
            "topic": _topic_label(entry["topic"]),
            "n": entry["n"],
            "recent_n": entry["recent_n"],
            "quote": entry["quotes"][0] if entry["quotes"] else None,
        }
        for entry in entries[:limit]
    ]


def _small_details(entries):
    rows = []
    for entry in entries:
        # A detail is shown by how diners mostly talk about it: praised or missed.
        kind = max(entry["kinds"], key=lambda kind: entry["kinds"][kind]["n"])
        label, status = SMALL_DETAIL_KINDS[kind]
        rows.append({
            "topic": _topic_label(entry["topic"]),
            "n": entry["kinds"][kind]["n"],
            "kind_label": label,
            "status": status,
            "quotes": entry["kinds"][kind]["quotes"][:2],
        })
    return rows


def _comments(comment_metrics):
    """The comment section, or None when the comments were not analysed."""
    if comment_metrics is None:
        return None
    return {
        "n_comments": comment_metrics["n_comments"],
        "recent_months": comment_metrics["recent_months"],
        "complaints": _topic_rows(comment_metrics["top_complaints"]),
        "praise": _topic_rows(comment_metrics["top_praise"]),
        "suggestions": _topic_rows(comment_metrics["top_suggestions"], limit=4),
        "small_details": _small_details(comment_metrics["small_details"]),
    }


def build_dashboard_data(reviews_path, insights, comment_metrics=None):
    """Everything the template needs, with every figure already formatted."""
    metrics = build_metrics(reviews_path)
    reviews, _ = load_google_reviews(reviews_path)
    review_summary = metrics["reviews"]
    monthly = metrics["reviews_monthly"]
    distribution = review_summary["distribution"]

    return {
        "insights": insights,
        "horizons": {key: {"label": label, "status": status} for key, (label, status) in HORIZONS.items()},
        "reviews_period": _period(review_summary["first_date"], review_summary["last_date"]),
        "n_reviews": review_summary["n_reviews"],
        "recent_months": review_summary["recent_months"],
        "kpis": _kpis(metrics),
        # One decimal (same format as the PNG chart): rounded shares can still add up
        # to 99.9% or 100.1%, but never visibly far from 100%.
        "distribution": [
            {"stars": stars, "n": n, "share": f"{n / review_summary['n_reviews']:.1%}"}
            for stars, n in distribution.items()
        ],
        "rating_sum": sum(stars * n for stars, n in distribution.items()),
        "months": [f"{MONTHS[int(key[-2:]) - 1][:3]} {key[:4]}" for key in monthly],
        "reviews_per_month": [values["n_reviews"] for values in monthly.values()],
        "trend": [{
            "label": "Estrellas promedio",
            "values": [None if values["mean_rating"] is None else round(values["mean_rating"], 1)
                       for values in monthly.values()],
        }],
        "topic_changes": _topic_changes(comment_metrics),
        "comments": _comments(comment_metrics),
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
    parser.add_argument("--reviews", default=SAMPLE_DIR / "google_reviews.csv")
    parser.add_argument("--insights", default=EXAMPLES_DIR / "insights.json")
    parser.add_argument("--comments", help="comment_metrics.json; omit to leave the comment section out")
    parser.add_argument("--output", default=EXAMPLES_DIR / "dashboard-ejemplo.html")
    args = parser.parse_args(argv)

    comment_metrics = None
    if args.comments:
        comment_metrics = json.loads(Path(args.comments).read_text(encoding="utf-8"))
    data = build_dashboard_data(args.reviews, load_insights(args.insights), comment_metrics)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(data), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
