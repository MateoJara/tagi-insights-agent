"""Comment analysis: export the comments for labeling, then validate and count the labels.

Deciding what a comment is about takes judgment, so the analista-comentarios
subagent does it. Counting is arithmetic, so it happens here.

Run with:
  python -m src.comments export --output-dir <dir>
  python -m src.comments count --output-dir <dir>
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from src.load_data import SAMPLE_DIR, load_google_reviews
from src.metrics import RECENT_MONTHS, recent_mask

KEY = ["id"]
KINDS = ("praise", "complaint", "suggestion")
NO_DETAIL_TOPIC = "sin detalle"  # for comments like "Excelente" that name nothing concrete
TOPIC_COLUMNS = ["topic", "description", "small_detail"]
LABEL_COLUMNS = [*KEY, "topic", "kind"]

COMMENTS_FILE = "comments.csv"
TOPICS_FILE = "comment_topics.csv"
LABELS_FILE = "comment_labels.csv"
METRICS_FILE = "comment_metrics.json"

MAX_QUOTES = 3
QUOTE_MIN_LENGTH, QUOTE_MAX_LENGTH = 20, 160


def export_comments(reviews, months=RECENT_MONTHS):
    """One row per review with a comment: id, date, stars, recent, text."""
    comments = pd.DataFrame({
        "id": reviews["review_id"],
        "date": reviews["review_date"].dt.date,
        "rating": reviews["rating"],
        "recent": recent_mask(reviews["review_date"], months),
        "text": reviews["text"],
    }).dropna(subset=["text"])
    return comments.sort_values("id", ignore_index=True)


def _validate(comments, topics, labels):
    problems = []
    for name, frame, expected in (("topics", topics, TOPIC_COLUMNS), ("labels", labels, LABEL_COLUMNS)):
        if list(frame.columns) != expected:
            problems.append(f"{name} file must have exactly these columns: {expected}")
    if problems:
        raise ValueError("; ".join(problems))

    if topics["topic"].duplicated().any():
        problems.append(f"repeated topics: {sorted(topics.loc[topics['topic'].duplicated(), 'topic'])}")
    if not topics["small_detail"].isin([True, False]).all():
        problems.append("small_detail must be true or false")
    bad_kinds = sorted(set(labels["kind"]) - set(KINDS))
    if bad_kinds:
        problems.append(f"unknown kinds {bad_kinds}; use one of {list(KINDS)}")
    unknown_topics = sorted(set(labels["topic"]) - set(topics["topic"]))
    if unknown_topics:
        problems.append(f"topics used in labels but not defined: {unknown_topics}")
    if labels.duplicated().any():
        problems.append(f"{int(labels.duplicated().sum())} repeated label rows")

    comment_keys = set(map(tuple, comments[KEY].values))
    label_keys = set(map(tuple, labels[KEY].values))
    unknown = sorted(label_keys - comment_keys)
    if unknown:
        problems.append(f"{len(unknown)} labels point to comments that do not exist, e.g. {unknown[:3]}")
    missing = sorted(comment_keys - label_keys)
    if missing:
        problems.append(f"{len(missing)} comments have no label, e.g. {missing[:5]}")
    if problems:
        raise ValueError("; ".join(problems))


def _quotes(rows):
    """Up to three verbatim quotes, newest first, long enough to say something."""
    lengths = rows["text"].str.len()
    usable = rows[lengths.between(QUOTE_MIN_LENGTH, QUOTE_MAX_LENGTH)]
    newest = usable.sort_values(["date", "id"], ascending=[False, True]).drop_duplicates("text")
    return newest["text"].head(MAX_QUOTES).tolist()


def _share(count, total):
    return count / total if total else None


def _summary(rows, totals):
    """Counts, and shares of all comments in each period: the recent period is a few
    months against many before it, so only shares compare fairly."""
    previous_n, recent_n = int((~rows["recent"]).sum()), int(rows["recent"].sum())
    return {
        "n": int(len(rows)),
        "previous_n": previous_n,
        "recent_n": recent_n,
        "previous_share": _share(previous_n, totals["previous"]),
        "recent_share": _share(recent_n, totals["recent"]),
        "quotes": _quotes(rows),
    }


def count_labels(comments, topics, labels, months=RECENT_MONTHS):
    """Validate the labels and count comments per topic and kind."""
    if list(topics.columns) == TOPIC_COLUMNS and NO_DETAIL_TOPIC not in set(topics["topic"]):
        # The no-detail topic always exists; whoever labels should not have to declare it.
        no_detail = pd.DataFrame([{"topic": NO_DETAIL_TOPIC, "description": "Comentario sin un tema concreto",
                                   "small_detail": False}])
        topics = pd.concat([topics, no_detail], ignore_index=True)
    _validate(comments, topics, labels)
    labeled = labels.merge(comments, on=KEY, validate="many_to_one")
    totals = {"previous": int((~comments["recent"]).sum()), "recent": int(comments["recent"].sum())}

    by_topic = []
    for topic in topics.itertuples():
        rows = labeled[labeled["topic"] == topic.topic]
        entry = {
            "topic": topic.topic,
            "description": topic.description,
            "small_detail": bool(topic.small_detail),
            # A comment counts once per topic even if it carries two kinds.
            **{key: value for key, value in _summary(rows.drop_duplicates(KEY), totals).items() if key != "quotes"},
            "kinds": {
                kind: _summary(rows[rows["kind"] == kind], totals)
                for kind in KINDS
                if (rows["kind"] == kind).any()
            },
        }
        by_topic.append(entry)
    by_topic.sort(key=lambda entry: (-entry["n"], entry["topic"]))

    def ranking(kind):
        # Comments that name nothing concrete are counted, but never ranked as a topic.
        ranked = [
            {"topic": entry["topic"], "small_detail": entry["small_detail"], **entry["kinds"][kind]}
            for entry in by_topic
            if kind in entry["kinds"] and entry["topic"] != NO_DETAIL_TOPIC
        ]
        return sorted(ranked, key=lambda entry: (-entry["n"], entry["topic"]))

    without_detail = labeled.loc[labeled["topic"] == NO_DETAIL_TOPIC, KEY].drop_duplicates()
    return {
        "n_comments": int(len(comments)),
        "n_recent_comments": totals["recent"],
        "n_previous_comments": totals["previous"],
        "n_without_detail": int(len(without_detail)),
        "recent_months": months,
        "topics": by_topic,
        "top_complaints": ranking("complaint"),
        "top_praise": ranking("praise"),
        "top_suggestions": ranking("suggestion"),
        # Praised or missed, however few mentions: a small detail is worth showing.
        "small_details": [entry for entry in by_topic if entry["small_detail"]],
    }


def _read(path, bool_columns=()):
    frame = pd.read_csv(path, dtype=str, encoding="utf-8").apply(lambda column: column.str.strip())
    for column in bool_columns:
        if column in frame:
            frame[column] = frame[column].str.lower().map({"true": True, "false": False})
    return frame


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export comments for labeling, or count the labels.")
    parser.add_argument("command", choices=("export", "count"))
    parser.add_argument("--reviews", default=SAMPLE_DIR / "google_reviews.csv")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reviews, _ = load_google_reviews(args.reviews)
    comments = export_comments(reviews)

    if args.command == "export":
        comments.to_csv(output_dir / COMMENTS_FILE, index=False, lineterminator="\n", encoding="utf-8")
        print(f"{output_dir / COMMENTS_FILE} ({len(comments)} comments)")
        return

    topics = _read(output_dir / TOPICS_FILE, bool_columns=["small_detail"])
    labels = _read(output_dir / LABELS_FILE)
    result = count_labels(comments, topics, labels)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    (output_dir / METRICS_FILE).write_text(text + "\n", encoding="utf-8")
    print(f"{output_dir / METRICS_FILE}: {result['n_comments']} comments, {len(result['topics'])} topics")


if __name__ == "__main__":
    main()
