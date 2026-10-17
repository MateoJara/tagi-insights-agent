"""Tests for applying import plans to the messy-format examples."""

import json

import pandas as pd
import pytest

from src import ingest
from src.generate_import_examples import KEY_DIR, OUTPUT_DIR, PASTED_ON
from src.load_data import load_google_reviews

EXAMPLES = OUTPUT_DIR
REVIEW_COLUMNS = ["review_date", "rating", "text", "owner_replied", "owner_reply_date"]

# The plans the importador is expected to write for each example file.
PLANS = {
    "csv_es": {
        "path": str(EXAMPLES / "resenas_exportadas.csv"),
        "table": "google_reviews",
        "reader": {"format": "csv", "sep": ";", "encoding": "utf-8-sig"},
        "columns": {
            "review_date": {"source": "Fecha", "transform": "date", "options": {"day_first": True}},
            "rating": {"source": "Calificación", "transform": "leading_number"},
            "text": {"source": "Reseña", "transform": "text"},
            "owner_replied": {"source": "¿Respondida?", "transform": "yes_no"},
            "owner_reply_date": {"source": "Fecha de respuesta", "transform": "date", "options": {"day_first": True}},
        },
    },
    "xlsx": {
        "path": str(EXAMPLES / "reviews_export.xlsx"),
        "table": "google_reviews",
        "reader": {"format": "excel", "sheet": "Reviews", "header_row": 2},
        "columns": {
            "review_date": {"source": "Date", "transform": "date"},
            "rating": {"source": "Rating", "transform": "number"},
            "text": {"source": "Review", "transform": "text"},
            "owner_replied": {"source": "Owner response", "transform": "not_empty"},
            "owner_reply_date": {"source": "Response date", "transform": "date"},
        },
    },
    "json": {
        "path": str(EXAMPLES / "google_business_reviews.json"),
        "table": "google_reviews",
        "reader": {"format": "json", "records_path": "reviews"},
        "columns": {
            "review_date": {"source": "createTime", "transform": "date", "options": {"timezone": "America/Bogota"}},
            "rating": {"source": "starRating", "transform": "star_word"},
            "text": {"source": "comment", "transform": "text"},
            "owner_replied": {"source": "reviewReply.comment", "transform": "not_empty"},
            "owner_reply_date": {"source": "reviewReply.updateTime", "transform": "date",
                                 "options": {"timezone": "America/Bogota"}},
        },
    },
    "pasted": {
        "path": str(EXAMPLES / "resenas_copiadas_de_maps.txt"),
        "table": "google_reviews",
        "reader": {"format": "google_maps_text"},
        "columns": {
            "review_date": {"source": "when", "transform": "relative_date",
                            "options": {"reference_date": str(PASTED_ON.date())}},
            "rating": {"source": "stars", "transform": "star_symbols"},
            "text": {"source": "text", "transform": "text"},
            "owner_replied": {"source": "reply_text", "transform": "not_empty"},
            "owner_reply_date": {"source": "reply_when", "transform": "relative_date",
                                 "options": {"reference_date": str(PASTED_ON.date())}},
        },
    },
}


def _import(tmp_path, *names):
    report = ingest.apply_plan({"files": [PLANS[name] for name in names]}, tmp_path)
    return report, tmp_path


def _expected_reviews(tmp_path):
    """The answer key, loaded and cleaned the same way the importer's output is."""
    key = pd.read_csv(KEY_DIR / "expected_reviews.csv")
    key.insert(0, "review_id", [f"K-{i}" for i in range(len(key))])
    path = tmp_path / "expected.csv"
    key.to_csv(path, index=False)
    return load_google_reviews(path)[0]


@pytest.mark.parametrize("name", ["csv_es", "xlsx", "json"])
def test_tabular_review_exports_match_the_key(tmp_path, name):
    report, out = _import(tmp_path, name)
    imported, _ = load_google_reviews(out / "google_reviews.csv")
    expected = _expected_reviews(tmp_path)
    pd.testing.assert_frame_equal(imported[REVIEW_COLUMNS], expected[REVIEW_COLUMNS], check_dtype=False)
    assert report["files"][0]["conversion_failures"] == {}
    assert report["files"][0]["rows_dropped_incomplete"] == 0


def test_names_never_reach_the_output(tmp_path):
    report, out = _import(tmp_path, "csv_es", "json")
    written = (out / "google_reviews.csv").read_text(encoding="utf-8")
    assert "Laura M." not in written and "Andrés Gómez" not in written
    assert "Cliente" in report["files"][0]["discarded_columns"]
    assert "reviewer.displayName" in report["files"][1]["discarded_columns"]


def test_pasted_maps_text_within_date_tolerance(tmp_path):
    report, out = _import(tmp_path, "pasted")
    imported, _ = load_google_reviews(out / "google_reviews.csv")
    key = pd.read_csv(KEY_DIR / "expected_reviews_pasted.csv", parse_dates=["review_date"])
    assert len(imported) == len(key)
    assert imported["rating"].tolist() == key["rating"].tolist()
    assert imported["owner_replied"].tolist() == key["owner_replied"].tolist()
    gaps = (imported["review_date"] - key["review_date"]).dt.days.abs()
    assert (gaps <= key["date_tolerance_days"]).all()
    assert any("approximate" in warning for warning in report["files"][0]["warnings"])


def _date_plan(source, options):
    return {"files": [{
        "path": str(source), "table": "google_reviews", "reader": {"format": "csv"},
        "columns": {
            "review_date": {"source": "Fecha", "transform": "date", "options": options},
            "rating": {"source": "Estrellas", "transform": "number"},
        },
    }]}


def test_mixed_date_formats_with_formats_option(tmp_path):
    source = tmp_path / "mixed.csv"
    source.write_text("Fecha,Estrellas\n03/04/2026,5\n2026-05-27,4\n27/05/2026,3\n", encoding="utf-8")
    report = ingest.apply_plan(_date_plan(source, {"formats": ["%d/%m/%Y", "%Y-%m-%d"]}), tmp_path / "out")
    imported, _ = load_google_reviews(tmp_path / "out" / "google_reviews.csv")
    # 03/04/2026 is read day-first because that format comes first in the list.
    assert imported["review_date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-04-03", "2026-05-27", "2026-05-27"]
    assert report["files"][0]["conversion_failures"] == {}


def test_a_date_matching_no_format_is_still_reported(tmp_path):
    source = tmp_path / "mixed.csv"
    source.write_text("Fecha,Estrellas\n03/04/2026,5\nmayo 2026,4\n", encoding="utf-8")
    report = ingest.apply_plan(_date_plan(source, {"formats": ["%d/%m/%Y", "%Y-%m-%d"]}), tmp_path / "out")
    failures = report["files"][0]["conversion_failures"]["review_date"]
    assert failures == {"count": 1, "examples": ["mayo 2026"]}
    assert report["files"][0]["rows_imported"] == 1


def test_format_and_formats_together_are_rejected(tmp_path):
    source = tmp_path / "mixed.csv"
    source.write_text("Fecha,Estrellas\n03/04/2026,5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="either 'format' or 'formats'"):
        ingest.apply_plan(_date_plan(source, {"format": "%d/%m/%Y", "formats": ["%Y-%m-%d"]}), tmp_path / "out")


def test_identical_reviews_are_kept(tmp_path):
    reviews = tmp_path / "reviews.csv"
    reviews.write_text("Fecha,Estrellas\n2026-01-05,5\n2026-01-05,5\n", encoding="utf-8")
    plan = {"files": [{
        "path": str(reviews), "table": "google_reviews", "reader": {"format": "csv"},
        "columns": {"review_date": {"source": "Fecha", "transform": "date"},
                    "rating": {"source": "Estrellas", "transform": "number"}},
    }]}
    ingest.apply_plan(plan, tmp_path / "out")
    imported, cleaning = load_google_reviews(tmp_path / "out" / "google_reviews.csv")
    assert len(imported) == 2 and cleaning.duplicates_removed == 0


def test_report_counts_values_it_could_not_convert(tmp_path):
    source = tmp_path / "bad.csv"
    source.write_text("Fecha,Estrellas,Texto\n2026-01-05,5,Bien\n2026-01-06,cinco y media,Raro\nayer,4,Sin fecha\n",
                      encoding="utf-8")
    plan = {"files": [{
        "path": str(source), "table": "google_reviews", "reader": {"format": "csv"},
        "columns": {
            "review_date": {"source": "Fecha", "transform": "date"},
            "rating": {"source": "Estrellas", "transform": "number"},
            "text": {"source": "Texto", "transform": "text"},
        },
    }]}
    report = ingest.apply_plan(plan, tmp_path / "out")
    file_report = report["files"][0]
    assert file_report["conversion_failures"]["rating"]["count"] == 1
    assert file_report["conversion_failures"]["review_date"]["examples"] == ["ayer"]
    assert file_report["rows_imported"] == 1 and file_report["rows_dropped_incomplete"] == 2
    assert any("owner_replied" in warning for warning in file_report["warnings"])


def test_plan_errors_name_the_problem(tmp_path):
    bad = dict(PLANS["csv_es"], columns={"rating": {"source": "Estrellas", "transform": "magic"}})
    with pytest.raises(ValueError, match="Estrellas") as error:
        ingest.apply_plan({"files": [bad]}, tmp_path)
    assert "magic" in str(error.value)


@pytest.mark.parametrize(
    ("label", "days"),
    [("hace unas horas", 0), ("hace un día", 1), ("hace 3 días", 3), ("hace una semana", 7),
     ("hace 2 semanas", 14), ("hace un mes", 30), ("hace 11 meses", 330), ("hace un año", 365),
     ("Respuesta del propietario hace 2 meses", 60), ("ayer", None)],
)
def test_relative_days(label, days):
    assert ingest.relative_days(label) == days


def test_inspect_describes_each_format():
    result = ingest.inspect_folder(EXAMPLES)
    by_name = {info["path"].split("\\")[-1].split("/")[-1]: info for info in result["files"]}
    assert by_name["resenas_exportadas.csv"]["separator"] == ";"
    assert by_name["resenas_exportadas.csv"]["encoding"] == "utf-8-sig"
    assert by_name["reviews_export.xlsx"]["format"] == "excel"
    assert by_name["google_business_reviews.json"]["top_level"]["reviews"] == "list of 600"
    assert by_name["resenas_copiadas_de_maps.txt"]["looks_like"] == "google_maps_text"
    assert json.dumps(result, default=str)


def test_cli_apply_writes_report(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"files": [PLANS["json"]]}), encoding="utf-8")
    ingest.main(["apply", "--plan", str(plan_path), "--output-dir", str(tmp_path / "out")])
    report = json.loads((tmp_path / "out" / ingest.REPORT_FILE).read_text(encoding="utf-8"))
    assert report["files"][0]["rows_imported"] == 600


def test_inspect_skips_earlier_outputs(tmp_path):
    # Running the analysis twice must not import its own output as new reviews.
    (tmp_path / "resenas.csv").write_text("Fecha,Estrellas\n2026-01-05,5\n", encoding="utf-8")
    plan = {"files": [{"path": str(tmp_path / "resenas.csv"), "table": "google_reviews", "reader": {"format": "csv"},
                       "columns": {"review_date": {"source": "Fecha", "transform": "date"},
                                   "rating": {"source": "Estrellas", "transform": "number"}}}]}
    ingest.apply_plan(plan, tmp_path / "tagi")
    (tmp_path / "tagi" / "comments").mkdir()
    (tmp_path / "tagi" / "comments" / "comments.csv").write_text("id,text\n", encoding="utf-8")
    result = ingest.inspect_folder(tmp_path)
    assert [info["path"] for info in result["files"]] == [str(tmp_path / "resenas.csv")]
    assert result["skipped_output_folders"] == [str(tmp_path / "tagi")]
    assert result["unsupported_files"] == []


def test_inspect_accepts_single_files_and_folders(tmp_path):
    # An owner may attach files to the chat instead of naming a folder.
    attached = EXAMPLES / "resenas_exportadas.csv"
    notes = tmp_path / "notas.docx"
    notes.write_bytes(b"not a data file")
    folder = tmp_path / "otra"
    folder.mkdir()
    (folder / "mas.csv").write_text("Fecha,Estrellas\n2026-01-05,5\n", encoding="utf-8")
    result = ingest.inspect_paths([attached, notes, folder, tmp_path / "no_existe.csv"])
    assert [info["path"] for info in result["files"]] == [str(attached), str(folder / "mas.csv")]
    assert result["files"][0]["separator"] == ";"
    assert result["unsupported_files"] == [str(notes)]
    assert result["missing"] == [str(tmp_path / "no_existe.csv")]


def test_cli_inspect_takes_several_paths(capsys):
    ingest.main(["inspect", str(EXAMPLES / "resenas_exportadas.csv"), str(EXAMPLES / "reviews_export.xlsx")])
    printed = json.loads(capsys.readouterr().out)
    assert len(printed["files"]) == 2
