"""
Security_Layer / sanitization.py
==================================
Input sanitization checks. Any agent that accepts user-uploaded files
or raw input should validate through here first.

This file answers ONE question: "Is this input safe to process?"
It does NOT save files, touch the database, or do anything else.
"""

import os

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {".pdf", ".csv"}


def validate_file(file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """
    Checks if an uploaded file is safe to process.
    Returns (is_valid: bool, reason: str) -- reason is "ok" if valid,
    otherwise explains what failed.
    """

    # --- Check file extension ---
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' not allowed. Only PDF and CSV accepted."

    # --- Check file size ---
    if len(file_bytes) == 0:
        return False, "File is empty."
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return False, f"File too large ({len(file_bytes)} bytes). Max allowed: {MAX_FILE_SIZE_BYTES} bytes."

    # --- Check the file's actual content matches its claimed type ---
    # A real PDF always starts with these bytes -- this catches disguised files
    # (e.g. a .exe renamed to .pdf won't have this signature)
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF"):
            return False, "File claims to be PDF but doesn't have a valid PDF signature."

    if ext == ".csv":
        # --- CSV injection check ---
        # Malicious CSVs can contain formulas that execute when opened in Excel.
        # Any cell starting with =, +, -, @ is a red flag.
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return False, "CSV file could not be decoded as text."

        risky_prefixes = ("=", "+", "-", "@")
        for line in text.splitlines():
            for cell in line.split(","):
                cell = cell.strip()
                if cell and cell[0] in risky_prefixes:
                    return False, f"Potential CSV injection detected: cell starts with '{cell[0]}'"

    return True, "ok"


# ============================================================
# TEST IT YOURSELF -- run this file directly
# ============================================================
if __name__ == "__main__":
    tests = [
        (b"date,site,consumption\n2025-07-01,Site A,4500\n", "test.csv"),
        (b"this is not a real pdf", "test.pdf"),
        (b"%PDF-1.4 rest of content here", "test.pdf"),
        (b"date,site,consumption\n=cmd|calc,Site A,4500\n", "bad.csv"),
        (b"hello", "test.exe"),
    ]
    for content, name in tests:
        print(f"{name}: {validate_file(content, name)}")