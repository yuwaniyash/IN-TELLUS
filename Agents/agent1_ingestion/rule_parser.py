"""
Person 2, step 2 — Rule-Based Parsing (the "fast path").

Takes whatever text_extraction.py produced and tries regex/pattern matching
to pull out: consumption value, unit, billing date/period, account number,
previous/current meter readings, and total amount due.

IMPORTANT DESIGN RULE: never fail all-or-nothing. If we find 2 out of 4
fields, return those 2 with the other 2 as None — Person 3 (NLP/IR) and
Person 4 (LLM fallback) build on top of whatever this leaves incomplete.
"""
import re
from dataclasses import dataclass, field

# --- Patterns tuned for common Sri Lankan electricity/water/fuel bill wording ---
# These are intentionally loose to start — Person 2 should tighten them against
# real sample bills in data/sample_bills/ once a few are collected.

CONSUMPTION_PATTERNS = [
    # Prefer the labeled-with-unit form first: "Units Consumed (m³) 850" / "Units Consumed (kWh) 3450"
    # captures BOTH value and the unit in parens together, which is more reliable than guessing unit separately.
    re.compile(r"units?\s*consumed\s*\(([^)]+)\)\D{0,15}?([\d,]+\.?\d*)", re.IGNORECASE),
    # "Units Consumed: 1,234" / "Consumption 450 kWh" / "No. of Units 320"
    re.compile(r"(?:units?\s*consumed|consumption|no\.?\s*of\s*units?)\D{0,10}([\d,]+\.?\d*)", re.IGNORECASE),
    re.compile(r"([\d,]+\.?\d*)\s*(?:kwh|units?)\b", re.IGNORECASE),
]

UNIT_PATTERNS = [
    # kWh, m³/m3, litres, kg — checked in this order since m³ (or the mangled "m3") is unambiguous when present
    re.compile(r"\b(kwh)\b", re.IGNORECASE),
    re.compile(r"(m³|m3)", re.IGNORECASE),
    re.compile(r"\b(units?|litres?|liters?|kg)\b", re.IGNORECASE),
]

# Only real month names — a bare "\b([A-Za-z]{3,9}\s+\d{4})\b" pattern is too loose and
# matches false positives like "Days\n2026" in a meter-reading table.
_MONTH_NAMES = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"

DATE_PATTERNS = [
    # ISO first, since Sri Lankan digital bills (CEB, NWSDB) commonly use yyyy-mm-dd / yyyy/mm/dd
    re.compile(r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b"),
    # dd/mm/yyyy, dd-mm-yyyy
    re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),
    # "01 Jan 2025" / "28 Jul 2026"
    re.compile(rf"\b(\d{{1,2}}\s+{_MONTH_NAMES}\s+\d{{4}})\b", re.IGNORECASE),
    # "January 2025" — real month name required, not any word
    re.compile(rf"\b({_MONTH_NAMES}\s+\d{{4}})\b", re.IGNORECASE),
]

# Slashes are common in Sri Lankan account numbers (e.g. water board: 08/42/105/928/14),
# so the capture group must allow them — cut off at whitespace/newline instead.
ACCOUNT_NUMBER_PATTERNS = [
    re.compile(r"(?:account\s*(?:no\.?|number)|a\/c\s*no\.?)\s*[:\.\-]?\s*([\w\-\/]{4,})", re.IGNORECASE),
]

# Labels that indicate a genuine "bill date" vs. an incidental date (like a meter
# reading row) — checked first so the right date wins when several appear in the text.
DATE_LABEL_PATTERNS = [
    re.compile(r"bill\s*date\D{0,5}(" + r"\d{4}[/-]\d{1,2}[/-]\d{1,2}" + r")", re.IGNORECASE),
    re.compile(r"billing\s*period\D{0,5}(" + r"\d{4}[/-]\d{1,2}(?:[/-]\d{1,2})?" + r")", re.IGNORECASE),
]

# Meter reading table rows — matches a date followed by a reading number,
# e.g. "2026-08-28   5120   32" or "2026-07-27   4780" (no trailing Days
# column on the older row, since that's typically only shown for the
# latest reading in a two-row table).
METER_READING_ROW_PATTERN = re.compile(
    r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})\s+([\d,]+\.?\d*)\s*(?:\d+)?"
)

# "Total Due" / "Total with Tax (Rs.)" / "Total Due (Rs.)" — anchored to
# "Total" + "Due"/"with Tax" so it doesn't accidentally match earlier rows
# like "Fixed Charge" or "This Month Charge".
AMOUNT_PATTERNS = [
    re.compile(r"total\s+due\D{0,15}([\d,]+\.\d{2})", re.IGNORECASE),
    re.compile(r"total\s+with\s+tax\D{0,15}([\d,]+\.\d{2})", re.IGNORECASE),
]


@dataclass
class ParsedField:
    value: str | None = None
    confidence: float = 0.0
    raw_match: str | None = None


@dataclass
class RuleParseResult:
    consumption: ParsedField = field(default_factory=ParsedField)
    unit_raw: ParsedField = field(default_factory=ParsedField)     # goes to Person 3's lookup for normalization
    billing_date: ParsedField = field(default_factory=ParsedField)
    account_number: ParsedField = field(default_factory=ParsedField)
    previous_reading: ParsedField = field(default_factory=ParsedField)
    current_reading: ParsedField = field(default_factory=ParsedField)
    amount_lkr: ParsedField = field(default_factory=ParsedField)
    missing_fields: list[str] = field(default_factory=list)


def _first_match(patterns: list[re.Pattern], text: str) -> tuple[str, str] | tuple[None, None]:
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return m.group(1), m.group(0)
    return None, None


def _extract_meter_readings(text: str) -> tuple[ParsedField, ParsedField]:
    """
    Finds all (date, reading) rows in a meter-reading table and returns
    (previous_reading, current_reading) as ParsedFields, sorted by date
    rather than assumed row order — some bill formats list newest-first,
    others oldest-first.
    """
    matches = METER_READING_ROW_PATTERN.findall(text)
    if len(matches) < 2:
        return ParsedField(), ParsedField()

    # ISO date strings (yyyy-mm-dd or yyyy/mm/dd) sort correctly as plain
    # strings, so no need to parse into real date objects here.
    sorted_rows = sorted(matches, key=lambda row: row[0])

    previous_date, previous_value = sorted_rows[0]
    current_date, current_value = sorted_rows[-1]

    previous = ParsedField(
        value=previous_value.replace(",", ""),
        confidence=0.85,
        raw_match=f"{previous_date} {previous_value}"
    )
    current = ParsedField(
        value=current_value.replace(",", ""),
        confidence=0.85,
        raw_match=f"{current_date} {current_value}"
    )
    return previous, current


def parse_bill_text(text: str) -> RuleParseResult:
    """
    Runs all pattern groups against the raw text. Never raises — always
    returns a result object, with missing_fields listing whatever wasn't
    found so downstream steps know what still needs solving.
    """
    result = RuleParseResult()

    # Consumption + unit: try the combined "Units Consumed (X) 850" pattern first —
    # it pins the unit to the SAME line as the value, avoiding mismatches where a
    # generic "kWh"/"units" elsewhere in the document gets picked instead.
    combined_pattern = CONSUMPTION_PATTERNS[0]
    m = combined_pattern.search(text)
    if m:
        unit_text, value_text = m.group(1), m.group(2)
        result.consumption = ParsedField(value=value_text.replace(",", ""), confidence=0.9, raw_match=m.group(0))
        result.unit_raw = ParsedField(value=unit_text.strip(), confidence=0.9, raw_match=m.group(0))
    else:
        value, raw = _first_match(CONSUMPTION_PATTERNS[1:], text)
        if value:
            result.consumption = ParsedField(value=value.replace(",", ""), confidence=0.85, raw_match=raw)
        else:
            result.missing_fields.append("consumption")

        value, raw = _first_match(UNIT_PATTERNS, text)
        if value:
            result.unit_raw = ParsedField(value=value, confidence=0.8, raw_match=raw)
        else:
            result.missing_fields.append("unit_raw")

    # Date: prefer a labeled "Bill Date" / "Billing Period" match over a bare date
    # pattern, since bare patterns can grab an unrelated date (e.g. a meter-reading row).
    date_value, date_raw = _first_match(DATE_LABEL_PATTERNS, text)
    if not date_value:
        date_value, date_raw = _first_match(DATE_PATTERNS, text)
    if date_value:
        result.billing_date = ParsedField(value=date_value, confidence=0.85 if date_raw else 0.7, raw_match=date_raw)
    else:
        result.missing_fields.append("billing_date")

    value, raw = _first_match(ACCOUNT_NUMBER_PATTERNS, text)
    if value:
        result.account_number = ParsedField(value=value, confidence=0.75, raw_match=raw)
    else:
        result.missing_fields.append("account_number")

    # Meter readings (previous/current) from the readings table
    result.previous_reading, result.current_reading = _extract_meter_readings(text)
    if not result.previous_reading.value:
        result.missing_fields.append("previous_reading")
    if not result.current_reading.value:
        result.missing_fields.append("current_reading")

    # Total amount due
    value, raw = _first_match(AMOUNT_PATTERNS, text)
    if value:
        result.amount_lkr = ParsedField(value=value.replace(",", ""), confidence=0.85, raw_match=raw)
    else:
        result.missing_fields.append("amount_lkr")

    return result


def parse_csv_rows(rows: list[dict]) -> RuleParseResult:
    """
    CSV path: headers are usually explicit, so this is a lighter-weight
    version — match on column names rather than free-text regex.
    Falls back to parse_bill_text on the flattened row content if no
    column names match anything expected.
    """
    if not rows:
        return RuleParseResult(missing_fields=[
            "consumption", "unit_raw", "billing_date", "account_number",
            "previous_reading", "current_reading", "amount_lkr"
        ])

    headers = {h.lower().strip(): h for h in rows[0].keys()}
    result = RuleParseResult()
    row = rows[0]  # TODO Person 2: decide how to handle multi-row bills (e.g. monthly breakdown)

    consumption_col = next((headers[h] for h in headers if "consum" in h or "units" in h or "kwh" in h), None)
    if consumption_col and row.get(consumption_col):
        result.consumption = ParsedField(value=row[consumption_col].replace(",", ""), confidence=0.9)
    else:
        result.missing_fields.append("consumption")

    date_col = next((headers[h] for h in headers if "date" in h or "period" in h), None)
    if date_col and row.get(date_col):
        result.billing_date = ParsedField(value=row[date_col], confidence=0.85)
    else:
        result.missing_fields.append("billing_date")

    account_col = next((headers[h] for h in headers if "account" in h or "a/c" in h), None)
    if account_col and row.get(account_col):
        result.account_number = ParsedField(value=row[account_col], confidence=0.85)
    else:
        result.missing_fields.append("account_number")

    unit_col = next((headers[h] for h in headers if "unit" in h and "consum" not in h), None)
    if unit_col and row.get(unit_col):
        result.unit_raw = ParsedField(value=row[unit_col], confidence=0.8)
    else:
        # Fallback: unit is sometimes embedded in the consumption column's
        # own header, e.g. "Consumption (kWh)" — check there before giving up.
        embedded_unit = None
        if consumption_col:
            m = re.search(r"\(([^)]+)\)", consumption_col)
            if m:
                embedded_unit = m.group(1)
        if embedded_unit:
            result.unit_raw = ParsedField(value=embedded_unit, confidence=0.7, raw_match=consumption_col)
        else:
            result.missing_fields.append("unit_raw")

    # Previous/current reading columns — column-name match, same spirit as above.
    prev_col = next((headers[h] for h in headers if "previous" in h and "read" in h), None)
    if prev_col and row.get(prev_col):
        result.previous_reading = ParsedField(value=row[prev_col].replace(",", ""), confidence=0.85)
    else:
        result.missing_fields.append("previous_reading")

    curr_col = next((headers[h] for h in headers if "current" in h and "read" in h), None)
    if curr_col and row.get(curr_col):
        result.current_reading = ParsedField(value=row[curr_col].replace(",", ""), confidence=0.85)
    else:
        result.missing_fields.append("current_reading")

    amount_col = next((headers[h] for h in headers if "total" in h or "amount" in h or "cost" in h), None)
    if amount_col and row.get(amount_col):
        result.amount_lkr = ParsedField(value=row[amount_col].replace(",", ""), confidence=0.8)
    else:
        result.missing_fields.append("amount_lkr")

    return result