"""
Person 2 — Fuel transaction log parser.

Real fuel logs are structurally different from a single-bill CSV (like a
CEB or NWSDB export): they're a transaction ledger, one row per refuel/
generator-fill event, already column-structured (no regex needed to find
values) but messy in a different way — inconsistent casing, unit spelling,
date formats, and free-text site names across rows.

This is a SEPARATE path from parse_csv_rows() in rule_parser.py, which
assumes one row = one bill summary. Use this module when the CSV has
columns like Quantity/Unit/FuelType/TransactionDate (a transaction log),
not when it has one row per billing period.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .site_lookup import normalize_site_name

# --- Unit normalization -----------------------------------------------------
# All variants seen in real logs map to a single canonical spelling.
# NOTE: 'gallons' is intentionally NOT auto-converted to litres — US and UK
# gallons differ (3.785 L vs 4.546 L) and the source data doesn't say which.
# Flag it instead of guessing; Person 3/Person 4 should resolve this with
# the supplier or a documented assumption before it feeds into Agent 2.
UNIT_NORMALIZATION = {
    "l": "litres", "litre": "litres", "litres": "litres",
    "liter": "litres", "liters": "litres",
    "ltr": "litres", "ltrs": "litres",
}
AMBIGUOUS_UNITS = {"gallon", "gallons", "gal"}

# --- Fuel type normalization -------------------------------------------------
FUEL_TYPE_NORMALIZATION = {
    "petrol": "petrol",
    "diesel": "diesel",
}

# --- Date formats actually observed in this dataset -------------------------
_DATE_FORMATS = [
    "%Y-%m-%d",    # 2026-07-10
    "%Y/%m/%d",    # 2026/07/19
    "%d-%m-%Y",    # 15-07-2026
    "%d/%m/%Y",    # 28/07/2026
    "%d.%m.%Y",    # 23.07.2026
    "%d/%m/%y",    # 07/12/26 (2-digit year)
    "%d %b %Y",    # 12 Jul 2026, 09 Jul 2026
    "%d-%b-%Y",    # 03-Jul-2026
    "%d %B %Y",    # 20 July 2026 (full month name)
    "%b %d %Y",    # Jul 27 2026 (month-first)
]


@dataclass
class FuelTransaction:
    transaction_id: str
    company: str
    transaction_date: date | None
    transaction_date_raw: str
    site: str                    # canonical site name, resolved via unit_lookup.normalize_site_name()
    site_raw: str
    fuel_type: str | None        # normalized: 'petrol' | 'diesel' | None if unrecognized
    fuel_type_raw: str
    quantity: float | None
    unit: str | None             # normalized: 'litres' | None
    unit_raw: str
    unit_ambiguous: bool         # True for gallons/etc — needs manual resolution
    warnings: list[str] = field(default_factory=list)


def normalize_unit(raw_unit: str) -> tuple[str | None, bool]:
    """Returns (normalized_unit, is_ambiguous)."""
    cleaned = raw_unit.strip().lower()
    if cleaned in UNIT_NORMALIZATION:
        return UNIT_NORMALIZATION[cleaned], False
    if cleaned in AMBIGUOUS_UNITS:
        return None, True
    return None, False  # genuinely unrecognized, not just ambiguous


def normalize_fuel_type(raw_fuel_type: str) -> str | None:
    cleaned = raw_fuel_type.strip().lower()
    return FUEL_TYPE_NORMALIZATION.get(cleaned)


def parse_date(raw_date: str) -> date | None:
    raw_date = raw_date.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw_date, fmt).date()
        except ValueError:
            continue
    return None  # caller should record this as a warning, not silently drop the row


def parse_fuel_transaction_row(row: dict) -> FuelTransaction:
    warnings = []

    parsed_date = parse_date(row.get("TransactionDate", ""))
    if parsed_date is None:
        warnings.append(f"Unrecognized date format: '{row.get('TransactionDate')}'")

    raw_qty = (row.get("Quantity") or "").strip()
    try:
        quantity = float(raw_qty)
    except ValueError:
        quantity = None
        warnings.append(f"Unparseable quantity: '{raw_qty}'")

    raw_unit = (row.get("Unit") or "").strip()
    unit, ambiguous = normalize_unit(raw_unit)
    if ambiguous:
        warnings.append(f"Ambiguous unit '{raw_unit}' (gallons: US vs UK not specified) — needs manual resolution")
    elif unit is None and raw_unit:
        warnings.append(f"Unrecognized unit: '{raw_unit}'")

    raw_fuel = (row.get("FuelType") or "").strip()
    fuel_type = normalize_fuel_type(raw_fuel)
    if fuel_type is None and raw_fuel:
        warnings.append(f"Unrecognized fuel type: '{raw_fuel}'")

    site_result = normalize_site_name(row.get("Site", ""))
    if site_result.get("needs_review"):
        warnings.append(f"site '{row.get('Site', '')}' unresolved, needs manual review")

    return FuelTransaction(
        transaction_id=row.get("TransactionID", ""),
        company=row.get("Company", "").strip(),
        transaction_date=parsed_date,
        transaction_date_raw=row.get("TransactionDate", ""),
        site=site_result["site"],
        site_raw=row.get("Site", ""),
        fuel_type=fuel_type,
        fuel_type_raw=raw_fuel,
        quantity=quantity,
        unit=unit,
        unit_raw=raw_unit,
        unit_ambiguous=ambiguous,
        warnings=warnings,
    )


def parse_fuel_transaction_csv(rows: list[dict]) -> list[FuelTransaction]:
    """
    Parses every row independently — one bad row (unparseable date, unknown
    unit) never blocks the rest of the file. Check each transaction's
    .warnings list to see what needs review before this feeds Agent 2.
    """
    return [parse_fuel_transaction_row(row) for row in rows]