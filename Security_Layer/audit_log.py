"""
Security_Layer / audit_log.py
================================
Calculation logging + suspicious-value flagging for Agent 2 (and reusable
by any other agent's endpoints later).

Writes structured JSON lines (one per event) to a local log file by
default. Swap `_write_log_line` for a real logging backend (a `logs` DB
table, a hosted log sink, etc.) without touching call sites — every
caller only ever calls log_calculation_run() / flag_suspicious_values().
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "agent2_calculations.log"

# Values above these aren't necessarily wrong, but are unusual enough for
# a single site/period at a mid-sized company (the project's target
# market) to be worth a human glance before the report goes out. Adjust
# if legitimate test/client data exceeds these.
SUSPICIOUS_THRESHOLDS = {
    "electricity_kwh_per_period": 5_000_000,   # ~5 GWh/month would be a large industrial site
    "fuel_litres_per_period": 500_000,
    "cost_lkr_per_period": 500_000_000,
}


def _write_log_line(record: dict) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _hash_payload(payload) -> str:
    """Short fingerprint of an input, for correlating log lines without storing raw data twice."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def log_calculation_run(endpoint: str, company_id: int, input_ref, output_summary: dict,
                         warnings: list = None, errors: list = None) -> str:
    """
    Logs one Agent 2 calculation run. `input_ref` is whatever identifies
    the request (e.g. {"file_id": 42}) — kept small since the real data
    already lives in Postgres; this log is for traceability, not a data
    copy. Returns a fingerprint the caller can echo back in the API
    response so a person can quote it if they report an issue.
    """
    fingerprint = _hash_payload(input_ref)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "company_id": company_id,
        "input_ref": input_ref,
        "input_fingerprint": fingerprint,
        "output_summary": output_summary,
        "warnings_count": len(warnings or []),
        "errors_count": len(errors or []),
    }
    _write_log_line(record)
    return fingerprint


def flag_suspicious_values(records: list) -> list:
    """
    Scans a batch of extraction-record-shaped dicts for values that are
    numerically VALID but unusually large for a mid-sized company, and
    returns human-readable flags. This does NOT reject the data (that's
    validation's job) — it's a secondary "worth a human look" signal
    logged alongside the calculation run.
    """
    flags = []
    for r in records:
        consumption = r.get("consumption")
        resource_type = r.get("resource_type")
        if consumption is None:
            continue
        if resource_type == "electricity" and consumption > SUSPICIOUS_THRESHOLDS["electricity_kwh_per_period"]:
            flags.append(
                f"Unusually high electricity consumption ({consumption} kWh) for "
                f"site={r.get('site')}, period={r.get('billing_period')}"
            )
        if resource_type == "fuel" and consumption > SUSPICIOUS_THRESHOLDS["fuel_litres_per_period"]:
            flags.append(
                f"Unusually high fuel consumption ({consumption}) for "
                f"site={r.get('site')}, period={r.get('billing_period')}"
            )
        amount = r.get("amount_lkr")
        if amount is not None and amount > SUSPICIOUS_THRESHOLDS["cost_lkr_per_period"]:
            flags.append(
                f"Unusually high cost (LKR {amount}) for "
                f"site={r.get('site')}, period={r.get('billing_period')}"
            )
    return flags
