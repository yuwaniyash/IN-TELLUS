"""
Person 2, step 1 — Text Extraction.

Gets plain text (PDF) or rows (CSV) out of a validated file. Does NOT try
to understand the content — that's rule_parser.py's job. Keep this dumb
and reliable.
"""
from pathlib import Path

import pandas as pd
import pdfplumber

UPLOAD_ROOT = Path(__file__).parent.parent.parent  # repo root, since file_path is relative to it


def extract_text_from_pdf(file_path: str) -> str:
    """
    Concatenates text from every page. If a bill spans multiple pages,
    all of it ends up in one string for rule_parser.py to search.
    """
    full_path = UPLOAD_ROOT / file_path
    text_chunks = []
    with pdfplumber.open(full_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
    return "\n".join(text_chunks)


def extract_rows_from_csv(file_path: str) -> list[dict]:
    """
    Returns a list of row dicts (column name -> value), using the first
    row as headers. Keeps everything as strings — type coercion happens
    in rule_parser.py, not here.
    """
    full_path = UPLOAD_ROOT / file_path
    df = pd.read_csv(full_path, dtype=str, keep_default_na=False)
    return df.to_dict(orient="records")


def extract_text(file_path: str, file_type: str) -> str | list[dict]:
    """
    Dispatches based on file_type ('pdf' | 'csv') from Person 1's intake step.
    Returns a string for PDFs, a list of row dicts for CSVs — rule_parser.py
    needs to handle both.
    """
    if file_type == "pdf":
        return extract_text_from_pdf(file_path)
    elif file_type == "csv":
        return extract_rows_from_csv(file_path)
    else:
        raise ValueError(f"Unsupported file_type: {file_type}")
