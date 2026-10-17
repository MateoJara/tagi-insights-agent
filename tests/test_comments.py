"""Tests for exporting comments and counting their labels."""

import json

import pandas as pd
import pytest

from src import comments
from src import generate_sample_data as gen
from src.load_data import load_google_reviews
from src.sample_comments import TOPICS


@pytest.fixture(scope="module")
def exported():
    reviews, _ = load_google_reviews()
    return comments.export_comments(reviews)


@pytest.fixture(scope="module")
def answer_key():
    return pd.read_csv(gen.ANSWER_KEY_PATH, dtype=str)


def labels_from(answer_key):
    """Turn the generator's answer key into a perfect set of labels."""
    labels = answer_key.assign(topic=answer_key["topics"].str.split("|")).explode("topic")
    labels["kind"] = labels["topic"].map(lambda topic: TOPICS[topic][1])
    topics = pd.DataFrame({"topic": sorted(labels["topic"].unique())})
    topics["description"] = "x"
    topics["small_detail"] = topics["topic"] == "detail_cookie"
    return topics, labels[comments.LABEL_COLUMNS].reset_index(drop=True)


def test_export_matches_the_answer_key(exported, answer_key):
    assert len(exported) == len(answer_key)
    assert set(exported["id"]) == set(answer_key["id"])
    assert exported["id"].is_unique
    assert exported["text"].str.strip().eq(exported["text"]).all()
    assert exported["rating"].between(1, 5).all()


def test_perfect_labels_recover_the_planted_stories(exported, answer_key):
    topics, labels = labels_from(answer_key)
    result = comments.count_labels(exported, topics, labels)
    assert result["n_comments"] == len(exported)
    assert result["n_previous_comments"] + result["n_recent_comments"] == len(exported)
    wait = next(entry for entry in result["top_complaints"] if entry["topic"] == "service_wait")
    assert wait["recent_share"] > wait["previous_share"]
    assert wait["n"] == wait["recent_n"] + wait["previous_n"]
    assert [entry["topic"] for entry in result["small_details"]] == ["detail_cookie"]
    assert result["small_details"][0]["n"] >= 10


def test_shares_are_counts_over_the_comments_of_each_period(exported, answer_key):
    topics, labels = labels_from(answer_key)
    result = comments.count_labels(exported, topics, labels)
    for entry in result["top_complaints"] + result["top_praise"]:
        assert entry["previous_share"] == pytest.approx(entry["previous_n"] / result["n_previous_comments"])
        assert entry["recent_share"] == pytest.approx(entry["recent_n"] / result["n_recent_comments"])


def test_small_details_and_vague_comments(exported, answer_key):
    topics, labels = labels_from(answer_key)
    vague = labels["topic"].str.startswith("generic_")
    labels = labels.assign(topic=labels["topic"].where(~vague, comments.NO_DETAIL_TOPIC))
    topics = pd.concat([
        topics[~topics["topic"].str.startswith("generic_")],
        pd.DataFrame([{"topic": comments.NO_DETAIL_TOPIC, "description": "x", "small_detail": False}]),
    ], ignore_index=True)
    # A small detail that is only complained about still has to be listed.
    topics.loc[topics["topic"] == "service_attitude", "small_detail"] = True

    result = comments.count_labels(exported, topics, labels)
    assert result["n_without_detail"] == labels.loc[labels["topic"] == comments.NO_DETAIL_TOPIC, "id"].nunique()
    ranked = result["top_complaints"] + result["top_praise"]
    assert comments.NO_DETAIL_TOPIC not in [entry["topic"] for entry in ranked]
    assert {entry["topic"] for entry in result["small_details"]} == {"detail_cookie", "service_attitude"}


def test_quotes_are_verbatim_and_limited(exported, answer_key):
    topics, labels = labels_from(answer_key)
    result = comments.count_labels(exported, topics, labels)
    texts = set(exported["text"])
    for entry in result["top_complaints"] + result["top_praise"]:
        assert len(entry["quotes"]) <= comments.MAX_QUOTES
        assert all(quote in texts for quote in entry["quotes"])
        assert len(set(entry["quotes"])) == len(entry["quotes"])


def test_validation_reports_what_is_wrong(exported, answer_key):
    topics, labels = labels_from(answer_key)
    with pytest.raises(ValueError, match="have no label"):
        comments.count_labels(exported, topics, labels.iloc[5:])
    with pytest.raises(ValueError, match="unknown kinds"):
        comments.count_labels(exported, topics, labels.assign(kind="queja"))
    with pytest.raises(ValueError, match="not defined"):
        comments.count_labels(exported, topics.iloc[1:], labels)
    ghost = pd.concat([labels, labels.iloc[[0]].assign(id="GR-9999")], ignore_index=True)
    with pytest.raises(ValueError, match="do not exist"):
        comments.count_labels(exported, topics, ghost)
    with pytest.raises(ValueError, match="exactly these columns"):
        comments.count_labels(exported, topics, labels.rename(columns={"kind": "tipo"}))


def test_cli_exports_then_counts(tmp_path, answer_key):
    comments.main(["export", "--output-dir", str(tmp_path)])
    assert len(pd.read_csv(tmp_path / comments.COMMENTS_FILE)) == len(answer_key)
    topics, labels = labels_from(answer_key)
    topics.to_csv(tmp_path / comments.TOPICS_FILE, index=False)
    labels.to_csv(tmp_path / comments.LABELS_FILE, index=False)
    comments.main(["count", "--output-dir", str(tmp_path)])
    result = json.loads((tmp_path / comments.METRICS_FILE).read_text(encoding="utf-8"))
    assert "service_wait" in [entry["topic"] for entry in result["top_complaints"]]


def test_the_no_detail_topic_need_not_be_declared(exported, answer_key):
    topics, labels = labels_from(answer_key)
    vague = labels["topic"].isin(["generic_praise", "generic_complaint"])
    labels.loc[vague, "topic"] = comments.NO_DETAIL_TOPIC
    labels = labels.drop_duplicates()
    topics = topics[~topics["topic"].isin(["generic_praise", "generic_complaint"])]
    result = comments.count_labels(exported, topics.reset_index(drop=True), labels)
    assert result["n_without_detail"] > 0
