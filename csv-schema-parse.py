"""
csv_schema_parser.py

Given a top-level directory, recursively walks it and all subdirectories to
find every .csv file, then derives a lightweight "schema" for each one: the
header row, an inferred type per column, a sample value per column, and a
short plain-English description of each column. The result is written out
as a single human-readable text file containing a markdown-style table per
CSV file found.

Uses ONLY the Python standard library (csv, argparse, pathlib, dataclasses,
datetime, logging) -- no third-party dependencies required.

Usage as a script:
    python csv_schema_parser.py /path/to/top_level_dir -o schema_report.txt
    python csv_schema_parser.py /path/to/top_level_dir --samples 10 --debug

Usage as a module:
    from csv_schema_parser import parse_directory, parse_file, save_text_report

    schemas = parse_directory("./data")          # recurses through ./data/**
    schema = parse_file("./data/sub/sales.csv")  # parse a single file
    save_text_report(schemas, "schema_report.txt")

Output format (one block per file):

    {{file path/filename}}
    |column number| column name| sample value| description|
    |--------------------|------------------|------------------|---------------|
    |1|OrderID|1|Whole-number (integer) values, e.g. 1.|
    ...

Design notes:
    - `parse_directory` always recurses -- it walks the given top-level
      directory plus every subdirectory beneath it (any depth) collecting
      .csv files.
    - Delimiter/dialect is auto-detected per file via csv.Sniffer, with a
      comma-delimited fallback if sniffing fails (e.g. very small files).
    - The header row is assumed to be the first non-blank row in the file.
    - Since CSV values are always strings, each value is inspected and
      classified as int, float, bool, datetime (a small set of common
      formats), or str; a column's inferred_type is the single type shared
      by all its sample values, "mixed" if they disagree, or "empty" if the
      column had no non-blank values in the sampled rows. Internally several
      sample values are collected per column to make that inference robust,
      even though only the first one is shown in the report.
    - A file that fails to open/parse (bad encoding, malformed CSV, etc.) is
      reported with an error line instead of raising, so one bad file
      doesn't stop the whole batch.
    - Debug-level logging traces execution step by step (file discovery,
      dialect sniffing, header detection, per-row sampling, per-column type
      inference). Enable with --debug on the CLI, or logging.DEBUG when used
      as a library.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import logging
from dataclasses import dataclass, field
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
    description: str = ""


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


def _describe_column(inferred_type: str, sample: Any) -> str:
    """Build a short, plain-English description of a column from its inferred
    type and single representative sample value."""
    example = "" if sample is None else str(sample)

    if inferred_type == "empty":
        return "No non-blank sample value found; column may be empty or sparsely populated."
    if inferred_type == "int":
        return f"Whole-number (integer) values, e.g. {example}."
    if inferred_type == "float":
        return f"Decimal (floating-point) number values, e.g. {example}."
    if inferred_type == "bool":
        return f"Boolean true/false values, e.g. {example}."
    if inferred_type == "datetime":
        return f"Date/time values, e.g. {example}."
    if inferred_type == "mixed":
        return f"Values of mixed/inconsistent types, e.g. {example}."
    # str / fallback
    return f"Text (string) values, e.g. {example}."


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
        dialect = csv.Sniffer().sniff(sample_text, delimiters=",;\t|")
        logger.debug("Sniffer detected dialect with delimiter %r", dialect.delimiter)
        return dialect
    except csv.Error:
        logger.debug("Sniffer could not determine dialect; falling back to comma-delimited")
        return csv.excel  # sensible comma-delimited default


def parse_file(file_path: str | Path, sample_size: int = 5, encoding: str = "utf-8-sig") -> FileSchema:
    """Parse a single CSV file into a FileSchema."""
    file_path = Path(file_path)
    logger.debug("Opening file: %s (encoding=%s)", file_path, encoding)
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
            logger.debug("Detected delimiter %r for %s", dialect.delimiter, file_path)

            reader = csv.reader(f, dialect)

            # Find the first non-blank row to use as the header.
            headers: list[str] | None = None
            header_row_num = 0
            for i, row in enumerate(reader, start=1):
                if any(cell.strip() != "" for cell in row):
                    headers = row
                    header_row_num = i
                    logger.debug("Header row found at line %d in %s: %r", i, file_path, row)
                    break
                logger.debug("Skipping blank line %d in %s", i, file_path)

            if headers is None:
                logger.debug("No non-blank rows found in %s; treating as empty file", file_path)
                return schema

            headers = [h.strip() if h.strip() != "" else f"Column_{idx}" for idx, h in enumerate(headers, start=1)]
            column_count = len(headers)
            schema.header_row = header_row_num
            schema.column_count = column_count
            logger.debug("Parsed %d header(s) from %s: %r", column_count, file_path, headers)

            samples_per_col: list[list[str]] = [[] for _ in range(column_count)]
            data_row_count = 0

            for row_num, row in enumerate(reader, start=header_row_num + 1):
                if not any(cell.strip() != "" for cell in row):
                    logger.debug("Skipping blank data row at line %d in %s", row_num, file_path)
                    continue  # skip fully blank rows
                data_row_count += 1
                for col_idx in range(column_count):
                    raw = row[col_idx] if col_idx < len(row) else ""
                    if raw.strip() != "" and len(samples_per_col[col_idx]) < sample_size:
                        samples_per_col[col_idx].append(raw)
            logger.debug("Read %d data row(s) from %s", data_row_count, file_path)

            schema.row_count = data_row_count

            columns = []
            for i, name in enumerate(headers):
                inferred_type, coerced_samples = _infer_column(samples_per_col[i])
                first_sample = coerced_samples[0] if coerced_samples else None
                description = _describe_column(inferred_type, first_sample)
                logger.debug(
                    "Column %d (%r) in %s inferred as %r with %d sample value(s)",
                    i + 1, name, file_path, inferred_type, len(coerced_samples),
                )
                columns.append(
                    ColumnSchema(
                        name=name,
                        column_index=i + 1,
                        inferred_type=inferred_type,
                        sample_values=coerced_samples,
                        description=description,
                    )
                )
            schema.columns = columns

    except Exception as exc:  # noqa: BLE001 - capture any read/parse failure
        logger.warning("Failed to parse %s: %s", file_path, exc)
        schema.error = f"{type(exc).__name__}: {exc}"

    logger.debug("Finished parsing %s: %d column(s), %d data row(s)", file_path, schema.column_count, schema.row_count)
    return schema


def parse_directory(
    directory: str | Path,
    sample_size: int = 5,
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    encoding: str = "utf-8-sig",
) -> list[FileSchema]:
    """Recursively parse every CSV file found under `directory`.

    Walks `directory` and all of its subdirectories (at any depth) looking
    for files matching `extensions`. Returns a list of FileSchema, one per
    file found, sorted by path.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")

    logger.debug("Beginning recursive scan of %s for extensions %s", directory, extensions)
    files: list[Path] = []
    for ext in extensions:
        matches = list(directory.rglob(f"*{ext}"))
        logger.debug("Found %d file(s) matching *%s under %s", len(matches), ext, directory)
        files.extend(matches)

    files = sorted(set(files))
    logger.info("Found %d CSV file(s) under %s (including subdirectories)", len(files), directory)

    schemas: list[FileSchema] = []
    for idx, f in enumerate(files, start=1):
        logger.debug("Parsing file %d/%d: %s", idx, len(files), f)
        schemas.append(parse_file(f, sample_size=sample_size, encoding=encoding))

    return schemas


# --------------------------------------------------------------------------- #
# Report generation
# --------------------------------------------------------------------------- #

def _escape_cell(value: Any) -> str:
    """Escape a value for safe use inside a markdown table cell."""
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def save_text_report(schemas: list[FileSchema], output_path: str | Path) -> None:
    """Write a human-readable text report: one markdown-style table per file,
    showing the original path/filename followed by a table of column number,
    column name, a single sample value, and a short description."""
    output_path = Path(output_path)
    logger.debug("Building text table report for %d file(s)", len(schemas))

    lines: list[str] = []

    for schema in schemas:
        lines.append(schema.file_path)

        if schema.error:
            lines.append(f"  ERROR: {schema.error}")
            lines.append("")
            continue

        if not schema.columns:
            lines.append("  (no columns detected -- file may be empty)")
            lines.append("")
            continue

        lines.append("|column number| column name| sample value| description|")
        lines.append("|--------------------|------------------|------------------|---------------|")
        for col in schema.columns:
            sample = col.sample_values[0] if col.sample_values else ""
            lines.append(
                f"|{col.column_index}|{_escape_cell(col.name)}|{_escape_cell(sample)}|{_escape_cell(col.description)}|"
            )
        lines.append("")
        logger.debug("Added table for %s (%d column rows)", schema.file_path, len(schema.columns))

    report_text = "\n".join(lines).rstrip() + "\n"
    with output_path.open("w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info("Wrote text table report for %d file(s) to %s", len(schemas), output_path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse CSV files in a directory and emit a header/sample-value schema."
    )
    parser.add_argument("directory", help="Top-level directory to search (recursively) for .csv files")
    parser.add_argument(
        "-o", "--output", default="schema_report.txt",
        help="Path to write the text table report (default: schema_report.txt)",
    )
    parser.add_argument(
        "-s", "--samples", type=int, default=5, help="Number of sample values to inspect per column (default: 5)"
    )
    parser.add_argument(
        "-e", "--encoding", default="utf-8-sig", help="File encoding to use when reading CSVs (default: utf-8-sig)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose (INFO-level) logging"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug-level logging (step-by-step execution trace)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.debug:
        level = logging.DEBUG
    elif args.verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    logger.debug("Starting run with args: %s", vars(args))

    schemas = parse_directory(
        args.directory,
        sample_size=args.samples,
        encoding=args.encoding,
    )
    save_text_report(schemas, args.output)

    # Brief console summary
    for s in schemas:
        if s.error:
            print(f"[ERROR] {s.file_name}: {s.error}")
            continue
        print(f"{s.file_name}: {s.column_count} columns, {s.row_count} data rows (delimiter='{s.delimiter}')")

    logger.debug("Run complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
