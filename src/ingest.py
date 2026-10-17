"""Import review files from any supported format into the canonical reviews table.

The importador subagent looks at the files and writes an import plan. This module
only applies plans, using a closed list of tested conversions, and reports what it
could not convert. Columns that the plan does not map, such as reviewer names or
emails, never reach the output.

Run with:
  python -m src.ingest inspect <folder>
  python -m src.ingest apply --plan <plan.json> --output-dir <dir>
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

from src.load_data import load_google_reviews
from src.schema import GOOGLE_REVIEWS, column_names

TABLES = {
    "google_reviews": (GOOGLE_REVIEWS, "google_reviews.csv", "review_id", "GR"),
}
SUPPORTED_SUFFIXES = (".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json")
ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")
REPORT_FILE = "import_report.json"
MAX_EXAMPLES = 3

# --- Conversions: the only operations a plan may ask for -------------------------

STAR_WORDS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
              "UNO": 1, "DOS": 2, "TRES": 3, "CUATRO": 4, "CINCO": 5}
YES = {"si", "sí", "yes", "y", "true", "verdadero", "1", "x"}
NO = {"no", "n", "false", "falso", "0"}
RELATIVE_UNITS = {"hora": 0, "horas": 0, "día": 1, "días": 1, "dia": 1, "dias": 1,
                  "semana": 7, "semanas": 7, "mes": 30, "meses": 30, "año": 365, "años": 365}
RELATIVE_WORDS = {"un": 1, "una": 1, "unos": 1, "unas": 1}


def _missing(value):
    """Empty in any of the ways files express it: None, NaN, NaT or blank text."""
    if isinstance(value, str):
        return not value.strip()
    return value is None or bool(pd.isna(value))


def _blank_to_na(values):
    # pandas may store None as NaN, so transforms check with _missing(), never `is None`.
    return values.astype("object").map(lambda v: None if _missing(v) else v)


def _text(values, options):
    return _blank_to_na(values).map(lambda v: None if _missing(v) else str(v).strip())


def _number(values, options):
    return pd.to_numeric(_blank_to_na(values), errors="coerce")


def _leading_number(values, options):
    """'5 estrellas' -> 5, '4 - Buena' -> 4, '10/10' -> 10."""
    def first(value):
        match = None if _missing(value) else re.search(r"-?\d+(?:[.,]\d+)?", str(value))
        return float(match.group().replace(",", ".")) if match else None
    return pd.to_numeric(_blank_to_na(values).map(first), errors="coerce")


def _star_word(values, options):
    return _blank_to_na(values).map(lambda v: None if _missing(v) else STAR_WORDS.get(str(v).strip().upper()))


def _star_symbols(values, options):
    """'★★★★☆' -> 4: counts filled stars."""
    return _blank_to_na(values).map(lambda v: None if _missing(v) or "★" not in str(v) else str(v).count("★"))


def _yes_no(values, options):
    def parse(value):
        if _missing(value):
            return None
        word = str(value).strip().lower()
        return True if word in YES else False if word in NO else None
    return _blank_to_na(values).map(parse)


def _not_empty(values, options):
    """True when the source has any content (e.g. the text of an owner reply)."""
    return _blank_to_na(values).map(lambda v: not _missing(v))


def _normalize_datetime_text(value):
    text = str(value).strip()
    text = re.sub(r"\s*(GMT|UTC)[+-]?\d*$", "", text)
    text = re.sub(r"\ba\.\s?m\.", "AM", text, flags=re.IGNORECASE)
    return re.sub(r"\bp\.\s?m\.", "PM", text, flags=re.IGNORECASE)


def _datetime(values, options):
    """Dates or date-times. Options: day_first, format, timezone (convert aware times to it)."""
    texts = _blank_to_na(values).map(lambda v: None if _missing(v) else _normalize_datetime_text(v))
    parsed = pd.to_datetime(texts, errors="coerce", dayfirst=options.get("day_first", False),
                            format=options.get("format"), utc=bool(options.get("timezone")))
    if options.get("timezone"):
        parsed = parsed.dt.tz_convert(options["timezone"]).dt.tz_localize(None)
    return parsed


def _date(values, options):
    return _datetime(values, options).dt.normalize()


def relative_days(value):
    """Days ago from a Google Maps label: 'hace 2 semanas' -> 14. None if unreadable."""
    match = re.search(r"hace\s+(\S+)\s+(\S+)", str(value).lower())
    if not match:
        return None
    amount, unit = match.groups()
    unit = unit.strip(".,")
    if unit not in RELATIVE_UNITS:
        return None
    number = RELATIVE_WORDS.get(amount) or (int(amount) if amount.isdigit() else None)
    return None if number is None else number * RELATIVE_UNITS[unit]


def _relative_date(values, options):
    """'hace 3 meses' counted back from options['reference_date']. Approximate by nature."""
    reference = pd.Timestamp(options["reference_date"])
    days = _blank_to_na(values).map(lambda v: None if _missing(v) else relative_days(v))
    return pd.to_datetime(days.map(lambda d: pd.NaT if _missing(d) else reference - pd.Timedelta(days=int(d))))


TRANSFORMS = {
    "text": _text,
    "number": _number,
    "leading_number": _leading_number,
    "star_word": _star_word,
    "star_symbols": _star_symbols,
    "yes_no": _yes_no,
    "not_empty": _not_empty,
    "date": _date,
    "datetime": _datetime,
    "relative_date": _relative_date,
}

# --- Readers ---------------------------------------------------------------------


def _read_json(path, records_path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in filter(None, (records_path or "").split(".")):
        data = data[key]
    if not isinstance(data, list):
        raise ValueError(f"{path}: records_path must lead to a list of records")
    return pd.json_normalize(data)


def parse_google_maps_text(text):
    """Reviews copied by hand from Google Maps, one block per review, blank line between.

    A block is: reviewer name, optional profile line, a line with stars and a relative
    date, the review text, and optionally 'Respuesta del propietario <cuándo>' plus
    the reply text.
    """
    rows = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        star_index = next((i for i, line in enumerate(lines) if "★" in line), None)
        if star_index is None:
            continue
        reply_index = next(
            (i for i, line in enumerate(lines) if line.lower().startswith("respuesta del propietario")), None
        )
        body_end = reply_index if reply_index is not None else len(lines)
        star_line = lines[star_index]
        reply_when = reply_text = None
        if reply_index is not None:
            reply_when = lines[reply_index]
            reply_text = " ".join(lines[reply_index + 1:]) or None
        rows.append({
            "stars": star_line,
            "when": star_line.replace("★", "").replace("☆", "").strip(),
            "text": " ".join(lines[star_index + 1:body_end]) or None,
            "reply_when": reply_when,
            "reply_text": reply_text,
        })
    return pd.DataFrame(rows, columns=["stars", "when", "text", "reply_when", "reply_text"])


def read_source(spec):
    reader = spec["reader"]
    path = Path(spec["path"])
    kind = reader["format"]
    if kind == "csv":
        return pd.read_csv(path, sep=reader.get("sep", ","), encoding=reader.get("encoding", "utf-8"),
                           header=reader.get("header_row", 0), dtype=str, keep_default_na=False)
    if kind == "excel":
        return pd.read_excel(path, sheet_name=reader.get("sheet", 0), header=reader.get("header_row", 0), dtype=object)
    if kind == "json":
        return _read_json(path, reader.get("records_path"))
    if kind == "google_maps_text":
        return parse_google_maps_text(path.read_text(encoding=reader.get("encoding", "utf-8")))
    raise ValueError(f"{path}: unknown reader format {kind!r}; use csv, excel, json or google_maps_text")


# --- Applying a plan -------------------------------------------------------------


def _convert_file(spec, file_number):
    table = spec["table"]
    if table not in TABLES:
        raise ValueError(f"{spec['path']}: unknown table {table!r}; use one of {list(TABLES)}")
    schema, _, id_column, prefix = TABLES[table]
    source = read_source(spec)
    mapping = spec["columns"]

    unknown_targets = sorted(set(mapping) - set(column_names(schema)))
    missing_sources = sorted({m["source"] for m in mapping.values()} - set(source.columns))
    unknown_transforms = sorted({m["transform"] for m in mapping.values()} - set(TRANSFORMS))
    problems = []
    if unknown_targets:
        problems.append(f"columns not in the {table} schema: {unknown_targets}")
    if missing_sources:
        problems.append(f"source columns not in the file: {missing_sources}; it has {list(source.columns)}")
    if unknown_transforms:
        problems.append(f"unknown transforms {unknown_transforms}; use one of {sorted(TRANSFORMS)}")
    if problems:
        raise ValueError(f"{spec['path']}: " + "; ".join(problems))

    output = pd.DataFrame(index=source.index)
    failures, warnings = {}, []
    for target, rule in mapping.items():
        raw = _blank_to_na(source[rule["source"]])
        converted = TRANSFORMS[rule["transform"]](source[rule["source"]], rule.get("options", {}))
        failed = raw.notna() & converted.isna()
        if failed.any():
            examples = raw[failed].astype(str).drop_duplicates().head(MAX_EXAMPLES).tolist()
            failures[target] = {"count": int(failed.sum()), "examples": examples}
        output[target] = converted
        if rule["transform"] == "relative_date":
            warnings.append(f"{target}: approximate dates, rebuilt from relative labels")

    # Positional ids: two diners can leave the same 5 stars with no text on the same
    # day, so identical reviews must stay distinct.
    if id_column not in mapping:
        output[id_column] = [f"{prefix}{file_number}-{i:04d}" for i in range(1, len(output) + 1)]
    if "owner_replied" not in mapping:
        output["owner_replied"] = False
        warnings.append("owner_replied: the file has no reply information; assumed no replies")
    for column in column_names(schema):
        if column not in output:
            output[column] = None

    required = [c.name for c in schema if c.required and c.name != id_column]
    incomplete = output[required].isna().any(axis=1)
    report = {
        "path": str(spec["path"]),
        "table": table,
        "rows_read": int(len(source)),
        "rows_imported": int((~incomplete).sum()),
        "rows_dropped_incomplete": int(incomplete.sum()),
        "mapped_columns": {target: rule["source"] for target, rule in mapping.items()},
        "discarded_columns": [c for c in source.columns if c not in {m["source"] for m in mapping.values()}],
        "conversion_failures": failures,
        "warnings": warnings,
    }
    return table, output.loc[~incomplete, column_names(schema)], report


def _write_table(table, frame, output_dir):
    schema, filename, _, _ = TABLES[table]
    frame = frame.copy()
    for column in schema:
        if column.kind == "rating":
            frame[column.name] = pd.to_numeric(frame[column.name], errors="coerce").round().astype("Int64")
        elif column.kind == "date":
            frame[column.name] = pd.to_datetime(frame[column.name]).dt.strftime("%Y-%m-%d")
        elif column.kind == "datetime":
            frame[column.name] = pd.to_datetime(frame[column.name]).dt.strftime("%Y-%m-%d %H:%M:%S")
    path = Path(output_dir) / filename
    frame.to_csv(path, index=False, lineterminator="\n", encoding="utf-8")
    return path


def apply_plan(plan, output_dir):
    """Convert every file in the plan; write the canonical CSVs and an import report."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    converted, reports = {}, []
    for number, spec in enumerate(plan["files"], start=1):
        table, frame, report = _convert_file(spec, number)
        converted.setdefault(table, []).append(frame)
        reports.append(report)

    written = {}
    for table, frames in converted.items():
        path = _write_table(table, pd.concat(frames, ignore_index=True), output_dir)
        # The rest of the system must be able to load what we wrote.
        load_google_reviews(path)
        written[table] = str(path)

    report = {"outputs": written, "files": reports}
    (output_dir / REPORT_FILE).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


# --- Inspecting a folder ---------------------------------------------------------


def _decode(path):
    raw = Path(path).read_bytes()
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1"


def inspect_file(path, preview_rows=6):
    """What a file looks like, so the importador can write a plan without guessing."""
    path = Path(path)
    info = {"path": str(path), "size_bytes": path.stat().st_size}
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None, header=None, nrows=preview_rows, dtype=object)
        info["format"] = "excel"
        info["sheets"] = {
            name: frame.astype(object).where(frame.notna(), None).astype(str).values.tolist()
            for name, frame in sheets.items()
        }
        return info
    text, encoding = _decode(path)
    info["encoding"] = encoding
    if suffix == ".json":
        data = json.loads(text)
        info["format"] = "json"
        info["top_level"] = {key: f"list of {len(value)}" if isinstance(value, list) else type(value).__name__
                             for key, value in data.items()} if isinstance(data, dict) else type(data).__name__
        records = next((value for value in data.values() if isinstance(value, list)), None) if isinstance(data, dict) else data
        info["first_records"] = (records or [])[:2]
        return info
    lines = text.splitlines()
    info["first_lines"] = [line[:200] for line in lines[: preview_rows + 2]]
    info["format"] = "text"
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t|")
        info["format"] = "csv"
        info["separator"] = dialect.delimiter
    except csv.Error:
        pass
    if "★" in text:
        info["looks_like"] = "google_maps_text"
    return info


def inspect_folder(folder):
    files = sorted(p for p in Path(folder).rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    skipped = sorted(str(p) for p in Path(folder).rglob("*") if p.is_file() and p.suffix.lower() not in SUPPORTED_SUFFIXES)
    return {"files": [inspect_file(path) for path in files], "unsupported_files": skipped}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect data files, or apply an import plan.")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("folder")
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--plan", required=True)
    apply_parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    if args.command == "inspect":
        print(json.dumps(inspect_folder(args.folder), indent=2, ensure_ascii=False, default=str))
        return
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    print(json.dumps(apply_plan(plan, args.output_dir), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
