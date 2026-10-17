"""Tests for the owner-facing HTML dashboard."""

import json
import re

import pandas as pd
import pytest

from src import comments
from src import dashboard
from src import generate_sample_data as gen
from src.load_data import SAMPLE_DIR, load_google_reviews
from src.metrics import build_metrics
from src.sample_comments import TOPICS

REVIEWS = SAMPLE_DIR / "google_reviews.csv"


def _insights(**overrides):
    insights = {
        "business_name": "Restaurante Demo",
        "headline": "headline",
        "summary": "summary",
        "alert": "alert",
        "actions": [{"horizon": "this_week", "title": "t", "text": "x", "why": "w"}],
        "next_level": "next",
        "questions": ["q1"],
        "data_note": "note",
    }
    insights.update(overrides)
    return insights


def _write(tmp_path, insights):
    path = tmp_path / "insights.json"
    path.write_text(json.dumps(insights), encoding="utf-8")
    return path


def _embedded_data(page):
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
    return json.loads(match.group(1))


def _comment_metrics():
    """Comment metrics from perfect labels, built from the generator's answer key."""
    key = pd.read_csv(gen.ANSWER_KEY_PATH, dtype=str)
    labels = key.assign(topic=key["topics"].str.split("|")).explode("topic")
    labels["kind"] = labels["topic"].map(lambda topic: TOPICS[topic][1])
    topics = pd.DataFrame({"topic": sorted(labels["topic"].unique())})
    topics["description"] = "x"
    topics["small_detail"] = topics["topic"] == "detail_cookie"
    exported = comments.export_comments(load_google_reviews()[0])
    return comments.count_labels(exported, topics, labels[comments.LABEL_COLUMNS])


@pytest.fixture(scope="module")
def data():
    return dashboard.build_dashboard_data(REVIEWS, _insights())


@pytest.fixture(scope="module")
def with_comments():
    return dashboard.build_dashboard_data(REVIEWS, _insights(), _comment_metrics())


def test_kpis_match_metrics(data):
    reviews = build_metrics(REVIEWS)["reviews"]
    values = [kpi["value"] for kpi in data["kpis"]]
    assert values == [
        dashboard.one_decimal(reviews["mean_rating"]),
        dashboard.one_decimal(reviews["recent_mean_rating"]),
        dashboard.percent(reviews["recent_satisfied_share"]),
        dashboard.percent(reviews["recent_reply_rate"]),
    ]
    assert f"{reviews['n_reviews']} reseñas" in data["kpis"][0]["detail"]
    assert f"antes {dashboard.one_decimal(reviews['previous_mean_rating'])}" in data["kpis"][1]["detail"]
    assert all(kpi["status"] in ("good", "warn", "crit") for kpi in data["kpis"])


def test_halves_round_up_like_a_reader_would():
    # In binary 91 / 20 is 4.5499..., and round() or f"{:.1f}" would show 4.5.
    assert dashboard.one_decimal(91 / 20) == "4.6"
    assert dashboard.round_half_up(91 / 20, 1) == 4.6
    assert dashboard.one_decimal(4.25) == "4.3"
    assert dashboard.percent(0.125) == "13%"
    assert dashboard.percent(0.285) == "29%"
    assert dashboard.percent(1 / 75) == "1%"
    assert dashboard.percent(0.0) == "0%"
    assert dashboard.percent(0.5265, 1) == "52.7%"


def test_flags_the_planted_story(data):
    assert data["kpis"][1]["status"] in ("warn", "crit")
    assert data["kpis"][3]["status"] == "crit"


def test_distribution_and_trend_are_consistent(data):
    assert sum(row["n"] for row in data["distribution"]) == data["n_reviews"] == gen.N_GOOGLE_REVIEWS
    assert data["rating_sum"] == sum(row["stars"] * row["n"] for row in data["distribution"])
    # Each share is rounded to 0.1, so five of them can miss 100 by at most 0.25.
    assert sum(float(row["share"].rstrip("%")) for row in data["distribution"]) == pytest.approx(100, abs=0.25)
    assert len(data["months"]) == len(data["reviews_per_month"]) == 24
    assert len(data["trend"]) == 1 and len(data["trend"][0]["values"]) == 24
    assert sum(data["reviews_per_month"]) == data["n_reviews"]


def test_listed_reviews_have_text_and_are_newest_first(data):
    reviews = data["reviews"]
    assert 0 < len(reviews) <= dashboard.MAX_REVIEWS_LISTED
    assert all(review["text"] for review in reviews)
    assert reviews[0]["date"].endswith("2026")
    assert data["n_reviews_with_text"] >= len(reviews)


def test_without_comments_there_is_no_topic_table(data):
    assert data["comments"] is None
    assert data["topic_changes"] == []


def test_topic_changes_flag_the_rising_complaint(with_comments):
    rows = {row["topic"]: row for row in with_comments["topic_changes"]}
    wait = rows["Service_wait"]
    assert (wait["kind"], wait["status_label"], wait["status"]) == ("Queja", "Aumentó", "crit")
    for row in with_comments["topic_changes"]:
        points = int(row["change"].split()[0])
        assert points == int(row["recent"].rstrip("%")) - int(row["previous"].rstrip("%"))


def test_comment_section_shows_rankings_and_small_details(with_comments):
    section = with_comments["comments"]
    assert len(section["complaints"]) <= dashboard.MAX_TOPICS_LISTED
    counts = [row["n"] for row in section["praise"]]
    assert counts == sorted(counts, reverse=True)
    detail = section["small_details"][0]
    assert (detail["topic"], detail["kind_label"]) == ("Detail_cookie", "Lo elogian")
    assert 0 < len(detail["quotes"]) <= 2


def test_render_embeds_the_same_data(data):
    page = dashboard.render_dashboard(data)
    assert "<title>Tablero Restaurante Demo</title>" in page
    assert "__DATA_JSON__" not in page and "__TITLE__" not in page
    assert _embedded_data(page) == json.loads(json.dumps(data))
    assert "formulario" not in page.lower()


def test_text_cannot_break_out_of_the_page():
    hostile = '</script><script>alert(1)</script> <b>&'
    data = dashboard.build_dashboard_data(REVIEWS, _insights(business_name=hostile, alert=hostile))
    page = dashboard.render_dashboard(data)
    assert page.count("</script>") == 2
    assert "<script>alert(1)" not in page
    assert _embedded_data(page)["insights"]["alert"] == hostile


def test_insights_are_validated(tmp_path):
    missing = _insights()
    del missing["alert"]
    with pytest.raises(ValueError, match="alert"):
        dashboard.load_insights(_write(tmp_path, missing))
    bad_horizon = _insights(actions=[{"horizon": "someday", "title": "t", "text": "x", "why": "w"}])
    with pytest.raises(ValueError, match="someday"):
        dashboard.load_insights(_write(tmp_path, bad_horizon))


def test_main_writes_the_file_with_comments(tmp_path):
    comments_path = tmp_path / "comment_metrics.json"
    comments_path.write_text(json.dumps(_comment_metrics()), encoding="utf-8")
    output = tmp_path / "out" / "dashboard.html"
    dashboard.main([
        "--insights", str(_write(tmp_path, _insights())),
        "--comments", str(comments_path),
        "--output", str(output),
    ])
    page = output.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>")
    assert _embedded_data(page)["topic_changes"]


def _few_reviews(tmp_path, dates, ratings, texts):
    path = tmp_path / "few.csv"
    pd.DataFrame({
        "review_id": [f"R{i}" for i in range(len(dates))],
        "review_date": pd.to_datetime(dates),
        "rating": ratings,
        "text": texts,
        "owner_replied": [False] * len(dates),
        "owner_reply_date": [None] * len(dates),
    }).to_csv(path, index=False)
    return path


def test_sample_has_no_low_data_notice_but_has_the_closing(data):
    assert data["data_warning"] is None
    assert "Tagi Insights Agent" in data["closing"]
    assert data["contact"]["url"].startswith("https://www.linkedin.com/")


def test_few_reviews_build_a_dashboard_with_a_notice(tmp_path):
    dates = pd.date_range("2024-01-01", periods=8, freq="90D")
    path = _few_reviews(tmp_path, dates, [5, 4, 3, 5, 2, 4, 5, 1],
                        ["Muy buen servicio", None, "Regular", None, None, "Bien", None, "Malo"])
    data = dashboard.build_dashboard_data(path, _insights())
    items = data["data_warning"]["items"]
    assert items[0].startswith("Con 8 reseñas")
    assert any("hay 2 reseñas" in item for item in items)
    assert any("Solo 4 reseñas traen comentario" in item for item in items)
    assert data["data_warning"]["invitation"].endswith("ayudarle:")
    assert "antes 3.8" in data["kpis"][1]["detail"]
    assert "<title>" in dashboard.render_dashboard(data)


def test_without_earlier_reviews_nothing_is_compared(tmp_path):
    path = _few_reviews(tmp_path, ["2026-08-01", "2026-08-15", "2026-09-01"], [5, 4, 5],
                        ["Excelente atención", "Bien", None])
    data = dashboard.build_dashboard_data(path, _insights())
    assert data["kpis"][1]["detail"] == "3 reseñas · sin reseñas anteriores"
    assert any("todavía no hay un antes" in item for item in data["data_warning"]["items"])
    no_earlier_comments = {"n_previous_comments": 0, "n_recent_comments": 2,
                           "top_complaints": [], "top_praise": []}
    assert dashboard._topic_changes(no_earlier_comments) == []


def test_a_single_review_without_text(tmp_path):
    data = dashboard.build_dashboard_data(_few_reviews(tmp_path, ["2026-08-01"], [3], [None]), _insights())
    assert data["kpis"][0]["detail"] == "1 reseña en total"
    assert "Ninguna reseña trae comentario: no hay temas que analizar." in data["data_warning"]["items"]
    assert data["reviews"] == [] and data["trend"][0]["values"] == [3.0]


def test_small_moves_are_not_called_a_change(with_comments):
    for row in with_comments["topic_changes"]:
        if abs(int(row["change"].split()[0])) < dashboard.CLEAR_SHARE_CHANGE * 100 - 1:
            assert (row["status"], row["status_label"]) == ("neutral", "Sin cambio claro")
