"""Tests for the messy-format import examples and their answer keys."""

import json

import pandas as pd
import pytest

from src import generate_import_examples as gen


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    root = tmp_path_factory.mktemp("import")
    paths = gen.write_import_examples(root / "examples", root / "key")
    return {path.name: path for path in paths}, root / "key"


def test_writes_every_format(written):
    paths, key_dir = written
    assert set(paths) == {
        "resenas_exportadas.csv",
        "reviews_export.xlsx",
        "google_business_reviews.json",
        "resenas_copiadas_de_maps.txt",
    }
    for name in ("expected_reviews.csv", "expected_reviews_pasted.csv"):
        assert (key_dir / name).exists()


def test_tabular_formats_hold_every_review(written):
    paths, key_dir = written
    expected = pd.read_csv(key_dir / "expected_reviews.csv")
    csv_es = pd.read_csv(paths["resenas_exportadas.csv"], sep=";", encoding="utf-8-sig")
    xlsx = pd.read_excel(paths["reviews_export.xlsx"], header=2)
    reviews = json.loads(paths["google_business_reviews.json"].read_text(encoding="utf-8"))["reviews"]
    assert len(csv_es) == len(xlsx) == len(reviews) == len(expected)
    assert xlsx["Rating"].tolist() == expected["rating"].tolist()
    assert sum("comment" in review for review in reviews) == expected["text"].notna().sum()
    assert sum("reviewReply" in review for review in reviews) == expected["owner_replied"].sum()


def test_owner_replies_match_the_stars(written):
    paths, _ = written
    reviews = json.loads(paths["google_business_reviews.json"].read_text(encoding="utf-8"))["reviews"]
    for review in reviews:
        if "reviewReply" in review and review["starRating"] in ("FOUR", "FIVE"):
            assert review["reviewReply"]["comment"] in gen.OWNER_REPLIES["positive"]


def test_pasted_text_uses_relative_dates(written):
    paths, key_dir = written
    text = paths["resenas_copiadas_de_maps.txt"].read_text(encoding="utf-8")
    key = pd.read_csv(key_dir / "expected_reviews_pasted.csv")
    assert len(key) == gen.N_PASTED_REVIEWS
    assert text.count("Local Guide") == gen.N_PASTED_REVIEWS
    assert "hace " in text and "2026-" not in text
    assert (key["date_tolerance_days"] > 0).all()


@pytest.mark.parametrize(
    ("days", "label"),
    [(0, "hace unas horas"), (1, "hace un día"), (3, "hace 3 días"), (8, "hace una semana"),
     (20, "hace 2 semanas"), (45, "hace un mes"), (100, "hace 3 meses"), (400, "hace un año")],
)
def test_relative_labels(days, label):
    assert gen._relative(days) == label


def test_same_seed_same_files(tmp_path):
    first = gen.write_import_examples(tmp_path / "a", tmp_path / "ka")
    second = gen.write_import_examples(tmp_path / "b", tmp_path / "kb")
    for path_a, path_b in zip(first, second):
        if path_a.suffix != ".xlsx":  # xlsx stores a creation timestamp
            assert path_a.read_bytes() == path_b.read_bytes()
