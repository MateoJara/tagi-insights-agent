"""Build the owner-facing HTML dashboard: one self-contained file, no network needed.

Figures come from src.metrics; the short texts (alert, actions, questions) come
from an insights JSON written by the informe-insights skill.

Run with: python -m src.dashboard --insights <json> --output <html>
"""

import argparse
import html
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from src.load_data import SAMPLE_DIR, load_google_reviews
from src.metrics import build_metrics

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

MAX_REVIEWS_LISTED = 40
# Per kind, in the lists and in the "before and now" table alike, so both show the same topics.
MAX_TOPICS_LISTED = 4
SMALL_DETAIL_KINDS = {
    "praise": ("Lo elogian", "good"),
    "complaint": ("Lo echan de menos", "warn"),
    "suggestion": ("Lo sugieren", "warn"),
}
# A smaller move in a topic's share of comments is too small to call a change.
CLEAR_SHARE_CHANGE = 0.10
# With fewer comments than this in a period, a topic is not called up or down at all.
MIN_COMMENTS_COMPARED = 10

# Shown as a link after the invitations to contact Tagi.
TAGI_CONTACT = {
    "label": "Mateo Jaramillo en LinkedIn",
    "url": "https://www.linkedin.com/in/mateo-jaramillo-londoño-b2a475226",
}

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


def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


def round_half_up(value, digits=0):
    """Round the way a reader does: 4.55 -> 4.6, 0.125 -> 0.13.

    round() and format() work on the binary value, where 4.55 is 4.5499999...,
    and would show 4.5. Going through the decimal text avoids that.
    """
    step = Decimal(1).scaleb(-digits)
    return float(Decimal(str(float(value))).quantize(step, rounding=ROUND_HALF_UP))


def one_decimal(value):
    return f"{round_half_up(value, 1):.1f}"


def _percent_points(value, digits=0):
    points = Decimal(str(float(value))) * 100
    return points.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def percent(value, digits=0):
    return f"{_percent_points(value, digits)}%"


def _words(text):
    return len(text.split())


def _sentences(text):
    """Sentences in a text. A period, question or exclamation mark followed by a space ends one, so "4.3" does not."""
    text = text.strip()
    return len([part for part in re.split(r"(?<=[.!?])\s+", text) if part]) if text else 0


def check_insights(insights, data_warnings=()):
    """The limits of references/tablero.md that code can count. Returns the problems, empty when there are none."""
    problems = []
    for field, limit in (("summary", 2), ("alert", 1), ("next_level", 3), ("data_note", 2)):
        if _sentences(insights[field]) > limit:
            problems.append(f"{field} tiene {_sentences(insights[field])} frases (máximo {limit})")
    if _words(insights["headline"]) > 8:
        problems.append(f"headline tiene {_words(insights['headline'])} palabras (máximo 8)")
    low, actions = bool(data_warnings), insights["actions"]
    fewest, most = (1, 3) if low else (3, 6)
    if not fewest <= len(actions) <= most:
        reason = " porque hay pocos datos" if low else ""
        problems.append(f"hay {len(actions)} acciones (deben ser de {fewest} a {most}{reason})")
    for action in actions:
        if _words(action["title"]) > 6:
            problems.append(f"el título {action['title']!r} tiene {_words(action['title'])} palabras (máximo 6)")
        if _sentences(action["text"]) > 2:
            problems.append(f"el texto de {action['title']!r} tiene {_sentences(action['text'])} frases (máximo 2)")
    if not 2 <= len(insights["questions"]) <= 4:
        problems.append(f"hay {len(insights['questions'])} preguntas (deben ser de 2 a 4)")
    return problems


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
        return "—" if value is None else one_decimal(value)

    def share(value):
        return "—" if value is None else percent(value)

    return [
        kpi(
            "Calificación en Google",
            rating(reviews["mean_rating"]),
            "/ 5",
            _rating_status(reviews["mean_rating"]),
            f"{_plural(reviews['n_reviews'], 'reseña', 'reseñas')} en total",
        ),
        kpi(
            f"Últimos {months} meses",
            rating(recent_mean),
            "★",
            _rating_status(recent_mean),
            f"{_plural(reviews['recent_n'], 'reseña', 'reseñas')} · "
            + ("sin reseñas anteriores" if previous_mean is None
               else f"antes {rating(previous_mean)} ({_plural(reviews['previous_n'], 'reseña', 'reseñas')})"),
        ),
        kpi(
            f"Clientes satisfechos, últimos {months} meses",
            share(recent_satisfied),
            "4–5★",
            _share_status(recent_satisfied, 0.8, 0.6, ("Alto", "Medio", "Bajo")),
            f"De {_plural(reviews['recent_n'], 'reseña', 'reseñas')} · "
            + ("sin reseñas anteriores" if previous_satisfied is None
               else f"antes {share(previous_satisfied)} de {reviews['previous_n']}"),
        ),
        kpi(
            "Reseñas recientes respondidas",
            share(reviews["recent_reply_rate"]),
            "",
            _share_status(reviews["recent_reply_rate"], 0.8, 0.3, ("Al día", "Irregular", "Sin responder")),
            f"De {reviews['recent_n']} recientes · "
            + ("nunca ha respondido" if last_reply is None else f"última respuesta: {_short_date(last_reply)}"),
        ),
    ]


def _topic_changes(comment_metrics):
    """Each main complaint and praise: its share of comments before and now."""
    # Without comments in both periods there is nothing to compare: 0% would look like data.
    if comment_metrics is None or not comment_metrics["n_previous_comments"] or not comment_metrics["n_recent_comments"]:
        return []
    n_previous, n_recent = comment_metrics["n_previous_comments"], comment_metrics["n_recent_comments"]
    rows = []
    for kind, label, worse_when_up in (("complaint", "Queja", True), ("praise", "Elogio", False)):
        ranking = comment_metrics["top_complaints" if kind == "complaint" else "top_praise"]
        for entry in ranking[:MAX_TOPICS_LISTED]:
            previous, recent = entry["previous_share"] or 0.0, entry["recent_share"] or 0.0
            # Points between the two rounded shares shown, so the row adds up for the reader.
            points = int(_percent_points(recent) - _percent_points(previous))
            if min(n_previous, n_recent) < MIN_COMMENTS_COMPARED:
                status = ("neutral", "Base pequeña")
            elif abs(recent - previous) < CLEAR_SHARE_CHANGE:
                status = ("neutral", "Sin cambio claro")
            elif (recent > previous) == worse_when_up:
                status = ("crit", "Aumentó" if worse_when_up else "Disminuyó")
            else:
                status = ("good", "Disminuyó" if worse_when_up else "Aumentó")
            rows.append({
                "topic": _topic_label(entry["topic"]),
                "kind": label,
                "previous": percent(previous),
                "recent": percent(recent),
                "previous_count": f"{entry['previous_n'] or 0} de {n_previous}",
                "recent_count": f"{entry['recent_n'] or 0} de {n_recent}",
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


def _data_warning(metrics):
    """The few-data notice, or None when every figure has enough reviews behind it."""
    codes, reviews = metrics["data_warnings"], metrics["reviews"]
    if not codes:
        return None
    months, n_comments = reviews["recent_months"], reviews["recent_text_n"] + reviews["previous_text_n"]
    messages = {
        "few_reviews": f"Con {_plural(reviews['n_reviews'], 'reseña', 'reseñas')}, todas las cifras son "
                       "orientativas: unas pocas opiniones nuevas pueden cambiarlas mucho.",
        "no_previous_reviews": f"Todas sus reseñas son de los últimos {months} meses: todavía no hay un antes "
                               "con qué comparar.",
        "few_previous_reviews": f"Antes de los últimos {months} meses hay solo "
                                f"{_plural(reviews['previous_n'], 'reseña', 'reseñas')}: muy pocas para "
                                "saber si algo cambió.",
        "few_recent_reviews": f"En los últimos {months} meses hay {_plural(reviews['recent_n'], 'reseña', 'reseñas')}: "
                              "muy pocas para saber si algo cambió frente a antes.",
        "few_comments": "Ninguna reseña trae comentario: no hay temas que analizar." if n_comments == 0 else
                        f"Solo {_plural(n_comments, 'reseña trae', 'reseñas traen')} comentario: los temas de los "
                        "comentarios son orientativos.",
    }
    return {
        "items": [messages[code] for code in codes],
        "invitation": "Si quiere conseguir más reseñas o entender mejor a sus clientes, en Tagi podemos "
                      "ayudarle:",
    }


def build_dashboard_data(reviews_path, insights, comment_metrics=None):
    """Everything the template needs, with every figure already formatted."""
    metrics = build_metrics(reviews_path)
    problems = check_insights(insights, metrics["data_warnings"])
    if problems:
        raise ValueError("insights.json no cumple los límites de references/tablero.md:\n- " + "\n- ".join(problems))
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
        "data_warning": _data_warning(metrics),
        # One decimal: rounded shares can still add up
        # to 99.9% or 100.1%, but never visibly far from 100%.
        "distribution": [
            {"stars": stars, "n": n, "share": percent(n / review_summary["n_reviews"], 1)}
            for stars, n in distribution.items()
        ],
        "rating_sum": sum(stars * n for stars, n in distribution.items()),
        "months": [f"{MONTHS[int(key[-2:]) - 1][:3]} {key[:4]}" for key in monthly],
        "reviews_per_month": [values["n_reviews"] for values in monthly.values()],
        "trend": [{
            "label": "Estrellas promedio",
            "values": [None if values["mean_rating"] is None else round_half_up(values["mean_rating"], 1)
                       for values in monthly.values()],
        }],
        "topic_changes": _topic_changes(comment_metrics),
        "comments": _comments(comment_metrics),
        "reviews": _reviews_listed(reviews),
        "n_reviews_with_text": int(reviews["text"].notna().sum()),
        "closing": "Hecho con Tagi Insights Agent, gratis y de código abierto. ¿No sabe cómo usarlo, tiene pocas "
                   "reseñas o quiere llevar herramientas de IA como Claude Code a su negocio? "
                   "Escríbanos:",
        "contact": TAGI_CONTACT,
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
    try:
        data = build_dashboard_data(args.reviews, load_insights(args.insights), comment_metrics)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(data), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
