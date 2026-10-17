"""Write the synthetic sample reviews again in the messy formats real exports come in.

Each file in data/sample/import_examples/ holds the same reviews as the canonical
CSV, so the expected result of importing it is known. The answers
go to tests/fixtures/import/, apart from the inputs.

Run with: python -m src.generate_import_examples
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "data" / "sample"
OUTPUT_DIR = SAMPLE_DIR / "import_examples"
KEY_DIR = ROOT / "tests" / "fixtures" / "import"
SEED = 7

# The day the pasted reviews were "copied" from Google Maps. Their dates are
# relative ("hace 2 meses"), so importing them needs this reference date.
PASTED_ON = pd.Timestamp("2026-10-01")
N_PASTED_REVIEWS = 30

FAKE_NAMES = [
    "Laura M.", "Andrés Gómez", "Camila R.", "Juan Pablo", "Valentina S.", "Diego H.",
    "María José", "Santiago P.", "Daniela Ruiz", "Felipe", "Natalia C.", "Sebastián T.",
    "Paula A.", "Nicolás", "Carolina V.", "Mateo L.", "Isabella", "Alejandro M.",
]
# The owner thanks happy diners and apologises to unhappy ones.
OWNER_REPLIES = {
    "positive": [
        "¡Gracias por tu visita! Nos alegra que lo hayas disfrutado.",
        "Muchas gracias por tus comentarios, te esperamos pronto.",
    ],
    "negative": [
        "Lamentamos lo ocurrido. Escríbenos para conocer más detalles y mejorar.",
        "Sentimos que tu experiencia no haya sido buena. Tomamos nota para mejorar.",
    ],
}
STAR_WORDS = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE"}
def _load_canonical():
    return pd.read_csv(SAMPLE_DIR / "google_reviews.csv", parse_dates=["review_date", "owner_reply_date"])


def _blank(value):
    return "" if pd.isna(value) else value


def _reviews_csv_es(out, reviews, names, replies):
    """Spanish headers, day-first dates, ';' separator and an Excel BOM."""
    frame = pd.DataFrame({
        "Cliente": names,
        "Fecha": reviews["review_date"].dt.strftime("%d/%m/%Y"),
        "Calificación": reviews["rating"].map(lambda r: f"{r} estrella" + ("s" if r > 1 else "")),
        "Reseña": reviews["text"].map(_blank),
        "¿Respondida?": reviews["owner_replied"].map({True: "Sí", False: "No"}),
        "Fecha de respuesta": reviews["owner_reply_date"].dt.strftime("%d/%m/%Y").fillna(""),
    })
    path = out / "resenas_exportadas.csv"
    frame.to_csv(path, index=False, sep=";", encoding="utf-8-sig")
    return path


def _reviews_xlsx(out, reviews, names, replies):
    """English headers below a title row, real dates, reply text instead of a flag."""
    frame = pd.DataFrame({
        "Reviewer": names,
        "Rating": reviews["rating"],
        "Date": reviews["review_date"],
        "Review": reviews["text"],
        "Owner response": [reply if replied else None for reply, replied in zip(replies, reviews["owner_replied"])],
        "Response date": reviews["owner_reply_date"],
    })
    path = out / "reviews_export.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Reviews", index=False, startrow=2)
        writer.sheets["Reviews"]["A1"] = "Review export - Demo Restaurant"
    return path


def _reviews_json(out, reviews, names, replies):
    """Shaped like the Google Business Profile API: star words, ISO times, nested reply."""
    items = []
    for row, name, reply in zip(reviews.itertuples(), names, replies):
        item = {
            "reviewId": f"rv{row.Index:05d}",
            "reviewer": {"displayName": name},
            "starRating": STAR_WORDS[int(row.rating)],
            # Midday in Bogotá, so the UTC date is the same local day.
            "createTime": f"{row.review_date:%Y-%m-%d}T17:00:00Z",
        }
        if not pd.isna(row.text):
            item["comment"] = row.text
        if row.owner_replied:
            item["reviewReply"] = {"comment": reply, "updateTime": f"{row.owner_reply_date:%Y-%m-%d}T17:00:00Z"}
        items.append(item)
    path = out / "google_business_reviews.json"
    path.write_text(json.dumps({"reviews": items, "totalReviewCount": len(items)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _relative(days):
    """How Google Maps shows age: 'hace 3 días', 'hace una semana', 'hace 2 meses'."""
    if days < 1:
        return "hace unas horas"
    if days < 7:
        return "hace un día" if days == 1 else f"hace {days} días"
    if days < 30:
        weeks = days // 7
        return "hace una semana" if weeks == 1 else f"hace {weeks} semanas"
    if days < 365:
        months = days // 30
        return "hace un mes" if months == 1 else f"hace {months} meses"
    years = days // 365
    return "hace un año" if years == 1 else f"hace {years} años"


def _tolerance(days):
    """How far off a date rebuilt from its relative label can honestly be."""
    if days < 7:
        return 1
    if days < 30:
        return 7
    if days < 365:
        return 31
    return 365


def _reviews_pasted(out, reviews, names, replies):
    """Text copied by hand from Google Maps: newest reviews with text, relative dates."""
    pasted = reviews[reviews["text"].notna()].sort_values("review_date", ascending=False).head(N_PASTED_REVIEWS)
    blocks = []
    for row in pasted.itertuples():
        days = (PASTED_ON - row.review_date).days
        lines = [names[row.Index], "Local Guide · 4 reseñas", f"{'★' * int(row.rating)}{'☆' * (5 - int(row.rating))} {_relative(days)}", row.text]
        if row.owner_replied:
            lines += [f"Respuesta del propietario {_relative((PASTED_ON - row.owner_reply_date).days)}", replies[row.Index]]
        blocks.append("\n".join(lines))
    path = out / "resenas_copiadas_de_maps.txt"
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")

    key = pasted[["review_date", "rating", "text", "owner_replied"]].copy()
    key["date_tolerance_days"] = [_tolerance((PASTED_ON - date).days) for date in pasted["review_date"]]
    return path, key


def write_import_examples(output_dir=OUTPUT_DIR, key_dir=KEY_DIR, seed=SEED):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    key_dir = Path(key_dir)
    key_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    reviews = _load_canonical()
    names = [str(rng.choice(FAKE_NAMES)) for _ in range(len(reviews))]
    replies = [
        str(rng.choice(OWNER_REPLIES["positive" if rating >= 4 else "negative"]))
        for rating in reviews["rating"]
    ]

    paths = [
        _reviews_csv_es(out, reviews, names, replies),
        _reviews_xlsx(out, reviews, names, replies),
        _reviews_json(out, reviews, names, replies),
    ]
    pasted_path, pasted_key = _reviews_pasted(out, reviews, names, replies)
    paths.append(pasted_path)

    common = {"lineterminator": "\n", "encoding": "utf-8", "index": False}
    reviews.drop(columns="review_id").to_csv(key_dir / "expected_reviews.csv", date_format="%Y-%m-%d", **common)
    pasted_key.to_csv(key_dir / "expected_reviews_pasted.csv", date_format="%Y-%m-%d", **common)
    (key_dir / "README.md").write_text(
        "Respuestas esperadas al importar `data/sample/import_examples/`.\n"
        "El importador no debe leer esta carpeta.\n\n"
        "- `expected_reviews.csv`: lo que deben dar el CSV, el Excel y el JSON de reseñas.\n"
        "- `expected_reviews_pasted.csv`: el texto copiado de Maps (30 reseñas). Sus fechas\n"
        f"  son relativas al {PASTED_ON:%Y-%m-%d}; cada una admite el margen de `date_tolerance_days`.\n",
        encoding="utf-8",
    )
    return paths


if __name__ == "__main__":
    for path in write_import_examples():
        print(path)
