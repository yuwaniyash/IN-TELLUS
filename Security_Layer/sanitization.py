"""
Security_Layer / sanitization.py
==================================
Input sanitization checks. Any agent that accepts user-uploaded files
or raw input should validate through here first.

This file answers ONE question: "Is this input safe to process?"
It does NOT save files, touch the database, or do anything else.
"""

import csv
import io
import os
import re

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {".pdf", ".csv"}

# Characters that indicate a spreadsheet formula/DDE trigger when they open
# a cell. '=' and '@' have essentially no legitimate use as the FIRST
# character of real data, so those stay blocked unconditionally.
#
# '+' and '-' are different: they're also how signed numbers are written
# (a legitimate negative fuel consumption value, a phone number with a
# country code, etc). Blocking every cell starting with '-' rejects real
# data — the actual attack uses '+'/'-' only as a way to sneak a formula
# past a naive "block '='" check (e.g. "-2+3+cmd|'/C calc'!A0"), not as a
# plain signed number. So for '+'/'-' specifically: allow it if the WHOLE
# cell is a plain signed number, and only flag it if there's anything else
# (letters, parentheses, pipes, quotes) riding along with the sign.
ALWAYS_BLOCKED_PREFIXES = ("=", "@")
CONDITIONALLY_BLOCKED_PREFIXES = ("+", "-")

# A plain signed integer or decimal, and nothing else: "-100", "+50",
# "-12.5", "100". Anything with letters/parens/pipes after the sign will
# NOT match this and will still be treated as a potential formula.
SAFE_SIGNED_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _cell_is_risky(cell: str) -> bool:
    if not cell:
        return False
    first = cell[0]
    if first in ALWAYS_BLOCKED_PREFIXES:
        return True
    if first in CONDITIONALLY_BLOCKED_PREFIXES:
        return not SAFE_SIGNED_NUMBER.match(cell)
    return False


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
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF"):
            return False, "File claims to be PDF but doesn't have a valid PDF signature."

    if ext == ".csv":
        # --- CSV injection check ---
        # Malicious CSVs can contain formulas that execute when opened in
        # Excel/Sheets. We parse with the csv module (not a naive
        # line.split(",")) so quoted cells containing commas don't get
        # mis-split into false-positive fragments.
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return False, "CSV file could not be decoded as text."

        reader = csv.reader(io.StringIO(text))
        for row in reader:
            for cell in row:
                cell = cell.strip()
                if _cell_is_risky(cell):
                    return False, (
                        f"This file contains a value that looks like a spreadsheet formula "
                        f"rather than plain data (starts with '{cell[0]}'). "
                        f"If this is meant to be a real number, please check the cell and try again."
                    )

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
        # New cases exercising the +/- fix specifically:
        (b"date,site,consumption\n2026-07-10,Site A,-100\n", "negative_fuel.csv"),      # should now PASS
        (b"date,site,consumption\n2026-07-10,Site A,+50\n", "positive_signed.csv"),      # should PASS
        (b"date,site,consumption\n2026-07-10,Site A,-2+3+cmd|'/C calc'!A0\n", "disguised_formula.csv"),  # should still FAIL
        (b"date,phone,consumption\n2026-07-10,+94771234567,100\n", "phone_number.csv"),  # should now PASS
        (b'name,note\n"Smith, John",hello\n', "quoted_comma.csv"),                        # proper CSV parsing check
    ]
    for content, name in tests:
        print(f"{name}: {validate_file(content, name)}")
        