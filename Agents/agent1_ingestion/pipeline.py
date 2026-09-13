"""
Person 4 — integration layer.

Wires Person 2's output (RuleParseResult: consumption, unit_raw, billing_date,
account_number, each with confidence) and Person 3's lookup_unit() together
into the partial_data dict shape app.py's ExtractionRecord expects
(resource_type, consumption, unit, billing_period, site).

Site resolution is now company-scoped: resolve_site() queries the
accounts/sites tables filtered by company_id, since the same account
number could legitimately belong to different companies (see team
discussion on multi-tenancy).
"""
from dateutil import parser as dateutil_parser

from .text_extraction import extract_text
from .rule_parser import parse_bill_text, parse_csv_rows, RuleParseResult
from .unit_lookup import lookup_unit
from .fuel_csv_parser import parse_fuel_transaction_csv, FuelTransaction
from Security_Layer.file_intake import get_connection

# Canonical unit (from Person 3's lookup_unit) -> resource_type.
UNIT_TO_RESOURCE_TYPE = {
    "kWh": "electricity",
    "m3": "water",
    "L": "fuel",
}


def normalize_billing_period(raw_date: str | None) -> str | None:
    """Turns whatever date format rule_parser.py found into 'YYYY-MM'."""
    if not raw_date:
        return None
    try:
        dt = dateutil_parser.parse(raw_date, dayfirst=True)
        return dt.strftime("%Y-%m")
    except (ValueError, OverflowError, TypeError):
        return None


def resolve_site(account_no: str | None, company_id: int, warnings: list[str]) -> str | None:
    """
    Looks up which site an account number belongs to, scoped to the
    uploading company — replaces the old hardcoded SITE_LOOKUP dict.
    """
    if not account_no:
        warnings.append("account number not found")
        return None

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.site_name FROM accounts a
            JOIN sites s ON a.site_id = s.site_id
            WHERE a.company_id = %s AND a.account_number = %s;
            """,
            (company_id, account_no)
        )
        row = cur.fetchone()
        if row:
            return row[0]
        warnings.append(
            f"no site mapping for account '{account_no}' — add it via POST /accounts"
        )
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

    # --- site (via account number lookup, scoped to company) ---
    site = resolve_site(result.account_number.value, company_id, warnings)

    # --- previous/current meter readings, amount due ---
    previous_reading = None
    if result.previous_reading.value:
        try:
            previous_reading = float(result.previous_reading.value)
        except ValueError:
            warnings.append(f"could not parse previous_reading value '{result.previous_reading.value}'")

    current_reading = None
    if result.current_reading.value:
        try:
            current_reading = float(result.current_reading.value)
        except ValueError:
            warnings.append(f"could not parse current_reading value '{result.current_reading.value}'")

    amount_lkr = None
    if result.amount_lkr.value:
        try:
            amount_lkr = float(result.amount_lkr.value)
        except ValueError:
            warnings.append(f"could not parse amount_lkr value '{result.amount_lkr.value}'")

    if not resource_type:
        warnings.append("resource_type could not be determined from unit")

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
        "previous_reading": previous_reading,
        "current_reading": current_reading,
        "amount_lkr": amount_lkr,
        "confidence": confidence,
        "extraction_method": "rule_based",
        "warnings": warnings,
    }


def is_fuel_transaction_log(rows: list[dict]) -> bool:
    """Distinguishes a fuel transaction log from a single-bill CSV."""
    if not rows:
        return False
    headers = {h.strip().lower().replace("_", "").replace(" ", "") for h in rows[0].keys()}
    fuel_log_signature = {"transactionid", "transactiondate", "fueltype", "quantity"}
    return len(fuel_log_signature & headers) >= 3


def fuel_transaction_to_partial_data(txn: FuelTransaction) -> dict:
    """Converts one Person 2 FuelTransaction into the partial_data shape.
    Site here comes from site_lookup.py's normalize_site_name() inside
    fuel_csv_parser.py already — no DB lookup needed for fuel logs, since
    the site name is written directly in the CSV, not just an account
    number."""
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

    company_id scopes site resolution for bills (electricity/water) —
    fuel logs resolve site independently via site_lookup.py, so it isn't
    needed in that branch.
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