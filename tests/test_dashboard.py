"""Tests for the owner-facing HTML dashboard."""

import json
import re

import pytest

from src import dashboard
from src import generate_sample_data as gen
from src.load_data import SAMPLE_DIR
from src.metrics import build_metrics

SURVEY = SAMPLE_DIR / "survey_responses.csv"
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


@pytest.fixture(scope="module")
def data():
    return dashboard.build_dashboard_data(SURVEY, REVIEWS, _insights())


def test_kpis_match_metrics(data):
    metrics = build_metrics(SURVEY, REVIEWS)
    values = [kpi["value"] for kpi in data["kpis"]]
    assert values == [
        f"{metrics['survey']['mean_overall']:.1f}",
        f"{metrics['survey']['satisfied_share']:.0%}",
        f"{metrics['reviews']['recent_mean_rating']:.1f}",
        f"{metrics['reviews']['recent_reply_rate']:.0%}",
    ]
    answered = metrics["survey"]["answered"]["rating_overall"]
    assert f"{answered} respuestas" in data["kpis"][0]["detail"]
    assert all(kpi["status"] in ("good", "warn", "crit") for kpi in data["kpis"])


def test_flags_the_planted_story(data):
    aspects = {row["label"]: row for row in data["aspects"]}
    assert aspects["Servicio"]["status_label"] == "Empeoró"
    assert aspects["Comida"]["status_label"] == "Se mantiene"
    assert not any(row["change"] in ("-0.0", "+0.0") for row in data["aspects"])
    assert data["kpis"][3]["status"] == "crit"


def test_distribution_and_trend_are_consistent(data):
    assert sum(row["n"] for row in data["distribution"]) == data["n_reviews"] == gen.N_GOOGLE_REVIEWS
    assert data["rating_sum"] == sum(row["stars"] * row["n"] for row in data["distribution"])
    assert sum(float(row["share"].rstrip("%")) for row in data["distribution"]) == pytest.approx(100)
    assert len(data["months"]) == len(data["responses_per_month"]) == 6
    assert all(len(serie["values"]) == 6 for serie in data["trend"])
    assert sum(data["responses_per_month"]) == data["n_responses"]


def test_listed_reviews_have_text_and_are_newest_first(data):
    reviews = data["reviews"]
    assert 0 < len(reviews) <= dashboard.MAX_REVIEWS_LISTED
    assert all(review["text"] for review in reviews)
    assert reviews[0]["date"].endswith("2026")
    assert data["n_reviews_with_text"] >= len(reviews)


def test_render_embeds_the_same_data(data):
    page = dashboard.render_dashboard(data)
    assert "<title>Tablero Restaurante Demo</title>" in page
    assert "__DATA_JSON__" not in page and "__TITLE__" not in page
    assert _embedded_data(page) == json.loads(json.dumps(data))


def test_text_cannot_break_out_of_the_page():
    hostile = '</script><script>alert(1)</script> <b>&'
    data = dashboard.build_dashboard_data(SURVEY, REVIEWS, _insights(business_name=hostile, alert=hostile))
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


def test_main_writes_the_file(tmp_path):
    output = tmp_path / "out" / "dashboard.html"
    dashboard.main(["--insights", str(_write(tmp_path, _insights())), "--output", str(output)])
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")
