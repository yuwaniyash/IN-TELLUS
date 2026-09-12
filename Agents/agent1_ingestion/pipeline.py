"""
Person 4 — integration layer.

Wires Person 2's output (RuleParseResult: consumption, unit_raw, billing_date,
account_number, each with confidence) and Person 3's lookup_unit() together
into the partial_data dict shape app.py's ExtractionRecord expects
(resource_type, consumption, unit, billing_period, site).

Three things this layer does that neither Person 2 nor Person 3's code does
on its own:

1. Determines resource_type. Nobody upstream extracts this directly — it's
   derived from the canonical unit Person 3's lookup resolves to (kWh ->
   electricity, m3 -> water, L -> fuel). If the unit doesn't resolve,
   resource_type stays None and the record correctly falls through to the
   LLM fallback in app.py.

2. Normalizes billing_date -> billing_period. Person 2's regex correctly
   pulls out full dates in whatever format the bill uses (ISO, dd/mm/yyyy,
   "28 Jul 2026", etc.) — this collapses any of those down to "YYYY-MM".

3. Resolves site via account number lookup, not text-scraping. Real bills
   print an account holder's name/address, not an internal site label —
   see SITE_LOOKUP below. This is intentionally a dict for now; in
   production it should be a database table Person 1/4 maintain.
"""
from dateutil import parser as dateutil_parser

from .text_extraction import extract_text
from .rule_parser import parse_bill_text, parse_csv_rows, RuleParseResult
from .unit_lookup import lookup_unit
from .fuel_csv_parser import parse_fuel_transaction_csv, FuelTransaction
from Security_Layer.file_intake import get_connection

# Canonical unit (from Person 3's lookup_unit) -> resource_type.
# Extend as Person 3 adds more units (e.g. a "diesel"/"petrol" canonical
# unit should also map here once fuel bills are handled).
UNIT_TO_RESOURCE_TYPE = {
    "kWh": "electricity",
    "m3": "water",
    "L": "fuel",
}

# Account number -> internal site name. In production this belongs in a
# database table (Person 1's raw_files / a dedicated sites table), not a
# hardcoded dict — real bills never print your internal site label, only
# the account holder's name/address, so this mapping has to live somewhere
# your org controls.
SITE_LOOKUP = {
    "4471829": "Colombo Office",       # electricity account
    "9012734": "Colombo Office",       # water account
    # TODO: add real account numbers as they're confirmed, e.g. the water
    # board's slash format: "08/42/105/928/14": "Colombo Office",
}


def normalize_billing_period(raw_date: str | None) -> str | None:
    """Turns whatever date format rule_parser.py found into 'YYYY-MM'.
    Returns None (rather than raising) if the string can't be parsed —
    callers are expected to add a warning when that happens."""
    if not raw_date:
        return None
    try:
        # dayfirst=True matches Sri Lankan dd/mm/yyyy convention. ISO
        # dates (yyyy-mm-dd) parse the same regardless of this flag.
        dt = dateutil_parser.parse(raw_date, dayfirst=True)
        return dt.strftime("%Y-%m")
    except (ValueError, OverflowError, TypeError):
        return None


def resolve_site(account_no: str | None, company_id: int, warnings: list[str]) -> str | None:
    if not account_no:
        warnings.append("account number not found")
        return None

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT sites.site_name
               FROM accounts
               JOIN sites ON accounts.site_id = sites.site_id
               WHERE accounts.account_number = %s
                 AND accounts.company_id = %s;""",
            (account_no, company_id)
        )
        row = cur.fetchone()
        if row:
            return row[0]
        warnings.append(f"no site mapping for account '{account_no}'")
        return None
    finally:
        cur.close()
        conn.close()


def rule_result_to_partial_data(result: RuleParseResult, company_id: int) -> dict:
    """Converts Person 2's RuleParseResult + Person 3's unit lookup into
    the partial_data dict shape app.py's ExtractionRecord expects."""
    warnings = [f"{f} not found by rule-based parser" for f in result.missing_fields]

    # --- consumption ---
    consumption = None
    if result.consumption.value:
        try:
            consumption = float(result.consumption.value)
        except ValueError:
            warnings.append(f"could not parse consumption value '{result.consumption.value}'")

    # --- unit + resource_type (via Person 3's lookup_unit) ---
    unit = None
    resource_type = None
    if result.unit_raw.value:
        unit_result = lookup_unit(result.unit_raw.value)
        if unit_result["resolved"]:
            unit = unit_result["canonical_unit"]
            resource_type = UNIT_TO_RESOURCE_TYPE.get(unit)
            # IMPORTANT: lookup_unit() returns a multiplier (e.g. gallons ->
            # litres is 3.78541, not 1.0) — the raw consumption value must
            # be scaled by it, or a bill reported in gallons would silently
            # understate consumption by ~3.8x once mislabeled as litres.
            if consumption is not None and unit_result.get("multiplier") is not None:
                consumption = consumption * unit_result["multiplier"]
            if unit_result["match_type"] != "exact":
                warnings.append(f"unit resolved via {unit_result['match_type']}")
        else:
            warnings.append(f"unit '{result.unit_raw.value}' not recognized by lookup_unit")

    # --- billing period ---
    billing_period = normalize_billing_period(result.billing_date.value)
    if result.billing_date.value and not billing_period:
        warnings.append(f"could not normalize billing date '{result.billing_date.value}'")

    # --- site (via account number lookup) ---
    site = resolve_site(result.account_number.value, company_id, warnings)

    if not resource_type:
        warnings.append("resource_type could not be determined from unit")

    # Average confidence across whichever fields the rule parser actually
    # found — gives a rough signal without pretending precision we don't have.
    found_confidences = [
        f.confidence for f in
        [result.consumption, result.unit_raw, result.billing_date, result.account_number]
        if f.value
    ]
    confidence = round(sum(found_confidences) / len(found_confidences), 2) if found_confidences else 0.0

    return {
        "resource_type": resource_type,
        "consumption": consumption,
        "unit": unit,
        "billing_period": billing_period,
        "site": site,
        "account_number": result.account_number.value,
        "confidence": confidence,
        "extraction_method": "rule_based",
        "warnings": warnings,
    }


def is_fuel_transaction_log(rows: list[dict]) -> bool:
    """
    Distinguishes a fuel transaction log (many rows, one per refuel event —
    Person 2's fuel_csv_parser.py) from a single-bill CSV (one row per
    billing period — rule_parser.parse_csv_rows()). Detected by column
    signature rather than row count, since a log could in principle have
    just one row.

    IMPORTANT CAVEAT: fuel_csv_parser.py reads columns via exact,
    case-sensitive keys (row.get("TransactionDate"), row.get("FuelType"),
    etc. — PascalCase). This check normalizes header casing to detect a
    fuel log reliably, but parse_fuel_transaction_csv() itself does NOT —
    if your real generated fuel CSV uses different header casing (e.g.
    "transaction_date" instead of "TransactionDate"), routing will
    correctly identify it as a fuel log, but every field will still come
    back None because the exact-case lookups inside fuel_csv_parser.py
    will miss. Worth confirming the real file's header casing matches
    before trusting a clean-looking result.
    """
    if not rows:
        return False
    headers = {h.strip().lower().replace("_", "").replace(" ", "") for h in rows[0].keys()}
    fuel_log_signature = {"transactionid", "transactiondate", "fueltype", "quantity"}
    return len(fuel_log_signature & headers) >= 3


def fuel_transaction_to_partial_data(txn: FuelTransaction) -> dict:
    """Converts one Person 2 FuelTransaction into the partial_data shape
    app.py's ExtractionRecord expects. Unlike bill parsing, unit and site
    here come directly from Person 2's own normalization (fuel_csv_parser.py
    already handles unit spelling and site-name casing) — no need to route
    through Person 3's lookup_unit(), which is tuned for utility bill unit
    strings (kWh/m3), not fuel log unit strings (litres/gallons)."""
    warnings = list(txn.warnings)

    if not txn.fuel_type:
        warnings.append("fuel_type not recognized")
    if txn.unit is None and not txn.unit_ambiguous:
        warnings.append(f"unit '{txn.unit_raw}' not recognized")

    resource_type = "fuel" if (txn.quantity is not None and txn.unit) else None
    if resource_type is None:
        warnings.append("resource_type could not be confirmed (missing quantity or unit)")

    return {
        "resource_type": resource_type,
        "fuel_type": txn.fuel_type,
        "consumption": txn.quantity,
        "unit": txn.unit,
        "billing_period": txn.transaction_date.strftime("%Y-%m") if txn.transaction_date else None,
        "transaction_date": txn.transaction_date.isoformat() if txn.transaction_date else None,
        "site": txn.site or None,
        "account_number": None,
        "confidence": 0.9 if not warnings else 0.6,
        "extraction_method": "rule_based",
        "warnings": warnings,
    }


def run_extraction_pipeline(file_path: str, file_type: str, company_id: int) -> tuple[str, list[dict]]:
    """
    Full Person 2 + Person 3 pipeline: a file already on disk -> a list of
    partial_data dicts ready for app.py's required-fields check + LLM
    fallback + Pydantic validation, one dict per record.

    Returns (raw_text, [partial_data, ...]). For a single bill (PDF or
    single-row CSV) this list has exactly one entry. For a fuel
    transaction log it has one entry per transaction row — app.py's
    /extract endpoint must loop over this list rather than assume a
    single record.

    raw_text is passed through for llm_fallback()'s prompt; for a fuel
    log it's a short preview, not the whole file, to avoid blowing up
    the prompt on a 1500+ row log (and once a real LLM is wired in,
    calling it per-row for a file that size would also be slow and
    costly — worth batching or capping fallback calls for fuel logs
    specifically once that's a real concern, not a placeholder one).
    """
    extracted = extract_text(file_path, file_type)

    if isinstance(extracted, str):
        raw_text = extracted
        result = parse_bill_text(extracted)
        return raw_text, [rule_result_to_partial_data(result, company_id)]

    if is_fuel_transaction_log(extracted):
        transactions = parse_fuel_transaction_csv(extracted)
        raw_text = f"Fuel transaction log, {len(transactions)} rows. First rows: {extracted[:2]}"
        return raw_text, [fuel_transaction_to_partial_data(t) for t in transactions]

    raw_text = str(extracted[:3])
    result = parse_csv_rows(extracted)
    return raw_text, [rule_result_to_partial_data(result, company_id)]