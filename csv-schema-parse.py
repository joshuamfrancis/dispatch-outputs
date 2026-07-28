"""
csv_schema_parser.py

Scans a directory for CSV files and, for each file, derives a lightweight
"schema": the header row, an inferred type per column, and a handful of
sample values per column.

Uses ONLY the Python standard library (csv, json, argparse, pathlib,
dataclasses, datetime) -- no third-party dependencies required.

Usage as a script:
    python csv_schema_parser.py /path/to/csvs -o schema.json
    python csv_schema_parser.py /path/to/csvs --samples 10 --recursive

Usage as a module:
    from csv_schema_parser import parse_directory, parse_file

    schema = parse_directory("./data", sample_size=5)
    schema = parse_file("./data/sales.csv", sample_size=5)

Design notes:
    - Delimiter/dialect is auto-detected per file via csv.Sniffer, with a
      comma-delimited fallback if sniffing fails (e.g. very small files).
    - The header row is assumed to be the first non-blank row in the file.
    - Since CSV values are always strings, each value is inspected and
      classified as int, float, bool, datetime (a small set of common
      formats), or str; a column's inferred_type is the single type shared
      by all its sample values, "mixed" if they disagree, or "empty" if the
      column had no non-blank values in the sampled rows.
    - A file that fails to open/parse (bad encoding, malformed CSV, etc.) is
      recorded with an "error" key instead of raising, so one bad file
      doesn't stop the whole batch.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("csv_schema_parser")

DEFAULT_EXTENSIONS = (".csv",)

# A handful of common date/time formats to try when inferring "datetime".
_DATETIME_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M:%S",
    "%d/%m/%Y",
)

# Deliberately excludes "1"/"0" here since those are ambiguous with
# numeric columns (e.g. an ID column) -- int/float are checked first below,
# so bare 1/0 will be classified as int, not bool.
_BOOL_TRUE = {"true", "yes", "y"}
_BOOL_FALSE = {"false", "no", "n"}


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class ColumnSchema:
    name: str
    column_index: int  # 1-based
    inferred_type: str
    sample_values: list[Any] = field(default_factory=list)


@dataclass
class FileSchema:
    file_name: str
    file_path: str
    delimiter: str
    header_row: int
    row_count: int
    column_count: int
    columns: list[ColumnSchema] = field(default_factory=list)
    error: str | None = None


# --------------------------------------------------------------------------- #
# Core parsing logic
# --------------------------------------------------------------------------- #

def _classify_scalar(raw: str) -> tuple[str, Any]:
    """Classify a single raw CSV string, returning (type_label, coerced_value)."""
    value = raw.strip()

    if value == "":
        return "empty", None

    try:
        return "int", int(value)
    except ValueError:
        pass

    try:
        return "float", float(value)
    except ValueError:
        pass

    lowered = value.lower()
    if lowered in _BOOL_TRUE or lowered in _BOOL_FALSE:
        return "bool", lowered in _BOOL_TRUE

    for fmt in _DATETIME_FORMATS:
        try:
            parsed = datetime.datetime.strptime(value, fmt)
            return "datetime", parsed.isoformat()
        except ValueError:
            continue

    return "str", value


def _infer_column(raw_values: Iterable[str]) -> tuple[str, list[Any]]:
    """Given raw string samples for one column, return (inferred_type, coerced_samples)."""
    types_seen = set()
    coerced: list[Any] = []

    for raw in raw_values:
        type_label, coerced_value = _classify_scalar(raw)
        if type_label == "empty":
            continue
        types_seen.add(type_label)
        coerced.append(coerced_value)

    if not coerced:
        return "empty", []
    if len(types_seen) == 1:
        return types_seen.pop(), coerced
    if types_seen == {"int", "float"}:
        return "float", coerced
    return "mixed", coerced


def _sniff_dialect(sample_text: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample_text, delimiters=",;\t|")
    except csv.Error:
        return csv.excel  # sensible comma-delimited default


def parse_file(file_path: str | Path, sample_size: int = 5, encoding: str = "utf-8-sig") -> FileSchema:
    """Parse a single CSV file into a FileSchema."""
    file_path = Path(file_path)
    schema = FileSchema(
        file_name=file_path.name,
        file_path=str(file_path),
        delimiter=",",
        header_row=0,
        row_count=0,
        column_count=0,
    )

    try:
        with file_path.open("r", newline="", encoding=encoding, errors="replace") as f:
            sample_text = f.read(8192)
            f.seek(0)
            dialect = _sniff_dialect(sample_text)
            schema.delimiter = dialect.delimiter

            reader = csv.reader(f, dialect)

            # Find the first non-blank row to use as the header.
            headers: list[str] | None = None
            header_row_num = 0
            for i, row in enumerate(reader, start=1):
                if any(cell.strip() != "" for cell in row):
                    headers = row
                    header_row_num = i
                    break

            if headers is None:
                # File is entirely blank.
                return schema

            headers = [h.strip() if h.strip() != "" else f"Column_{idx}" for idx, h in enumerate(headers, start=1)]
            column_count = len(headers)
            schema.header_row = header_row_num
            schema.column_count = column_count

            samples_per_col: list[list[str]] = [[] for _ in range(column_count)]
            data_row_count = 0

            for row in reader:
                if not any(cell.strip() != "" for cell in row):
                    continue  # skip fully blank rows
                data_row_count += 1
                for col_idx in range(column_count):
                    raw = row[col_idx] if col_idx < len(row) else ""
                    if raw.strip() != "" and len(samples_per_col[col_idx]) < sample_size:
                        samples_per_col[col_idx].append(raw)

            schema.row_count = data_row_count

            columns = []
            for i, name in enumerate(headers):
                inferred_type, coerced_samples = _infer_column(samples_per_col[i])
                columns.append(
                    ColumnSchema(
                        name=name,
                        column_index=i + 1,
                        inferred_type=inferred_type,
                        sample_values=coerced_samples,
                    )
                )
            schema.columns = columns

    except Exception as exc:  # noqa: BLE001 - capture any read/parse failure
        logger.warning("Failed to parse %s: %s", file_path, exc)
        schema.error = f"{type(exc).__name__}: {exc}"

    return schema


def parse_directory(
    directory: str | Path,
    sample_size: int = 5,
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    recursive: bool = False,
    encoding: str = "utf-8-sig",
) -> list[FileSchema]:
    """Parse every CSV file in `directory` matching `extensions`.

    Returns a list of FileSchema, one per file found.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")

    glob_fn = directory.rglob if recursive else directory.glob
    files: list[Path] = []
    for ext in extensions:
        files.extend(glob_fn(f"*{ext}"))

    files = sorted(set(files))
    logger.info("Found %d CSV file(s) in %s", len(files), directory)

    return [parse_file(f, sample_size=sample_size, encoding=encoding) for f in files]


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #

def schemas_to_dict(schemas: list[FileSchema]) -> list[dict]:
    return [asdict(s) for s in schemas]


def save_schema(schemas: list[FileSchema], output_path: str | Path) -> None:
    output_path = Path(output_path)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(schemas_to_dict(schemas), f, indent=2)
    logger.info("Wrote schema for %d file(s) to %s", len(schemas), output_path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse CSV files in a directory and emit a header/sample-value schema."
    )
    parser.add_argument("directory", help="Directory containing .csv files")
    parser.add_argument(
        "-o", "--output", default="schema.json", help="Path to write the resulting JSON schema (default: schema.json)"
    )
    parser.add_argument(
        "-s", "--samples", type=int, default=5, help="Number of sample values to capture per column (default: 5)"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recurse into subdirectories"
    )
    parser.add_argument(
        "-e", "--encoding", default="utf-8-sig", help="File encoding to use when reading CSVs (default: utf-8-sig)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose (INFO-level) logging"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")

    schemas = parse_directory(
        args.directory,
        sample_size=args.samples,
        recursive=args.recursive,
        encoding=args.encoding,
    )
    save_schema(schemas, args.output)

    # Brief console summary
    for s in schemas:
        if s.error:
            print(f"[ERROR] {s.file_name}: {s.error}")
            continue
        print(f"{s.file_name}: {s.column_count} columns, {s.row_count} data rows (delimiter='{s.delimiter}')")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
